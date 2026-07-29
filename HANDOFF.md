# ITAM — Project Handoff / Continue-Here

Paste this whole file into a new Claude Code session to pick the project up with
full context, then say what you want to build next.

---

## What this project is
An **Enterprise IT Asset Management System (ITAM)** for **Mada International
Academy** (branches: Mada 1, Mada 2, Mada 3). It's a free, self-hosted, web-based
app that tracks IT assets, people, licenses, maintenance, inventory and reports.
It runs on the school's own server (on-prem), with one shared database, opened in
a browser. Goal scale: 3,000+ assets and 500+ employees.

## Where everything lives
- **Repo:** `laithyahya2022-code/IT-Asset-Management-System-`
- **Main working branch:** `claude/itam-m4nmpb` (has ALL the latest work — see log below)
- **Permanent download:** https://github.com/laithyahya2022-code/IT-Asset-Management-System-/releases/latest  (asset: `ITAM.exe`)
- **Live interactive demo:** https://claude.ai/code/artifact/2a2d6312-74b4-4d86-bf85-0e2ad9380dc5
- **User's data:** the `instance/` folder next to `ITAM.exe` on the server (SQLite). Never part of git.

## Tech stack
- Python **Flask** + **Flask-SQLAlchemy**, **SQLite** by default (PostgreSQL optional via `DATABASE_URL`)
- Server: **waitress**; packaged to Windows `ITAM.exe` via **PyInstaller** (`--noconsole`)
- Desktop window via **pywebview** (falls back to Edge/Chrome app-mode, then browser)
- **openpyxl** (Excel), **qrcode** + **python-barcode** (labels)
- PWA: manifest + service worker + icons (installable)
- Tests: **pytest** (`tests/test_app.py`, 26 passing)
- CI: `.github/workflows/build-exe.yml` (CI + 90-day artifact) and `release.yml`
  (publishes/refreshes the permanent `v1.0.0` release on every push to `claude/**`)

## Architecture / key files
- `run_server.py` — launcher: serves with waitress, opens a desktop app window, writes access info to a text file.
- `itam/__init__.py` — app factory; `APP_VERSION` constant (shown in sidebar); ProxyFix for domain hosting.
- `itam/models.py` — SQLAlchemy models + constants (BRANCHES, BUILDINGS, FLOORS, PLACES, EMPLOYEE_TYPES, ASSET_STATUSES, ASSET_CONDITIONS, LOCATION_KINDS).
- `itam/blueprints/` — `auth`, `main`, `assets`, `operations` (ops: licenses/maintenance/inventory), `org` (employees/departments/locations/vendors), `reports`, `admin`, `api`.
- `itam/utils.py` — CSV/XLSX helpers (`read_table`, `csv_response`, `xlsx_response`), QR/barcode, charts, settings.
- `itam/templates/` — Jinja2 templates; `base.html` is the shell (sidebar shows logged-in user + version).
- `itam/static/` — `style.css`, `app.js`, icons (`icon.svg`, `icon-192/512.png`, `apple-touch-icon.png`, `app.ico`), `manifest.webmanifest`, `sw.js`.
- `deploy/` — `HOST-AS-A-WEBSITE.md`, `Caddyfile`, `start-itam.bat` (on-prem domain hosting).
- `demo/itam-demo.html` — self-contained INTERACTIVE demo (localStorage). Publish as an artifact for a clickable demo link (not a screenshot tour).

## Features already built
- Asset register with auto-generated Asset IDs (category prefix, e.g. DES-000001) + QR codes.
- Branch / Building / Floor / Location / Assigned-to / Updated-by fields; filters + columns on the Assets list.
- Robust Excel/CSV import for messy real-world sheets: flexible header matching (TAG, Serial No., Asset Status, Assigned to, Dept, etc.), auto-generates unique tags when the file's tags are missing/duplicated, auto-creates categories & departments, parses DD/MM/YYYY, fills Type from the category column.
- Employees import keyed on Employee ID (shared emails allowed; email is optional/non-unique); understands "Employee Type"/"Job Title"; auto-creates departments.
- Lending (check-out/check-in), licenses, maintenance, inventory audits, vendors, reports, analytics, roles/permissions, Arabic (RTL) support.
- Add + Import/Export (Excel & CSV) on licenses/maintenance/inventory/employees; per-row Edit.
- 6×3 printable QR labels; live label preview on the asset form.
- PWA install; Mada green "M" branding across app + favicon + exe icon.
- Windows `ITAM.exe` opens as a desktop window (no console, no browser tab).
- Permanent GitHub Release download; on-prem domain hosting (Caddy) for `itam.madaacademy.edu.jo`.

## Conventions
- Match existing code style. Run `pytest` before committing.
- After changing anything under `itam/`, a push to `claude/**` rebuilds `ITAM.exe` and refreshes the release automatically.
- Bump `APP_VERSION` in `itam/__init__.py` on notable releases (it's visible in the sidebar so users can confirm their build).
- Data lives in `instance/` — updating the app never touches it; users keep that folder across updates.

## How to run / test locally
```
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q          # 26 tests
ITAM_NO_BROWSER=1 PORT=8099 python run_server.py   # serve headless
# login: admin / admin123
```

## Open / possible next tasks
- Finalize on-prem domain hosting for `itam.madaacademy.edu.jo` (needs server LAN IP + DNS record from school IT).
- Optional: a "Branches" overview page (asset counts by branch → building → floor).
- Optional: link "Assigned to" text to actual employee records (currently kept in notes on import).
- Optional: code-signing certificate to remove the Windows SmartScreen "unknown publisher" prompt.

---

**To continue:** confirm you're on branch `claude/itam-m4nmpb` (or merge it in), run the tests, then tell me what to build next.
