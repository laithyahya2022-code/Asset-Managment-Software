# Mada Asset Management System (AMS)

A full-featured, self-hosted IT asset management web application built with
Flask. Dark-sidebar dashboard UI, role-based access control, QR codes,
maintenance, licenses, procurement, reports, Arabic/RTL support, and a REST API.

## Feature highlights

- **Authentication & security** — login/logout, password reset links, admin
  user registration, 4 roles (admin / manager / technician / viewer) with an
  editable permission matrix (RBAC), session management, full activity &
  audit log, profile + change password.
- **Dashboard** — KPI cards (total assets, checked out + overdue, under
  maintenance, expiring warranties, total asset value, licenses, available,
  retired), assets-by-category bar chart, assets-by-status donut, alerts and
  recent activity.
- **Assets** — CRUD, categories, types, tags, status, condition, lifecycle,
  notes, images & file attachments (invoices, warranties, manuals), custom
  fields, cloning, bulk actions, CSV import (with validation, duplicate
  detection and preview) and export.
- **QR & barcode** — QR + Code-128 generation per asset, printable label
  sheets, camera scanning page (built-in browser BarcodeDetector) and manual
  code lookup.
- **Inventory** — physical audit sessions (found / missing per asset),
  missing-asset tracking, audit CSV export.
- **Employees, departments, locations** — directory with assignment history,
  departments with cost centers, hierarchical locations
  (branch → building → floor → room → storage), asset transfers.
- **Assignment** — check-out / check-in with due dates and overdue alerts,
  reservations, full history.
- **Maintenance** — preventive & corrective tasks, scheduling, technician
  assignment, spare parts, costs, status workflow.
- **Warranty** — expiry tracking with dashboard alerts and a warranty report.
- **Software licenses** — seats, keys, assignment to assets or employees,
  expiry/renewal alerts, compliance (over-use detection).
- **Vendors & procurement** — supplier directory with purchase history,
  purchase requests → approve → order → receive (optionally auto-creating
  the received assets).
- **Financial** — purchase cost, straight-line depreciation, current value,
  cost analysis by department.
- **Reports** — 8 built-in reports plus a **custom report builder**
  (pick your own columns and filters), all printable and exportable to CSV
  (Excel-compatible, UTF-8 with BOM so Arabic opens correctly).
- **Search** — global search across assets, employees, licenses, vendors, POs,
  plus per-user **saved searches** on the asset list.
- **Notifications** — in-app alerts (warranty, license, maintenance, overdue)
  with optional SMTP email.
- **Multi-language** — English + Arabic with full right-to-left layout and a
  one-click switcher.
- **Mobile & PWA** — responsive layout, installable as an app
  (Add to Home Screen), works on iPhone/Android/tablets.
- **Backup & recovery** — one-click SQLite backup, download, restore, delete,
  plus **automatic daily backups** (keeps the newest 14, toggle in Settings).
- **REST API** — `/api/v1/assets`, `/api/v1/employees`, `/api/v1/licenses`
  with per-user Bearer API keys.
- **Deployment** — SQLite by default, PostgreSQL via `DATABASE_URL`, Docker +
  docker-compose included, runs on Windows or Linux servers.

## Quick start (local / school server)

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

flask --app app seed             # optional sample data
flask --app app run --host=0.0.0.0
```

Open http://SERVER-IP:5000 and log in with **admin / admin123**
(created automatically on first run — change it immediately in Profile).

Sample accounts from the seed: `admin/admin123`, `tech/tech1234`,
`viewer/viewer123`.

## Production with Docker + PostgreSQL

```bash
cp .env.example .env             # set SECRET_KEY and DB_PASSWORD
docker compose up -d
```

The app is served by gunicorn on port 8000 with PostgreSQL storage.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | session signing key | dev value — set in production |
| `DATABASE_URL` | e.g. `postgresql://user:pw@host/db` | SQLite in `instance/` |
| `UPLOAD_FOLDER` | asset file uploads | `instance/uploads` |
| `BACKUP_FOLDER` | database backups | `instance/backups` |

In-app settings (Admin → Settings): application name, QR prefix, custom asset
fields, default checkout period, SMTP email, backup & audit options.

## Tests

```bash
pytest
```

## Project layout

```
app.py                    entry point (flask --app app run / gunicorn app:app)
itam/
  __init__.py             app factory, language switcher, defaults
  models.py               all database models
  security.py             sessions, RBAC decorators
  i18n.py                 English/Arabic translations
  utils.py                settings, audit log, notifications, charts, QR, CSV
  seed.py                 sample data (flask --app app seed)
  blueprints/             auth, main, assets, operations, org, reports, admin, api
  templates/              Jinja2 templates (dark-sidebar UI)
  static/                 CSS, JS, PWA manifest + service worker
tests/test_app.py         pytest suite
Dockerfile, docker-compose.yml
```

## Roadmap / future expansion

REST API write endpoints, Microsoft 365 / Google Workspace / LDAP
integrations, and plugin hooks are planned; the blueprint-based architecture
keeps modules independent so new ones can be added without touching the core.
