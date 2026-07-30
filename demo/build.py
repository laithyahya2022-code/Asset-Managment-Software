"""Build demo/itam-demo-ams.html — a self-contained, offline, interactive demo.

Reads the seeded database through the app itself, so the demo ships the same
records, the same QR/Code-128 codes and the same Arabic strings the real app
would serve.

    flask --app app seed      # once, to create instance/itam.sqlite
    python demo/build.py
"""
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(ROOT, "demo")
sys.path.insert(0, ROOT)

from itam import APP_VERSION, create_app  # noqa: E402
from itam.i18n import AR  # noqa: E402
from itam.models import (ASSET_CONDITIONS, ASSET_STATUSES, BRANCHES,  # noqa: E402
                         BUILDINGS, FLOORS, MAINTENANCE_KINDS,
                         MAINTENANCE_STATUSES, PLACES, Asset, Assignment,
                         Category, Department, Employee, License,
                         LicenseAssignment, Location, Maintenance,
                         Notification, Vendor)
from itam.utils import barcode_svg, qr_svg  # noqa: E402


def iso(v):
    return v.isoformat() if v else None


def loc_path(loc):
    parts, node = [], loc
    while node is not None:
        parts.append(node.name)
        node = node.parent
    return " / ".join(reversed(parts))


def tidy_svg(svg):
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
    svg = re.sub(r"<!DOCTYPE[^>]*>", "", svg)
    return " ".join(svg.split())


# The sidebar/topbar icon set, lifted from itam/templates/_icons.html so the
# demo's chrome matches the app exactly.
ICONS = {
    "dashboard": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "asset": '<rect x="2" y="4" width="20" height="13" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>',
    "checkout": '<polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>',
    "license": '<circle cx="12" cy="8" r="6"/><path d="M15.5 13.5 17 22l-5-3-5 3 1.5-8.5"/>',
    "wrench": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    "location": '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
    "qr": '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><line x1="14" y1="14" x2="17" y2="14"/><line x1="21" y1="14" x2="21" y2="17"/><line x1="14" y1="18" x2="14" y2="21"/><line x1="18" y1="18" x2="21" y2="21"/>',
    "report": '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
    "users": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "activity": '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "bell": '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
    "search": '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    "dollar": '<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "box": '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
    "truck": '<rect x="1" y="3" width="15" height="13" rx="1"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>',
    "building": '<rect x="4" y="2" width="16" height="20" rx="1"/><line x1="9" y1="7" x2="10" y2="7"/><line x1="14" y1="7" x2="15" y2="7"/><line x1="9" y1="12" x2="10" y2="12"/><line x1="14" y1="12" x2="15" y2="12"/><line x1="9" y1="17" x2="15" y2="17"/>',
    "clipboard": '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/>',
    "alert": '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    "check": '<polyline points="20 6 9 17 4 12"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "trend": '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>',
    "user": '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "menu": '<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "logout": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
}


