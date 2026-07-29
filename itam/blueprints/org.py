from datetime import datetime

from flask import (Blueprint, flash, g, redirect, render_template, request,
                   url_for)

from ..models import (EMPLOYEE_TYPES, LOCATION_KINDS, Asset, Category,
                      Department, Employee, Location, Vendor, db)
from ..security import perm_required
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
            emp.emp_code = code or emp.emp_code
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
        email = request.form["email"].strip().lower()
        other = db.session.scalar(db.select(Employee).where(Employee.email == email))
        if other and (not emp or other.id != emp.id):
            flash(f'An employee with email "{email}" already exists.', "error")
        else:
            if not emp:
                emp = Employee()
                db.session.add(emp)
            emp.name = request.form["name"].strip()
            emp.emp_code = request.form.get("emp_code", "").strip() or None
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
                           emp_types=EMPLOYEE_TYPES)


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


# -------------------------------------------------------------- departments

@bp.route("/departments", methods=["GET", "POST"])
@perm_required("assets.view")
def departments():
    if request.method == "POST":
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
        loc_id = request.form.get("id")
        if loc_id:
            loc = db.get_or_404(Location, int(loc_id))
        else:
            loc = Location()
            db.session.add(loc)
        loc.name = request.form["name"].strip()
        loc.kind = (request.form.get("kind") if request.form.get("kind") in LOCATION_KINDS
                    else "Room")
        parent = request.form.get("parent_id")
        loc.parent_id = int(parent) if parent and (not loc.id or int(parent) != loc.id) else None
        db.session.commit()
        flash(f'Location "{loc.name}" saved.', "success")
        return redirect(url_for("org.locations"))
    rows = db.session.scalars(db.select(Location).order_by(Location.name)).all()
    return render_template("org/locations.html", rows=rows, kinds=LOCATION_KINDS)


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
