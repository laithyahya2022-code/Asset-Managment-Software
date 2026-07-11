import os
import shutil
from datetime import datetime

from flask import Flask, g, redirect, request, session, url_for

from .i18n import LANGS, t
from .models import (DEFAULT_ROLE_PERMS, PERMISSIONS, ROLES, Notification,
                     RolePermission, User, db)
from .security import has_perm, load_user
from .utils import get_setting


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    database_url = os.environ.get("DATABASE_URL", "")
    if "://" not in database_url:
        database_url = "sqlite:///" + os.path.join(app.instance_path, "itam.sqlite")
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-me"),
        SQLALCHEMY_DATABASE_URI=database_url,
        UPLOAD_FOLDER=os.environ.get("UPLOAD_FOLDER",
                                     os.path.join(app.instance_path, "uploads")),
        BACKUP_FOLDER=os.environ.get("BACKUP_FOLDER",
                                     os.path.join(app.instance_path, "backups")),
        MAX_CONTENT_LENGTH=32 * 1024 * 1024,
        PERMANENT_SESSION_LIFETIME=3600 * 12,
    )
    if test_config:
        app.config.update(test_config)

    for d in (app.instance_path, app.config["UPLOAD_FOLDER"], app.config["BACKUP_FOLDER"]):
        os.makedirs(d, exist_ok=True)

    db.init_app(app)

    from .blueprints import admin, api, assets, auth, main, operations, org, reports
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(assets.bp)
    app.register_blueprint(operations.bp)
    app.register_blueprint(org.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(api.bp)

    @app.before_request
    def before():
        load_user()
        g.lang = session.get("lang") or (g.user.language if g.user else "en")
        _auto_backup(app)

    @app.get("/lang/<code>")
    def set_lang(code):
        if code in LANGS:
            session["lang"] = code
            if g.user:
                g.user.language = code
                db.session.commit()
        return redirect(request.referrer or url_for("main.dashboard"))

    app.jinja_env.globals.update(t=t, has_perm=has_perm)

    @app.context_processor
    def inject():
        unread = 0
        if g.get("user"):
            unread = db.session.scalar(
                db.select(db.func.count(Notification.id)).where(Notification.read == False)  # noqa: E712
            ) or 0
        return dict(t=t, has_perm=has_perm, app_name=get_setting("app_name"),
                    unread_count=unread, LANGS=LANGS, now=datetime.utcnow())

    with app.app_context():
        db.create_all()
        _ensure_defaults()

    @app.cli.command("seed")
    def seed_command():
        from .seed import seed
        seed()
        print("Database seeded. Login: admin / admin123")

    return app


_last_backup_check = [0.0]


def _auto_backup(app, keep=14):
    """Daily automatic SQLite backup, checked at most once per hour."""
    import time
    now = time.time()
    if now - _last_backup_check[0] < 3600:
        return
    _last_backup_check[0] = now
    try:
        if get_setting("backup_auto") != "1":
            return
        uri = app.config["SQLALCHEMY_DATABASE_URI"]
        if not uri.startswith("sqlite:///"):
            return
        src = uri.replace("sqlite:///", "")
        if not os.path.exists(src):
            return
        folder = app.config["BACKUP_FOLDER"]
        backups = sorted(f for f in os.listdir(folder)
                         if f.startswith("auto-") and f.endswith(".sqlite"))
        newest_age = (now - os.path.getmtime(os.path.join(folder, backups[-1]))
                      if backups else 1e12)
        if newest_age < 24 * 3600:
            return
        name = f"auto-{datetime.utcnow():%Y%m%d-%H%M%S}.sqlite"
        shutil.copy2(src, os.path.join(folder, name))
        for old in backups[:max(0, len(backups) + 1 - keep)]:
            os.remove(os.path.join(folder, old))
    except Exception:
        pass  # backups must never break a request


def _ensure_defaults():
    # role -> permission matrix
    if not db.session.scalar(db.select(RolePermission).limit(1)):
        for role in ROLES:
            for perm in DEFAULT_ROLE_PERMS[role]:
                db.session.add(RolePermission(role=role, permission=perm))
    # first-run admin account
    if not db.session.scalar(db.select(User).limit(1)):
        admin = User(username="admin", name="Administrator",
                     email="admin@example.com", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
    db.session.commit()
