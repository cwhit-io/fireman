'''
FTP Media Cleaner
=================
Connects to an FTP server and deletes files older than a configurable
threshold. Designed for API/CI contexts with structured JSON output.

Environment variables
---------------------
FTP connection:
  FTP_HOST            (default: 10.10.96.127)
  FTP_PORT            (default: 21)
  FTP_USERNAME        (optional)
  FTP_PASSWORD        (optional)
  FTP_TIMEOUT_SECONDS (default: 30)

Cleanup config:
  TARGET_DIRECTORY    (default: /usb/Media)
  KEEP_WEEKS          (default: WEEKS_THRESHOLD fallback, then 2)
  WEEKS_THRESHOLD     (legacy fallback; default: 2)
  DRY_RUN             (default: true)

Output/logging:
  JSON_OUTPUT         (default: true)
  INCLUDE_LISTING     (default: true)
  LOG_LEVEL           (default: INFO)

Boolean env vars treat these values as true:
  1, true, t, yes, y, on  (case-insensitive)

Timestamp resolution order (per file)
--------------------------------------
1. Filename date  -- YYYYMMDD_HHMM parsed from the filename itself.
                     Strips leading ._ (macOS sidecar prefix) before matching.
2. MLSD           -- RFC 3659 machine-readable facts (full UTC).
3. MDTM           -- per-file exact timestamp command.
4. LIST estimate  -- Unix LIST mtime, year inferred (least reliable).

macOS sidecar files (._*) are skipped entirely -- the HyperDeck firmware
exposes them in LIST output but blocks FTP deletion with 550. They are
4 KB stubs with no meaningful storage impact.
'''

import ftplib
import datetime as dt
import os
import re
import json
import logging
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Tuple


# ---------------------------------------------------------------------------
# Env helpers
# ---------------------------------------------------------------------------

def _bool_env(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _int_env(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or not val.strip():
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _to_iso(ts: Optional[dt.datetime]) -> Optional[str]:
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    return ts.isoformat()


# ---------------------------------------------------------------------------
# Filename date parser
# ---------------------------------------------------------------------------

# Matches: 20251123_0845  (YYYYMMDD_HHMM)
# Anchored to start so it works on both:
#   20251123_0845-.mp4
#   ._20251123_0845-.mp4  (macOS sidecar -- ._ stripped before match)
_FILENAME_DATE_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})")


