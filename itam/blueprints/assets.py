import csv
import io
import json
import os
import uuid
from datetime import date, datetime, timedelta

from flask import (Blueprint, Response, current_app, flash, g, jsonify,
                   redirect, render_template, request, send_from_directory,
                   url_for)
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload
from werkzeug.utils import secure_filename

from ..models import (ASSET_CONDITIONS, ASSET_STATUSES, BRANCHES, BUILDINGS,
                      BLOCKED_CHECKOUT_STATUSES, FLOORS, OPERATING_SYSTEMS,
                      PLACES, Asset,
                      Assignment, Category, Department, Employee, Location,
                      Reservation, Transfer, Vendor, db)
from ..security import has_perm, login_required, perm_required
from ..utils import (barcode_svg, csv_response, custom_field_names,
                     get_setting, label_layout, log_activity, parse_date,
                     qr_svg)

bp = Blueprint("assets", __name__, url_prefix="/assets")

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
ALLOWED_EXTS = IMAGE_EXTS | {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".txt", ".csv"}


def _lookups():
    return dict(
        categories=db.session.scalars(db.select(Category).order_by(Category.name)).all(),
        departments=db.session.scalars(db.select(Department).order_by(Department.name)).all(),
        locations=db.session.scalars(db.select(Location).order_by(Location.name)).all(),
        vendors=db.session.scalars(db.select(Vendor).order_by(Vendor.name)).all(),
        employees=db.session.scalars(db.select(Employee).where(Employee.active)
                                     .order_by(Employee.name)).all(),
        statuses=ASSET_STATUSES, conditions=ASSET_CONDITIONS,
        branches=BRANCHES, buildings=BUILDINGS, floors=FLOORS, places=PLACES,
        operating_systems=OPERATING_SYSTEMS, today_iso=date.today().isoformat(),
        custom_names=custom_field_names(),
    )


def next_tag(category):
    """Sequential per-category tag, e.g. PC-000001 (spec section 10)."""
    prefix = category.tag_prefix if category else "AST"
    top = 0
    for (tag,) in db.session.execute(
            db.select(Asset.tag).where(Asset.tag.like(f"{prefix}-%"))).all():
        suffix = tag.rsplit("-", 1)[-1]
        if suffix.isdigit():
            top = max(top, int(suffix))
    return f"{prefix}-{top + 1:06d}"


def _next_tag_map():
    """{category_id: next auto-generated Asset ID} for live form preview."""
    return {c.id: next_tag(c) for c in
            db.session.scalars(db.select(Category)).all()}


def _from_form(a, form):
    a.name = form["name"].strip()
    a.category_id = int(form["category_id"]) if form.get("category_id") else None
    tag = form.get("tag", "").strip()
    a.tag = tag or next_tag(db.session.get(Category, a.category_id)
                            if a.category_id else None)
    a.asset_type = form.get("asset_type", "").strip() or None
    a.serial = form.get("serial", "").strip() or None
    a.manufacturer = form.get("manufacturer", "").strip() or None
    a.model = form.get("model", "").strip() or None
    if form.get("status") in ASSET_STATUSES:
        a.status = form["status"]
    if form.get("condition") in ASSET_CONDITIONS:
        a.condition = form["condition"]
    # Only write fields the form actually submitted. "OS version" was removed
    # from the form, and blanking it here would erase imported values.
    for field in ("os_name", "os_version", "cpu", "ram", "storage", "gpu",
                  "hostname", "mac_address", "ip_address", "invoice_number"):
        if field in form:
            setattr(a, field, form.get(field, "").strip() or None)
    a.branch = form.get("branch") if form.get("branch") in BRANCHES else None
    a.building = form.get("building") if form.get("building") in BUILDINGS else None
    a.floor = form.get("floor") if form.get("floor") in FLOORS else None
    a.location_name = form.get("location_name", "").strip() or None
    # "Updated by" is shown on the asset form but no longer editable there, so
    # the field isn't submitted. Stamp whoever saved the record instead; the
    # importer and the API still pass their own value and keep it.
    if "updated_by" in form:
        a.updated_by = form.get("updated_by", "").strip() or None
    elif getattr(g, "user", None) is not None:
        a.updated_by = g.user.name
    a.vendor_id = int(form["vendor_id"]) if form.get("vendor_id") else None
    a.purchase_date = parse_date(form.get("purchase_date"))
    a.purchase_cost = form.get("purchase_cost") or None
    a.depreciation_years = int(form.get("depreciation_years") or 5)
    a.warranty_expiry = parse_date(form.get("warranty_expiry"))
    a.notes = form.get("notes", "").strip() or None
    custom = {name: form.get(f"custom_{i}", "").strip()
              for i, name in enumerate(custom_field_names())}
    a.custom_fields = json.dumps({k: v for k, v in custom.items() if v})
    # The asset form no longer offers "Part of (parent asset)". Only touch the
    # link when a form actually submits the field, otherwise saving an edit
    # would silently unlink assets that already have a parent.
    if "parent_id" in form:
        parent = form.get("parent_id")
        a.parent_id = int(parent) if parent and (not a.id or int(parent) != a.id) else None


