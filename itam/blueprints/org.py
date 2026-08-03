from datetime import datetime

from flask import (Blueprint, flash, g, redirect, render_template, request,
                   url_for)

from ..models import (EMPLOYEE_TYPES, LOCATION_KINDS, Asset, Category,
                      Department, Employee, Location, Vendor, db)
from ..security import has_perm, perm_required
from ..utils import (csv_response, log_activity, parse_date, read_table,
                     xlsx_response)

bp = Blueprint("org", __name__)


# ---------------------------------------------------------------- employees

@bp.route("/employees")
@perm_required("assets.view")
def employees():
    rows = db.session.scalars(db.select(Employee).order_by(Employee.name)).all()
    return render_template("org/employees.html", rows=rows)


def _employee_rows():
    return [(e.name, e.emp_code or "", e.emp_type or "", e.email, e.phone or "",
             e.title or "", e.department.name if e.department else "",
             "Yes" if e.active else "No", len(e.current_assets))
            for e in db.session.scalars(db.select(Employee).order_by(Employee.name))]


EMP_HEADERS = ["Name", "Employee ID", "Type", "Email", "Phone", "Title",
               "Department", "Active", "Assets Held"]


@bp.route("/employees/export.xlsx")
@perm_required("assets.view")
def employees_export_xlsx():
    return xlsx_response(EMP_HEADERS, _employee_rows(), "employees.xlsx", "Employees")


@bp.route("/employees/export.csv")
@perm_required("assets.view")
def employees_export_csv():
    return csv_response(EMP_HEADERS, _employee_rows(), "employees.csv")


@bp.route("/employees/import", methods=["GET", "POST"])
@perm_required("people.manage")
def employees_import():
    if request.method == "POST" and request.files.get("file"):
        _, rows = read_table(request.files["file"])
        depts = {d.name.lower(): d for d in db.session.scalars(db.select(Department))}

        def pick(r, *keys):
            for k in keys:
                v = (r.get(k) or "").strip()
                if v:
                    return v
            return ""

        created = updated = skipped = 0
        for r in rows:
            name = pick(r, "name", "employee name", "full name")
            code = pick(r, "employee id", "emp_code", "emp code", "id", "badge")
            email = pick(r, "email", "e-mail", "email address").lower()
            if not name and not code:
                skipped += 1
                continue
            # match an existing employee by Employee ID; only fall back to email
            # when the row has no ID (emails may be shared, so they can't key rows)
            emp = None
            if code:
                emp = db.session.scalar(db.select(Employee).where(Employee.emp_code == code))
            elif email:
                emp = db.session.scalar(db.select(Employee).where(Employee.email == email))
            if not emp:
                emp = Employee()
                db.session.add(emp)
                created += 1
            else:
                updated += 1
            emp.name = name or emp.name or code
            # Without an ID the next import cannot match this row and would
            # add them a second time.
            emp.emp_code = code or emp.emp_code or next_employee_code()
            emp.email = email or emp.email
            emp.emp_type = (pick(r, "employee type", "type", "emp_type", "staff type")
                            or emp.emp_type)
            emp.phone = pick(r, "phone", "mobile", "telephone") or emp.phone
            emp.title = pick(r, "job title", "title", "position", "role") or emp.title
            dname = pick(r, "department", "dept")
            if dname:
                dep = depts.get(dname.lower())
                if not dep:                       # auto-create missing departments
                    dep = Department(name=dname)
                    db.session.add(dep)
                    db.session.flush()
                    depts[dname.lower()] = dep
                emp.department_id = dep.id
        log_activity("employees_imported", "employee", None,
                     f"{created} new, {updated} updated")
        db.session.commit()
        flash(f"Imported {created} new and {updated} updated employees "
              f"({skipped} skipped).", "success")
        return redirect(url_for("org.employees"))
    return render_template("org/import.html", title="Import employees",
                           cols=["Name", "Employee ID", "Employee Type", "Email",
                                 "Job Title", "Department"],
                           post_url=url_for("org.employees_import"),
                           back_url=url_for("org.employees"))


