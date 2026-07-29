from functools import wraps

from flask import Blueprint, g, jsonify, request

from ..models import Asset, Employee, License, User, db
from ..security import role_perms

bp = Blueprint("api", __name__, url_prefix="/api/v1")


def api_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        user = db.session.scalar(db.select(User).where(
            User.api_key == token, User.active)) if token else None
        if not user or "api.access" not in role_perms(user.role):
            return jsonify(error="unauthorized"), 401
        g.user = user
        return f(*args, **kwargs)
    return wrapper


def asset_json(a):
    return {
        "id": a.id, "tag": a.tag, "name": a.name,
        "category": a.category.name if a.category else None,
        "type": a.asset_type, "serial": a.serial,
        "manufacturer": a.manufacturer, "model": a.model,
        "status": a.status, "condition": a.condition,
        "location": a.location.path if a.location else None,
        "department": a.department.name if a.department else None,
        "purchase_date": str(a.purchase_date) if a.purchase_date else None,
        "purchase_cost": float(a.purchase_cost) if a.purchase_cost else None,
        "current_value": a.current_value,
        "warranty_expiry": str(a.warranty_expiry) if a.warranty_expiry else None,
        "assigned_to": a.current_assignment.employee.name if a.current_assignment else None,
        "custom_fields": a.custom,
    }


@bp.get("/assets")
@api_auth
def assets():
    stmt = db.select(Asset).order_by(Asset.tag)
    if request.args.get("status"):
        stmt = stmt.where(Asset.status == request.args["status"])
    return jsonify([asset_json(a) for a in db.session.scalars(stmt.limit(500))])


@bp.get("/assets/<int:asset_id>")
@api_auth
def asset(asset_id):
    a = db.session.get(Asset, asset_id)
    if not a:
        return jsonify(error="not found"), 404
    return jsonify(asset_json(a))


@bp.post("/assets")
@api_auth
def create_asset():
    data = request.get_json(silent=True) or {}
    if not data.get("tag") or not data.get("name"):
        return jsonify(error="tag and name are required"), 400
    if db.session.scalar(db.select(Asset).where(Asset.tag == data["tag"])):
        return jsonify(error="tag already exists"), 409
    a = Asset(tag=data["tag"], name=data["name"],
              serial=data.get("serial"), status=data.get("status", "Available"))
    db.session.add(a)
    db.session.commit()
    return jsonify(asset_json(a)), 201


@bp.get("/employees")
@api_auth
def employees():
    return jsonify([
        {"id": e.id, "name": e.name, "email": e.email,
         "department": e.department.name if e.department else None,
         "assets": [a.tag for a in e.current_assets]}
        for e in db.session.scalars(db.select(Employee).order_by(Employee.name))])


@bp.get("/licenses")
@api_auth
def licenses():
    return jsonify([
        {"id": l.id, "name": l.name, "seats": l.seats, "seats_used": l.seats_used,
         "compliant": l.compliant,
         "expiry_date": str(l.expiry_date) if l.expiry_date else None}
        for l in db.session.scalars(db.select(License).order_by(License.name))])