def _apply_assignment(a, form):
    """Handle the 'Assign to' field on the asset form (spec section 15)."""
    emp_id = form.get("assign_employee_id")
    cur = a.current_assignment
    if not emp_id:
        return
    emp_id = int(emp_id)
    if cur and cur.employee_id == emp_id:
        return  # already assigned to this person
    if a.status in BLOCKED_CHECKOUT_STATUSES:
        return
    if cur:  # reassignment: return the current holder first
        cur.returned_at = datetime.utcnow()
    emp = db.session.get(Employee, emp_id)
    if not emp:
        return
    db.session.add(Assignment(asset=a, employee=emp, assigned_by=g.user.id,
                              handled_by=g.user.name))
    a.status = "Checked Out"
    log_activity("checked_out", "asset", a.id, f"{a.tag} → {emp.name}")


#: Rows per page on the asset list. Rendering every row of a 3,000-asset
#: register produced a 1 MB page and one SQL query per asset.
PAGE_SIZE = 50


def _assets_query(args):
    # The list shows category, department, location and the current holder for
    # every row. Without this each row fetched its own, which is where the
    # 3,000-query page load came from.
    stmt = db.select(Asset).options(
        joinedload(Asset.category),
        joinedload(Asset.department),
        joinedload(Asset.location),
        selectinload(Asset.assignments).joinedload(Assignment.employee),
    ).order_by(Asset.tag)
    q = args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Asset.tag.ilike(like), Asset.name.ilike(like),
                              Asset.serial.ilike(like), Asset.manufacturer.ilike(like),
                              Asset.model.ilike(like), Asset.asset_type.ilike(like),
                              Asset.hostname.ilike(like), Asset.mac_address.ilike(like),
                              Asset.ip_address.ilike(like), Asset.os_name.ilike(like)))
    if args.get("status"):
        stmt = stmt.where(Asset.status == args["status"])
    # A hand-edited URL or a stale bookmark used to reach int() directly and
    # crash the page with a 500. A filter that isn't a number is no filter.
    for param, column in (("category", Asset.category_id),
                          ("department", Asset.department_id),
                          ("location", Asset.location_id)):
        raw = args.get(param)
        if raw:
            try:
                stmt = stmt.where(column == int(raw))
            except (TypeError, ValueError):
                pass
    if args.get("condition"):
        stmt = stmt.where(Asset.condition == args["condition"])
    if args.get("branch"):
        stmt = stmt.where(Asset.branch == args["branch"])
    if args.get("building"):
        stmt = stmt.where(Asset.building == args["building"])
    if args.get("floor"):
        stmt = stmt.where(Asset.floor == args["floor"])
    return stmt


def _filtered_assets(args):
    """Every matching asset — used by exports and the label sheet."""
    return db.session.scalars(_assets_query(args)).unique().all()