@bp.route("/employees/new", methods=["GET", "POST"])
@bp.route("/employees/<int:emp_id>/edit", methods=["GET", "POST"])
@perm_required("people.manage")
def employee_form(emp_id=None):
    emp = db.get_or_404(Employee, emp_id) if emp_id else None
    if request.method == "POST":
        # The model has always said email is optional and may repeat -- a
        # school has drivers, cleaners and security with no address, and
        # departments that share one inbox. The form demanded it anyway and
        # refused duplicates, so those people could not be added at all.
        # Identity is the Employee ID; that is what the importer matches on.
        email = request.form.get("email", "").strip().lower() or None
        if not emp:
            emp = Employee()
            db.session.add(emp)
        emp.name = request.form["name"].strip()
        emp.emp_code = (request.form.get("emp_code", "").strip()
                        or emp.emp_code or next_employee_code())
        emp.emp_type = request.form.get("emp_type", "").strip() or None
        emp.email = email
        emp.phone = request.form.get("phone", "").strip() or None
        emp.title = request.form.get("title", "").strip() or None
        emp.department_id = (int(request.form["department_id"])
                             if request.form.get("department_id") else None)
        emp.active = request.form.get("active") == "1"
        db.session.flush()
        log_activity("employee_saved", "employee", emp.id, emp.name)
        db.session.commit()
        flash(f"Employee {emp.name} saved.", "success")
        return redirect(url_for("org.employee_detail", emp_id=emp.id))
    from ..models import EMPLOYEE_TYPES
    departments = db.session.scalars(db.select(Department).order_by(Department.name)).all()
    return render_template("org/employee_form.html", emp=emp, departments=departments,
                           emp_types=EMPLOYEE_TYPES,
                           suggested_code=next_employee_code() if not emp else None)


@bp.route("/employees/<int:emp_id>")
@perm_required("assets.view")
def employee_detail(emp_id):
    emp = db.get_or_404(Employee, emp_id)
    return render_template("org/employee_detail.html", emp=emp)


@bp.post("/employees/<int:emp_id>/delete")
@perm_required("people.manage")
def employee_delete(emp_id):
    emp = db.get_or_404(Employee, emp_id)
    if emp.current_assets:
        flash("Employee still has assets checked out. Check them in first.", "error")
        return redirect(url_for("org.employee_detail", emp_id=emp.id))
    for a in list(emp.assignments):
        db.session.delete(a)
    log_activity("employee_deleted", "employee", emp.id, emp.name)
    db.session.delete(emp)
    db.session.commit()
    flash("Employee deleted.", "success")
    return redirect(url_for("org.employees"))


def next_employee_code():
    """The next Employee ID, following whatever format is already in use.

    Adding someone by hand left this blank unless the person typed one, and an
    import without an ID column produced employees with no ID at all -- which
    is the field the importer keys on, so the next import could not match them
    and made duplicates instead.
    """
    import re
    from collections import Counter

    top, shapes = 0, Counter()
    pattern = re.compile(r"^([A-Za-z]*)([-_ ]?)(\d+)$")
    for (code,) in db.session.execute(
            db.select(Employee.emp_code).where(Employee.emp_code.isnot(None))).all():
        match = pattern.match((code or "").strip())
        if match:
            shapes[(match.group(1).upper(), match.group(2), len(match.group(3)))] += 1
            top = max(top, int(match.group(3)))
    stem, separator, width = (shapes.most_common(1)[0][0] if shapes
                              else ("EMP", "-", 4))
    return f"{stem}{separator}{top + 1:0{width}d}"


# -------------------------------------------------------------- departments

@bp.route("/departments", methods=["GET", "POST"])
@perm_required("assets.view")
def departments():
    if request.method == "POST":
        # The route is readable by anyone who can see assets, so the write
        # branch needs its own check -- otherwise a viewer or an auditor could
        # create and rename departments. (Categories already does this.)
        if not has_perm("org.manage"):
            flash("You do not have permission to do that.", "error")
            return redirect(url_for("org.departments"))
        dep_id = request.form.get("id")
        name = request.form["name"].strip()
        if dep_id:
            dep = db.get_or_404(Department, int(dep_id))
        else:
            dep = Department()
            db.session.add(dep)
        dep.name = name
        dep.cost_center = request.form.get("cost_center", "").strip() or None
        db.session.commit()
        flash(f'Department "{name}" saved.', "success")
        return redirect(url_for("org.departments"))
    rows = db.session.scalars(db.select(Department).order_by(Department.name)).all()
    return render_template("org/departments.html", rows=rows)


@bp.post("/departments/<int:dep_id>/delete")
@perm_required("org.manage")
def department_delete(dep_id):
    dep = db.get_or_404(Department, dep_id)
    if dep.assets or dep.employees:
        flash("Department has assets or employees and cannot be deleted.", "error")
    else:
        db.session.delete(dep)
        db.session.commit()
        flash("Department deleted.", "success")
    return redirect(url_for("org.departments"))


