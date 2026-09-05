from datetime import date, datetime

from flask import (Blueprint, flash, g, jsonify, redirect, render_template,
                   request, url_for)
from sqlalchemy.orm import joinedload, selectinload

from ..models import (BLOCKED_CHECKOUT_STATUSES, MAINTENANCE_KINDS,
                      MAINTENANCE_STATUSES, Asset,
                      Assignment, Category, Employee, InventoryAudit,
                      InventoryCheck, License, LicenseAssignment, Maintenance,
                      Reservation, User, Vendor, db)
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
        # Same guard as the employee importer: an unreadable file is a
        # message, not a 500.
        try:
            _, rows = read_table(request.files["file"])
        except Exception:
            flash("Could not read that file. In Excel use Save As → "
                  "Excel Workbook (.xlsx) — the old .xls format is not "
                  "supported — then upload it again.", "error")
            return redirect(url_for("ops.licenses_import"))
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
    """Everything owned -- equipment and software -- not just the audit log."""
    return xlsx_response(INVENTORY_HEADERS, _inventory_rows(),
                         "inventory.xlsx", "Inventory")


@bp.route("/inventory/export.csv")
@perm_required("assets.view")
def inventory_export_csv():
    return csv_response(INVENTORY_HEADERS, _inventory_rows(), "inventory.csv")


# ---------------------------------------------------------------- checkouts

def _place_held_assets():
    """Assets held by a class or room rather than a person.

    The inventory sheet assigns shared devices to places ('Grade3.B', copy
    room …). Those can't be loans to an employee, but they belong on the
    Lending screen all the same — otherwise 180 devices look unaccounted for.
    """
    return db.session.scalars(
        db.select(Asset)
        .where(Asset.notes.contains("Assigned to: "),
               ~Asset.assignments.any(Assignment.returned_at.is_(None)))
        .order_by(Asset.tag)).all()


@bp.route("/checkouts")
@perm_required("assets.view")
def checkouts():
    show = request.args.get("show", "active")
    stmt = (db.select(Assignment)
            .options(joinedload(Assignment.asset), joinedload(Assignment.employee))
            .order_by(Assignment.assigned_at.desc()))
    if show == "active":
        stmt = stmt.where(Assignment.returned_at.is_(None))
    elif show == "overdue":
        stmt = stmt.where(Assignment.returned_at.is_(None),
                          Assignment.due_at.isnot(None),
                          Assignment.due_at < date.today())
    rows = db.session.scalars(stmt.limit(300)).all()
    reservations = db.session.scalars(
        db.select(Reservation)
        .options(joinedload(Reservation.asset), joinedload(Reservation.employee))
        .where(Reservation.status == "Active")
        .order_by(Reservation.start_date)).all()
    return render_template("checkouts.html", rows=rows, show=show,
                           place_rows=_place_held_assets() if show != "overdue" else [],
                           reservations=reservations, today=date.today(),
                           available=_lendable_assets(),
                           available_total=_lendable_count(),
                           picker_limit=PICKER_LIMIT,
                           out_assets=_assets_on_loan(),
                           employees=db.session.scalars(
                               db.select(Employee).where(Employee.active)
                               .order_by(Employee.name)).all())


#: How many assets either picker renders at once. A register of a few thousand
#: assets turned this page into a megabyte of <option> tags; the search box
#: reaches the rest.
PICKER_LIMIT = 200


def _lendable_query(q=None):
    """Assets that can actually be lent right now.

    "Available" is the status the rest of the app sets on check-in, but an
    asset can also be free simply because nobody ever took it out, so this
    asks "has no open assignment and isn't blocked" rather than trusting the
    status on its own.
    """
    open_asset_ids = db.select(Assignment.asset_id).where(
        Assignment.returned_at.is_(None))
    stmt = (db.select(Asset)
            .where(Asset.status.notin_(BLOCKED_CHECKOUT_STATUSES),
                   Asset.status != "Checked Out",
                   Asset.id.notin_(open_asset_ids))
            .order_by(Asset.tag))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(db.or_(Asset.tag.ilike(like), Asset.name.ilike(like),
                                 Asset.serial.ilike(like)))
    return stmt


def _lendable_assets(q=None):
    return db.session.scalars(_lendable_query(q).limit(PICKER_LIMIT)).all()


def _lendable_count():
    return db.session.scalar(
        db.select(db.func.count()).select_from(_lendable_query().subquery()))


