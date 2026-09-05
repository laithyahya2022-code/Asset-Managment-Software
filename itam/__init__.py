import os
import shutil
from datetime import datetime

from flask import Flask, g, redirect, render_template, request, session, url_for

APP_VERSION = "2026.09.05.67"  # bumped on each release so users can confirm their build

from .i18n import LANGS, t, translate_html
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

    # SQLite lets a writer wait a few seconds for the lock, then gives up. A
    # second AMS.exe left running (or a slow disk) then turned every save
    # into an Internal Server Error. Waiting longer costs nothing and rides
    # out the moment instead.
    app.config.setdefault("SQLALCHEMY_ENGINE_OPTIONS", {})
    app.config["SQLALCHEMY_ENGINE_OPTIONS"].setdefault(
        "connect_args", {}).setdefault("timeout", 30)

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

    # Every unhandled exception lands in instance/error.log with a full
    # traceback. The packaged app has no console, so without this a crash
    # is just a blank "Internal Server Error" with nothing to diagnose.
    if not app.testing:
        import logging
        from logging.handlers import RotatingFileHandler
        try:
            handler = RotatingFileHandler(
                os.path.join(app.instance_path, "error.log"),
                maxBytes=512_000, backupCount=2, encoding="utf-8")
            handler.setLevel(logging.WARNING)
            handler.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s"))
            app.logger.addHandler(handler)
            logging.getLogger("waitress").addHandler(handler)
        except OSError:
            pass

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

    @app.errorhandler(500)
    def server_error(e):
        """A crash becomes a page that says what went wrong and what to do.

        The common field failures -- a second AMS.exe locking the database,
        the database file marked read-only after a manual copy, a full disk
        -- each get their own instruction instead of a bare error.
        """
        original = getattr(e, "original_exception", None)
        detail = f"{type(original).__name__}: {original}" if original else ""
        low = detail.lower()
        if "locked" in low:
            hint = ("The database is locked by another running copy of AMS. "
                    "Open Task Manager, end every AMS.exe you find, then "
                    "start the app once — or simply restart the computer.")
        elif "readonly" in low or "read-only" in low or "permission" in low:
            hint = ("The database cannot be written. Right-click "
                    "C:\\ProgramData\\AMS\\instance\\itam.sqlite → Properties "
                    "and clear the Read-only box, and make sure the app is "
                    "allowed to write in that folder.")
        elif "no space" in low or ("disk" in low and "full" in low):
            hint = "The disk is full — free some space and try again."
        else:
            hint = ""
        try:
            return render_template("errors/500.html",
                                   detail=detail, hint=hint), 500
        except Exception:
            return e        # even the error page failed: show the plain one

    @app.before_request
    def before():
        import time
        _last_request[0] = time.time()
        load_user()
        g.lang = session.get("lang") or (g.user.language if g.user else "en")
        g.theme = (session.get("theme")
                   or (g.user.theme if g.user else None) or "dark")
        _auto_backup(app)

    @app.after_request
    def arabic(response):
        """Translate the finished page when the user is reading Arabic."""
        if (getattr(g, "lang", "en") == "ar"
                and response.content_type
                and response.content_type.startswith("text/html")
                and response.direct_passthrough is False):
            body = response.get_data(as_text=True)
            response.set_data(translate_html(body))
        return response

    @app.get("/lang/<code>")
    def set_lang(code):
        if code in LANGS:
            session["lang"] = code
            if g.user:
                g.user.language = code
                db.session.commit()
        return redirect(request.referrer or url_for("main.dashboard"))

    @app.get("/theme/<mode>")
    def set_theme(mode):
        if mode in ("dark", "light"):
            session["theme"] = mode
            if g.user:
                g.user.theme = mode
                db.session.commit()
        return redirect(request.referrer or url_for("main.dashboard"))

    from .utils import code128_svg
    app.jinja_env.globals.update(t=t, has_perm=has_perm, code128=code128_svg)

    @app.context_processor
    def inject():
        unread = 0
        if g.get("user"):
            unread = db.session.scalar(
                db.select(db.func.count(Notification.id)).where(Notification.read == False)  # noqa: E712
            ) or 0
        short, full = app_name_parts()
        return dict(t=t, has_perm=has_perm, app_name=get_setting("app_name"),
                    rail_counts=_rail_counts() if g.get("user") else {},
                    app_short=short, app_full=full,
                    label_org=get_setting("label_org"),
                    update_pending=get_setting("update_pending"),
                    unread_count=unread, LANGS=LANGS, now=datetime.utcnow(),
                    app_version=APP_VERSION)

    with app.app_context():
        db.create_all()
        _sync_schema()
        _ensure_defaults()
        # An applied update leaves its "ready" note behind; drop it once the
        # running build is no longer older than the advertised one.
        pending = get_setting("update_pending")
        if pending:
            from . import updater
            if not updater.is_newer(pending, APP_VERSION):
                from .utils import set_setting
                set_setting("update_pending", "")
                db.session.commit()
        _start_update_check(app)

    @app.cli.command("seed")
    def seed_command():
        from .seed import seed
        seed()
        print("Database seeded. Login: admin / admin123")

    return app