def collect():
    data = {
        "constants": {
            "statuses": ASSET_STATUSES, "conditions": ASSET_CONDITIONS,
            "branches": BRANCHES, "buildings": BUILDINGS, "floors": FLOORS,
            "places": PLACES, "maintKinds": MAINTENANCE_KINDS,
            "maintStatuses": MAINTENANCE_STATUSES,
        },
        "categories": [{"id": c.id, "name": c.name, "prefix": c.prefix}
                       for c in Category.query.order_by(Category.name)],
        "departments": [{"id": x.id, "name": x.name, "costCenter": x.cost_center}
                        for x in Department.query.order_by(Department.name)],
        "locations": [{"id": l.id, "name": l.name, "kind": l.kind,
                       "parentId": l.parent_id, "path": loc_path(l)}
                      for l in Location.query.order_by(Location.id)],
        "vendors": [{"id": v.id, "name": v.name, "contactName": v.contact_name,
                     "email": v.email, "phone": v.phone, "website": v.website,
                     "assetCount": len(v.assets), "licenseCount": len(v.licenses)}
                    for v in Vendor.query.order_by(Vendor.name)],
        "employees": [{"id": e.id, "name": e.name, "code": e.emp_code,
                       "type": e.emp_type, "email": e.email, "phone": e.phone,
                       "title": e.title,
                       "department": e.department.name if e.department else None,
                       "active": e.active}
                      for e in Employee.query.order_by(Employee.name)],
        "assets": [], "assignments": [], "licenses": [], "maintenance": [],
        "notifications": [],
    }

    for a in Asset.query.order_by(Asset.tag):
        holder = next((x.employee.name for x in a.assignments
                       if x.returned_at is None and x.employee), None)
        data["assets"].append({
            "id": a.id, "tag": a.tag, "name": a.name,
            "category": a.category.name if a.category else None,
            "type": a.asset_type, "serial": a.serial,
            "manufacturer": a.manufacturer, "model": a.model,
            "status": a.status, "condition": a.condition,
            "branch": a.branch, "building": a.building, "floor": a.floor,
            "locationPath": loc_path(a.location) if a.location else None,
            "locationName": a.location_name,
            "department": a.department.name if a.department else None,
            "vendor": a.vendor.name if a.vendor else None,
            "purchaseDate": iso(a.purchase_date),
            "purchaseCost": float(a.purchase_cost) if a.purchase_cost else None,
            "depreciationYears": a.depreciation_years,
            "warrantyExpiry": iso(a.warranty_expiry),
            "notes": a.notes, "updatedBy": a.updated_by,
            "createdAt": iso(a.created_at), "assignedTo": holder,
        })

    for x in Assignment.query.order_by(Assignment.id):
        data["assignments"].append({
            "id": x.id, "assetTag": x.asset.tag if x.asset else None,
            "assetName": x.asset.name if x.asset else None,
            "employee": x.employee.name if x.employee else None,
            "checkoutAt": iso(x.assigned_at), "dueAt": iso(x.due_at),
            "returnedAt": iso(x.returned_at), "notes": x.notes,
        })

    for x in License.query.order_by(License.name):
        data["licenses"].append({
            "id": x.id, "name": x.name, "key": x.key, "seats": x.seats,
            "used": LicenseAssignment.query.filter_by(license_id=x.id).count(),
            "vendor": x.vendor.name if x.vendor else None,
            "purchaseDate": iso(x.purchase_date), "expiry": iso(x.expiry_date),
            "cost": float(x.cost) if x.cost else None,
        })

    for x in Maintenance.query.order_by(Maintenance.id):
        data["maintenance"].append({
            "id": x.id, "assetTag": x.asset.tag if x.asset else None,
            "assetName": x.asset.name if x.asset else None,
            "kind": x.kind, "status": x.status, "title": x.title,
            "description": x.description, "scheduledFor": iso(x.scheduled_for),
            "completedAt": iso(x.completed_at),
            "cost": float(x.cost) if x.cost else None,
            "technician": x.technician.name if x.technician else None,
        })

    for n in Notification.query.order_by(Notification.id):
        data["notifications"].append({
            "kind": n.kind, "message": n.message, "createdAt": iso(n.created_at),
        })

    codes = {a["tag"]: {"qr": tidy_svg(qr_svg(a["tag"])),
                        "barcode": tidy_svg(barcode_svg(a["tag"]))}
             for a in data["assets"]}
    return data, codes


def main():
    app = create_app()
    with app.app_context():
        data, codes = collect()

    if not data["assets"]:
        sys.exit("No assets found — run `flask --app app seed` first.")

    with open(os.path.join(ROOT, "itam", "static", "icon.svg")) as f:
        logo = tidy_svg(f.read())

    with open(os.path.join(HERE, "app.template.html")) as f:
        html = f.read()

    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    for token, value in [
        ("__DATA__", dump(data)), ("__CODES__", dump(codes)),
        ("__AR__", dump(AR)), ("__ICONS__", dump(ICONS)),
        ("__LOGO__", dump(logo)), ("__VERSION__", APP_VERSION),
        ("__TODAY__", date.today().isoformat()),
    ]:
        html = html.replace(token, value)

    left = [t for t in ("__DATA__", "__CODES__", "__AR__", "__ICONS__",
                        "__LOGO__", "__VERSION__", "__TODAY__") if t in html]
    if left:
        sys.exit("Unsubstituted placeholders: " + ", ".join(left))

    # NB: itam-demo.html is the hand-maintained published demo — never
    # overwrite it from here.
    out = os.path.join(HERE, "itam-demo-ams.html")
    with open(out, "w") as f:
        f.write(html)

    print(f"wrote {out} ({os.path.getsize(out) / 1024:.0f} KB)")
    for key in ("assets", "employees", "licenses", "maintenance", "assignments"):
        print(f"  {key}: {len(data[key])}")


if __name__ == "__main__":
    main()
