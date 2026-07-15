from datetime import date, datetime

from flask import (Blueprint, flash, g, redirect, render_template, request,
                   url_for)

from ..models import (MAINTENANCE_KINDS, MAINTENANCE_STATUSES, Asset,
                      Assignment, Employee, InventoryAudit, InventoryCheck,
                      License, LicenseAssignment, Maintenance, Reservation,
                      User, Vendor, db)
from ..security import perm_required
from ..utils import csv_response, log_activity, parse_date

bp = Blueprint("ops", __name__)


# ---------------------------------------------------------------- checkouts

@bp.route("/checkouts")
@perm_required("assets.view")
def checkouts():
    show = request.args.get("show", "active")
    stmt = db.select(Assignment).order_by(Assignment.assigned_at.desc())
    if show == "active":
        stmt = stmt.where(Assignment.returned_at.is_(None))
    elif show == "overdue":
        stmt = stmt.where(Assignment.returned_at.is_(None),
                          Assignment.due_at.isnot(None),
                          Assignment.due_at < date.today())
    rows = db.session.scalars(stmt.limit(300)).all()
    reservations = db.session.scalars(
        db.select(Reservation).where(Reservation.status == "Active")
        .order_by(Reservation.start_date)).all()
    available = db.session.scalars(
        db.select(Asset).where(Asset.status == "Available").order_by(Asset.tag)).all()
    out_assets = db.session.scalars(
        db.select(Asset).where(Asset.status == "Checked Out").order_by(Asset.tag)).all()
    employees = db.session.scalars(
        db.select(Employee).where(Employee.active).order_by(Employee.name)).all()
    return render_template("checkouts.html", rows=rows, show=show,
                           reservations=reservations, today=date.today(),
                           available=available, out_assets=out_assets,
                           employees=employees)


@bp.post("/lend")
@perm_required("checkout.manage")
def lend():
    from ..models import BLOCKED_CHECKOUT_STATUSES
    asset = db.get_or_404(Asset, int(request.form["asset_id"]))
    if asset.current_assignment or asset.status in BLOCKED_CHECKOUT_STATUSES:
        flash(f"{asset.tag} cannot be lent out right now.", "error")
        return redirect(url_for("ops.checkouts"))
    emp = db.get_or_404(Employee, int(request.form["employee_id"]))
    db.session.add(Assignment(asset=asset, employee=emp, assigned_by=g.user.id,
                              due_at=parse_date(request.form.get("due_at")),
                              notes=request.form.get("notes", "").strip() or None))
    asset.status = "Checked Out"
    log_activity("checked_out", "asset", asset.id, f"{asset.tag} → {emp.name}")
    db.session.commit()
    flash(f"{asset.tag} lent to {emp.name}.", "success")
    return redirect(url_for("ops.checkouts"))


@bp.post("/return")
@perm_required("checkout.manage")
def return_asset():
    asset = db.get_or_404(Asset, int(request.form["asset_id"]))
    asg = asset.current_assignment
    if not asg:
        flash(f"{asset.tag} is not currently lent out.", "error")
        return redirect(url_for("ops.checkouts"))
    asg.returned_at = datetime.utcnow()
    asset.status = "Available"
    log_activity("checked_in", "asset", asset.id, f"{asset.tag} ← {asg.employee.name}")
    db.session.commit()
    flash(f"{asset.tag} returned from {asg.employee.name}.", "success")
    return redirect(url_for("ops.checkouts"))


@bp.post("/reservations/<int:res_id>/cancel")
@perm_required("checkout.manage")
def reservation_cancel(res_id):
    r = db.get_or_404(Reservation, res_id)
    r.status = "Cancelled"
    db.session.commit()
    flash("Reservation cancelled.", "success")
    return redirect(url_for("ops.checkouts"))


# --------------------------------------------------------------- maintenance

@bp.route("/maintenance")
@perm_required("assets.view")
def maintenance_list():
    status = request.args.get("status", "")
    stmt = db.select(Maintenance).order_by(
        Maintenance.status, Maintenance.scheduled_for.is_(None), Maintenance.scheduled_for)
    if status:
        stmt = stmt.where(Maintenance.status == status)
    rows = db.session.scalars(stmt.limit(300)).all()
    return render_template("maintenance/list.html", rows=rows, status=status,
                           statuses=MAINTENANCE_STATUSES, today=date.today())