_update_checked = [False]

#: Wall-clock time of the most recent HTTP request, so the auto-updater can
#: install at a quiet moment instead of under someone's hands.
_last_request = [0.0]


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
        import time

        from . import updater
        base = os.path.dirname(sys.executable)
        # Check on startup and then every 30 minutes: a server that runs for
        # weeks would otherwise only ever see the releases that existed the
        # moment it started.
        while True:
            try:
                status = updater.check_for_update(
                    get_setting("update_repo"), APP_VERSION, base,
                    token=get_setting("update_token") or None)
                if status in ("downloaded", "pending"):
                    if status == "downloaded":
                        release = updater.latest_release(
                            get_setting("update_repo"),
                            get_setting("update_token") or None)
                        version = updater.remote_version(
                            release, get_setting("update_token") or None) or "newer"
                        with app.app_context():
                            from .utils import set_setting
                            set_setting("update_pending", version)
                            db.session.commit()
                    # Install like a real app: wait until nobody has used the
                    # site for ten minutes, then swap the executable and
                    # restart. On success restart_into_update never returns;
                    # a failed swap just tries again at the next quiet moment.
                    while True:
                        time.sleep(60)
                        if time.time() - _last_request[0] > 600:
                            updater.restart_into_update(base)
            except Exception:
                pass      # an update check must never disturb the app
            time.sleep(1800)

    threading.Thread(target=run, daemon=True).start()


_rail_cache = {"at": 0.0, "counts": {}}


