import os
import shutil
from datetime import datetime

from flask import (Blueprint, current_app, flash, g, redirect, render_template,
                   request, send_from_directory, url_for)

from ..models import (PERMISSIONS, ROLES, RolePermission, User, db)
from ..security import clear_perm_cache, new_token, perm_required
from ..utils import DEFAULT_SETTINGS, get_setting, log_activity, set_setting

bp = Blueprint("admin", __name__, url_prefix="/admin")


# ------------------------------------------------------------------ users

@bp.route("/users")
@perm_required("admin.users")
def users():
    rows = db.session.scalars(db.select(User).order_by(User.username)).all()
    return render_template("admin/users.html", rows=rows)


@bp.route("/users/new", methods=["GET", "POST"])
@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@perm_required("admin.users")
def user_form(user_id=None):
    user = db.get_or_404(User, user_id) if user_id else None
    if request.method == "POST":
        username = request.form["username"].strip().lower()
        email = request.form["email"].strip().lower()
        clash = db.session.scalar(db.select(User).where(
            db.or_(User.username == username, User.email == email)))
        if clash and (not user or clash.id != user.id):
            flash("Username or email already in use.", "error")
        else:
            creating = user is None
            if creating:
                user = User()
                db.session.add(user)
            user.username = username
            user.name = request.form["name"].strip()
            user.email = email
            if request.form.get("role") in ROLES:
                user.role = request.form["role"]
            user.active = request.form.get("active") == "1"
            if request.form.get("password"):
                if len(request.form["password"]) < 8:
                    flash("Password must be at least 8 characters.", "error")
                    return render_template("admin/user_form.html", user=user, roles=ROLES)
                user.set_password(request.form["password"])
            elif creating:
                flash("A password is required for new users.", "error")
                return render_template("admin/user_form.html", user=None, roles=ROLES)
            db.session.flush()
            log_activity("user_created" if creating else "user_updated",
                         "user", user.id, user.username)
            db.session.commit()
            flash(f"User {user.username} saved.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/user_form.html", user=user, roles=ROLES)


@bp.post("/users/<int:user_id>/apikey")
@perm_required("admin.users")
def user_apikey(user_id):
    user = db.get_or_404(User, user_id)
    user.api_key = new_token()
    log_activity("api_key_generated", "user", user.id, user.username)
    db.session.commit()
    flash(f"New API key for {user.username}: {user.api_key}", "success")
    return redirect(url_for("admin.users"))


@bp.post("/users/<int:user_id>/delete")
@perm_required("admin.users")
def user_delete(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == g.user.id:
        flash("You cannot delete your own account.", "error")
    else:
        log_activity("user_deleted", "user", user.id, user.username)
        db.session.delete(user)
        db.session.commit()
        flash("User deleted.", "success")
    return redirect(url_for("admin.users"))


# ------------------------------------------------------------------ roles

@bp.route("/roles", methods=["GET", "POST"])
@perm_required("admin.users")
def roles():
    if request.method == "POST":
        db.session.execute(db.delete(RolePermission))
        for role in ROLES:
            perms = request.form.getlist(f"perm_{role}")
            if role == "admin":
                perms = PERMISSIONS  # admin always has everything
            for p in perms:
                if p in PERMISSIONS:
                    db.session.add(RolePermission(role=role, permission=p))
        clear_perm_cache()
        log_activity("roles_updated", "role", None)
        db.session.commit()
        flash("Role permissions updated.", "success")
        return redirect(url_for("admin.roles"))
    matrix = {role: {p.permission for p in db.session.scalars(
        db.select(RolePermission).where(RolePermission.role == role))} for role in ROLES}
    return render_template("admin/roles.html", roles=ROLES,
                           permissions=PERMISSIONS, matrix=matrix)


# ---------------------------------------------------------------- settings

SETTING_GROUPS = {
    "General": ["app_name", "qr_prefix", "custom_asset_fields", "checkout_days"],
    "Email": ["email_enabled", "smtp_host", "smtp_port", "smtp_user",
              "smtp_password", "smtp_from"],
    "Backup & Audit": ["backup_auto", "audit_retention_days"],
}


@bp.route("/settings", methods=["GET", "POST"])
@perm_required("admin.settings")
def settings():
    keys = [k for group in SETTING_GROUPS.values() for k in group]
    if request.method == "POST":
        for key in keys:
            if key in ("email_enabled", "backup_auto"):
                set_setting(key, "1" if request.form.get(key) else "0")
            else:
                set_setting(key, request.form.get(key, "").strip())
        log_activity("settings_updated", "setting", None)
        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("admin.settings"))
    values = {k: get_setting(k) for k in keys}
    return render_template("admin/settings.html", groups=SETTING_GROUPS, values=values)


# ----------------------------------------------------------------- backups

def _db_path():
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    return uri.replace("sqlite:///", "") if uri.startswith("sqlite:///") else None


@bp.route("/backups")
@perm_required("admin.settings")
def backups():
    folder = current_app.config["BACKUP_FOLDER"]
    files = sorted(os.listdir(folder), reverse=True) if os.path.isdir(folder) else []
    files = [(f, os.path.getsize(os.path.join(folder, f))) for f in files
             if f.endswith(".sqlite")]
    return render_template("admin/backups.html", files=files, sqlite=_db_path() is not None)


@bp.post("/backups/create")
@perm_required("admin.settings")
def backup_create():
    src = _db_path()
    if not src or not os.path.exists(src):
        flash("Automatic file backup works with SQLite. For PostgreSQL use pg_dump.", "error")
        return redirect(url_for("admin.backups"))
    name = f"backup-{datetime.utcnow():%Y%m%d-%H%M%S}.sqlite"
    shutil.copy2(src, os.path.join(current_app.config["BACKUP_FOLDER"], name))
    log_activity("backup_created", "backup", None, name)
    db.session.commit()
    flash(f"Backup {name} created.", "success")
    return redirect(url_for("admin.backups"))


@bp.route("/backups/<name>/download")
@perm_required("admin.settings")
def backup_download(name):
    return send_from_directory(current_app.config["BACKUP_FOLDER"],
                               os.path.basename(name), as_attachment=True)


@bp.post("/backups/<name>/restore")
@perm_required("admin.settings")
def backup_restore(name):
    src = os.path.join(current_app.config["BACKUP_FOLDER"], os.path.basename(name))
    dst = _db_path()
    if not dst or not os.path.exists(src):
        flash("Restore is only available for SQLite databases.", "error")
        return redirect(url_for("admin.backups"))
    db.session.remove()
    db.engine.dispose()
    shutil.copy2(src, dst)
    flash(f"Database restored from {os.path.basename(name)}.", "success")
    return redirect(url_for("admin.backups"))


@bp.post("/backups/<name>/delete")
@perm_required("admin.settings")
def backup_delete(name):
    path = os.path.join(current_app.config["BACKUP_FOLDER"], os.path.basename(name))
    if os.path.exists(path):
        os.remove(path)
        flash("Backup deleted.", "success")
    return redirect(url_for("admin.backups"))