# ---------------------------------------------------------------- locations

@bp.route("/locations", methods=["GET", "POST"])
@perm_required("assets.view")
def locations():
    if request.method == "POST":
        # Readable by anyone who can see assets, so the write branch needs its
        # own check -- exactly as Departments and Categories do.
        if not has_perm("org.manage"):
            flash("You do not have permission to do that.", "error")
            return redirect(url_for("org.locations"))
        loc_id = request.form.get("id")
        if loc_id:
            # Editing one row: plain name / kind / parent.
            loc = db.get_or_404(Location, int(loc_id))
            loc.name = request.form.get("name", "").strip() or loc.name
            loc.kind = (request.form.get("kind")
                        if request.form.get("kind") in LOCATION_KINDS else loc.kind)
            parent = request.form.get("parent_id")
            loc.parent_id = (int(parent) if parent and int(parent) != loc.id
                             else None)
            db.session.commit()
            flash(f'Location "{loc.name}" saved.', "success")
            return redirect(url_for("org.locations"))

        # Adding: fill in the levels you know and the chain is built for you,
        # rather than adding a branch, then a building, then a floor, then a
        # room, choosing the right parent every time.
        levels = [(request.form.get("branch", "").strip(), "Branch"),
                  (request.form.get("building", "").strip(), "Building"),
                  (request.form.get("department", "").strip(), "Department"),
                  (request.form.get("floor", "").strip(), "Floor"),
                  (request.form.get("room", "").strip(), "Room")]
        if not any(name for name, _ in levels):
            flash("Fill in at least one level.", "error")
            return redirect(url_for("org.locations"))

        node, made = None, 0
        for name, kind in levels:
            if not name:
                continue
            parent_id = node.id if node else None
            existing = db.session.scalar(db.select(Location).where(
                Location.name == name, Location.kind == kind,
                Location.parent_id == parent_id))
            if existing:
                node = existing
                continue
            node = Location(name=name, kind=kind, parent_id=parent_id)
            db.session.add(node)
            db.session.flush()
            made += 1
        db.session.commit()
        path = " / ".join(name for name, _ in levels if name)
        flash(f'"{path}" is ready.' if made else f'"{path}" already existed.',
              "success")
        return redirect(url_for("org.locations"))
    # Keep the list in step with the register without anyone pressing a
    # button: whatever places the assets name, this page shows.
    sync_locations_from_assets()
    rows = db.session.scalars(db.select(Location).order_by(Location.name)).all()
    # Location.path walks up the parent chain and l.assets loads every asset,
    # so a template touching both once per row cost a query per ancestor and
    # per location. Resolve both up front in two queries instead.
    by_id = {l.id: l for l in rows}
    paths = {}

    def path_of(loc):
        if loc.id in paths:
            return paths[loc.id]
        parent = by_id.get(loc.parent_id)
        paths[loc.id] = (f"{path_of(parent)} / {loc.name}"
                         if parent and parent.id != loc.id else loc.name)
        return paths[loc.id]

    for loc in rows:
        path_of(loc)
    counts = dict(db.session.execute(
        db.select(Asset.location_id, db.func.count(Asset.id))
        .where(Asset.location_id.isnot(None)).group_by(Asset.location_id)).all())

    # The standard tree is ~600 rows and printing them all made this the
    # heaviest page in the app. Filter and page the table; the parent dropdown
    # still lists everything, since any location can be a parent.
    q = request.args.get("q", "").strip().lower()
    listed = [l for l in rows if not q or q in paths[l.id].lower()
              or q in (l.kind or "").lower()]
    listed.sort(key=lambda l: paths[l.id])
    page_rows, paging = _paginate(listed, request.args.get("page"))
    return render_template("org/locations.html", rows=rows, page_rows=page_rows,
                           kinds=LOCATION_KINDS, paths=paths, counts=counts,
                           paging=paging, q=request.args.get("q", ""),
                           **_level_options(),
                           departments=db.session.scalars(
                               db.select(Department).order_by(Department.name)).all(),
                           # One grouped query rather than len(d.assets) per
                           # department, which is a query each.
                           dept_counts=dict(db.session.execute(
                               db.select(Asset.department_id, db.func.count(Asset.id))
                               .where(Asset.department_id.isnot(None))
                               .group_by(Asset.department_id)).all()))


#: Rows per page on the Locations table.
LOCATION_PAGE_SIZE = 50