def _parse_date_from_filename(name: str) -> Optional[dt.datetime]:
    """
    Extract a UTC datetime from a recorder-style filename.

    Strips a leading "._" prefix (macOS AppleDouble sidecar) before
    attempting the match, so sidecar files age out in sync with their
    parent recording.

    Returns a timezone-aware UTC datetime at the recorded time, or
    None if the filename does not match the expected pattern.

    Examples
    --------
    "20251123_0845-.mp4"    -> 2025-11-23 08:45:00+00:00
    "._20251123_0845-.mp4"  -> 2025-11-23 08:45:00+00:00
    "HyperDeck_0001.mp4"    -> None  (falls through to mtime)
    "._."                   -> None
    """
    stem = name[2:] if name.startswith("._") else name
    m = _FILENAME_DATE_RE.match(stem)
    if not m:
        return None
    year, month, day, hour, minute = (int(x) for x in m.groups())
    try:
        return dt.datetime(year, month, day, hour, minute, tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def _is_sidecar(name: str) -> bool:
    """
    Returns True for macOS AppleDouble sidecar files (._*).

    These appear in FTP LIST output on HyperDeck/NAS firmware but cannot
    be deleted via FTP (server returns 550). They are 4 KB metadata stubs
    with no meaningful storage impact -- skip them entirely rather than
    generating spurious errors.
    """
    return name.startswith("._")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class FileRecord:
    name: str
    modified_at: Optional[str]
    size_bytes: Optional[int]
    action: str
    reason: Optional[str] = None
    # filename | mlsd | mdtm | list_exact | list_estimated | n/a
    timestamp_source: Optional[str] = None


@dataclass
class RunResult:
    ok: bool
    host: str
    port: int
    directory: str
    dry_run: bool
    weeks_threshold: int
    cutoff_utc: str
    started_utc: str
    finished_utc: Optional[str] = None
    totals: Dict[str, int] = None
    files: List[Dict[str, Any]] = None
    errors: List[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["totals"] = d["totals"] or {
            "scanned": 0, "kept": 0, "deleted": 0,
            "skipped": 0, "errors": 0,
            "ts_filename": 0, "ts_mlsd": 0, "ts_mdtm": 0,
            "ts_list_exact": 0, "ts_list_estimated": 0,
        }
        d["files"] = d["files"] or []
        d["errors"] = d["errors"] or []
        return d


# ---------------------------------------------------------------------------
# Structured logger
# ---------------------------------------------------------------------------

class JsonLineLogger:
    """
    Minimal structured logger for API contexts.
    JSON_OUTPUT=true  -> JSON lines to stdout.
    JSON_OUTPUT=false -> standard logging format.
    """

    def __init__(self, json_output: bool = True, level: str = "INFO"):
        self.json_output = json_output
        self.level = level.upper()
        logging.basicConfig(
            level=getattr(logging, self.level, logging.INFO),
            format="%(asctime)s %(levelname)s %(message)s",
        )
        self._logger = logging.getLogger("ftp-cleaner")

    def _emit(self, level: str, message: str, **fields: Any):
        if self.json_output:
            payload = {
                "ts_utc": _to_iso(_utc_now()),
                "level": level,
                "message": message,
                **fields,
            }
            print(json.dumps(payload, default=str), flush=True)
        else:
            getattr(self._logger, level.lower(), self._logger.info)(
                f"{message} | {fields}"
            )

    def info(self, message: str, **fields: Any):
        self._emit("INFO", message, **fields)

    def warning(self, message: str, **fields: Any):
        self._emit("WARNING", message, **fields)

    def error(self, message: str, **fields: Any):
        self._emit("ERROR", message, **fields)

    def debug(self, message: str, **fields: Any):
        if self.level == "DEBUG":
            self._emit("DEBUG", message, **fields)


# ---------------------------------------------------------------------------
# FTP Cleaner
# ---------------------------------------------------------------------------

class FTPCleaner:

    def __init__(
        self,
        host: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        port: int = 21,
        timeout_seconds: int = 30,
        logger: Optional[JsonLineLogger] = None,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.timeout_seconds = timeout_seconds
        self.ftp: Optional[ftplib.FTP] = None
        self.log = logger or JsonLineLogger(json_output=True)
        self._ts_counters: Dict[str, int] = {
            "ts_filename": 0,
            "ts_mlsd": 0,
            "ts_mdtm": 0,
            "ts_list_exact": 0,
            "ts_list_estimated": 0,
        }

    # -- Connection ----------------------------------------------------------

    def connect(self) -> None:
        try:
            self.ftp = ftplib.FTP(timeout=self.timeout_seconds)
            self.ftp.connect(self.host, self.port)
            if self.username is None and self.password is None:
                self.ftp.login()
                auth_mode = "anonymous"
            elif self.username and self.password is None:
                self.ftp.login(user=self.username)
                auth_mode = "user-only"
            else:
                self.ftp.login(self.username, self.password)
                auth_mode = "user-pass"
            self.log.info(
                "ftp_connected",
                host=self.host,
                port=self.port,
                auth_mode=auth_mode,
            )
        except Exception as e:
            self.log.error(
                "ftp_connect_failed",
                host=self.host,
                port=self.port,
                error=str(e),
            )
            raise

    def disconnect(self) -> None:
        if not self.ftp:
            return
        try:
            self.ftp.quit()
            self.log.info("ftp_disconnected", host=self.host, port=self.port)
        except Exception:
            try:
                self.ftp.close()
            except Exception:
                pass

    # -- Directory helpers ---------------------------------------------------

    def _cwd(self, directory: str) -> str:
        assert self.ftp is not None
        original = self.ftp.pwd()
        if directory and directory != ".":
            self.ftp.cwd(directory)
        return original

    # -- Timestamp resolution ------------------------------------------------

    def _try_mlsd(self) -> Optional[List[Tuple[str, Dict[str, str]]]]:
        """
        Prefer MLSD (RFC 3659) -- machine-readable facts with full UTC timestamps.
        Returns list of (name, facts) or None if server does not support MLSD.
        Logs a WARNING on fallback so operators know which path is active.
        """
        assert self.ftp is not None
        try:
            rows = list(self.ftp.mlsd())
            self.log.debug("mlsd_supported", host=self.host)
            return rows
        except Exception as e:
            self.log.warning(
                "mlsd_not_supported_falling_back_to_list",
                host=self.host,
                reason=str(e),
            )
            return None

    def _try_mdtm(self, filename: str) -> Optional[dt.datetime]:
        """
        MDTM fallback -- fetches exact modification time per file.
        Used when LIST gives an uncertain year (HH:MM format, no year).
        Returns UTC datetime or None if MDTM unsupported or fails.
        MDTM response format: 213 YYYYMMDDHHMMSS
        """
        assert self.ftp is not None
        try:
            resp = self.ftp.sendcmd(f"MDTM {filename}")
            ts_str = resp.split()[-1]
            if len(ts_str) >= 14:
                return dt.datetime.strptime(ts_str[:14], "%Y%m%d%H%M%S").replace(
                    tzinfo=dt.timezone.utc
                )
        except Exception as e:
            self.log.debug("mdtm_failed", filename=filename, reason=str(e))
        return None

    def _parse_list_line_unix(self, line: str) -> Optional[Dict[str, Any]]:
        """
        Best-effort parser for Unix LIST format.

        Year correction: if the inferred date is more than 1 day in the
        future, subtract one year. Prevents Nov/Dec files from being
        stamped with next year when listed in Jan/Feb.
        """
        parts = line.split()
        if len(parts) < 9:
            return None
        kind = parts[0][0]
        size_str = parts[4]
        month_str = parts[5]
        day_str = parts[6]
        year_or_time = parts[7]
        name = " ".join(parts[8:])
        size_bytes = None
        try:
            size_bytes = int(size_str)
        except Exception:
            pass
        MONTHS = {
            "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
            "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
            "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
        }
        month_num = MONTHS.get(month_str, 1)
        day_num = int(day_str)
        now = _utc_now()
        year_uncertain = False
        if ":" in year_or_time:
            year_uncertain = True
            year = now.year
            modified = dt.datetime(year, month_num, day_num, tzinfo=dt.timezone.utc)
            if modified > now + dt.timedelta(days=1):
                modified = modified.replace(year=year - 1)
        else:
            year = int(year_or_time)
            modified = dt.datetime(year, month_num, day_num, tzinfo=dt.timezone.utc)
        return {
            "name": name,
            "is_dir": (kind == "d"),
            "size_bytes": size_bytes,
            "modified": modified,
            "year_uncertain": year_uncertain,
        }

    # -- File listing --------------------------------------------------------

    def _list_files(self, directory: str) -> List[Dict[str, Any]]:
        """
        Returns a list of file dicts with resolved timestamps.

        Timestamp resolution order per file:
          1. Filename date  (YYYYMMDD_HHMM pattern -- most reliable)
          2. MLSD           (RFC 3659 full UTC -- best for non-standard names)
          3. MDTM           (per-file exact time -- LIST year uncertain)
          4. LIST estimate  (year inferred -- last resort)

        macOS sidecar files (._*) are included in the raw listing but
        filtered out by delete_old_files() before any action is taken.
        """
        assert self.ftp is not None
        original = self._cwd(directory)
        try:
            mlsd_rows = self._try_mlsd()
            if mlsd_rows is not None:
                entries: List[Dict[str, Any]] = []
                for name, facts in mlsd_rows:
                    ftype = (facts.get("type") or "").lower()
                    is_dir = ftype in {"dir", "cdir", "pdir"}
                    size_bytes = None
                    if "size" in facts:
                        try:
                            size_bytes = int(facts["size"])
                        except Exception:
                            pass
                    modified = None
                    mod = facts.get("modify")
                    if mod and len(mod) >= 14:
                        try:
                            modified = dt.datetime.strptime(
                                mod[:14], "%Y%m%d%H%M%S"
                            ).replace(tzinfo=dt.timezone.utc)
                        except Exception:
                            pass
                    fn_date = _parse_date_from_filename(name)
                    if fn_date is not None:
                        modified = fn_date
                        ts_source = "filename"
                    else:
                        ts_source = "mlsd"
                    entries.append({
                        "name": name,
                        "is_dir": is_dir,
                        "size_bytes": size_bytes,
                        "modified": modified,
                        "timestamp_source": ts_source,
                    })
                return entries

            # Fallback: LIST + optional MDTM
            lines: List[str] = []
            self.ftp.retrlines("LIST", lines.append)
            entries2: List[Dict[str, Any]] = []
            for line in lines:
                parsed = self._parse_list_line_unix(line)
                if not parsed:
                    continue
                name = parsed["name"]
                fn_date = _parse_date_from_filename(name)
                if fn_date is not None:
                    parsed["modified"] = fn_date
                    ts_source = "filename"
                elif parsed.get("year_uncertain") and not parsed["is_dir"]:
                    mdtm_ts = self._try_mdtm(name)
                    if mdtm_ts is not None:
                        parsed["modified"] = mdtm_ts
                        ts_source = "mdtm"
                    else:
                        ts_source = "list_estimated"
                else:
                    ts_source = "list_exact"
                parsed["timestamp_source"] = ts_source
                entries2.append(parsed)
            return entries2
        finally:
            try:
                self.ftp.cwd(original)
            except Exception:
                pass

    # -- Main cleanup --------------------------------------------------------

    def delete_old_files(
        self,
        directory: str = ".",
        weeks: int = 3,
        dry_run: bool = True,
        include_listing: bool = True,
    ) -> RunResult:
        started = _utc_now()
        cutoff = started - dt.timedelta(weeks=weeks)
        self._ts_counters = {k: 0 for k in self._ts_counters}
        result = RunResult(
            ok=False,
            host=self.host,
            port=self.port,
            directory=directory,
            dry_run=dry_run,
            weeks_threshold=weeks,
            cutoff_utc=_to_iso(cutoff),
            started_utc=_to_iso(started),
            totals={
                "scanned": 0, "kept": 0, "deleted": 0,
                "skipped": 0, "errors": 0,
                "ts_filename": 0, "ts_mlsd": 0, "ts_mdtm": 0,
                "ts_list_exact": 0, "ts_list_estimated": 0,
            },
            files=[],
            errors=[],
        )
        assert self.ftp is not None
        self.log.info(
            "cleanup_start",
            directory=directory,
            weeks_threshold=weeks,
            dry_run=dry_run,
            cutoff_utc=result.cutoff_utc,
        )
        try:
            entries = self._list_files(directory)
            files = [e for e in entries if not e.get("is_dir")]
            result.totals["scanned"] = len(files)
            original = self._cwd(directory)
            try:
                for e in files:
                    name: str = e["name"]
                    modified: Optional[dt.datetime] = e.get("modified")
                    size_bytes: Optional[int] = e.get("size_bytes")
                    ts_source: str = e.get("timestamp_source", "unknown")

                    # -- Skip macOS AppleDouble sidecar stubs ----------------
                    # The HyperDeck firmware lists these but returns 550 on
                    # delete. They are 4 KB metadata stubs -- not managed files.
                    if _is_sidecar(name):
                        rec = FileRecord(
                            name=name,
                            modified_at=_to_iso(modified),
                            size_bytes=size_bytes,
                            action="skip",
                            reason="macos_sidecar",
                            timestamp_source="n/a",
                        )
                        result.totals["skipped"] += 1
                        if include_listing:
                            result.files.append(asdict(rec))
                        continue

                    # -- Count timestamp source ------------------------------
                    ts_key = f"ts_{ts_source}"
                    if ts_key in result.totals:
                        result.totals[ts_key] += 1

                    # -- No timestamp -> flag as error -----------------------
                    if modified is None:
                        rec = FileRecord(
                            name=name,
                            modified_at=None,
                            size_bytes=size_bytes,
                            action="error",
                            reason="missing_modified_time",
                            timestamp_source=ts_source,
                        )
                        result.totals["errors"] += 1
                        if include_listing:
                            result.files.append(asdict(rec))
                        continue

                    # -- Older than cutoff -> delete -------------------------
                    if modified < cutoff:
                        if dry_run:
                            rec = FileRecord(
                                name=name,
                                modified_at=_to_iso(modified),
                                size_bytes=size_bytes,
                                action="delete",
                                reason="older_than_cutoff_dry_run",
                                timestamp_source=ts_source,
                            )
                            result.totals["deleted"] += 1
                            if include_listing:
                                result.files.append(asdict(rec))
                        else:
                            try:
                                self.ftp.delete(name)
                                rec = FileRecord(
                                    name=name,
                                    modified_at=_to_iso(modified),
                                    size_bytes=size_bytes,
                                    action="delete",
                                    reason="deleted",
                                    timestamp_source=ts_source,
                                )
                                result.totals["deleted"] += 1
                                self.log.info(
                                    "file_deleted",
                                    name=name,
                                    modified_at=_to_iso(modified),
                                    size_bytes=size_bytes,
                                    timestamp_source=ts_source,
                                )
                                if include_listing:
                                    result.files.append(asdict(rec))
                            except Exception as ex:
                                rec = FileRecord(
                                    name=name,
                                    modified_at=_to_iso(modified),
                                    size_bytes=size_bytes,
                                    action="error",
                                    reason=f"delete_failed: {ex}",
                                    timestamp_source=ts_source,
                                )
                                result.totals["errors"] += 1
                                self.log.error(
                                    "file_delete_failed",
                                    name=name,
                                    error=str(ex),
                                )
                                if include_listing:
                                    result.files.append(asdict(rec))

                    # -- Newer than cutoff -> keep ---------------------------
                    else:
                        rec = FileRecord(
                            name=name,
                            modified_at=_to_iso(modified),
                            size_bytes=size_bytes,
                            action="keep",
                            reason="newer_than_cutoff",
                            timestamp_source=ts_source,
                        )
                        result.totals["kept"] += 1
                        if include_listing:
                            result.files.append(asdict(rec))

            finally:
                try:
                    self.ftp.cwd(original)
                except Exception:
                    pass
            result.ok = True
            return result
        except Exception as e:
            result.errors.append(str(e))
            result.totals["errors"] += 1
            self.log.error("cleanup_failed", error=str(e))
            return result
        finally:
            result.finished_utc = _to_iso(_utc_now())
            self.log.info(
                "cleanup_finished",
                ok=result.ok,
                totals=result.totals,
                finished_utc=result.finished_utc,
            )


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    FTP_HOST = os.getenv("FTP_HOST", "10.10.96.127")
    FTP_PORT = _int_env("FTP_PORT", 21)
    FTP_USERNAME = os.getenv("FTP_USERNAME") or None
    FTP_PASSWORD = os.getenv("FTP_PASSWORD") or None
    TIMEOUT_SECONDS = _int_env("FTP_TIMEOUT_SECONDS", 30)
    TARGET_DIRECTORY = os.getenv("TARGET_DIRECTORY", "/usb/Media")
    KEEP_WEEKS = _int_env("KEEP_WEEKS", default=_int_env("WEEKS_THRESHOLD", 2))
    DRY_RUN = _bool_env("DRY_RUN", default=True)
    JSON_OUTPUT = _bool_env("JSON_OUTPUT", default=True)
    INCLUDE_LISTING = _bool_env("INCLUDE_LISTING", default=True)
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    log = JsonLineLogger(json_output=JSON_OUTPUT, level=LOG_LEVEL)
    cleaner = FTPCleaner(
        FTP_HOST, FTP_USERNAME, FTP_PASSWORD, FTP_PORT,
        timeout_seconds=TIMEOUT_SECONDS,
        logger=log,
    )

    exit_code = 1
    result: Optional[RunResult] = None

    try:
        cleaner.connect()
        result = cleaner.delete_old_files(
            directory=TARGET_DIRECTORY,
            weeks=KEEP_WEEKS,
            dry_run=DRY_RUN,
            include_listing=INCLUDE_LISTING,
        )
        exit_code = 0 if result.ok else 2
    except Exception as e:
        log.error("fatal_error", error=str(e))
        result = RunResult(
            ok=False,
            host=FTP_HOST,
            port=FTP_PORT,
            directory=TARGET_DIRECTORY,
            dry_run=DRY_RUN,
            weeks_threshold=KEEP_WEEKS,
            cutoff_utc=_to_iso(_utc_now() - dt.timedelta(weeks=KEEP_WEEKS)),
            started_utc=_to_iso(_utc_now()),
            finished_utc=_to_iso(_utc_now()),
            totals={
                "scanned": 0, "kept": 0, "deleted": 0,
                "skipped": 0, "errors": 1,
                "ts_filename": 0, "ts_mlsd": 0, "ts_mdtm": 0,
                "ts_list_exact": 0, "ts_list_estimated": 0,
            },
            files=[],
            errors=[str(e)],
        )
        exit_code = 2
    finally:
        cleaner.disconnect()
        if JSON_OUTPUT and result is not None:
            print(json.dumps(result.to_dict(), indent=2, default=str), flush=True)
        elif result is not None:
            print(f"OK={result.ok} totals={result.totals} dry_run={result.dry_run}")

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
