# Interactive demo

`itam-demo.html` is a single self-contained page that reproduces the app's UI
and runs entirely in the browser — no server, no network, no database. It is
meant for showing the system to people who can't reach the school server.

Open the file directly in any browser, or host it anywhere static.

## What is real

The page is generated from a seeded database by `build.py`, so it ships the
same records the app itself would serve:

- the seeded assets, employees, departments, locations, vendors, licenses and
  maintenance tasks
- **real, scannable QR and Code-128 labels**, produced by the app's own
  `qrcode` and `python-barcode` generators — not drawings that merely look
  like codes
- the Arabic strings from `itam/i18n.py`, driving a working RTL toggle
- the design tokens from `itam/static/style.css`

Working: sidebar navigation, all eight asset filters, column sorting, asset
detail, check-out/check-in, status changes, the New Asset form (live 6×3 label
preview and prefix-based tag numbering), maintenance completion, inventory
ticking, tag lookup, all ten reports, CSV export, global search, notifications
and the language toggle.

## What is not

- **State is in-memory.** Anything you change resets on reload; the ribbon has
  a Reset button.
- **No camera.** A static page can't run the barcode scanner, so the Scanner
  screen offers manual tag lookup instead.
- Backups and settings are acknowledged but not simulated further.

## Rebuilding

`build.py` reads the database through the app, so seed it first:

```bash
flask --app app seed        # creates instance/itam.sqlite
python demo/build.py        # writes demo/itam-demo.html
```

Edit `app.template.html` for markup, styles or behaviour — `itam-demo.html` is
generated output and any edits to it are overwritten on the next build.