@bp.route("/maintenance/new", methods=["GET", "POST"])
@perm_required("maintenance.manage")
def maintenance_new():
    if request.method == "POST":
        m = Maintenance(
            asset_id=int(request.form["asset_id"]),
            kind=request.form.get("kind", "Corrective"),
            title=request.form["title"].strip(),
            description=request.form.get("description", "").strip() or None,
            solution=request.form.get("solution", "").strip() or None,
            scheduled_for=parse_date(request.form.get("scheduled_for")),
            technician_id=int(request.form["technician_id"]) if request.form.get("technician_id") else None,
            cost=request.form.get("cost") or None,
            parts=request.form.get("parts", "").strip() or None,
        )
        db.session.add(m)
        asset = db.session.get(Asset, m.asset_id)
        if request.form.get("set_status"):
            asset.status = "Under Maintenance"
        log_activity("maintenance_created", "asset", m.asset_id, m.title)
        db.session.commit()
        flash("Maintenance task created.", "success")
        return redirect(url_for("ops.maintenance_list"))
    assets = db.session.scalars(db.select(Asset).order_by(Asset.tag)).all()
    techs = db.session.scalars(db.select(User).where(User.active).order_by(User.name)).all()
    preselect = request.args.get("asset", type=int)
    return render_template("maintenance/form.html", assets=assets, techs=techs,
                           kinds=MAINTENANCE_KINDS, preselect=preselect)


@bp.post("/maintenance/<int:mid>/status")
@perm_required("maintenance.manage")
def maintenance_status(mid):
    m = db.get_or_404(Maintenance, mid)
    status = request.form["status"]
    if status in MAINTENANCE_STATUSES:
        m.status = status
        if status == "Completed":
            m.completed_at = datetime.utcnow()
            if request.form.get("cost"):
                m.cost = request.form["cost"]
            if request.form.get("solution"):
                m.solution = request.form["solution"].strip()
            if m.asset.status == "Under Maintenance":
                m.asset.status = "Available"
        elif status == "In Progress":
            m.asset.status = "Under Maintenance"
        log_activity("maintenance_" + status.lower().replace(" ", "_"),
                     "asset", m.asset_id, m.title)
        db.session.commit()
        flash(f"Maintenance marked {status}.", "success")
    return redirect(request.referrer or url_for("ops.maintenance_list"))


# ------------------------------------------------------------------ licenses

@bp.route("/licenses")
@perm_required("assets.view")
def licenses():
    rows = db.session.scalars(db.select(License).order_by(License.name)).all()
    return render_template("licenses/list.html", rows=rows, today=date.today())


@bp.route("/licenses/new", methods=["GET", "POST"])
@bp.route("/licenses/<int:license_id>/edit", methods=["GET", "POST"])
@perm_required("licenses.manage")
def license_form(license_id=None):
    lic = db.get_or_404(License, license_id) if license_id else None
    if request.method == "POST":
        if not lic:
            lic = License()
            db.session.add(lic)
        lic.name = request.form["name"].strip()
        lic.vendor_id = int(request.form["vendor_id"]) if request.form.get("vendor_id") else None
        lic.key = request.form.get("key", "").strip() or None
        lic.seats = int(request.form.get("seats") or 1)
        lic.purchase_date = parse_date(request.form.get("purchase_date"))
        lic.expiry_date = parse_date(request.form.get("expiry_date"))
        lic.cost = request.form.get("cost") or None
        lic.notes = request.form.get("notes", "").strip() or None
        db.session.flush()
        log_activity("license_saved", "license", lic.id, lic.name)
        db.session.commit()
        flash(f"License {lic.name} saved.", "success")
        return redirect(url_for("ops.license_detail", license_id=lic.id))
    vendors = db.session.scalars(db.select(Vendor).order_by(Vendor.name)).all()
    return render_template("licenses/form.html", lic=lic, vendors=vendors)


@bp.route("/licenses/<int:license_id>")
@perm_required("assets.view")
def license_detail(license_id):
    lic = db.get_or_404(License, license_id)
    assets = db.session.scalars(db.select(Asset).order_by(Asset.tag)).all()
    employees = db.session.scalars(db.select(Employee).where(Employee.active)
                                   .order_by(Employee.name)).all()
    return render_template("licenses/detail.html", lic=lic, assets=assets,
                           employees=employees, today=date.today())


@bp.post("/licenses/<int:license_id>/assign")
@perm_required("licenses.manage")
def license_assign(license_id):
    lic = db.get_or_404(License, license_id)
    if lic.seats_used >= lic.seats:
        flash("No seats left — license would become non-compliant.", "error")
        return redirect(url_for("ops.license_detail", license_id=lic.id))
    asset_id = request.form.get("asset_id") or None
    employee_id = request.form.get("employee_id") or None
    if not asset_id and not employee_id:
        flash("Pick an asset or an employee.", "error")
        return redirect(url_for("ops.license_detail", license_id=lic.id))
    db.session.add(LicenseAssignment(license=lic,
                                     asset_id=int(asset_id) if asset_id else None,
                                     employee_id=int(employee_id) if employee_id else None))
    log_activity("license_assigned", "license", lic.id, lic.name)
    db.session.commit()
    flash("Seat assigned.", "success")
    return redirect(url_for("ops.license_detail", license_id=lic.id))


