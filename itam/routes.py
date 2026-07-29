from datetime import datetime, date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_

from .models import ASSET_STATUSES, Asset, Assignment, Category, Employee, db

bp = Blueprint("itam", __name__)


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _asset_from_form(asset, form):
    asset.asset_tag = form["asset_tag"].strip()
    asset.name = form["name"].strip()
    asset.category_id = int(form["category_id"]) if form.get("category_id") else None
    asset.serial_number = form.get("serial_number", "").strip() or None
    asset.manufacturer = form.get("manufacturer", "").strip() or None
    asset.model = form.get("model", "").strip() or None
    asset.location = form.get("location", "").strip() or None
    asset.purchase_date = _parse_date(form.get("purchase_date"))
    asset.purchase_cost = form.get("purchase_cost") or None
    asset.warranty_expiry = _parse_date(form.get("warranty_expiry"))
    asset.notes = form.get("notes", "").strip() or None
    status = form.get("status")
    if status in ASSET_STATUSES:
        asset.status = status


# ---------------------------------------------------------------- dashboard


@bp.route("/")
def dashboard():
    total = db.session.scalar(db.select(func.count(Asset.id)))
    by_status = dict(
        db.session.execute(
            db.select(Asset.status, func.count(Asset.id)).group_by(Asset.status)
        ).all()
    )
    by_category = db.session.execute(
        db.select(Category.name, func.count(Asset.id))
        .join(Asset, Asset.category_id == Category.id)
        .group_by(Category.name)
        .order_by(func.count(Asset.id).desc())
    ).all()
    recent_assets = db.session.scalars(
        db.select(Asset).order_by(Asset.created_at.desc()).limit(5)
    ).all()
    recent_assignments = db.session.scalars(
        db.select(Assignment).order_by(Assignment.assigned_at.desc()).limit(5)
    ).all()
    expiring = db.session.scalars(
        db.select(Asset)
        .where(Asset.warranty_expiry.isnot(None), Asset.status != "Retired")
        .order_by(Asset.warranty_expiry)
        .limit(5)
    ).all()
    return render_template(
        "dashboard.html",
        total=total,
        by_status=by_status,
        by_category=by_category,
        recent_assets=recent_assets,
        recent_assignments=recent_assignments,
        expiring=expiring,
        statuses=ASSET_STATUSES,
        today=date.today(),
    )


# ------------------------------------------------------------------- assets


@bp.route("/assets")
def asset_list():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    category_id = request.args.get("category", "")

    stmt = db.select(Asset).order_by(Asset.asset_tag)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Asset.asset_tag.ilike(like),
                Asset.name.ilike(like),
                Asset.serial_number.ilike(like),
                Asset.manufacturer.ilike(like),
                Asset.model.ilike(like),
                Asset.location.ilike(like),
            )
        )
    if status:
        stmt = stmt.where(Asset.status == status)
    if category_id:
        stmt = stmt.where(Asset.category_id == int(category_id))

    assets = db.session.scalars(stmt).all()
    categories = db.session.scalars(db.select(Category).order_by(Category.name)).all()
    return render_template(
        "assets/list.html",
        assets=assets,
        categories=categories,
        statuses=ASSET_STATUSES,
        q=q,
        status=status,
        category_id=category_id,
    )


@bp.route("/assets/new", methods=["GET", "POST"])
def asset_new():
    categories = db.session.scalars(db.select(Category).order_by(Category.name)).all()
    if request.method == "POST":
        tag = request.form["asset_tag"].strip()
        if db.session.scalar(db.select(Asset).where(Asset.asset_tag == tag)):
            flash(f"Asset tag '{tag}' already exists.", "error")
        else:
            asset = Asset()
            _asset_from_form(asset, request.form)
            db.session.add(asset)
            db.session.commit()
            flash(f"Asset {asset.asset_tag} created.", "success")
            return redirect(url_for("itam.asset_detail", asset_id=asset.id))
    return render_template(
        "assets/form.html", asset=None, categories=categories, statuses=ASSET_STATUSES
    )


@bp.route("/assets/<int:asset_id>")
def asset_detail(asset_id):
    asset = db.get_or_404(Asset, asset_id)
    employees = db.session.scalars(db.select(Employee).order_by(Employee.name)).all()
    return render_template("assets/detail.html", asset=asset, employees=employees)


@bp.route("/assets/<int:asset_id>/edit", methods=["GET", "POST"])
def asset_edit(asset_id):
    asset = db.get_or_404(Asset, asset_id)
    categories = db.session.scalars(db.select(Category).order_by(Category.name)).all()
    if request.method == "POST":
        tag = request.form["asset_tag"].strip()
        existing = db.session.scalar(db.select(Asset).where(Asset.asset_tag == tag))
        if existing and existing.id != asset.id:
            flash(f"Asset tag '{tag}' already exists.", "error")
        else:
            _asset_from_form(asset, request.form)
            db.session.commit()
            flash(f"Asset {asset.asset_tag} updated.", "success")
            return redirect(url_for("itam.asset_detail", asset_id=asset.id))
    return render_template(
        "assets/form.html", asset=asset, categories=categories, statuses=ASSET_STATUSES
    )