def _level_options():
    """What to offer for each level of the tree.

    Whatever the school has already created, plus the standard names, so the
    lists grow with real use instead of being stuck on the constants compiled
    into the app.
    """
    from ..models import BRANCHES, BUILDINGS, FLOORS, PLACES

    used = {}
    for kind, name in db.session.execute(
            db.select(Location.kind, Location.name).distinct()).all():
        used.setdefault(kind, set()).add(name)

    def merge(kind, standard):
        return sorted(used.get(kind, set()) | set(standard))

    return {
        "branches": merge("Branch", BRANCHES),
        "buildings": merge("Building", BUILDINGS),
        "floors": merge("Floor", FLOORS),
        "rooms": merge("Room", PLACES) + merge("Storage Area", []),
        "dept_names": sorted(
            used.get("Department", set())
            | {d.name for d in db.session.scalars(db.select(Department))}),
    }


def _paginate(items, page_arg):
    total = len(items)
    pages = max(1, -(-total // LOCATION_PAGE_SIZE))
    try:
        page = int(page_arg or 1)
    except (TypeError, ValueError):
        page = 1
    page = min(max(page, 1), pages)
    start = (page - 1) * LOCATION_PAGE_SIZE
    window = items[start:start + LOCATION_PAGE_SIZE]
    return window, {"page": page, "pages": pages, "total": total,
                    "first": start + 1 if window else 0,
                    "last": start + len(window)}


@bp.post("/locations/<int:loc_id>/delete")
@perm_required("org.manage")
def location_delete(loc_id):
    loc = db.get_or_404(Location, loc_id)
    if loc.assets or loc.children:
        flash("Location has assets or sub-locations and cannot be deleted.", "error")
    else:
        db.session.delete(loc)
        db.session.commit()
        flash("Location deleted.", "success")
    return redirect(url_for("org.locations"))


@bp.post("/locations/bulk-delete")
@perm_required("org.manage")
def locations_bulk_delete():
    return _bulk_delete(
        Location, request.form.getlist("ids", type=int),
        lambda l: (f"{l.name} has assets or sub-locations." if l.assets or l.children else None),
        "org.locations", "location")


# ------------------------------------------------------------------ vendors

@bp.route("/vendors")
@perm_required("assets.view")
def vendors():
    rows = db.session.scalars(db.select(Vendor).order_by(Vendor.name)).all()
    return render_template("org/vendors.html", rows=rows)


@bp.route("/vendors/new", methods=["GET", "POST"])
@bp.route("/vendors/<int:vendor_id>/edit", methods=["GET", "POST"])
@perm_required("org.manage")
def vendor_form(vendor_id=None):
    vendor = db.get_or_404(Vendor, vendor_id) if vendor_id else None
    if request.method == "POST":
        if not vendor:
            vendor = Vendor()
            db.session.add(vendor)
        vendor.name = request.form["name"].strip()
        vendor.contact_name = request.form.get("contact_name", "").strip() or None
        vendor.email = request.form.get("email", "").strip() or None
        vendor.phone = request.form.get("phone", "").strip() or None
        vendor.website = request.form.get("website", "").strip() or None
        vendor.notes = request.form.get("notes", "").strip() or None
        db.session.flush()
        log_activity("vendor_saved", "vendor", vendor.id, vendor.name)
        db.session.commit()
        flash(f"Vendor {vendor.name} saved.", "success")
        return redirect(url_for("org.vendor_detail", vendor_id=vendor.id))
    return render_template("org/vendor_form.html", vendor=vendor)


@bp.route("/vendors/<int:vendor_id>")
@perm_required("assets.view")
def vendor_detail(vendor_id):
    vendor = db.get_or_404(Vendor, vendor_id)
    return render_template("org/vendor_detail.html", vendor=vendor)


@bp.post("/vendors/<int:vendor_id>/delete")
@perm_required("org.manage")
def vendor_delete(vendor_id):
    vendor = db.get_or_404(Vendor, vendor_id)
    if vendor.assets or vendor.licenses or vendor.orders:
        flash("Vendor is referenced by assets, licenses, or orders.", "error")
    else:
        db.session.delete(vendor)
        db.session.commit()
        flash("Vendor deleted.", "success")
    return redirect(url_for("org.vendors"))


# ------------------------------------------------------------- bulk actions

def _bulk_delete(model, ids, blocked, endpoint, noun):
    """Delete the chosen rows, skipping any that are still in use.

    `blocked` returns a reason string when a row must be kept, so a bulk run
    applies exactly the same rules as deleting the rows one at a time.
    """
    deleted, kept = 0, []
    for row in db.session.scalars(db.select(model).where(model.id.in_(ids))):
        reason = blocked(row)
        if reason:
            kept.append(reason)
            continue
        db.session.delete(row)
        deleted += 1
    db.session.commit()
    if deleted:
        flash(f"{deleted} {noun}{'' if deleted == 1 else 's'} deleted.", "success")
    for reason in kept[:5]:
        flash(reason, "error")
    if len(kept) > 5:
        flash(f"…and {len(kept) - 5} more could not be deleted.", "error")
    if not deleted and not kept:
        flash("Nothing selected.", "error")
    return redirect(url_for(endpoint))


@bp.post("/employees/bulk-delete")
@perm_required("people.manage")
def employees_bulk_delete():
    ids = request.form.getlist("ids", type=int)
    for emp in db.session.scalars(db.select(Employee).where(Employee.id.in_(ids))):
        if not emp.current_assets:
            for assignment in list(emp.assignments):
                db.session.delete(assignment)
            log_activity("employee_deleted", "employee", emp.id, emp.name)
    return _bulk_delete(
        Employee, ids,
        lambda e: (f"{e.name} still has assets checked out." if e.current_assets else None),
        "org.employees", "employee")


@bp.post("/departments/bulk-delete")
@perm_required("org.manage")
def departments_bulk_delete():
    return _bulk_delete(
        Department, request.form.getlist("ids", type=int),
        lambda d: (f"{d.name} has assets or employees." if d.assets or d.employees else None),
        "org.departments", "department")


def sync_locations_from_assets():
    """Build the Locations tree out of the places the assets actually name.

    Every asset already carries branch / building / floor / location_name, so
    the real map of the school is sitting in the register. This turns those
    values into Location rows and links each asset to its room.

    It replaces a button that created a fixed Branch x Building x Floor x Room
    tree from constants: ~600 rows, mostly rooms nothing was ever in, and it
    still didn't contain a place unique to one campus. Deriving from the data
    means the list is exactly what exists, and grows by itself as assets are
    added or imported.

    Idempotent and cheap: on a register where nothing has moved it creates
    nothing and links nothing.
    """
    combos = db.session.execute(
        db.select(Asset.branch, Asset.building, Asset.floor, Asset.location_name)
        .distinct()).all()

    existing = {}
    for loc in db.session.scalars(db.select(Location)):
        existing[(loc.name, loc.kind, loc.parent_id)] = loc

    created = 0

    def ensure(name, kind, parent):
        nonlocal created
        parent_id = parent.id if parent else None
        key = (name, kind, parent_id)
        if key in existing:
            return existing[key]
        loc = Location(name=name, kind=kind, parent_id=parent_id)
        db.session.add(loc)
        db.session.flush()
        existing[key] = loc
        created += 1
        return loc

    # leaf per (branch, building, floor, room) so assets can be linked to it
    leaf_of = {}
    for branch, building, floor, room in combos:
        node = None
        for name, kind in ((branch, "Branch"), (building, "Building"),
                           (floor, "Floor"), (room, "Room")):
            if name and name.strip():
                node = ensure(name.strip(), kind, node)
        if node is not None:
            leaf_of[(branch, building, floor, room)] = node.id

    # Fill in the link only where it is missing: a location picked by hand on
    # the asset itself must win over anything inferred from the text fields.
    #
    # The loop below costs one statement per distinct place, so check first
    # whether there is anything at all to link. Once a register has settled
    # that is a single query, instead of a few hundred on every page load.
    linked = 0
    unlinked = db.session.scalar(
        db.select(db.func.count(Asset.id)).where(Asset.location_id.is_(None)))
    if not unlinked:
        if created:
            db.session.commit()
        return created, 0

    for (branch, building, floor, room), loc_id in leaf_of.items():
        result = db.session.execute(
            db.update(Asset)
            .where(Asset.location_id.is_(None), Asset.branch.is_(branch),
                   Asset.building.is_(building), Asset.floor.is_(floor),
                   Asset.location_name.is_(room))
            .values(location_id=loc_id))
        linked += result.rowcount or 0

    if created or linked:
        db.session.commit()
    return created, linked


@bp.post("/vendors/bulk-delete")
@perm_required("org.manage")
def vendors_bulk_delete():
    return _bulk_delete(
        Vendor, request.form.getlist("ids", type=int),
        lambda v: (f"{v.name} still has assets or licences."
                   if v.assets or v.licenses else None),
        "org.vendors", "vendor")
