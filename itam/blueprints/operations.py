from datetime import date, datetime

from flask import (Blueprint, flash, g, redirect, render_template, request,
                   url_for)

from ..models import (MAINTENANCE_KINDS, MAINTENANCE_STATUSES, Asset,
                      Assignment, Employee, InventoryAudit, InventoryCheck,
                      License, LicenseAssignment, Maintenance, Reservation,
                      User, Vendor, db)
from ..security import perm_required
from ..utils import (csv_response, log_activity, parse_date, read_table,
                     xlsx_response)

bp = Blueprint("ops", __name__)


# ------------------------------------------------------- Excel/CSV exports

def _license_rows():
    return [(l.name, l.vendor.name if l.vendor else "", l.key or "", l.seats,
             l.seats_used, "Yes" if l.compliant else "No",
             l.purchase_date or "", l.expiry_date or "", l.cost or "")
            for l in db.session.scalars(db.select(License).order_by(License.name))]


LIC_HEADERS = ["Name", "Vendor", "Key", "Seats", "Used", "Compliant",
               "Purchase Date", "Expiry", "Cost"]


@bp.route("/licenses/export.xlsx")
@perm_required("assets.view")
def licenses_export_xlsx():
    return xlsx_response(LIC_HEADERS, _license_rows(), "licenses.xlsx", "Licenses")


@bp.route("/licenses/export.csv")
@perm_required("assets.view")
def licenses_export_csv():
    return csv_response(LIC_HEADERS, _license_rows(), "licenses.csv")


@bp.route("/licenses/import", methods=["GET", "POST"])
@perm_required("licenses.manage")
def licenses_import():
    if request.method == "POST" and request.files.get("file"):
        _, rows = read_table(request.files["file"])
        vendors = {v.name.lower(): v for v in db.session.scalars(db.select(Vendor))}
        created = updated = skipped = 0
        for r in rows:
            name = (r.get("name") or "").strip()
            if not name:
                skipped += 1
                continue
            lic = db.session.scalar(db.select(License).where(License.name == name))
            if not lic:
                lic = License(name=name)
                db.session.add(lic)
                created += 1
            else:
                updated += 1
            lic.key = r.get("key") or lic.key
            try:
                lic.seats = int(float(r.get("seats"))) if r.get("seats") else lic.seats
            except ValueError:
                pass
            lic.expiry_date = parse_date(r.get("expiry")) or lic.expiry_date
            lic.cost = r.get("cost") or lic.cost
            vend = vendors.get((r.get("vendor") or "").lower())
            if vend:
                lic.vendor_id = vend.id
        log_activity("licenses_imported", "license", None, f"{created} new, {updated} updated")
        db.session.commit()
        flash(f"Imported {created} new and {updated} updated licenses "
              f"({skipped} skipped).", "success")
        return redirect(url_for("ops.licenses"))
    return render_template("org/import.html", title="Import licenses",
                           cols=["name", "vendor", "key", "seats", "expiry", "cost"],
                           post_url=url_for("ops.licenses_import"),
                           back_url=url_for("ops.licenses"))


@bp.route("/maintenance/export.xlsx")
@perm_required("assets.view")
def maintenance_export_xlsx():
    rows = [(m.asset.tag, m.asset.name, m.kind, m.title, m.status,
             m.scheduled_for or "", m.completed_at.date() if m.completed_at else "",
             m.technician.name if m.technician else "", m.cost or "", m.parts or "")
            for m in db.session.scalars(db.select(Maintenance).order_by(Maintenance.created_at.desc()))]
    return xlsx_response(
        ["Asset", "Asset Name", "Kind", "Title", "Status", "Scheduled",
         "Completed", "Technician", "Cost", "Parts"], rows,
        "maintenance.xlsx", "Maintenance")