def _assets_page(args):
    """One page of matching assets, plus the paging figures for the template."""
    try:
        page = max(1, int(args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    stmt = _assets_query(args)
    total = db.session.scalar(
        db.select(db.func.count()).select_from(stmt.order_by(None).subquery()))
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, pages)
    rows = db.session.scalars(
        stmt.limit(PAGE_SIZE).offset((page - 1) * PAGE_SIZE)).unique().all()
    return rows, {"page": page, "pages": pages, "total": total,
                  "size": PAGE_SIZE,
                  "first": 0 if not total else (page - 1) * PAGE_SIZE + 1,
                  "last": min(page * PAGE_SIZE, total)}


def _distinct(col):
    """Sorted list of the non-empty values actually present in the data."""
    vals = db.session.scalars(
        db.select(col).where(col.isnot(None), col != "").distinct()).all()
    return sorted(vals)


def _locations_in_use(all_locations, keep_id=None):
    """Locations worth offering as a filter.

    The standard tree is ~600 rows, which made a 39 KB <select> on the busiest
    page in the app. Filtering by a location that holds nothing returns
    nothing, so only list the ones actually in use — plus whichever is
    currently selected, so an active filter never vanishes from its own box.
    """
    used = set(db.session.scalars(
        db.select(Asset.location_id).where(Asset.location_id.isnot(None)).distinct()))
    if keep_id:
        used.add(keep_id)
    return [l for l in all_locations if l.id in used]


@bp.route("/")
@perm_required("assets.view")
def list_():
    from ..models import SavedSearch
    searches = db.session.scalars(db.select(SavedSearch)
                                  .where(SavedSearch.user_id == g.user.id)
                                  .order_by(SavedSearch.name)).all()
    rows, paging = _assets_page(request.args)
    looks = _lookups()
    try:
        active_loc = int(request.args.get("location") or 0)
    except (TypeError, ValueError):
        active_loc = 0
    return render_template("assets/list.html", assets=rows, paging=paging,
                           args=request.args, searches=searches,
                           branch_opts=_distinct(Asset.branch),
                           building_opts=_distinct(Asset.building),
                           floor_opts=_distinct(Asset.floor),
                           filter_locations=_locations_in_use(
                               looks["locations"], active_loc),
                           **looks)


@bp.get("/locations.json")
@perm_required("assets.view")
def locations_json():
    """Feeds the bulk "transfer to location" picker.

    Unlike the filter, a transfer target may well be an empty location, so
    this searches the whole tree rather than only what's in use.
    """
    q = request.args.get("q", "").strip().lower()
    rows = db.session.scalars(db.select(Location).order_by(Location.name)).all()
    hits = [l for l in rows if not q or q in l.path.lower()]
    hits.sort(key=lambda l: l.path)
    return jsonify([{"id": l.id, "path": l.path} for l in hits[:200]])


@bp.post("/searches")
@perm_required("assets.view")
def search_save():
    from ..models import SavedSearch
    name = request.form.get("name", "").strip()
    query = request.form.get("query", "").strip()
    if not name or not query:
        flash("Apply some filters first, then give the search a name.", "error")
    else:
        db.session.add(SavedSearch(user_id=g.user.id, name=name[:80], query=query[:500]))
        db.session.commit()
        flash(f'Search "{name}" saved.', "success")
    return redirect(url_for("assets.list_") + ("?" + query if query else ""))


@bp.post("/searches/<int:search_id>/delete")
@perm_required("assets.view")
def search_delete(search_id):
    from ..models import SavedSearch
    s = db.get_or_404(SavedSearch, search_id)
    if s.user_id == g.user.id:
        db.session.delete(s)
        db.session.commit()
        flash("Saved search removed.", "success")
    return redirect(url_for("assets.list_"))


@bp.route("/export.csv")
@perm_required("assets.view")
def export_csv():
    rows = [(a.tag, a.name, a.category.name if a.category else "", a.asset_type or "",
             a.serial or "", a.manufacturer or "", a.model or "", a.status, a.condition,
             a.os_name or "", a.cpu or "", a.ram or "", a.storage or "",
             a.hostname or "", a.mac_address or "", a.ip_address or "",
             a.location.path if a.location else "", a.department.name if a.department else "",
             a.vendor.name if a.vendor else "", a.purchase_date or "", a.purchase_cost or "",
             a.invoice_number or "", a.warranty_expiry or "", a.current_value or "",
             a.notes or "")
            for a in _filtered_assets(request.args)]
    return csv_response(
        ["Tag", "Name", "Category", "Type", "Serial", "Manufacturer", "Model", "Status",
         "Condition", "OS", "CPU", "RAM", "Storage", "Hostname", "MAC", "IP",
         "Location", "Department", "Vendor", "Purchase Date", "Purchase Cost",
         "Invoice", "Warranty Expiry", "Current Value", "Notes"], rows, "assets.csv")


@bp.route("/new", methods=["GET", "POST"])
@perm_required("assets.manage")
def new():
    source = None
    if request.args.get("clone"):
        try:
            source = db.session.get(Asset, int(request.args["clone"]))
        except (TypeError, ValueError):
            source = None       # a junk ?clone= is not worth a 500
    if request.method == "POST":
        tag = request.form.get("tag", "").strip()
        if tag and db.session.scalar(db.select(Asset).where(Asset.tag == tag)):
            flash(f'Asset tag "{tag}" already exists.', "error")
        else:
            a = Asset()
            _from_form(a, request.form)
            db.session.add(a)
            db.session.flush()
            log_activity("created", "asset", a.id, f"{a.tag} — {a.name}")
            _apply_assignment(a, request.form)
            db.session.commit()
            flash(f"Asset {a.tag} created.", "success")
            return redirect(url_for("assets.detail", asset_id=a.id))
    return render_template("assets/form.html", asset=None, source=source,
                           next_tags=_next_tag_map(),
                           qr_prefix=get_setting("qr_prefix"), **_lookups())


@bp.route("/<int:asset_id>")
@perm_required("assets.view")
def detail(asset_id):
    from ..models import ActivityLog, InventoryCheck
    a = db.get_or_404(Asset, asset_id)
    timeline = db.session.scalars(
        db.select(ActivityLog)
        .where(ActivityLog.entity_type == "asset", ActivityLog.entity_id == a.id)
        .order_by(ActivityLog.created_at.desc()).limit(12)).all()
    last_check = db.session.scalars(
        db.select(InventoryCheck).where(InventoryCheck.asset_id == a.id)
        .order_by(InventoryCheck.checked_at.desc()).limit(1)).first()
    return render_template("assets/detail.html", asset=a, today=date.today(),
                           timeline=timeline, last_check=last_check,
                           default_due=(date.today() + timedelta(
                               days=int(get_setting("checkout_days") or 30))),
                           image_exts=IMAGE_EXTS, **_lookups())


@bp.route("/<int:asset_id>/edit", methods=["GET", "POST"])
@perm_required("assets.manage")
def edit(asset_id):
    a = db.get_or_404(Asset, asset_id)
    if request.method == "POST":
        tag = request.form["tag"].strip()
        other = db.session.scalar(db.select(Asset).where(Asset.tag == tag))
        if other and other.id != a.id:
            flash(f'Asset tag "{tag}" already exists.', "error")
        else:
            _from_form(a, request.form)
            log_activity("updated", "asset", a.id, a.tag)
            _apply_assignment(a, request.form)
            db.session.commit()
            flash(f"Asset {a.tag} updated.", "success")
            return redirect(url_for("assets.detail", asset_id=a.id))
    return render_template("assets/form.html", asset=a, source=None,
                           next_tags=_next_tag_map(),
                           qr_prefix=get_setting("qr_prefix"), **_lookups())


@bp.post("/<int:asset_id>/delete")
@perm_required("assets.manage")
def delete(asset_id):
    a = db.get_or_404(Asset, asset_id)
    log_activity("deleted", "asset", a.id, a.tag)
    db.session.delete(a)
    db.session.commit()
    flash(f"Asset {a.tag} deleted.", "success")
    return redirect(url_for("assets.list_"))


# ----------------------------------------------------------------- categories

@bp.route("/categories", methods=["GET", "POST"])
@perm_required("assets.view")
def categories():
    if request.method == "POST":
        if not has_perm("assets.manage"):
            flash("You do not have permission to do that.", "error")
            return redirect(url_for("assets.categories"))
        name = request.form["name"].strip()
        prefix = request.form.get("prefix", "").strip().upper() or None
        if name and not db.session.scalar(db.select(Category).where(Category.name == name)):
            db.session.add(Category(name=name, prefix=prefix))
            log_activity("category_created", "category", None, name)
            db.session.commit()
            flash(f'Category "{name}" created.', "success")
        else:
            flash("Category name is empty or already exists.", "error")
        return redirect(url_for("assets.categories"))
    rows = db.session.scalars(db.select(Category).order_by(Category.name)).all()
    return render_template("assets/categories.html", rows=rows)


@bp.post("/categories/<int:cat_id>/delete")
@perm_required("assets.manage")
def category_delete(cat_id):
    cat = db.get_or_404(Category, cat_id)
    if cat.assets:
        flash("Category is in use by assets.", "error")
    else:
        db.session.delete(cat)
        db.session.commit()
        flash("Category deleted.", "success")
    return redirect(url_for("assets.categories"))


# ------------------------------------------------------------ lifecycle ops

@bp.post("/<int:asset_id>/checkout")
@perm_required("checkout.manage")
def checkout(asset_id):
    a = db.get_or_404(Asset, asset_id)
    if a.current_assignment or a.status in BLOCKED_CHECKOUT_STATUSES:
        flash("This asset cannot be checked out.", "error")
        return redirect(url_for("assets.detail", asset_id=a.id))
    emp = db.get_or_404(Employee, int(request.form["employee_id"]))
    db.session.add(Assignment(asset=a, employee=emp, assigned_by=g.user.id,
                              due_at=parse_date(request.form.get("due_at")),
                              handled_by=g.user.name,
                              notes=request.form.get("notes", "").strip() or None))
    a.status = "Checked Out"
    a.updated_by = g.user.name
    log_activity("checked_out", "asset", a.id, f"{a.tag} → {emp.name}")
    db.session.commit()
    flash(f"Checked out to {emp.name}.", "success")
    return redirect(url_for("assets.detail", asset_id=a.id))


@bp.post("/<int:asset_id>/checkin")
@perm_required("checkout.manage")
def checkin(asset_id):
    a = db.get_or_404(Asset, asset_id)
    asg = a.current_assignment
    if not asg:
        flash("Asset is not checked out.", "error")
        return redirect(url_for("assets.detail", asset_id=a.id))
    asg.returned_at = datetime.utcnow()
    # return inspection (spec section 16)
    condition = request.form.get("return_condition", "")
    if condition in ASSET_CONDITIONS and condition != a.condition:
        log_activity("condition_changed", "asset", a.id,
                     f"{a.tag}: {a.condition} → {condition} on return")
        a.condition = condition
        asg.return_condition = condition
    asg.return_notes = request.form.get("return_notes", "").strip() or None
    a.status = "Damaged" if condition == "Damaged" else "Available"
    log_activity("checked_in", "asset", a.id, f"{a.tag} ← {asg.employee.name}")
    db.session.commit()
    flash(f"Checked in from {asg.employee.name}.", "success")
    return redirect(url_for("assets.detail", asset_id=a.id))


@bp.post("/<int:asset_id>/transfer")
@perm_required("checkout.manage")
def transfer(asset_id):
    a = db.get_or_404(Asset, asset_id)
    to_id = int(request.form["location_id"])
    db.session.add(Transfer(asset=a, from_location_id=a.location_id,
                            to_location_id=to_id, by_user=g.user.id,
                            notes=request.form.get("notes", "").strip() or None))
    a.location_id = to_id
    log_activity("transferred", "asset", a.id, a.tag)
    db.session.commit()
    flash("Asset transferred.", "success")
    return redirect(url_for("assets.detail", asset_id=a.id))


@bp.post("/<int:asset_id>/reserve")
@perm_required("checkout.manage")
def reserve(asset_id):
    a = db.get_or_404(Asset, asset_id)
    start = parse_date(request.form["start_date"])
    end = parse_date(request.form["end_date"])
    if not start or not end or end < start:
        flash("Enter a valid reservation period.", "error")
        return redirect(url_for("assets.detail", asset_id=a.id))
    db.session.add(Reservation(asset=a, employee_id=int(request.form["employee_id"]),
                               start_date=start, end_date=end,
                               notes=request.form.get("notes", "").strip() or None))
    log_activity("reserved", "asset", a.id, a.tag)
    db.session.commit()
    flash("Reservation created.", "success")
    return redirect(url_for("assets.detail", asset_id=a.id))


# ------------------------------------------------------------------ files

@bp.post("/<int:asset_id>/files")
@perm_required("assets.manage")
def upload_file(asset_id):
    a = db.get_or_404(Asset, asset_id)
    f = request.files.get("file")
    if not f or not f.filename:
        flash("Choose a file to upload.", "error")
        return redirect(url_for("assets.detail", asset_id=a.id))
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_EXTS:
        flash(f"File type {ext} is not allowed.", "error")
        return redirect(url_for("assets.detail", asset_id=a.id))
    stored = f"{uuid.uuid4().hex}{ext}"
    f.save(os.path.join(current_app.config["UPLOAD_FOLDER"], stored))
    from ..models import AssetFile
    db.session.add(AssetFile(asset=a, stored_name=stored,
                             orig_name=secure_filename(f.filename) or f"file{ext}",
                             kind=request.form.get("kind", "document"),
                             uploaded_by=g.user.id))
    log_activity("file_uploaded", "asset", a.id, f.filename)
    db.session.commit()
    flash("File uploaded.", "success")
    return redirect(url_for("assets.detail", asset_id=a.id))


@bp.route("/files/<int:file_id>")
@perm_required("assets.view")
def get_file(file_id):
    from ..models import AssetFile
    af = db.get_or_404(AssetFile, file_id)
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], af.stored_name,
                               download_name=af.orig_name,
                               as_attachment=request.args.get("dl") == "1")


