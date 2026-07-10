import secrets
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for

from .models import RolePermission, User, db

_perm_cache = {}


def role_perms(role):
    if role not in _perm_cache:
        _perm_cache[role] = {
            p.permission
            for p in db.session.scalars(
                db.select(RolePermission).where(RolePermission.role == role)
            )
        }
    return _perm_cache[role]


def clear_perm_cache():
    _perm_cache.clear()


def has_perm(perm):
    return g.user is not None and perm in role_perms(g.user.role)


def load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        user = db.session.get(User, uid)
        if user and user.active:
            g.user = user


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


def perm_required(perm):
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("auth.login", next=request.path))
            if not has_perm(perm):
                flash("You do not have permission to do that.", "error")
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return deco


def new_token():
    return secrets.token_urlsafe(32)
