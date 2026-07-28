import csv
import io
import smtplib
from datetime import datetime
from email.message import EmailMessage

from flask import Response, g, request
from markupsafe import Markup

from .models import ActivityLog, Notification, Setting, db

# ------------------------------------------------------------------ settings

DEFAULT_SETTINGS = {
    "app_name": "Mada Asset Management System (AMS)",
    "qr_prefix": "",
    "smtp_host": "", "smtp_port": "587", "smtp_user": "", "smtp_password": "",
    "smtp_from": "", "email_enabled": "0",
    "backup_auto": "1", "audit_retention_days": "365",
    "custom_asset_fields": "",
    "checkout_days": "30",
    "warranty_alert_days": "90", "license_alert_days": "90",
}


def get_setting(key):
    row = db.session.get(Setting, key)
    return row.value if row and row.value is not None else DEFAULT_SETTINGS.get(key, "")


def set_setting(key, value):
    row = db.session.get(Setting, key)
    if row:
        row.value = value
    else:
        db.session.add(Setting(key=key, value=value))


def custom_field_names():
    return [f.strip() for f in get_setting("custom_asset_fields").split(",") if f.strip()]

# ------------------------------------------------------------------ auditing


def log_activity(action, entity_type=None, entity_id=None, details=None):
    db.session.add(ActivityLog(
        user_id=g.user.id if getattr(g, "user", None) else None,
        action=action, entity_type=entity_type, entity_id=entity_id,
        details=details, ip=request.remote_addr if request else None,
    ))

# -------------------------------------------------------------- notifications


def notify(kind, message, link=None, dedupe_key=None):
    if dedupe_key and db.session.scalar(
            db.select(Notification).where(Notification.dedupe_key == dedupe_key)):
        return
    db.session.add(Notification(kind=kind, message=message, link=link,
                                dedupe_key=dedupe_key))
    if get_setting("email_enabled") == "1":
        send_email(f"[AMS] {kind}", message)


def send_email(subject, body, to=None):
    host = get_setting("smtp_host")
    if not host:
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = get_setting("smtp_from") or get_setting("smtp_user")
        msg["To"] = to or get_setting("smtp_from") or get_setting("smtp_user")
        msg.set_content(body)
        with smtplib.SMTP(host, int(get_setting("smtp_port") or 587), timeout=10) as s:
            s.starttls()
            if get_setting("smtp_user"):
                s.login(get_setting("smtp_user"), get_setting("smtp_password"))
            s.send_message(msg)
        return True
    except Exception:
        return False

# ------------------------------------------------------------------ CSV


def csv_response(headers, rows, filename):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        w.writerow(["" if v is None else v for v in r])
    return Response(
        "﻿" + buf.getvalue(),  # BOM so Excel opens UTF-8 (Arabic) correctly
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def xlsx_response(headers, rows, filename, sheet="Sheet1"):
    """Build a real .xlsx download from headers + rows."""
    from flask import send_file
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = sheet[:31]
    ws.append(list(headers))
    for r in rows:
        ws.append([("" if v is None else
                    (v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else
                     (float(v) if hasattr(v, "is_integer") or _is_decimal(v) else v)))
                   for v in r])
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return send_file(out, download_name=filename, as_attachment=True,
                     mimetype="application/vnd.openxmlformats-officedocument"
                              ".spreadsheetml.sheet")


def _is_decimal(v):
    import decimal
    return isinstance(v, decimal.Decimal)


def read_table(file_storage):
    """Read an uploaded .xlsx or .csv into (headers, list-of-dict-rows)."""
    name = (file_storage.filename or "").lower()
    if name.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        wb = load_workbook(file_storage, read_only=True, data_only=True)
        ws = wb.active
        data = [[("" if c is None else
                  (c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else c))
                 for c in row] for row in ws.iter_rows(values_only=True)]
        wb.close()
    else:
        raw = file_storage.read().decode("utf-8-sig", errors="replace")
        data = [row for row in csv.reader(io.StringIO(raw))]
    if not data:
        return [], []
    headers = [str(h or "").strip().lower() for h in data[0]]
    rows = []
    for line in data[1:]:
        if not any(str(c).strip() for c in line):
            continue
        rows.append({headers[i]: (str(line[i]).strip() if i < len(line) else "")
                     for i in range(len(headers))})
    return headers, rows

# ------------------------------------------------------------------ QR / barcode


def qr_svg(data):
    import qrcode
    import qrcode.image.svg
    img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage,
                      box_size=12, border=2)
    return img.to_string().decode()


def barcode_svg(data):
    import barcode
    from barcode.writer import SVGWriter
    buf = io.BytesIO()
    barcode.get("code128", data, writer=SVGWriter()).write(
        buf, options={"module_height": 10, "font_size": 8, "text_distance": 3})
    return buf.getvalue().decode()

# ------------------------------------------------------------------ SVG charts

