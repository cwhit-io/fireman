import shutil

from django.conf import settings


def disk_usage(request):
    """Inject disk usage stats for the sidebar widget."""
    try:
        path = getattr(settings, "MEDIA_MOUNT_POINT", settings.MEDIA_ROOT)
        usage = shutil.disk_usage(path)
        total = usage.total
        used = usage.used
        pct = round(used / total * 100, 1) if total else 0

        def _humanize(n):
            for unit in ("B", "KB", "MB", "GB", "TB"):
                if n < 1024.0:
                    return f"{n:.1f}\u00a0{unit}"
                n /= 1024.0
            return f"{n:.1f}\u00a0PB"

        return {
            "disk_total": total,
            "disk_used": used,
            "disk_free": usage.free,
            "disk_pct": pct,
            "disk_used_human": _humanize(used),
            "disk_total_human": _humanize(total),
        }
    except OSError:
        return {}