@bp.route("/assets/<int:asset_id>/delete", methods=["POST"])
def asset_delete(asset_id):
    asset = db.get_or_404(Asset, asset_id)
    db.session.delete(asset)
    db.session.commit()
    flash(f"Asset {asset.asset_tag} deleted.", "success")
    return redirect(url_for("itam.asset_list"))


@bp.route("/assets/<int:asset_id>/checkout", methods=["POST"])
def asset_checkout(asset_id):
    asset = db.get_or_404(Asset, asset_id)
    if asset.current_assignment:
        flash("Asset is already checked out.", "error")
        return redirect(url_for("itam.asset_detail", asset_id=asset.id))
    if asset.status == "Retired":
        flash("Retired assets cannot be checked out.", "error")
        return redirect(url_for("itam.asset_detail", asset_id=asset.id))
    employee = db.get_or_404(Employee, int(request.form["employee_id"]))
    assignment = Assignment(
        asset=asset,
        employee=employee,
        notes=request.form.get("notes", "").strip() or None,
    )
    asset.status = "Assigned"
    db.session.add(assignment)
    db.session.commit()
    flash(f"Checked out to {employee.name}.", "success")
    return redirect(url_for("itam.asset_detail", asset_id=asset.id))


@bp.route("/assets/<int:asset_id>/checkin", methods=["POST"])
def asset_checkin(asset_id):
    asset = db.get_or_404(Asset, asset_id)
    assignment = asset.current_assignment
    if not assignment:
        flash("Asset is not checked out.", "error")
        return redirect(url_for("itam.asset_detail", asset_id=asset.id))
    assignment.returned_at = datetime.utcnow()
    asset.status = "Available"
    db.session.commit()
    flash(f"Checked in from {assignment.employee.name}.", "success")
    return redirect(url_for("itam.asset_detail", asset_id=asset.id))


# ---------------------------------------------------------------- employees


@bp.route("/employees")
def employee_list():
    employees = db.session.scalars(db.select(Employee).order_by(Employee.name)).all()
    return render_template("employees/list.html", employees=employees)


@bp.route("/employees/new", methods=["GET", "POST"])
def employee_new():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        if db.session.scalar(db.select(Employee).where(Employee.email == email)):
            flash(f"An employee with email '{email}' already exists.", "error")
        else:
            employee = Employee(
                name=request.form["name"].strip(),
                email=email,
                department=request.form.get("department", "").strip() or None,
            )
            db.session.add(employee)
            db.session.commit()
            flash(f"Employee {employee.name} created.", "success")
            return redirect(url_for("itam.employee_detail", employee_id=employee.id))
    return render_template("employees/form.html", employee=None)


@bp.route("/employees/<int:employee_id>")
def employee_detail(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    return render_template("employees/detail.html", employee=employee)


@bp.route("/employees/<int:employee_id>/edit", methods=["GET", "POST"])
def employee_edit(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        existing = db.session.scalar(db.select(Employee).where(Employee.email == email))
        if existing and existing.id != employee.id:
            flash(f"An employee with email '{email}' already exists.", "error")
        else:
            employee.name = request.form["name"].strip()
            employee.email = email
            employee.department = request.form.get("department", "").strip() or None
            db.session.commit()
            flash(f"Employee {employee.name} updated.", "success")
            return redirect(url_for("itam.employee_detail", employee_id=employee.id))
    return render_template("employees/form.html", employee=employee)


@bp.route("/employees/<int:employee_id>/delete", methods=["POST"])
def employee_delete(employee_id):
    employee = db.get_or_404(Employee, employee_id)
    if employee.current_assets:
        flash("Employee still has assets checked out. Check them in first.", "error")
        return redirect(url_for("itam.employee_detail", employee_id=employee.id))
    for assignment in list(employee.assignments):
        db.session.delete(assignment)
    db.session.delete(employee)
    db.session.commit()
    flash(f"Employee {employee.name} deleted.", "success")
    return redirect(url_for("itam.employee_list"))


# --------------------------------------------------------------- categories


@bp.route("/categories", methods=["GET", "POST"])
def category_list():
    if request.method == "POST":
        name = request.form["name"].strip()
        if not name:
            flash("Category name is required.", "error")
        elif db.session.scalar(db.select(Category).where(Category.name == name)):
            flash(f"Category '{name}' already exists.", "error")
        else:
            db.session.add(Category(name=name))
            db.session.commit()
            flash(f"Category '{name}' created.", "success")
        return redirect(url_for("itam.category_list"))
    categories = db.session.scalars(db.select(Category).order_by(Category.name)).all()
    return render_template("categories/list.html", categories=categories)


@bp.route("/categories/<int:category_id>/delete", methods=["POST"])
def category_delete(category_id):
    category = db.get_or_404(Category, category_id)
    if category.assets:
        flash("Category is in use by assets and cannot be deleted.", "error")
    else:
        db.session.delete(category)
        db.session.commit()
        flash(f"Category '{category.name}' deleted.", "success")
    return redirect(url_for("itam.category_list"))