PALETTE = ["#22a04a", "#2f6fed", "#e8a13c", "#7c5cd6", "#18a8a0",
           "#d05574", "#8a929e", "#4a4f57"]


def bar_chart(pairs, color="#22a04a", height=210):
    """pairs: [(label, value)] -> responsive SVG bar chart."""
    if not pairs:
        return Markup("<p class='empty'>No data.</p>")
    n = len(pairs)
    bw, gap, pad_l, pad_b = 40, 22, 34, 46
    width = pad_l + n * (bw + gap) + 10
    top = max(v for _, v in pairs) or 1
    bars = []
    for i, (label, v) in enumerate(pairs):
        h = round((v / top) * (height - pad_b - 24), 1)
        x = pad_l + i * (bw + gap)
        y = height - pad_b - h
        short = label if len(label) <= 9 else label[:8] + "…"
        bars.append(
            f'<rect x="{x}" y="{y}" width="{bw}" height="{h}" rx="4" fill="{color}">'
            f'<title>{label}: {v}</title></rect>'
            f'<text x="{x + bw / 2}" y="{y - 6}" text-anchor="middle" class="cv">{v}</text>'
            f'<text x="{x + bw / 2}" y="{height - pad_b + 14}" text-anchor="middle" '
            f'class="cl" transform="rotate(28 {x + bw / 2} {height - pad_b + 14})">{short}</text>'
        )
    grid = "".join(
        f'<line x1="{pad_l - 6}" y1="{height - pad_b - f * (height - pad_b - 24)}" '
        f'x2="{width}" y2="{height - pad_b - f * (height - pad_b - 24)}" class="cg"/>'
        for f in (0, 0.5, 1))
    return Markup(
        f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" '
        f'preserveAspectRatio="xMinYMid meet">{grid}{"".join(bars)}</svg>')


def donut_chart(pairs, size=190):
    """pairs: [(label, value, color)] -> donut with legend."""
    total = sum(v for _, v, _ in pairs)
    if not total:
        return Markup("<p class='empty'>No data.</p>")
    import math
    cx = cy = size / 2
    r, stroke = size / 2 - 16, 26
    circ = 2 * math.pi * r
    offset, segs = 0.0, []
    for label, v, color in pairs:
        frac = v / total
        segs.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" '
            f'stroke-width="{stroke}" stroke-dasharray="{frac * circ} {circ}" '
            f'stroke-dashoffset="{-offset * circ}" transform="rotate(-90 {cx} {cy})">'
            f'<title>{label}: {v}</title></circle>')
        offset += frac
    legend = "".join(
        f'<span class="lg"><i style="background:{c}"></i>{label} ({v})</span>'
        for label, v, c in pairs if v)
    return Markup(
        f'<div class="donut-wrap"><svg viewBox="0 0 {size} {size}" class="chart donut" role="img">'
        f'{"".join(segs)}'
        f'<text x="{cx}" y="{cy - 2}" text-anchor="middle" class="dv">{total}</text>'
        f'<text x="{cx}" y="{cy + 16}" text-anchor="middle" class="dl">assets</text>'
        f'</svg><div class="legend">{legend}</div></div>')


def line_chart(pairs, color="#22a04a", height=200, money=False):
    """pairs: [(label, value)] month series -> SVG line/area chart."""
    if not pairs:
        return Markup("<p class='empty'>No data.</p>")
    n = len(pairs)
    pad_l, pad_b, pad_t = 40, 30, 14
    width = max(420, n * 52 + pad_l)
    top = max(v for _, v in pairs) or 1
    step = (width - pad_l - 14) / max(1, n - 1)
    pts = []
    for i, (_, v) in enumerate(pairs):
        x = pad_l + i * step
        y = pad_t + (1 - v / top) * (height - pad_b - pad_t)
        pts.append((round(x, 1), round(y, 1)))
    poly = " ".join(f"{x},{y}" for x, y in pts)
    area = f"{pad_l},{height - pad_b} " + poly + f" {pts[-1][0]},{height - pad_b}"
    labels = "".join(
        f'<text x="{pts[i][0]}" y="{height - 8}" text-anchor="middle" class="cl">{label}</text>'
        for i, (label, _) in enumerate(pairs))
    dots = "".join(f'<circle cx="{x}" cy="{y}" r="3.5" fill="{color}"/>' for x, y in pts)
    fmt = (lambda v: f"{v:,.0f}") if money else (lambda v: v)
    vals = "".join(
        f'<text x="{pts[i][0]}" y="{pts[i][1] - 8}" text-anchor="middle" class="cv">{fmt(v)}</text>'
        for i, (_, v) in enumerate(pairs))
    return Markup(
        f'<svg viewBox="0 0 {width} {height}" class="chart" role="img">'
        f'<polygon points="{area}" fill="{color}" opacity="0.12"/>'
        f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="2.5"/>'
        f'{dots}{vals}{labels}</svg>')

# ------------------------------------------------------------------ misc


def parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def month_key(d):
    return d.strftime("%b %y")