@bp.route("/inventory/export.xlsx")
@perm_required("assets.view")
def inventory_export_xlsx():
    audit_rows = [(au.name, au.started_at.date(),
                   au.completed_at.date() if au.completed_at else "in progress",
                   au.verified_count, au.missing_count)
                  for au in db.session.scalars(db.select(InventoryAudit)
                                               .order_by(InventoryAudit.started_at.desc()))]
    return xlsx_response(
        ["Audit", "Started", "Completed", "Verified", "Missing"], audit_rows,
        "inventory.xlsx", "Inventory")


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
                           kinds=MAINTENANCE_KINDS, preselect=preselect, m=None)


@bp.route("/maintenance/<int:mid>/edit", methods=["GET", "POST"])
@perm_required("maintenance.manage")
def maintenance_edit(mid):
    m = db.get_or_404(Maintenance, mid)
    if request.method == "POST":
        m.asset_id = int(request.form["asset_id"])
        m.kind = request.form.get("kind", "Corrective")
        m.title = request.form["title"].strip()
        m.description = request.form.get("description", "").strip() or None
        m.solution = request.form.get("solution", "").strip() or None
        m.scheduled_for = parse_date(request.form.get("scheduled_for"))
        m.technician_id = (int(request.form["technician_id"])
                           if request.form.get("technician_id") else None)
        m.cost = request.form.get("cost") or None
        m.parts = request.form.get("parts", "").strip() or None
        log_activity("maintenance_updated", "asset", m.asset_id, m.title)
        db.session.commit()
        flash("Maintenance task updated.", "success")
        return redirect(url_for("ops.maintenance_list"))
    assets = db.session.scalars(db.select(Asset).order_by(Asset.tag)).all()
    techs = db.session.scalars(db.select(User).where(User.active).order_by(User.name)).all()
    return render_template("maintenance/form.html", assets=assets, techs=techs,
                           kinds=MAINTENANCE_KINDS, preselect=m.asset_id, m=m)


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


# ------------------------------------------------------------- bulk actions

@bp.post("/licenses/bulk-delete")
@perm_required("licenses.manage")
def licenses_bulk_delete():
    ids = request.form.getlist("ids", type=int)
    count = 0
    for lic in db.session.scalars(db.select(License).where(License.id.in_(ids))):
        log_activity("license_deleted", "license", lic.id, lic.name)
        db.session.delete(lic)
        count += 1
    db.session.commit()
    flash(f"{count} license{'' if count == 1 else 's'} deleted." if count
          else "Nothing selected.", "success" if count else "error")
    return redirect(url_for("ops.licenses"))


@bp.post("/maintenance/bulk-delete")
@perm_required("maintenance.manage")
def maintenance_bulk_delete():
    ids = request.form.getlist("ids", type=int)
    count = 0
    for task in db.session.scalars(db.select(Maintenance).where(Maintenance.id.in_(ids))):
        log_activity("maintenance_deleted", "maintenance", task.id, task.title)
        db.session.delete(task)
        count += 1
    db.session.commit()
    flash(f"{count} task{'' if count == 1 else 's'} deleted." if count
          else "Nothing selected.", "success" if count else "error")
    return redirect(url_for("ops.maintenance_list"))


@bp.post("/checkouts/bulk-checkin")
@perm_required("checkout.manage")
def checkouts_bulk_checkin():
    """Return several loans at once, mirroring the single check-in."""
    ids = request.form.getlist("ids", type=int)
    count = 0
    for asg in db.session.scalars(db.select(Assignment).where(
            Assignment.id.in_(ids), Assignment.returned_at.is_(None))):
        asg.returned_at = datetime.utcnow()
        asset = asg.asset
        if asset is not None and asset.status not in ("Damaged", "Lost", "Missing"):
            asset.status = "Available"
        log_activity("checked_in", "asset", asg.asset_id,
                     f"{asset.tag if asset else '?'} ← {asg.employee.name}")
        count += 1
    db.session.commit()
    flash(f"{count} asset{'' if count == 1 else 's'} checked in." if count
          else "Nothing selected.", "success" if count else "error")
    return redirect(url_for("ops.checkouts"))
