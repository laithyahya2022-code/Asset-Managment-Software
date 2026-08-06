from datetime import date, datetime, timedelta

from flask import (Blueprint, flash, make_response, redirect, render_template,
                   request, url_for)
from sqlalchemy import func, or_

from ..models import (ASSET_STATUSES, ActivityLog, Asset, Assignment, Category,
                      Employee, License, Maintenance, Notification,
                      Vendor, db)
from ..security import login_required, perm_required
from ..models import Department
from ..utils import (bar_chart, donut_chart, get_setting, line_chart,
                     month_key, notify)

bp = Blueprint("main", __name__)

# The five handoff status tones, extended to the app's full status list with
# neighbours on the same low-chroma lightness step.
STATUS_COLORS = {
    "Available": "#b8c95e", "Checked Out": "#7fa6f2", "In Use": "#9db1ea",
    "Reserved": "#b3a1e8", "In Storage": "#6ec4bc", "Under Maintenance": "#e0a94f",
    "Lost": "#e8886a", "Damaged": "#e8886a", "Missing": "#e8886a",
    "Retired": "#98958a", "Disposed": "#7c796e",
}


def _alert_days(key, default):
    try:
        return int(get_setting(key) or default)
    except ValueError:
        return default


def _generate_alerts():
    """Create in-app notifications for warranty/license/maintenance/overdue items."""
    today = date.today()
    horizon = today + timedelta(days=_alert_days("warranty_alert_days", 90))
    lic_horizon = today + timedelta(days=_alert_days("license_alert_days", 90))
    for a in db.session.scalars(db.select(Asset).where(
            Asset.warranty_expiry.isnot(None), Asset.warranty_expiry <= horizon,
            Asset.status.notin_(["Retired", "Disposed"]))):
        state = "expired" if a.warranty_expiry < today else "expires soon"
        notify("Warranty", f"Warranty for {a.tag} ({a.name}) {state} ({a.warranty_expiry})",
               link=url_for("assets.detail", asset_id=a.id),
               dedupe_key=f"warr-{a.id}-{a.warranty_expiry}")
    for lic in db.session.scalars(db.select(License).where(
            License.expiry_date.isnot(None), License.expiry_date <= lic_horizon)):
        state = "expired" if lic.expiry_date < today else "expires soon"
        notify("License", f"License {lic.name} {state} ({lic.expiry_date})",
               link=url_for("ops.license_detail", license_id=lic.id),
               dedupe_key=f"lic-{lic.id}-{lic.expiry_date}")
    for m in db.session.scalars(db.select(Maintenance).where(
            Maintenance.status == "Scheduled", Maintenance.scheduled_for.isnot(None),
            Maintenance.scheduled_for <= today + timedelta(days=7))):
        notify("Maintenance", f"Maintenance due: {m.title} ({m.asset.tag}) on {m.scheduled_for}",
               link=url_for("ops.maintenance_list"),
               dedupe_key=f"mnt-{m.id}-{m.scheduled_for}")
    for asg in db.session.scalars(db.select(Assignment).where(
            Assignment.returned_at.is_(None), Assignment.due_at.isnot(None),
            Assignment.due_at < today)):
        notify("Assignment", f"Overdue: {asg.asset.tag} with {asg.employee.name} "
                             f"(due {asg.due_at})",
               link=url_for("assets.detail", asset_id=asg.asset_id),
               dedupe_key=f"due-{asg.id}-{asg.due_at}")
    db.session.commit()


