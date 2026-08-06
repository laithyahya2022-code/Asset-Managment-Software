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
- **Repo:** `laithyahya2022-code/Asset-Managment-Software`
- **Main working branch:** `claude/itam-m4nmpb` (has ALL the latest work — see log below)
- **Permanent download:** https://github.com/laithyahya2022-code/Asset-Managment-Software/releases/latest  (assets: `AMS.exe`, `AMS-Server-Setup.zip`)
- **Live interactive demo:** https://claude.ai/code/artifact/2a2d6312-74b4-4d86-bf85-0e2ad9380dc5
- **User's data:** the `instance/` folder next to `ITAM.exe` on the server (SQLite). Never part of git.

## Tech stack
- Python **Flask** + **Flask-SQLAlchemy**, **SQLite** by default (PostgreSQL optional via `DATABASE_URL`)
- Server: **waitress**; packaged to Windows `ITAM.exe` via **PyInstaller** (`--noconsole`)
- Desktop window via **pywebview** (falls back to Edge/Chrome app-mode, then browser)
- **openpyxl** (Excel), **qrcode** + **python-barcode** (labels)
- PWA: manifest + service worker + icons (installable)
- Tests: **pytest** (`tests/test_app.py`, 78 passing)
- CI: `.github/workflows/build-exe.yml` (CI + 90-day artifact) and `release.yml`
  (publishes/refreshes the permanent `v1.0.0` release on every push to `claude/**`)

## Architecture / key files
- `run_server.py` — launcher: serves with waitress, opens a desktop app window, writes access info to a text file.
- `itam/__init__.py` — app factory; `APP_VERSION` constant (shown in sidebar); ProxyFix for domain hosting.
- `itam/models.py` — SQLAlchemy models + constants (BRANCHES, BUILDINGS, FLOORS, PLACES, EMPLOYEE_TYPES, ASSET_STATUSES, ASSET_CONDITIONS, LOCATION_KINDS).
- `itam/blueprints/` — `auth`, `main`, `assets`, `operations` (ops: licenses/maintenance/inventory), `org` (employees/departments/locations/vendors), `reports`, `admin`, `api`.
- `itam/utils.py` — CSV/XLSX helpers (`read_table`, `csv_response`, `xlsx_response`), QR/barcode, charts, settings.
- `itam/templates/` — Jinja2 templates; `base.html` is the shell (sidebar shows logged-in user + version).
- `itam/static/` — `style.css`, `app.js`, icons (`icon.svg`, `icon-192/512.png`, `apple-touch-icon.png`, `app.ico`), `manifest.webmanifest`. The service worker is **not** static: it is
  rendered by `main.service_worker()` from `itam/templates/sw.js` so its cache name carries `APP_VERSION`.
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
- Windows `AMS.exe` opens as a maximized desktop window (no console, no browser tab).
- Permanent GitHub Release download; on-prem domain hosting (Caddy) for `itam.madaacademy.edu.jo`.

## Conventions
- Match existing code style. Run `pytest` before committing.
- After changing anything under `itam/`, a push to `claude/**` rebuilds `AMS.exe` and refreshes the release automatically.
- **Bump `APP_VERSION` in `itam/__init__.py` on every release.** It is not cosmetic:
  the updater compares it against the published `version.txt`, and it busts the
  service-worker cache and the `?v=` on `style.css` / `app.js`. Ship a build without
  bumping it and installed copies stay on the old exe *and* the old stylesheet.
  The release job warns in its run summary when the version is unchanged.
- Data lives in `instance/` — updating the app never touches it; users keep that folder across updates.

## How to run / test locally
```
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q          # 78 tests
AMS_NO_BROWSER=1 PORT=8099 python run_server.py    # serve headless
# login: admin / admin123
```

## Open / possible next tasks
- Finalize on-prem domain hosting for `itam.madaacademy.edu.jo` (needs server LAN IP + DNS record from school IT).
- Optional: a "Branches" overview page (asset counts by branch → building → floor).
- Optional: link "Assigned to" text to actual employee records (currently kept in notes on import).
- Optional: code-signing certificate to remove the Windows SmartScreen "unknown publisher" prompt.

---

**To continue:** confirm you're on branch `claude/itam-m4nmpb` (or merge it in), run the tests, then tell me what to build next.

## Performance notes (measured on a 3,000-asset database)
Pages that render a whole table, and reports that loop over rows touching a
relationship, are where this app gets slow. Both patterns have bitten it:

| Page | Before | After |
|---|---|---|
| `/assets/` | 1292 ms · 3026 queries · 1 MB | 14 ms · 19 queries · 34 KB |
| `/locations` | 383 ms · 593 queries · 354 KB | 28 ms · 8 queries · 77 KB |
| `/checkouts` | 1.33 MB page | 31 KB · 50 ms |
| `/reports/locations` | 297 ms · 593 queries | 10 ms · 8 queries |

Rules of thumb that came out of it:
- Page any list that can grow (`PAGE_SIZE` in `assets.py`, `LOCATION_PAGE_SIZE`
  in `org.py`). Exports and label sheets must still cover *every* matching row,
  not just the visible page — see `_filtered_assets` vs `_assets_page`.
- Never print a `<select>` of the whole location tree. "Add standard locations"
  creates ~600 of them. Filters list only locations in use; pickers that need
  the full tree fetch it from `/assets/locations.json` or `/lend/assets.json`.
- Eager-load with `joinedload`/`selectinload` anything a template or report
  reads per row, and prefer one grouped aggregate over a per-row `len(x.assets)`.
- Query counts, not wall-clock, are the signal. Attach a
  `before_cursor_execute` listener and count.

## Things that are easy to get wrong here
- Removing a field from a form silently blanks the stored value on the next
  save, because `form.get()` returns None. Guard with `if field in form`
  (`_from_form` in `assets.py` does this for `os_version`, `parent_id`,
  `updated_by`).
- Assignment belongs to **Lending**. The asset form shows the holder and the
  data-entry name but does not submit them. Every place that creates an
  `Assignment` must set `handled_by`, or "Edited by" is blank depending on
  which screen the loan came from.
- `int(request.args[...])` on a filter crashes the page for a hand-edited URL.
  Wrap it; a filter that isn't a number is no filter.
- `itam/routes.py` is dead code — not registered, references models that no
  longer exist (`asset.asset_tag`). Don't take it as a guide.

## Deployment: it is a server app, not a file you double-click
The single-exe model caused two data scares in one afternoon, because the
database lives in `instance/` **next to the executable**:
- Windows saves a re-download as `AMS (1).exe`, which runs beside a *new*
  empty `instance/` — the old data is untouched but invisible.
- Copying `AMS.exe` to a second PC creates a second empty system with only
  the default `admin/admin123`. The two never merge.

`deploy/Install-AMS.ps1` (+ `.bat` wrapper, shipped as `AMS-Server-Setup.zip`)
is the answer: fixed `C:\AMS`, scheduled task at boot as SYSTEM, firewall rule,
headless, re-runnable as an upgrade. It must never write to `instance/` — a
test asserts that, and CI parses both scripts on a Windows runner before
release.

Everyone else uses a browser against the one address. That is the only
supported way to share data.

## Session key
`SECRET_KEY` used to fall back to the literal `"dev-change-me"`, so any
network-reachable install signed cookies with a key published in the source
and an attacker could forge an admin session. It is now generated per
installation and stored in `instance/secret_key` (so upgrades don't log
everyone out); the environment variable still wins for central management.
