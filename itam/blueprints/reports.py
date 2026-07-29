from datetime import date

from flask import Blueprint, render_template, request

from ..models import (ASSET_CONDITIONS, ASSET_STATUSES, Asset, Assignment,
                      Category, Department, Employee, InventoryAudit, License,
                      Location, Maintenance, User, db)
from ..security import perm_required
from ..utils import csv_response

bp = Blueprint("reports", __name__, url_prefix="/reports")

REPORTS = {
    "assets": "Asset Register",
    "departments": "Assets by Department",
    "locations": "Assets by Branch / Building",
    "employees": "Employee Assignments",
    "maintenance": "Maintenance Log",
    "warranty": "Warranty Status",
    "licenses": "License Compliance",
    "financial": "Financial / Depreciation",
    "inventory": "Inventory & Missing Assets",
    "movement": "Asset Movement / Transfers",
    "lifecycle": "Lifecycle & End-of-Life",
}


def _report_data(name, args):
    """Return (headers, rows) where each row cell may be (text, url) or text."""
    today = date.today()
    if name == "assets":
        headers = ["Tag", "Name", "Category", "Status", "Condition", "Location",
                   "Department", "Serial"]
        rows = [[a.tag, a.name, a.category.name if a.category else "", a.status,
                 a.condition, a.location.path if a.location else "",
                 a.department.name if a.department else "", a.serial or ""]
                for a in db.session.scalars(db.select(Asset).order_by(Asset.tag))]
    elif name == "departments":
        headers = ["Department", "Cost Center", "Assets", "Purchase Cost", "Current Value"]
        rows = []
        for d in db.session.scalars(db.select(Department).order_by(Department.name)):
            cost = sum(float(a.purchase_cost or 0) for a in d.assets)
            value = sum(a.current_value or 0 for a in d.assets)
            rows.append([d.name, d.cost_center or "", len(d.assets),
                         f"{cost:,.2f}", f"{value:,.2f}"])
    elif name == "employees":
        headers = ["Employee", "Department", "Email", "Assets Held", "Overdue"]
        rows = []
        for e in db.session.scalars(db.select(Employee).order_by(Employee.name)):
            active = [x for x in e.assignments if x.returned_at is None]
            overdue = len([x for x in active if x.overdue])
            rows.append([e.name, e.department.name if e.department else "",
                         e.email, len(active), overdue])
    elif name == "maintenance":
        headers = ["Asset", "Title", "Kind", "Status", "Scheduled", "Completed", "Cost"]
        rows = [[m.asset.tag, m.title, m.kind, m.status, m.scheduled_for or "",
                 m.completed_at.date() if m.completed_at else "", m.cost or ""]
                for m in db.session.scalars(
                    db.select(Maintenance).order_by(Maintenance.created_at.desc()))]
    elif name == "warranty":
        headers = ["Tag", "Name", "Warranty Expiry", "Status"]
        rows = []
        for a in db.session.scalars(db.select(Asset)
                                    .where(Asset.warranty_expiry.isnot(None))
                                    .order_by(Asset.warranty_expiry)):
            state = ("Expired" if a.warranty_expiry < today
                     else f"{(a.warranty_expiry - today).days} days left")
            rows.append([a.tag, a.name, a.warranty_expiry, state])
    elif name == "licenses":
        headers = ["License", "Seats", "Used", "Compliant", "Expiry", "Cost"]
        rows = [[l.name, l.seats, l.seats_used, "Yes" if l.compliant else "NO",
                 l.expiry_date or "", l.cost or ""]
                for l in db.session.scalars(db.select(License).order_by(License.name))]
    elif name == "financial":
        headers = ["Tag", "Name", "Purchase Date", "Purchase Cost",
                   "Depreciation (yrs)", "Current Value"]
        rows = [[a.tag, a.name, a.purchase_date or "", a.purchase_cost or "",
                 a.depreciation_years or 5,
                 f"{a.current_value:,.2f}" if a.current_value is not None else ""]
                for a in db.session.scalars(db.select(Asset).order_by(Asset.tag))]
    elif name == "locations":
        headers = ["Location", "Kind", "Assets", "Purchase Cost"]
        rows = []
        for loc in db.session.scalars(db.select(Location)):
            if not loc.assets:
                continue
            cost = sum(float(a.purchase_cost or 0) for a in loc.assets)
            rows.append([loc.path, loc.kind, len(loc.assets), f"{cost:,.2f}"])
        rows.sort(key=lambda r: r[0])
    elif name == "movement":
        from ..models import Transfer
        headers = ["Asset", "From", "To", "When", "By", "Notes"]
        rows = []
        for tr in db.session.scalars(db.select(Transfer)
                                     .order_by(Transfer.at.desc()).limit(500)):
            by = db.session.get(User, tr.by_user) if tr.by_user else None
            rows.append([tr.asset.tag,
                         tr.from_location.path if tr.from_location else "",
                         tr.to_location.path if tr.to_location else "",
                         tr.at.strftime("%Y-%m-%d %H:%M"),
                         by.name if by else "", tr.notes or ""])
    elif name == "lifecycle":
        headers = ["Tag", "Name", "Age (years)", "Depreciation (yrs)",
                   "Warranty", "Recommendation"]
        rows = []
        for a in db.session.scalars(db.select(Asset)
                                    .where(Asset.status.notin_(["Retired", "Disposed"]))
                                    .order_by(Asset.tag)):
            age = ((today - a.purchase_date).days / 365.25) if a.purchase_date else None
            dep = a.depreciation_years or 5
            end_of_life = (age is not None and age >= dep) or a.warranty_expired
            rows.append([a.tag, a.name,
                         f"{age:.1f}" if age is not None else "unknown", dep,
                         "expired" if a.warranty_expired
                         else (a.warranty_expiry or "—"),
                         "REPLACE — end of life" if end_of_life
                         else ("plan replacement soon"
                               if age is not None and age >= dep - 1 else "OK")])
    elif name == "inventory":
        headers = ["Audit", "Started", "Completed", "Verified", "Missing"]
        rows = [[au.name, au.started_at.date(),
                 au.completed_at.date() if au.completed_at else "in progress",
                 au.verified_count, au.missing_count]
                for au in db.session.scalars(
                    db.select(InventoryAudit).order_by(InventoryAudit.started_at.desc()))]
        rows += [["MISSING ASSET", a.tag, a.name, "", ""] for a in
                 db.session.scalars(db.select(Asset).where(Asset.status == "Missing"))]
    else:
        return None, None
    return headers, rows


