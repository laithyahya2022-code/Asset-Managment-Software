# IT Asset Management System (ITAM)

A lightweight web application for tracking IT assets — hardware inventory,
employee assignments, and warranty status — built with Flask and SQLite.

## Features

- **Asset inventory** — track asset tag, serial number, manufacturer/model,
  location, purchase date/cost, warranty expiry, and notes.
- **Lifecycle statuses** — Available, Assigned, In Repair, Retired.
- **Check-out / check-in** — assign assets to employees and keep a full
  assignment history per asset and per employee.
- **Employees** — manage staff and see what each person currently holds.
- **Categories** — organize assets (Laptops, Monitors, Phones, …).
- **Dashboard** — asset counts by status and category, recent activity, and
  warranty expiry warnings.
- **Search & filters** — find assets by tag, name, serial, manufacturer,
  model, or location; filter by status and category.

## Getting started

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# optional: load sample data
flask --app app seed

flask --app app run
```

Then open http://127.0.0.1:5000. The SQLite database is created automatically
in the `instance/` folder on first run.

## Running tests

```bash
pytest
```

## Project layout

```
app.py                  # entry point (flask --app app run)
itam/
  __init__.py           # app factory + `flask seed` CLI command
  models.py             # Category, Employee, Asset, Assignment
  routes.py             # all views (dashboard, assets, employees, categories)
  seed.py               # sample data
  templates/            # Jinja2 templates
  static/style.css      # styling
tests/test_app.py       # pytest suite
```
