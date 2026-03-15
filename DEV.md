Assets layout and migration

This project stores server-only printer assets (barcode TIFFs, fonts, PPDs)
under `assets/printer/`.

Structure

- assets/printer/barcodes/ (TIFFs: 001.tif ...)
- assets/printer/fonts/trueType/ (TTF fonts used by ReportLab/Pillow)
- assets/printer/ppd/ (PPD files)

Migration

1. Run `make organize-assets` to create the directories and copy existing
   `barcodes/`, `fonts/usps/trueType/` and `EF678921.PPD` into `assets/printer/`.
   Files are copied with `cp -n` so existing destination files are not overwritten.

2. Confirm the app finds assets (the code prefers `ASSETS_DIR/printer/...` and
   falls back to legacy `barcodes/` and `fonts/` paths).

3. If you use Docker, ensure the `assets/printer/` directory is included in the
   image or mounted into the container.

Notes

- The code change is backward-compatible: if assets are not present under
  `assets/printer/`, the app will still look in the legacy locations.
- After verifying everything, you may opt to remove the legacy `barcodes/`
  directory, but keep a backup until deployments are updated.