@bp.post("/licenses/assignments/<int:la_id>/revoke")
@perm_required("licenses.manage")
def license_revoke(la_id):
    la = db.get_or_404(LicenseAssignment, la_id)
    la.revoked_at = datetime.utcnow()
    db.session.commit()
    flash("Seat revoked.", "success")
    return redirect(url_for("ops.license_detail", license_id=la.license_id))


@bp.post("/licenses/<int:license_id>/delete")
@perm_required("licenses.manage")
def license_delete(license_id):
    lic = db.get_or_404(License, license_id)
    log_activity("license_deleted", "license", lic.id, lic.name)
    db.session.delete(lic)
    db.session.commit()
    flash("License deleted.", "success")
    return redirect(url_for("ops.licenses"))


# ------------------------------------------------------------------ inventory

@bp.route("/inventory")
@perm_required("assets.view")
def inventory():
    audits = db.session.scalars(
        db.select(InventoryAudit).order_by(InventoryAudit.started_at.desc())).all()
    missing = db.session.scalars(db.select(Asset).where(Asset.status == "Missing")
                                 .order_by(Asset.tag)).all()
    total_assets = db.session.scalar(db.select(db.func.count(Asset.id))) or 0
    return render_template("inventory/list.html", audits=audits, missing=missing,
                           total_assets=total_assets)


@bp.post("/inventory/new")
@perm_required("inventory.manage")
def inventory_new():
    audit = InventoryAudit(name=request.form.get("name", "").strip()
                           or f"Audit {date.today()}", by_user=g.user.id)
    db.session.add(audit)
    log_activity("audit_started", "audit", None, audit.name)
    db.session.commit()
    return redirect(url_for("ops.inventory_audit", audit_id=audit.id))


@bp.route("/inventory/<int:audit_id>")
@perm_required("assets.view")
def inventory_audit(audit_id):
    audit = db.get_or_404(InventoryAudit, audit_id)
    checked = {c.asset_id: c.status for c in audit.checks}
    assets = db.session.scalars(db.select(Asset).where(Asset.status != "Retired")
                                .order_by(Asset.tag)).all()
    return render_template("inventory/audit.html", audit=audit, assets=assets,
                           checked=checked)


@bp.post("/inventory/<int:audit_id>/check")
@perm_required("inventory.manage")
def inventory_check(audit_id):
    audit = db.get_or_404(InventoryAudit, audit_id)
    if audit.completed_at:
        flash("This audit is already completed.", "error")
        return redirect(url_for("ops.inventory_audit", audit_id=audit.id))
    asset_id = int(request.form["asset_id"])
    status = "Verified" if request.form["result"] == "verified" else "Missing"
    check = db.session.scalar(db.select(InventoryCheck).where(
        InventoryCheck.audit_id == audit.id, InventoryCheck.asset_id == asset_id))
    if check:
        check.status = status
        check.checked_at = datetime.utcnow()
    else:
        db.session.add(InventoryCheck(audit_id=audit.id, asset_id=asset_id, status=status))
    asset = db.session.get(Asset, asset_id)
    if status == "Missing":
        asset.status = "Missing"
    elif asset.status == "Missing":
        asset.status = "Available"
    db.session.commit()
    return redirect(url_for("ops.inventory_audit", audit_id=audit.id))


@bp.post("/inventory/<int:audit_id>/complete")
@perm_required("inventory.manage")
def inventory_complete(audit_id):
    audit = db.get_or_404(InventoryAudit, audit_id)
    audit.completed_at = datetime.utcnow()
    log_activity("audit_completed", "audit", audit.id,
                 f"{audit.verified_count} verified, {audit.missing_count} missing")
    db.session.commit()
    flash("Audit completed.", "success")
    return redirect(url_for("ops.inventory"))


@bp.route("/inventory/<int:audit_id>/export.csv")
@perm_required("assets.view")
def inventory_export(audit_id):
    audit = db.get_or_404(InventoryAudit, audit_id)
    rows = [(c.asset.tag, c.asset.name, c.status, c.checked_at) for c in audit.checks]
    return csv_response(["Tag", "Name", "Result", "Checked At"], rows,
                        f"audit-{audit.id}.csv")