@bp.post("/files/<int:file_id>/delete")
@perm_required("assets.manage")
def delete_file(file_id):
    from ..models import AssetFile
    af = db.get_or_404(AssetFile, file_id)
    asset_id = af.asset_id
    try:
        os.remove(os.path.join(current_app.config["UPLOAD_FOLDER"], af.stored_name))
    except OSError:
        pass
    db.session.delete(af)
    db.session.commit()
    flash("File deleted.", "success")
    return redirect(url_for("assets.detail", asset_id=asset_id))


# ------------------------------------------------------------ QR / barcode

@bp.route("/qr-preview.svg")
@perm_required("assets.view")
def qr_preview():
    data = request.args.get("data", "").strip() or "PREVIEW"
    return Response(qr_svg(get_setting("qr_prefix") + data), mimetype="image/svg+xml")


@bp.route("/<int:asset_id>/qr.svg")
@perm_required("assets.view")
def qr(asset_id):
    a = db.get_or_404(Asset, asset_id)
    return Response(qr_svg(get_setting("qr_prefix") + a.tag), mimetype="image/svg+xml")


@bp.route("/<int:asset_id>/barcode.svg")
@perm_required("assets.view")
def barcode(asset_id):
    a = db.get_or_404(Asset, asset_id)
    return Response(barcode_svg(a.tag), mimetype="image/svg+xml")


