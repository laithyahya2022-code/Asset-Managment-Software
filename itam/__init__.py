import os
import shutil
from datetime import datetime

from flask import Flask, g, redirect, request, session, url_for

APP_VERSION = "2026.08.01.5"  # bumped on each release so users can confirm their build

from .i18n import LANGS, t
from .models import (DEFAULT_ROLE_PERMS, PERMISSIONS, ROLES, Notification,
                     RolePermission, Setting, User, db)
from .security import has_perm, load_user
from .utils import DEFAULT_SETTINGS, app_name_parts, get_setting


def _secret_key(instance_path):
    """A per-installation session key, generated once and kept in instance/.

    This used to fall back to a fixed "dev-change-me" unless an administrator
    remembered to set SECRET_KEY by hand, which meant a shared install signed
    its session cookies with a value published in the source. Anyone who could
    reach the app could forge one. Generate a real key on first run instead;
    SECRET_KEY in the environment still wins for anyone managing it centrally.

    Keeping it in instance/ means it survives updates along with the data, so
    an upgrade never logs everybody out.
    """
    import secrets

    path = os.path.join(instance_path, "secret_key")
    try:
        os.makedirs(instance_path, exist_ok=True)
        if os.path.exists(path):
            key = open(path, encoding="ascii").read().strip()
            if len(key) >= 32:
                return key
        key = secrets.token_urlsafe(48)
        with open(path, "w", encoding="ascii") as fh:
            fh.write(key)
        try:                      # best effort: keep it out of other accounts
            os.chmod(path, 0o600)
        except OSError:
            pass
        return key
    except OSError:
        # A read-only or unwritable instance folder must not stop the app; a
        # per-process key just means sessions end when the app restarts.
        return secrets.token_urlsafe(48)


def create_app(test_config=None, instance_path=None):
    app = Flask(__name__, instance_relative_config=True, instance_path=instance_path)
    database_url = os.environ.get("DATABASE_URL", "")
    if "://" not in database_url:
        database_url = "sqlite:///" + os.path.join(app.instance_path, "itam.sqlite")
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or _secret_key(app.instance_path),
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

    # When served behind a reverse proxy (Caddy / Nginx / IIS) that terminates
    # HTTPS for a domain like https://itam.yourschool.edu, trust the standard
    # forwarded headers so redirects and generated links use the right
    # scheme/host. Enabled by default; harmless for direct LAN access.
    # ITAM_BEHIND_PROXY is the pre-rename spelling, still honoured.
    if os.environ.get("AMS_BEHIND_PROXY",
                      os.environ.get("ITAM_BEHIND_PROXY", "1")) == "1":
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

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
        short, full = app_name_parts()
        return dict(t=t, has_perm=has_perm, app_name=get_setting("app_name"),
                    app_short=short, app_full=full,
                    label_org=get_setting("label_org"),
                    update_pending=get_setting("update_pending"),
                    unread_count=unread, LANGS=LANGS, now=datetime.utcnow(),
                    app_version=APP_VERSION)

    with app.app_context():
        db.create_all()
        _sync_schema()
        _ensure_defaults()
        _start_update_check(app)

    @app.cli.command("seed")
    def seed_command():
        from .seed import seed
        seed()
        print("Database seeded. Login: admin / admin123")

    return app


_update_checked = [False]


def _start_update_check(app):
    """Look for a newer build in the background, once per run.

    Only the packaged executable can update itself, so this is a no-op when
    running from source. It never blocks startup and never raises: a school PC
    with no internet, or a check that fails for any other reason, just carries
    on with the build it has.
    """
    import sys
    import threading

    if _update_checked[0] or not getattr(sys, "frozen", False):
        return
    if get_setting("update_auto") != "1":
        return
    _update_checked[0] = True

    def run():
        from . import updater
        base = os.path.dirname(sys.executable)
        try:
            status = updater.check_for_update(
                get_setting("update_repo"), APP_VERSION, base,
                token=get_setting("update_token") or None)
            if status != "downloaded":
                return
            release = updater.latest_release(get_setting("update_repo"),
                                             get_setting("update_token") or None)
            version = updater.remote_version(
                release, get_setting("update_token") or None) or "newer"
            with app.app_context():
                from .utils import set_setting
                set_setting("update_pending", version)
                db.session.commit()
        except Exception:
            pass          # an update check must never disturb the app

    threading.Thread(target=run, daemon=True).start()


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


def _sync_schema():
    """Add columns that later releases introduced to an existing database.

    db.create_all() only ever creates missing *tables*, so upgrading the app
    over a database made by an older build leaves the new columns absent and
    almost every page fails with "no such column". Compare each mapped table
    against the live database and ALTER in whatever is missing. Adding a
    column is non-destructive: existing rows get NULL (or the column default).

    Anything this cannot express safely is skipped and reported rather than
    risking a half-applied schema; renames and drops are deliberately not
    handled, since guessing at those could lose data.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    added, skipped = [], []

    for table in db.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # create_all() just made it, so it is already current
        present = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in present:
                continue
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" ' \
                  f"{column.type.compile(db.engine.dialect)}"
            default = getattr(column.default, "arg", None)
            if not column.nullable:
                # SQLite refuses a NOT NULL column without a usable default.
                if default is None or callable(default):
                    skipped.append(f"{table.name}.{column.name}")
                    continue
                literal = f"'{default}'" if isinstance(default, str) else default
                ddl += f" NOT NULL DEFAULT {literal}"
            elif default is not None and not callable(default):
                literal = f"'{default}'" if isinstance(default, str) else default
                ddl += f" DEFAULT {literal}"
            try:
                with db.engine.begin() as conn:
                    conn.execute(text(ddl))
                added.append(f"{table.name}.{column.name}")
            except Exception as exc:                     # pragma: no cover
                skipped.append(f"{table.name}.{column.name} ({exc.__class__.__name__})")

    if added:
        print(f"Database updated: added {len(added)} column(s) — {', '.join(added)}")
    if skipped:
        print(f"Database: could not add {', '.join(skipped)} automatically.")
    return added, skipped


def _ensure_defaults():
    # role -> permission matrix
    if not db.session.scalar(db.select(RolePermission).limit(1)):
        for role in ROLES:
            for perm in DEFAULT_ROLE_PERMS[role]:
                db.session.add(RolePermission(role=role, permission=perm))
    # Carry the ITAM -> AMS rename onto installs that had already saved the old
    # name into their settings. A name the school chose themselves is left alone.
    row = db.session.get(Setting, "app_name")
    if row is not None and row.value in ("ITAM Enterprise", "ITAM"):
        row.value = DEFAULT_SETTINGS["app_name"]
    # first-run admin account
    if not db.session.scalar(db.select(User).limit(1)):
        admin = User(username="admin", name="Administrator",
                     email="admin@example.com", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
    db.session.commit()
