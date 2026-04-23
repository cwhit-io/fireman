"""
Service for pulling the Fiery job log via its REST API and importing
entries into PrintLog.

The Fiery XF/IS REST API is available at:
  https://<fiery_ip>/live/api/v5/

Authentication: POST /login  → returns a session cookie.
Job log:        GET  /jobs   → paginated list of completed jobs.

Relevant fields returned per job:
  id, title, userName, jobStatus, colorMode,
  colorPages, bwPages, copies, mediaSize, mediaType,
  isDuplex, jobSubmitTime, jobCompleteTime

Reference: Fiery API Programmer Guide v5 (EFI).
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal

import requests
from django.conf import settings

from .models import CostRate, PrintLog

logger = logging.getLogger(__name__)


def _fiery_settings() -> dict:
    """Read Fiery connection settings at call time so .env changes take effect without restart."""
    ip = getattr(settings, "FIERY_IP", "10.10.96.103")
    return {
        "ip": ip,
        # IC-419 is Fiery FS400 platform → API v4
        # v5 is FS500+/FS600+. Try v4 first; fall back to v5 if needed.
        "base": f"https://{ip}/live/api/v4",
        "user": getattr(settings, "FIERY_API_USER", "admin"),
        "password": getattr(settings, "FIERY_API_PASS", ""),
        # accessrights must be a key registered in Fiery Configure → Security → APIs
        "accessrights": getattr(settings, "FIERY_API_KEY", ""),
        "verify": getattr(settings, "FIERY_VERIFY_SSL", False),
    }


def _login(session: requests.Session, cfg: dict) -> str | None:
    """
    Authenticate against the Fiery REST API.
    Returns None on success, or an error string on failure.
    """
    # Try HTTPS v4, then HTTPS v5, then HTTP v4 in sequence.
    candidates = [
        cfg["base"],
        cfg["base"].replace("/v4", "/v5"),
        cfg["base"].replace("https://", "http://"),
    ]
    for base in candidates:
        try:
            resp = session.post(
                f"{base}/login",
                json={"username": cfg["user"], "password": cfg["password"], "accessrights": cfg["accessrights"]},
                verify=cfg["verify"],
                timeout=10,
            )
            resp.raise_for_status()
            # Store the working base on the session for later calls
            session._fiery_base = base
            logger.info("Fiery login succeeded at %s", base)
            return None
        except requests.RequestException as exc:
            logger.warning("Fiery login attempt failed at %s: %s", base, exc)
            last_exc = exc
    return str(last_exc)


def _logout(session: requests.Session, cfg: dict) -> None:
    base = getattr(session, "_fiery_base", cfg["base"])
    try:
        session.delete(f"{base}/login", verify=cfg["verify"], timeout=5)
    except requests.RequestException:
        pass


def _parse_fiery_dt(value: str | None) -> datetime | None:
    """Parse ISO-8601 datetime string from Fiery, return UTC-aware datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None


def _color_mode(raw: str) -> str:
    raw = (raw or "").lower()
    if raw in ("color", "colour"):
        return PrintLog.ColorMode.COLOR
    if raw in ("grayscale", "bw", "black and white", "black&white", "monochrome"):
        return PrintLog.ColorMode.BW
    return PrintLog.ColorMode.MIXED


def _import_job(entry: dict, rate: CostRate | None) -> tuple[str, str]:
    """
    Create or skip a PrintLog record from a raw Fiery job dict.
    Returns ("created"|"skipped"|"error", reason).
    """
    fiery_id = str(entry.get("id") or "")
    printed_at = _parse_fiery_dt(entry.get("jobCompleteTime") or entry.get("jobSubmitTime"))
    if printed_at is None:
        return ("error", f"No timestamp for job {fiery_id!r}")

    username = (entry.get("userName") or "unknown").strip() or "unknown"
    color_pages = int(entry.get("colorPages") or 0)
    bw_pages = int(entry.get("bwPages") or 0)
    copies = max(int(entry.get("copies") or 1), 1)

    # Skip if already imported
    if fiery_id and PrintLog.objects.filter(fiery_job_id=fiery_id).exists():
        return ("skipped", "already imported")

    color_mode = _color_mode(entry.get("colorMode") or "")

    log = PrintLog(
        fiery_job_id=fiery_id,
        username=username,
        job_name=(entry.get("title") or "")[:500],
        printed_at=printed_at,
        color_pages=color_pages,
        bw_pages=bw_pages,
        copies=copies,
        color_mode=color_mode,
        media_size=(entry.get("mediaSize") or "")[:100],
        media_type=(entry.get("mediaType") or "")[:100],
        duplex=bool(entry.get("isDuplex") or False),
        raw_data=entry,
    )

    if rate:
        cost = (
            Decimal(color_pages) * copies * rate.color_per_page
            + Decimal(bw_pages) * copies * rate.bw_per_page
        )
        log.cost_rate = rate
        log.calculated_cost = cost

    log.save()
    return ("created", "")


def sync_fiery_logs(limit: int = 500) -> dict:
    """
    Pull the latest *limit* completed jobs from the Fiery and import new ones.
    Returns a summary dict: {"created": N, "skipped": N, "errors": N}.
    """
    cfg = _fiery_settings()
    rate = CostRate.objects.filter(active=True).order_by("-updated_at").first()
    summary = {"created": 0, "skipped": 0, "errors": 0}

    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})

    login_error = _login(session, cfg)
    if login_error:
        return {"error": f"Could not authenticate with Fiery — {login_error}"}

    base = session._fiery_base
    try:
        resp = session.get(
            f"{base}/jobs",
            params={"jobstatus": "printed", "limit": limit},
            verify=cfg["verify"],
            timeout=30,
        )
        resp.raise_for_status()
        jobs = resp.json()
        if isinstance(jobs, dict):
            jobs = jobs.get("jobs") or jobs.get("data") or []
    except requests.RequestException as exc:
        logger.error("Failed to fetch Fiery job log: %s", exc)
        _logout(session, cfg)
        return {"error": str(exc)}
    finally:
        _logout(session, cfg)

    for entry in jobs:
        status, _ = _import_job(entry, rate)
        summary[status] = summary.get(status, 0) + 1

    logger.info("Fiery log sync: %s", summary)
    return summary