@bp.route("/<int:asset_id>/label")
@perm_required("assets.view")
def label(asset_id):
    a = db.get_or_404(Asset, asset_id)
    return render_template("assets/label.html", asset=a,
                           app_name=get_setting("label_org"),
                           L=label_layout(),
                           auto=request.args.get("auto") == "1")


@bp.route("/labels")
@perm_required("assets.view")
def labels():
    ids = request.args.getlist("id", type=int)
    stmt = db.select(Asset).order_by(Asset.tag)
    if ids:
        stmt = stmt.where(Asset.id.in_(ids))
    return render_template("assets/labels.html",
                           assets=db.session.scalars(stmt).all(),
                           app_name=get_setting("label_org"),
                           L=label_layout())


# ------------------------------------------------------------------ bulk

@bp.post("/bulk")
@perm_required("assets.manage")
def bulk():
    ids = request.form.getlist("id", type=int)
    action = request.form.get("action")
    if not ids:
        flash("Select at least one asset.", "error")
        return redirect(url_for("assets.list_"))
    if action == "labels":
        return redirect(url_for("assets.labels", id=ids))
    assets = db.session.scalars(db.select(Asset).where(Asset.id.in_(ids))).all()
    if action == "delete":
        for a in assets:
            log_activity("deleted", "asset", a.id, a.tag)
            db.session.delete(a)
        flash(f"{len(assets)} assets deleted.", "success")
    elif action and action.startswith("status:"):
        status = action.split(":", 1)[1]
        if status in ASSET_STATUSES:
            for a in assets:
                a.status = status
                log_activity("updated", "asset", a.id, f"{a.tag} status → {status}")
            flash(f"{len(assets)} assets set to {status}.", "success")
    elif action == "assign" and request.form.get("employee_id"):
        emp = db.get_or_404(Employee, int(request.form["employee_id"]))
        done = skipped = 0
        for a in assets:
            if a.current_assignment or a.status in BLOCKED_CHECKOUT_STATUSES:
                skipped += 1
                continue
            db.session.add(Assignment(asset=a, employee=emp, assigned_by=g.user.id,
                                      handled_by=g.user.name))
            a.status = "Checked Out"
            a.updated_by = g.user.name
            log_activity("checked_out", "asset", a.id, f"{a.tag} → {emp.name} (bulk)")
            done += 1
        flash(f"Assigned {done} assets to {emp.name}"
              + (f" ({skipped} skipped)." if skipped else "."), "success")
    elif action == "transfer" and request.form.get("location_id"):
        loc_id = int(request.form["location_id"])
        for a in assets:
            db.session.add(Transfer(asset=a, from_location_id=a.location_id,
                                    to_location_id=loc_id, by_user=g.user.id,
                                    notes="Bulk transfer"))
            a.location_id = loc_id
            log_activity("transferred", "asset", a.id, f"{a.tag} (bulk)")
        flash(f"{len(assets)} assets transferred.", "success")
    db.session.commit()
    return redirect(url_for("assets.list_"))