def _assets_on_loan():
    """Assets with an open assignment, for the check-in list."""
    stmt = (db.select(Asset)
            .options(selectinload(Asset.assignments).joinedload(Assignment.employee))
            .join(Assignment, Assignment.asset_id == Asset.id)
            .where(Assignment.returned_at.is_(None))
            .order_by(Asset.tag)
            .limit(PICKER_LIMIT))
    return db.session.scalars(stmt).unique().all()


@bp.get("/lend/assets.json")
@perm_required("checkout.manage")
def lendable_search():
    """Feeds the lending picker's search box."""
    rows = _lendable_assets(request.args.get("q", "").strip())
    return jsonify([{"id": a.id, "label": f"{a.tag} — {a.name}"} for a in rows])


@bp.get("/lend/assets/<int:asset_id>.json")
@perm_required("checkout.manage")
def lendable_detail(asset_id):
    """The read-only detail card under the lending picker."""
    a = db.get_or_404(Asset, asset_id)
    where = " · ".join(p for p in (a.branch, a.building, a.floor, a.location_name) if p)
    return jsonify({
        "tag": a.tag, "name": a.name,
        "category": a.category.name if a.category else "",
        "model": " ".join(p for p in (a.manufacturer, a.model) if p),
        "serial": a.serial or "", "location": where,
        "department": a.department.name if a.department else "",
        "condition": a.condition or "", "status": a.status or "",
    })


def _lookup_query(q):
    """Search the *whole* register — lent-out assets included.

    The lend picker only lists what's free, so it can't answer "who has
    device X right now?". This one spans every asset so the desk can look up
    a device, see its holder, and decide whether to lend it or leave it.
    """
    like = f"%{q}%"
    return (db.select(Asset)
            .where(db.or_(Asset.tag.ilike(like), Asset.name.ilike(like),
                          Asset.serial.ilike(like)))
            .order_by(Asset.tag)
            .limit(PICKER_LIMIT))


