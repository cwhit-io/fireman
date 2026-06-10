# Printing incident: pdftops filter failure (May 28, 2026)

Summary
-------

On 2026-05-28 CUPS disabled the `fiery_hold` queue after a PDF->PS filter failure: logs show `pdftops filter function failed.` The failure coincides with a package update to `poppler-utils` (which provides `pdftops`) on 2026-05-27.

What I did
---------

- Confirmed presence of `lp`, `lpr`, `lpstat`, and `pdftops` on the host.
- Re-enabled `fiery_hold` and verified a simple test job is accepted by CUPS.
- Pinned `poppler-utils` to its current version to prevent automatic updates.
- Added a lightweight monitor script and systemd timer templates to detect disabled printers and recent `pdftops` filter failures.

Commands run (for audit)
-------------------------

To pin `poppler-utils`:

```bash
sudo dnf install -y 'dnf-plugins-core'
sudo dnf versionlock add poppler-utils
```

To re-enable the queue (if needed):

```bash
sudo cupsenable fiery_hold
sudo lpadmin -p fiery_hold -E
```

Monitoring (what I added)
-------------------------

- `scripts/cups_monitor.sh` — checks for disabled printers and recent `pdftops` failures; writes to `/var/log/fireman/cups_monitor.log` and exits non-zero on issues.
- `packaging/systemd/fireman-cups-monitor.service` and `.timer` — templates to run the script every 5 minutes.

Install the monitor
-------------------

1. Copy the script to a system path and make executable:

```bash
sudo cp scripts/cups_monitor.sh /usr/local/bin/fireman-cups-monitor.sh
sudo chmod +x /usr/local/bin/fireman-cups-monitor.sh
```

2. Install and enable the systemd unit and timer:

```bash
sudo cp packaging/systemd/fireman-cups-monitor.service /etc/systemd/system/
sudo cp packaging/systemd/fireman-cups-monitor.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fireman-cups-monitor.timer
```

3. Check the monitor log:

```bash
sudo tail -n 200 /var/log/fireman/cups_monitor.log
```

Notes and recommendations
------------------------

- Pinning `poppler-utils` avoids auto-updating a component of the PDF filter chain that previously caused CUPS to disable a printer. Consider pinning related packages (e.g., `cups-filters`, `ghostscript`) only if you observe repeated regressions.
- The CUPS `ErrorPolicy` is currently `stop-printer` (in `/etc/cups/cupsd.conf`). You can change this to a less aggressive policy (e.g., `retry-job`) but that only avoids automatic disabling; it does not fix underlying filter errors.
- For better app visibility, consider having the app poll CUPS job status after submission (using `lpstat` or `pycups`) and surface job errors to operators.

Files added
-----------

- `scripts/cups_monitor.sh`
- `packaging/systemd/fireman-cups-monitor.service`
- `packaging/systemd/fireman-cups-monitor.timer`