# ------------------------------------------------------- import (Excel/CSV)

IMPORT_COLS = ["tag", "name", "category / asset", "type", "serial / serial no.",
               "manufacturer", "model", "status / asset status", "condition",
               "branch", "building", "floor", "location", "room", "assigned to",
               "department / dept", "ip address", "os", "cpu", "ram", "storage",
               "hostname", "mac address", "purchase date", "warranty expiry",
               "purchase cost", "updated by", "notes"]

# Map many possible spreadsheet header names -> our canonical field.
# Keys are "normalized" (lowercased, non-alphanumerics collapsed to spaces).
HEADER_ALIASES = {
    "tag": "tag", "asset tag": "tag", "asset id": "tag", "assetid": "tag",
    "barcode qr code": "tag", "barcode": "tag", "qr code": "tag", "qr": "tag",
    "name": "name", "device name": "name", "asset name": "name", "device": "name",
    "hostname": "hostname", "host name": "hostname", "computer name": "hostname",
    "asset": "category", "category": "category", "asset category": "category",
    "type": "type", "asset type": "type", "device type": "type",
    "serial": "serial", "serial no": "serial", "serial number": "serial",
    "serialno": "serial", "serial num": "serial",
    "manufacturer": "manufacturer", "brand": "manufacturer", "make": "manufacturer",
    "model": "model",
    "status": "status", "asset status": "status", "state": "status",
    "condition": "condition",
    "branch": "branch", "site": "branch", "campus": "branch",
    "building": "building",
    "floor": "floor", "level": "floor",
    "location": "location", "location name": "location", "place": "location",
    "room": "room",
    "assigned to": "assigned_to", "assigned": "assigned_to", "assignee": "assigned_to",
    "user": "assigned_to", "owner": "assigned_to", "holder": "assigned_to",
    "department": "department", "dept": "department",
    "ip address": "ip_address", "ip": "ip_address", "ipaddress": "ip_address",
    "os": "os", "operating system": "os", "os name": "os",
    "cpu": "cpu", "processor": "cpu",
    "ram": "ram", "memory": "ram",
    "storage": "storage", "disk": "storage", "hdd": "storage", "ssd": "storage",
    "mac": "mac_address", "mac address": "mac_address",
    "purchase date": "purchase_date", "purchased": "purchase_date", "buy date": "purchase_date",
    "warranty expiry": "warranty_expiry", "warranty": "warranty_expiry",
    "warranty expiration": "warranty_expiry", "warranty end": "warranty_expiry",
    "purchase cost": "purchase_cost", "cost": "purchase_cost", "price": "purchase_cost",
    "updated by": "updated_by", "data entry": "updated_by", "entered by": "updated_by",
    "notes": "notes", "note": "notes", "remarks": "notes", "comment": "notes",
    "comments": "notes",
}


