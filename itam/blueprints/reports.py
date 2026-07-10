from datetime import date

from flask import Blueprint, render_template, request

from ..models import (Asset, Assignment, Department, Employee, InventoryAudit,
                      License, Maintenance, db)
from ..security import perm_required
from ..utils import csv_response

bp = Blueprint("reports", __name__, url_prefix="/reports")

REPORTS = {
    "assets": "Asset Register",
    "departments": "Assets by Department",
    "employees": "Employee Assignments",
    "maintenance": "Maintenance Log",
    "warranty": "Warranty Status",
    "licenses": "License Compliance",
    "financial": "Financial / Depreciation",
    "inventory": "Inventory & Missing Assets",
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