@bp.route("/")
@perm_required("reports.view")
def index():
    stats = {
        "assets": db.session.scalar(db.select(db.func.count(Asset.id))) or 0,
        "checkouts": db.session.scalar(db.select(db.func.count(Assignment.id))
                                       .where(Assignment.returned_at.is_(None))) or 0,
        "licenses": db.session.scalar(db.select(db.func.count(License.id))) or 0,
    }
    return render_template("reports/index.html", reports=REPORTS, stats=stats)


# ------------------------------------------------------ custom report builder

CUSTOM_COLS = {
    "tag": ("Tag", lambda a: a.tag),
    "name": ("Name", lambda a: a.name),
    "category": ("Category", lambda a: a.category.name if a.category else ""),
    "type": ("Type", lambda a: a.asset_type or ""),
    "serial": ("Serial", lambda a: a.serial or ""),
    "manufacturer": ("Manufacturer", lambda a: a.manufacturer or ""),
    "model": ("Model", lambda a: a.model or ""),
    "status": ("Status", lambda a: a.status),
    "condition": ("Condition", lambda a: a.condition),
    "location": ("Location", lambda a: a.location.path if a.location else ""),
    "department": ("Department", lambda a: a.department.name if a.department else ""),
    "vendor": ("Vendor", lambda a: a.vendor.name if a.vendor else ""),
    "assigned_to": ("Assigned To", lambda a: a.current_assignment.employee.name
                    if a.current_assignment else ""),
    "purchase_date": ("Purchase Date", lambda a: a.purchase_date or ""),
    "purchase_cost": ("Purchase Cost", lambda a: a.purchase_cost or ""),
    "current_value": ("Current Value",
                      lambda a: f"{a.current_value:,.2f}" if a.current_value is not None else ""),
    "warranty_expiry": ("Warranty Expiry", lambda a: a.warranty_expiry or ""),
    "notes": ("Notes", lambda a: a.notes or ""),
}
DEFAULT_COLS = ["tag", "name", "category", "status", "assigned_to"]


@bp.route("/custom")
@perm_required("reports.view")
def custom():
    cols = [c for c in request.args.getlist("col") if c in CUSTOM_COLS] or DEFAULT_COLS
    stmt = db.select(Asset).order_by(Asset.tag)
    if request.args.get("status"):
        stmt = stmt.where(Asset.status == request.args["status"])
    if request.args.get("category"):
        stmt = stmt.where(Asset.category_id == int(request.args["category"]))
    if request.args.get("department"):
        stmt = stmt.where(Asset.department_id == int(request.args["department"]))
    if request.args.get("condition"):
        stmt = stmt.where(Asset.condition == request.args["condition"])
    assets = db.session.scalars(stmt).all()
    headers = [CUSTOM_COLS[c][0] for c in cols]
    rows = [[CUSTOM_COLS[c][1](a) for c in cols] for a in assets]
    if request.args.get("format") == "csv":
        return csv_response(headers, rows, "report-custom.csv")
    return render_template(
        "reports/custom.html", headers=headers, rows=rows, cols=cols,
        all_cols=CUSTOM_COLS, statuses=ASSET_STATUSES, conditions=ASSET_CONDITIONS,
        categories=db.session.scalars(db.select(Category).order_by(Category.name)).all(),
        departments=db.session.scalars(db.select(Department).order_by(Department.name)).all(),
        args=request.args)


@bp.route("/<name>")
@perm_required("reports.view")
def show(name):
    headers, rows = _report_data(name, request.args)
    if headers is None:
        return render_template("reports/index.html", reports=REPORTS, stats={}), 404
    if request.args.get("format") == "csv":
        return csv_response(headers, rows, f"report-{name}.csv")
    return render_template("reports/show.html", name=name, title=REPORTS[name],
                           headers=headers, rows=rows)