@bp.get("/lend/lookup.json")
@perm_required("assets.view")
def asset_lookup():
    """Feeds the 'Who has this device?' search box."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    rows = db.session.scalars(_lookup_query(q)).all()
    out = []
    for a in rows:
        holder = a.assigned_label
        out.append({"id": a.id, "label": f"{a.tag} — {a.name}",
                    "hint": f"out to {holder}" if holder else "available"})
    return jsonify(out)


@bp.get("/lend/lookup/<int:asset_id>.json")
@perm_required("assets.view")
def asset_lookup_detail(asset_id):
    """Full detail for any asset, with who is holding it right now."""
    a = db.get_or_404(Asset, asset_id)
    where = " · ".join(p for p in (a.branch, a.building, a.floor, a.location_name) if p)
    asg = a.current_assignment
    holder = holder_kind = since = due = None
    overdue = False
    if asg:
        holder, holder_kind = asg.employee.name, "person"
        since = asg.assigned_at.strftime("%Y-%m-%d") if asg.assigned_at else None
        due = asg.due_at.strftime("%Y-%m-%d") if asg.due_at else None
        overdue = bool(asg.due_at and asg.due_at < date.today())
    elif a.assigned_label:
        holder, holder_kind = a.assigned_label, "place"
    return jsonify({
        "tag": a.tag, "name": a.name,
        "category": a.category.name if a.category else "",
        "model": " ".join(p for p in (a.manufacturer, a.model) if p),
        "serial": a.serial or "", "location": where,
        "department": a.department.name if a.department else "",
        "condition": a.condition or "", "status": a.status or "",
        "holder": holder, "holder_kind": holder_kind,
        "since": since, "due": due, "overdue": overdue,
        "lendable": (asg is None and a.status not in BLOCKED_CHECKOUT_STATUSES
                     and a.status != "Checked Out"),
        "detail_url": url_for("assets.detail", asset_id=a.id),
    })


@bp.post("/lend")
@perm_required("checkout.manage")
def lend():
    asset = db.get_or_404(Asset, int(request.form["asset_id"]))
    if asset.current_assignment or asset.status in BLOCKED_CHECKOUT_STATUSES:
        flash(f"{asset.tag} cannot be lent out right now.", "error")
        return redirect(url_for("ops.checkouts"))
    emp = db.get_or_404(Employee, int(request.form["employee_id"]))
    handled_by = request.form.get("handled_by", "").strip() or g.user.name
    db.session.add(Assignment(asset=asset, employee=emp, assigned_by=g.user.id,
                              due_at=parse_date(request.form.get("due_at")),
                              handled_by=handled_by,
                              notes=request.form.get("notes", "").strip() or None))
    # The asset card shows who last touched the record; lending is a change.
    asset.updated_by = handled_by
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
    """Everything the school owns: equipment and software, in one place."""
    audits = db.session.scalars(
        db.select(InventoryAudit).order_by(InventoryAudit.started_at.desc())).all()
    missing = db.session.scalars(
        db.select(Asset).options(joinedload(Asset.location))
        .where(Asset.status == "Missing").order_by(Asset.tag)).all()
    owned = _owned_summary()
    return render_template("inventory/list.html", audits=audits, missing=missing,
                           **owned)


def _owned_summary():
    """Counts and breakdowns for the inventory page.

    Grouped queries rather than loading the register: at three thousand assets
    the page has to stay as quick as any other.
    """
    total_assets = db.session.scalar(db.select(db.func.count(Asset.id))) or 0
    by_category = db.session.execute(
        db.select(Category.name, db.func.count(Asset.id),
                  db.func.sum(Asset.purchase_cost))
        .select_from(Asset).outerjoin(Category, Asset.category_id == Category.id)
        .group_by(Category.name).order_by(db.func.count(Asset.id).desc())).all()
    by_status = db.session.execute(
        db.select(Asset.status, db.func.count(Asset.id))
        .group_by(Asset.status).order_by(db.func.count(Asset.id).desc())).all()

    licenses = db.session.scalars(
        db.select(License).options(joinedload(License.vendor))
        .order_by(License.name)).all()
    seats = sum(l.seats or 0 for l in licenses)
    seats_used = sum(l.seats_used or 0 for l in licenses)

    asset_value = db.session.scalar(
        db.select(db.func.sum(Asset.purchase_cost))) or 0
    license_value = sum(float(l.cost or 0) for l in licenses)

    return dict(
        total_assets=total_assets, by_category=by_category, by_status=by_status,
        licenses=licenses, license_count=len(licenses), seats=seats,
        seats_used=seats_used, over_seats=[l for l in licenses if not l.compliant],
        asset_value=float(asset_value), license_value=license_value,
        total_value=float(asset_value) + license_value)


def _inventory_rows():
    """One flat "what we own" table covering equipment and software."""
    rows = []
    for a in db.session.scalars(
            db.select(Asset)
            .options(joinedload(Asset.category), joinedload(Asset.department))
            .order_by(Asset.tag)):
        where = " · ".join(p for p in (a.branch, a.building, a.floor,
                                       a.location_name) if p)
        rows.append(["Asset", a.tag, a.name,
                     a.category.name if a.category else "", a.status or "",
                     a.serial or "", where,
                     a.department.name if a.department else "",
                     "", "", a.purchase_cost or ""])
    for l in db.session.scalars(
            db.select(License).options(joinedload(License.vendor))
            .order_by(License.name)):
        rows.append(["Software licence", l.key or "", l.name, "Software",
                     "Compliant" if l.compliant else "OVER SEATS", "",
                     l.vendor.name if l.vendor else "", "",
                     l.seats or 0, l.seats_used or 0, l.cost or ""])
    return rows


INVENTORY_HEADERS = ["Kind", "ID / Key", "Name", "Category", "Status", "Serial",
                     "Location / Vendor", "Department", "Seats", "Seats used",
                     "Cost"]


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


@bp.post("/checkouts/release/<int:asset_id>")
@perm_required("checkout.manage")
def checkout_release_place(asset_id):
    """Take back a device held by a class/room: drop the note that binds it."""
    a = db.get_or_404(Asset, asset_id)
    label = a.assigned_label or "its room"
    lines = [line for line in (a.notes or "").splitlines()
             if not line.startswith("Assigned to: ")]
    a.notes = "\n".join(lines).strip() or None
    log_activity("checked_in", "asset", a.id, f"{a.tag} ← {label}")
    db.session.commit()
    flash(f"{a.tag} released from {label}.", "success")
    return redirect(url_for("ops.checkouts"))


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


@bp.post("/inventory/bulk-delete")
@perm_required("inventory.manage")
def inventory_bulk_delete():
    ids = request.form.getlist("ids", type=int)
    audits = db.session.scalars(
        db.select(InventoryAudit).where(InventoryAudit.id.in_(ids))).all()
    for audit in audits:
        for check in list(audit.checks):
            db.session.delete(check)
        db.session.delete(audit)
    db.session.commit()
    flash(f"{len(audits)} audit(s) deleted." if audits else "Nothing selected.",
          "success" if audits else "error")
    return redirect(url_for("ops.inventory"))