def _rail_counts():
    """Record counts for the navigation rail, refreshed at most once a minute.

    Eight COUNT queries are cheap, but not per page load for every user, so
    the numbers may lag by up to sixty seconds. They are wayfinding, not data.
    """
    import time

    from .models import (Asset, Assignment, Employee, License, Location,
                         Maintenance, User, Vendor)
    now = time.time()
    if now - _rail_cache["at"] > 60:
        try:
            _rail_cache["counts"] = {
                "assets": db.session.scalar(db.select(db.func.count(Asset.id))) or 0,
                # People holding devices plus shared devices held by a
                # class/room — everything the Lending screen lists.
                "loans": (db.session.scalar(
                    db.select(db.func.count(Assignment.id))
                    .where(Assignment.returned_at.is_(None))) or 0) +
                (db.session.scalar(
                    db.select(db.func.count(Asset.id))
                    .where(Asset.notes.contains("Assigned to: "),
                           ~Asset.assignments.any(
                               Assignment.returned_at.is_(None)))) or 0),
                "maintenance": db.session.scalar(
                    db.select(db.func.count(Maintenance.id))
                    .where(Maintenance.status != "Completed")) or 0,
                "licenses": db.session.scalar(db.select(db.func.count(License.id))) or 0,
                # Distinct place names, not tree nodes: the same room under
                # every floor of every building would otherwise count once
                # per combination and read as "600 locations".
                "locations": db.session.scalar(
                    db.select(db.func.count(db.func.distinct(Location.name)))) or 0,
                "vendors": db.session.scalar(db.select(db.func.count(Vendor.id))) or 0,
                "employees": db.session.scalar(
                    db.select(db.func.count(Employee.id)).where(Employee.active)) or 0,
                "users": db.session.scalar(db.select(db.func.count(User.id))) or 0,
            }
            _rail_cache["at"] = now
        except Exception:
            return _rail_cache["counts"]   # mid-migration; stale is fine
    return _rail_cache["counts"]


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
    # The GitHub repository was renamed. Installs that saved the old path keep
    # asking for it; GitHub redirects renamed repos, but that stops the moment
    # anything else claims the old name, so move them to the new one. A repo
    # the school pointed elsewhere themselves is left alone.
    row = db.session.get(Setting, "update_repo")
    if row is not None and row.value == "laithyahya2022-code/IT-Asset-Management-System-":
        row.value = DEFAULT_SETTINGS["update_repo"]
    # The school measured their Xprinter label stock at 2.46 × 1.57 in
    # (62.5 × 39.9 mm) in their label design tool and asked for the app to
    # print at exactly that size. Applied once; a size changed in Settings
    # after this update is left alone.
    if db.session.get(Setting, "label_stock_246_applied") is None:
        for key, value in (("label_width_mm", "62.5"),
                           ("label_height_mm", "39.9")):
            row = db.session.get(Setting, key)
            if row is None:
                db.session.add(Setting(key=key, value=value))
            else:
                row.value = value
        db.session.add(Setting(key="label_stock_246_applied", value="1"))
    # first-run admin account
    if not db.session.scalar(db.select(User).limit(1)):
        admin = User(username="admin", name="Administrator",
                     email="admin@example.com", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
    # Categories a school actually has. Without these a fresh install opened
    # with an empty Category list, and since the Asset ID is generated from
    # the category, there was no way to add a properly numbered asset until
    # someone worked out they had to go and create categories first.
    # Only ever seeded into an empty table, so nobody's own list is touched.
    from .models import Category, Department, Location
    if not db.session.scalar(db.select(Category).limit(1)):
        for name, prefix in DEFAULT_CATEGORIES:
            db.session.add(Category(name=name, prefix=prefix))
    # Same reasoning for departments: the asset and employee forms both offer
    # one, and both opened with nothing to choose.
    from .models import DEFAULT_DEPARTMENTS
    if not db.session.scalar(db.select(Department).limit(1)):
        for name in DEFAULT_DEPARTMENTS:
            db.session.add(Department(name=name))
    # And the school's Branch / Building / Floor / Room tree, so Locations and
    # "Transfer to location" are usable from the first minute.
    if not db.session.scalar(db.select(Location).limit(1)):
        _seed_locations()
    db.session.commit()


def _seed_locations():
    """The standard Branch → Building → Floor → Room tree, built once."""
    from .models import BRANCHES, BUILDINGS, FLOORS, PLACES, Location

    for branch_name in BRANCHES:
        branch = Location(name=branch_name, kind="Branch")
        db.session.add(branch)
        db.session.flush()
        for building_name in BUILDINGS:
            building = Location(name=building_name, kind="Building",
                                parent_id=branch.id)
            db.session.add(building)
            db.session.flush()
            for floor_name in FLOORS:
                floor = Location(name=floor_name, kind="Floor",
                                 parent_id=building.id)
                db.session.add(floor)
                db.session.flush()
                for room_name in PLACES:
                    db.session.add(Location(name=room_name, kind="Room",
                                            parent_id=floor.id))


#: (name, Asset ID prefix) seeded on a brand-new database only.
DEFAULT_CATEGORIES = [
    ("Desktop Computers", "PC"), ("Laptops", "LT"), ("Servers", "SRV"),
    ("Monitors", "MN"), ("Printers", "PRN"), ("Projectors", "PRJ"),
    ("Scanners", "SCN"), ("Tablets", "TAB"), ("Phones", "PH"),
    ("Telephones", "TEL"), ("Switches", "SW"), ("Routers", "RTR"),
    ("Access Points", "AP"), ("Firewalls", "FW"), ("UPS Devices", "UPS"),
    ("CCTV", "CCTV"), ("Networking", "NET"), ("Peripherals", "PER"),
    ("Accessories", "ACC"), ("Software Licenses", "SL"), ("Other", "AST"),
]
