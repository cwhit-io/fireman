# ember-express

A CUPS print queue that bridges networked clients (Windows, macOS, Linux) to a
**Fiery** RIP over IPP, with enforced job settings.

---

## What it does

- Registers a CUPS printer called **EmberExpress** that points directly at the Fiery (`ipp://10.10.96.103/ipp/print`)
- Advertises the printer on the LAN via **mDNS/Bonjour** (macOS, Linux) and **WSD** (Windows — no extra software needed)
- Locks every job to:
  - **8.5 × 11 in** (US Letter)
  - **Plain paper** (81–91 g/m²)
  - **No hole punch**
- Lets users choose: **color / mono**, **simplex / duplex**, **copies**

---

## Requirements

| Component | Notes |
|-----------|-------|
| Fedora (or RHEL-compatible) | Host OS |
| CUPS | Print server |
| Avahi | mDNS/Bonjour discovery |
| wsdd + samba | WSD discovery for Windows |
| Fiery PPD | `~/fireman/assets/printer/ppd/EF678921.PPD` |

---

## Setup

Run once on a fresh machine:

```bash
make register-printer
```

This will:
1. Install CUPS, Avahi, wsdd, and Samba
2. Configure CUPS to listen on the LAN
3. Open firewall ports (IPP 631, mDNS 5353, WSD 3702)
4. Register the **EmberExpress** printer with locked defaults

---

## Make targets

| Target | Description |
|--------|-------------|
| `make register-printer` | Full setup — deps, CUPS config, printer registration |
| `make status` | Show current queue status |
| `make enable` | Re-enable queue if CUPS disabled it after an error |
| `make test-print` | Send a CUPS test page |
| `make cups-log` | Follow the CUPS journal log |
| `make remove-printer` | Remove the EmberExpress queue |

---

## Windows discovery

After `make register-printer`, on Windows go to:

**Settings → Bluetooth & devices → Printers & scanners → Add a device**

**EmberExpress** will appear automatically via WSD. No drivers or Bonjour software required.

---

## Fiery connection

| Setting | Value |
|---------|-------|
| IP | `10.10.96.103` |
| Queue | `ipp/print` |
| PPD | `EF678921.PPD` |

To change the Fiery IP, edit the `FIERY_IP` variable at the top of the `Makefile`, then re-run `make register-printer`.

---

## Locked job settings

These are applied to every job regardless of what the client requests:

| Setting | Value | Fiery option |
|---------|-------|--------------|
| Page size | US Letter (8.5 × 11 in) | `PageSize=Letter` |
| Media type | Plain paper | `MediaType=Plain` |
| Hole punch | Off | `Punch=Off` |

Users may still select color mode, duplex, and copy count from their print dialog.