@bp.route("/static/sw.js")
def service_worker():
    """Rendered, not static, so its cache name carries the build number.

    Registered under /static/ deliberately: a worker's scope is its own
    directory, and this one only ever answers /static/ requests. It must not
    be cached itself, or a browser could keep an old worker alive.
    """
    from .. import APP_VERSION

    resp = make_response(render_template("sw.js", app_version=APP_VERSION))
    resp.headers["Content-Type"] = "application/javascript"
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@bp.route("/welcome")
def welcome():
    """The public landing page from the design handoff.

    No sign-in required: it explains the system and routes to /login. The
    stat band uses live numbers -- they are wayfinding, not secrets, and this
    page only exists inside the school's network.
    """
    from ..i18n import t as tr
    assets = db.session.scalar(db.select(func.count(Asset.id))) or 0
    loans = db.session.scalar(db.select(func.count(Assignment.id))
                              .where(Assignment.returned_at.is_(None))) or 0
    from ..models import Location
    rooms = db.session.scalar(db.select(func.count(Location.id))
                              .where(Location.kind.in_(["Room", "Storage Area"]))) or 0
    stats = [(f"{assets:,}", tr("Assets tracked")),
             (f"{loans:,}", tr("On loan today")),
             (f"{rooms:,}", tr("Rooms & stores")),
             ("2", tr("Languages"))]
    features = [
        (tr("Scan to find"), tr("Every asset carries a QR label. Scan it with any phone and the record opens.")),
        (tr("Lending in two clicks"), tr("Check equipment out to a member of staff with a due date, and back in when it returns.")),
        (tr("Warranty watch"), tr("Expiring warranties and licenses surface on the dashboard before they lapse.")),
        (tr("Licenses beside hardware"), tr("Seats owned against seats in use, kept next to the machines they run on.")),
        (tr("Term-end inventory"), tr("Physical audits record what was verified and what is missing, room by room.")),
        (tr("Arabic and English"), tr("The whole interface mirrors to Arabic, right to left, per user.")),
    ]
    return render_template("welcome.html", stats=stats, features=features)


@bp.route("/")
@login_required
def dashboard():
    _generate_alerts()
    today = date.today()
    counts = dict(db.session.execute(
        db.select(Asset.status, func.count(Asset.id)).group_by(Asset.status)).all())
    total = sum(counts.values())
    total_value = sum(float(a.purchase_cost or 0) for a in db.session.scalars(db.select(Asset)))
    overdue = db.session.scalar(db.select(func.count(Assignment.id)).where(
        Assignment.returned_at.is_(None), Assignment.due_at.isnot(None),
        Assignment.due_at < today)) or 0
    scheduled = db.session.scalar(db.select(func.count(Maintenance.id)).where(
        Maintenance.status.in_(["Scheduled", "In Progress"]))) or 0
    expiring = db.session.scalar(db.select(func.count(Asset.id)).where(
        Asset.warranty_expiry.isnot(None), Asset.warranty_expiry >= today,
        Asset.warranty_expiry <= today + timedelta(days=90),
        Asset.status != "Retired")) or 0
    licenses = db.session.scalars(db.select(License)).all()
    active_lic = len([l for l in licenses if not l.expired])
    lic_soon = len([l for l in licenses if l.expiry_date and not l.expired
                    and l.expiry_date <= today + timedelta(days=60)])
    added_month = db.session.scalar(db.select(func.count(Asset.id)).where(
        Asset.created_at >= datetime(today.year, today.month, 1))) or 0

    by_cat = db.session.execute(
        db.select(Category.name, func.count(Asset.id))
        .join(Asset, Asset.category_id == Category.id)
        .group_by(Category.name).order_by(func.count(Asset.id).desc())).all()
    cat_chart = bar_chart([(n, c) for n, c in by_cat])
    donut = donut_chart([(s, counts.get(s, 0), STATUS_COLORS[s]) for s in ASSET_STATUSES])
    by_dept = db.session.execute(
        db.select(Department.name, func.count(Asset.id))
        .join(Asset, Asset.department_id == Department.id)
        .group_by(Department.name).order_by(func.count(Asset.id).desc())).all()
    dept_chart = bar_chart([(n, c) for n, c in by_dept], color="#7fa6f2")

    due_soon = db.session.scalars(
        db.select(Assignment).where(
            Assignment.returned_at.is_(None), Assignment.due_at.isnot(None),
            Assignment.due_at <= today + timedelta(days=7))
        .order_by(Assignment.due_at).limit(8)).all()

    recent = db.session.scalars(
        db.select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(8)).all()
    alerts = db.session.scalars(
        db.select(Notification).where(Notification.read == False)  # noqa: E712
        .order_by(Notification.created_at.desc()).limit(6)).all()

    value_short = (f"${total_value / 1000:.1f}K" if total_value >= 1000
                   else f"${total_value:,.0f}")
    return render_template(
        "dashboard.html", total=total, counts=counts, overdue=overdue,
        scheduled=scheduled, expiring=expiring, active_lic=active_lic,
        lic_soon=lic_soon, added_month=added_month, value_short=value_short,
        cat_chart=cat_chart, donut=donut, dept_chart=dept_chart,
        due_soon=due_soon, today=today, recent=recent, alerts=alerts)