def _norm_header(h):
    out = []
    for ch in str(h or "").lower():
        out.append(ch if ch.isalnum() else " ")
    return " ".join("".join(out).split())


def _flex_date(value):
    """Parse a date written in several common formats; return date or None."""
    v = str(value or "").strip()
    if not v:
        return None
    v = v.split(" ")[0]  # drop any time portion
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y",
                "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


def _xlsx_to_csv(file_storage):
    """Convert the first sheet of an .xlsx upload to a CSV string."""
    from openpyxl import load_workbook
    wb = load_workbook(file_storage, read_only=True, data_only=True)
    ws = wb.active
    buf = io.StringIO()
    w = csv.writer(buf)
    for row in ws.iter_rows(values_only=True):
        w.writerow(["" if v is None else
                    (v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else v)
                    for v in row])
    wb.close()
    return buf.getvalue()


@bp.route("/export.xlsx")
@perm_required("assets.view")
def export_xlsx():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Assets"
    ws.append(["Tag", "Name", "Category", "Type", "Serial", "Manufacturer", "Model",
               "Status", "Condition", "Location", "Department", "Vendor",
               "Purchase Date", "Purchase Cost", "Warranty Expiry", "Current Value",
               "Notes"])
    for a in _filtered_assets(request.args):
        ws.append([a.tag, a.name, a.category.name if a.category else "",
                   a.asset_type or "", a.serial or "", a.manufacturer or "",
                   a.model or "", a.status, a.condition,
                   a.location.path if a.location else "",
                   a.department.name if a.department else "",
                   a.vendor.name if a.vendor else "",
                   a.purchase_date, float(a.purchase_cost) if a.purchase_cost else None,
                   a.warranty_expiry, a.current_value, a.notes or ""])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    from flask import send_file
    return send_file(buf, download_name="assets.xlsx", as_attachment=True,
                     mimetype="application/vnd.openxmlformats-officedocument"
                              ".spreadsheetml.sheet")


@bp.route("/import", methods=["GET", "POST"])
@perm_required("assets.manage")
def import_():
    preview, errors, token = None, [], None
    if request.method == "POST" and "file" in request.files:
        f = request.files["file"]
        if (f.filename or "").lower().endswith((".xlsx", ".xlsm")):
            try:
                raw = _xlsx_to_csv(f)
            except Exception:
                flash("Could not read that Excel file — is it a valid .xlsx?", "error")
                return render_template("assets/import.html", preview=None, errors=[],
                                       token=None, cols=IMPORT_COLS)
        else:
            raw = f.read().decode("utf-8-sig", errors="replace")
        token = f"import-{uuid.uuid4().hex}.csv"
        with open(os.path.join(current_app.config["UPLOAD_FOLDER"], token), "w",
                  encoding="utf-8") as out:
            out.write(raw)
        preview, errors = _validate_import(raw)
    elif request.method == "POST" and request.form.get("token"):
        token_name = os.path.basename(request.form["token"])
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], token_name)
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        rows, errors = _validate_import(raw)
        created = _apply_asset_import(rows)
        log_activity("imported", "asset", None, f"{created} assets from file")
        db.session.commit()
        try:
            os.remove(path)
        except OSError:
            pass
        skipped = len([r for r in rows if r["_error"]])
        flash(f"Imported {created} assets ({skipped} rows skipped).", "success")
        return redirect(url_for("assets.list_"))
    return render_template("assets/import.html", preview=preview, errors=errors,
                           token=token, cols=IMPORT_COLS)


def _apply_asset_import(rows):
    """Create assets from validated rows, auto-creating categories & departments
    and auto-generating a unique Asset ID whenever the file's tag is missing or
    duplicated."""
    # 1) auto-create categories and departments referenced in the file
    cats = {c.name.lower(): c for c in db.session.scalars(db.select(Category))}
    deps = {d.name.lower(): d for d in db.session.scalars(db.select(Department))}
    for r in rows:
        if r["_error"]:
            continue
        cn = r["category"].strip()
        if cn and cn.lower() not in cats:
            c = Category(name=cn)
            db.session.add(c)
            cats[cn.lower()] = c
        dn = r["department"].strip()
        if dn and dn.lower() not in deps:
            d = Department(name=dn)
            db.session.add(d)
            deps[dn.lower()] = d
    db.session.flush()  # assign ids to the new categories/departments

    # 2) seed per-prefix counters and the set of tags already in use
    used = {t.lower() for (t,) in db.session.execute(db.select(Asset.tag)).all()}
    counters = {}

    def gen_tag(cat):
        prefix = cat.tag_prefix if cat else "AST"
        n = counters.get(prefix)
        if n is None:
            n = 0
            for t in used:
                if t.startswith(prefix.lower() + "-"):
                    suf = t.rsplit("-", 1)[-1]
                    if suf.isdigit():
                        n = max(n, int(suf))
        while True:
            n += 1
            counters[prefix] = n
            cand = f"{prefix}-{n:06d}"
            if cand.lower() not in used:
                used.add(cand.lower())
                return cand

    created = 0
    for r in rows:
        if r["_error"]:
            continue
        cat = cats.get(r["category"].strip().lower()) if r["category"].strip() else None
        dep = deps.get(r["department"].strip().lower()) if r["department"].strip() else None
        tag = r["tag"].strip()
        if not tag or r["_auto_tag"] or tag.lower() in used:
            tag = gen_tag(cat)
        else:
            used.add(tag.lower())
        # fold "assigned to" and any secondary room into notes
        extra = []
        if r["assigned_to"].strip():
            extra.append(f"Assigned to: {r['assigned_to'].strip()}")
        if r["room"].strip() and r["room"].strip().lower() != r["location"].strip().lower():
            extra.append(f"Room: {r['room'].strip()}")
        notes = "\n".join([p for p in [r["notes"].strip(), *extra] if p]) or None
        try:
            cost = float(r["purchase_cost"]) if r["purchase_cost"].strip() else None
        except ValueError:
            cost = None
        a = Asset(
            tag=tag,
            name=r["name"].strip(),
            category_id=cat.id if cat else None,
            # if the sheet has no separate "type" column, reuse the category
            # (e.g. the "Asset" column: Desktop / Printer / IP Phone …)
            asset_type=(r["type"].strip() or r["category"].strip()) or None,
            serial=r["serial"].strip() or None,
            manufacturer=r["manufacturer"].strip() or None,
            model=r["model"].strip() or None,
            status=r["status"].strip() if r["status"].strip() in ASSET_STATUSES else "In Use",
            condition=r["condition"].strip() if r["condition"].strip() in ASSET_CONDITIONS else "Good",
            branch=r["branch"].strip() or None,
            building=r["building"].strip() or None,
            floor=r["floor"].strip() or None,
            location_name=(r["location"].strip() or r["room"].strip()) or None,
            updated_by=r["updated_by"].strip() or None,
            department_id=dep.id if dep else None,
            ip_address=r["ip_address"].strip() or None,
            os_name=r["os"].strip() or None,
            cpu=r["cpu"].strip() or None,
            ram=r["ram"].strip() or None,
            storage=r["storage"].strip() or None,
            hostname=(r["hostname"].strip() or r["name"].strip()) or None,
            mac_address=r["mac_address"].strip() or None,
            purchase_date=_flex_date(r["purchase_date"]),
            warranty_expiry=_flex_date(r["warranty_expiry"]),
            purchase_cost=cost,
            notes=notes,
        )
        db.session.add(a)
        created += 1
    return created


# canonical fields carried on each parsed row
_CANON = ["tag", "name", "category", "type", "serial", "manufacturer", "model",
          "status", "condition", "branch", "building", "floor", "location", "room",
          "assigned_to", "department", "ip_address", "os", "cpu", "ram", "storage",
          "hostname", "mac_address", "purchase_date", "warranty_expiry",
          "purchase_cost", "updated_by", "notes"]


def _validate_import(raw):
    errors = []
    reader = csv.DictReader(io.StringIO(raw))
    # map each source header to a canonical field (first match wins)
    col_of = {}
    for fn in (reader.fieldnames or []):
        canon = HEADER_ALIASES.get(_norm_header(fn))
        if canon and canon not in col_of:
            col_of[canon] = fn
    if "name" not in col_of and "tag" not in col_of and "hostname" not in col_of:
        return [], ['The file needs at least a "Name" column (a "Tag"/"Asset ID" '
                    'column is optional — IDs are generated automatically).']

    raw_rows = list(reader)
    # decide whether the file's tag column is trustworthy: if tags repeat, ignore it
    tag_vals = [(_row_val(rec, col_of, "tag")) for rec in raw_rows]
    nonempty = [t for t in tag_vals if t]
    ignore_tags = bool(nonempty) and len(set(t.lower() for t in nonempty)) < len(nonempty)

    seen, rows = set(), []
    for i, rec in enumerate(raw_rows, start=2):
        row = {c: _row_val(rec, col_of, c) for c in _CANON}
        # a usable name: fall back to hostname, then tag, then category+line
        if not row["name"]:
            row["name"] = (row["hostname"] or row["tag"]
                           or (f"{row['category']} {i - 1}".strip() if row["category"]
                               else ""))
        err = None
        if not row["name"]:
            err = "row is empty (no name)"
        auto_tag = ignore_tags or not row["tag"] or row["tag"].lower() in seen
        if not auto_tag:
            seen.add(row["tag"].lower())
        row["_auto_tag"] = auto_tag
        row["_line"], row["_error"] = i, err
        if err:
            errors.append(f"Row {i}: {err}")
        rows.append(row)
    return rows, errors


def _row_val(rec, col_of, canon):
    src = col_of.get(canon)
    if not src:
        return ""
    return (rec.get(src, "") or "").strip()