@bp.route("/analytics")
@perm_required("reports.view")
def analytics():
    assets = db.session.scalars(db.select(Asset)).all()
    months = []
    cursor = date.today().replace(day=1)
    for _ in range(12):
        months.append(cursor)
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    months.reverse()

    added = [(month_key(m), len([a for a in assets
              if a.created_at.year == m.year and a.created_at.month == m.month]))
             for m in months]
    spend = [(month_key(m), sum(float(a.purchase_cost or 0) for a in assets
              if a.purchase_date and a.purchase_date.year == m.year
              and a.purchase_date.month == m.month)) for m in months]
    mnt = db.session.scalars(db.select(Maintenance)).all()
    mnt_cost = [(month_key(m), sum(float(x.cost or 0) for x in mnt
                 if x.completed_at and x.completed_at.year == m.year
                 and x.completed_at.month == m.month)) for m in months]

    by_dept = {}
    for a in assets:
        key = a.department.name if a.department else "Unassigned"
        d = by_dept.setdefault(key, {"count": 0, "cost": 0.0, "value": 0.0})
        d["count"] += 1
        d["cost"] += float(a.purchase_cost or 0)
        d["value"] += a.current_value or 0
    dept_rows = sorted(by_dept.items(), key=lambda kv: -kv[1]["cost"])

    util = 0
    active_assets = [a for a in assets if a.status != "Retired"]
    if active_assets:
        util = round(100 * len([a for a in active_assets if a.status == "Checked Out"])
                     / len(active_assets))
    return render_template("analytics.html",
                           added_chart=line_chart(added),
                           spend_chart=line_chart(spend, color="#7fa6f2", money=True),
                           mnt_chart=line_chart(mnt_cost, color="#e0a94f", money=True),
                           dept_rows=dept_rows, utilization=util)


@bp.route("/search")
@login_required
def search():
    q = request.args.get("q", "").strip()
    results = {}
    if q:
        like = f"%{q}%"
        results["assets"] = db.session.scalars(db.select(Asset).where(or_(
            Asset.tag.ilike(like), Asset.name.ilike(like), Asset.serial.ilike(like),
            Asset.manufacturer.ilike(like), Asset.model.ilike(like))).limit(25)).all()
        results["employees"] = db.session.scalars(db.select(Employee).where(or_(
            Employee.name.ilike(like), Employee.email.ilike(like))).limit(15)).all()
        results["licenses"] = db.session.scalars(db.select(License).where(
            License.name.ilike(like)).limit(15)).all()
        results["vendors"] = db.session.scalars(db.select(Vendor).where(
            Vendor.name.ilike(like)).limit(15)).all()
    return render_template("search.html", q=q, results=results)


@bp.route("/notifications")
@login_required
def notifications():
    items = db.session.scalars(
        db.select(Notification).order_by(Notification.created_at.desc()).limit(200)).all()
    return render_template("notifications.html", items=items)


@bp.post("/notifications/read")
@login_required
def notifications_read():
    nid = request.form.get("id")
    stmt = db.update(Notification).values(read=True)
    if nid:
        stmt = stmt.where(Notification.id == int(nid))
    db.session.execute(stmt)
    db.session.commit()
    return redirect(request.referrer or url_for("main.notifications"))


@bp.route("/activity")
@login_required
def activity():
    action = request.args.get("action", "")
    stmt = db.select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(300)
    if action:
        stmt = db.select(ActivityLog).where(ActivityLog.action == action) \
            .order_by(ActivityLog.created_at.desc()).limit(300)
    logs = db.session.scalars(stmt).all()
    actions = [r[0] for r in db.session.execute(
        db.select(ActivityLog.action).distinct().order_by(ActivityLog.action)).all()]
    return render_template("activity.html", logs=logs, actions=actions, action=action)


@bp.route("/scanner")
@login_required
def scanner():
    return render_template("scanner.html")


@bp.route("/scan-go")
@login_required
def scan_go():
    code = request.args.get("code", "").strip()
    asset = db.session.scalar(db.select(Asset).where(
        or_(Asset.tag == code, Asset.serial == code)))
    if asset:
        return redirect(url_for("assets.detail", asset_id=asset.id))
    flash(f'No asset found for code "{code}".', "error")
    return redirect(url_for("main.scanner"))
