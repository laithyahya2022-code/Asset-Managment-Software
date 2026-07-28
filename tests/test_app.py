import io

import pytest

from itam import create_app
from itam.models import Asset, Category, Employee, License, User, db


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "BACKUP_FOLDER": str(tmp_path / "backups"),
    })
    with app.app_context():
        db.create_all()
        viewer = User(username="viewer", name="View Only",
                      email="viewer@example.com", role="viewer")
        viewer.set_password("viewer123")
        db.session.add(viewer)
        db.session.add(Category(name="Laptops"))
        db.session.add(Employee(name="Alice Hart", email="alice@example.com"))
        db.session.commit()
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, username="admin", password="admin123"):
    return client.post("/login", data={"username": username, "password": password},
                       follow_redirects=True)


def test_login_required(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_login_logout(client):
    resp = login(client)
    assert b"Dashboard" in resp.data
    resp = client.get("/logout", follow_redirects=True)
    assert b"Log in" in resp.data


def test_bad_login_rejected(client):
    resp = client.post("/login", data={"username": "admin", "password": "wrong"},
                       follow_redirects=True)
    assert b"Invalid username or password" in resp.data


def test_asset_crud_and_checkout(client, app):
    login(client)
    resp = client.post("/assets/new", data={
        "tag": "LT-0001", "name": "Test Laptop", "category_id": "1",
        "status": "Available", "condition": "Good", "depreciation_years": "5",
        "purchase_date": "2026-01-15", "purchase_cost": "1200.50",
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        a = db.session.scalar(db.select(Asset).where(Asset.tag == "LT-0001"))
        assert a is not None and a.status == "Available"
        asset_id = a.id
        emp_id = db.session.scalar(db.select(Employee.id))

    client.post(f"/assets/{asset_id}/checkout", data={"employee_id": emp_id})
    with app.app_context():
        a = db.session.get(Asset, asset_id)
        assert a.status == "Checked Out"
        assert a.current_assignment.employee.name == "Alice Hart"

    client.post(f"/assets/{asset_id}/checkin")
    with app.app_context():
        a = db.session.get(Asset, asset_id)
        assert a.status == "Available"
        assert a.current_assignment is None


def test_duplicate_tag_rejected(client, app):
    login(client)
    for _ in range(2):
        client.post("/assets/new", data={
            "tag": "DUP-1", "name": "Laptop", "status": "Available",
            "condition": "Good", "depreciation_years": "5"})
    with app.app_context():
        assert db.session.scalar(
            db.select(db.func.count(Asset.id)).where(Asset.tag == "DUP-1")) == 1


def test_rbac_viewer_cannot_manage(client, app):
    login(client, "viewer", "viewer123")
    resp = client.post("/assets/new", data={
        "tag": "V-1", "name": "X", "status": "Available",
        "condition": "Good", "depreciation_years": "5"})
    assert resp.status_code == 403
    resp = client.get("/admin/users")
    assert resp.status_code == 403
    # but viewer can view assets
    assert client.get("/assets/").status_code == 200


def test_activity_log_written(client, app):
    login(client)
    client.post("/assets/new", data={
        "tag": "LOG-1", "name": "X", "status": "Available",
        "condition": "Good", "depreciation_years": "5"})
    resp = client.get("/activity")
    assert b"LOG-1" in resp.data


def test_license_seats_and_compliance(client, app):
    login(client)
    client.post("/licenses/new", data={"name": "Office Suite", "seats": "1"},
                follow_redirects=True)
    with app.app_context():
        lic = db.session.scalar(db.select(License))
        lic_id = lic.id
        emp_id = db.session.scalar(db.select(Employee.id))
    client.post(f"/licenses/{lic_id}/assign", data={"employee_id": emp_id})
    # second assign should be blocked (seats exhausted)
    client.post(f"/licenses/{lic_id}/assign", data={"employee_id": emp_id})
    with app.app_context():
        lic = db.session.get(License, lic_id)
        assert lic.seats_used == 1
        assert lic.compliant


def test_csv_export_and_qr(client, app):
    login(client)
    client.post("/assets/new", data={
        "tag": "QR-1", "name": "Scanner Test", "status": "Available",
        "condition": "Good", "depreciation_years": "5"})
    resp = client.get("/assets/export.csv")
    assert resp.status_code == 200
    assert b"QR-1" in resp.data
    with app.app_context():
        asset_id = db.session.scalar(db.select(Asset.id).where(Asset.tag == "QR-1"))
    resp = client.get(f"/assets/{asset_id}/qr.svg")
    assert resp.status_code == 200
    assert b"<svg" in resp.data
    resp = client.get(f"/assets/{asset_id}/barcode.svg")
    assert resp.status_code == 200


def test_api_requires_token(client, app):
    assert client.get("/api/v1/assets").status_code == 401
    login(client)
    with app.app_context():
        admin = db.session.scalar(db.select(User).where(User.username == "admin"))
        admin_id = admin.id
    client.post(f"/admin/users/{admin_id}/apikey")
    with app.app_context():
        key = db.session.get(User, admin_id).api_key
    fresh = app.test_client()
    resp = fresh.get("/api/v1/assets", headers={"Authorization": f"Bearer {key}"})
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_excel_import_and_export(client, app):
    import io
    from openpyxl import Workbook, load_workbook
    login(client)
    wb = Workbook()
    ws = wb.active
    ws.append(["tag", "name", "category", "status", "purchase_cost"])
    ws.append(["XL-0001", "Excel Laptop", "Laptops", "Available", 999.5])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    resp = client.post("/assets/import",
                       data={"file": (buf, "assets.xlsx")},
                       content_type="multipart/form-data")
    assert b"Import preview" in resp.data
    import re
    token = re.search(rb'name="token" value="([^"]+)"', resp.data).group(1).decode()
    client.post("/assets/import", data={"token": token}, follow_redirects=True)
    with app.app_context():
        a = db.session.scalar(db.select(Asset).where(Asset.tag == "XL-0001"))
        assert a is not None and a.name == "Excel Laptop"
        assert float(a.purchase_cost) == 999.5
        assert a.category.name == "Laptops"    # category auto-created

    resp = client.get("/assets/export.xlsx")
    assert resp.status_code == 200
    out = load_workbook(io.BytesIO(resp.data))
    tags = [row[0].value for row in out.active.iter_rows(min_row=2)]
    assert "XL-0001" in tags


def test_import_flexible_headers_and_autotag(client, app):
    """Real-world sheet: odd headers, no usable tags, DD/MM/YYYY dates,
    duplicated tag column -> every row still imports with a generated ID."""
    import re
    login(client)
    csv = (
        "No,Asset,TAG,Branch,Floor,Assigned to,Name,Asset Status,Condition,"
        "Purchase Date,Serial No.,Dept\n"
        "1,Desktop,eff,Mada 3,GF,Ms A,M3-PC01,In Use,Good,16/07/2026,SN-1,Reg\n"
        "2,Desktop,eff,Mada 3,GF,Ms B,M3-PC02,In Use,Good,16/07/2026,SN-2,Reg\n"
        "3,Printer,eff,Mada 3,F1,Copy Room,M3-PR01,In Use,Good,16/07/2026,SN-3,IT\n"
    )
    resp = client.post("/assets/import",
                       data={"file": (io.BytesIO(csv.encode()), "db.csv")},
                       content_type="multipart/form-data")
    assert b"Import preview" in resp.data
    token = re.search(rb'name="token" value="([^"]+)"', resp.data).group(1).decode()
    client.post("/assets/import", data={"token": token}, follow_redirects=True)
    with app.app_context():
        assets = db.session.scalars(db.select(Asset)).all()
        assert len(assets) == 3                       # all rows imported
        assert len({a.tag for a in assets}) == 3      # unique generated tags
        pc = db.session.scalar(db.select(Asset).where(Asset.name == "M3-PC01"))
        assert pc.category.name == "Desktop"          # from "Asset" column
        assert pc.branch == "Mada 3" and pc.floor == "GF"
        assert pc.serial == "SN-1"
        assert str(pc.purchase_date) == "2026-07-16"  # DD/MM/YYYY parsed
        assert "Ms A" in (pc.notes or "")             # "Assigned to" kept


def test_search_page(client, app):
    login(client)
    client.post("/assets/new", data={
        "tag": "SRCH-1", "name": "Zebra Machine", "status": "Available",
        "condition": "Good", "depreciation_years": "5"})
    resp = client.get("/search?q=Zebra")
    assert b"SRCH-1" in resp.data


def test_saved_searches(client, app):
    login(client)
    client.post("/assets/searches", data={"name": "My laptops", "q": "",
                                          "query": "status=Available&category=1"})
    resp = client.get("/assets/")
    assert "My laptops".encode() in resp.data
    from itam.models import SavedSearch
    with app.app_context():
        s = db.session.scalar(db.select(SavedSearch))
        assert s.query == "status=Available&category=1"
        sid = s.id
    client.post(f"/assets/searches/{sid}/delete")
    resp = client.get("/assets/")
    assert "My laptops".encode() not in resp.data


def test_custom_report_builder(client, app):
    login(client)
    client.post("/assets/new", data={
        "tag": "CR-1", "name": "Report Machine", "category_id": "1",
        "status": "Available", "condition": "Good", "depreciation_years": "5"})
    resp = client.get("/reports/custom?col=tag&col=name&col=condition&status=Available")
    assert b"CR-1" in resp.data and b"Report Machine" in resp.data
    resp = client.get("/reports/custom?col=tag&status=Available&format=csv")
    assert resp.status_code == 200 and b"CR-1" in resp.data
    # unavailable filter excludes it
    resp = client.get("/reports/custom?col=tag&status=Retired")
    assert b"CR-1" not in resp.data


def test_custom_instance_path(tmp_path):
    custom = tmp_path / "portable-instance"
    app = create_app({"TESTING": True}, instance_path=str(custom))
    assert app.instance_path == str(custom)
    assert custom.exists()
    assert (custom / "itam.sqlite").exists() or app.config["SQLALCHEMY_DATABASE_URI"].endswith(
        "itam.sqlite")


def test_auto_backup(tmp_path):
    import itam as itam_pkg
    dbfile = tmp_path / "live.sqlite"
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{dbfile}",
        "UPLOAD_FOLDER": str(tmp_path / "up"),
        "BACKUP_FOLDER": str(tmp_path / "bk"),
    })
    client = app.test_client()
    itam_pkg._last_backup_check[0] = 0.0          # force the hourly check
    client.get("/login")
    backups = list((tmp_path / "bk").glob("auto-*.sqlite"))
    assert len(backups) == 1
    # second request within the hour must not create another
    client.get("/login")
    assert len(list((tmp_path / "bk").glob("auto-*.sqlite"))) == 1


def test_auto_asset_numbering(client, app):
    login(client)
    with app.app_context():
        cat = db.session.scalar(db.select(Category))
        cat.prefix = "LPT"
        db.session.commit()
        cat_id = cat.id
    for _ in range(2):
        client.post("/assets/new", data={
            "tag": "", "name": "Auto Laptop", "category_id": str(cat_id),
            "status": "Available", "condition": "Good", "depreciation_years": "5"})
    with app.app_context():
        tags = sorted(t for (t,) in db.session.execute(
            db.select(Asset.tag).where(Asset.tag.like("LPT-%"))).all())
        assert tags == ["LPT-000001", "LPT-000002"]


def test_return_inspection(client, app):
    login(client)
    client.post("/assets/new", data={
        "tag": "RI-1", "name": "Loaner", "status": "Available",
        "condition": "Good", "depreciation_years": "5"})
    with app.app_context():
        asset_id = db.session.scalar(db.select(Asset.id).where(Asset.tag == "RI-1"))
        emp_id = db.session.scalar(db.select(Employee.id))
    client.post(f"/assets/{asset_id}/checkout", data={"employee_id": emp_id})
    client.post(f"/assets/{asset_id}/checkin",
                data={"return_condition": "Damaged", "return_notes": "cracked lid"})
    with app.app_context():
        a = db.session.get(Asset, asset_id)
        assert a.condition == "Damaged"
        assert a.status == "Damaged"
        assert a.assignments[0].return_notes == "cracked lid"


def test_new_roles_have_permissions(app):
    from itam.models import RolePermission
    with app.app_context():
        auditor_perms = {p.permission for p in db.session.scalars(
            db.select(RolePermission).where(RolePermission.role == "auditor"))}
        assert "reports.view" in auditor_perms
        assert "assets.manage" not in auditor_perms
        superadmin_perms = {p.permission for p in db.session.scalars(
            db.select(RolePermission).where(RolePermission.role == "superadmin"))}
        assert "admin.settings" in superadmin_perms


def test_lifecycle_and_movement_reports(client):
    login(client)
    assert client.get("/reports/lifecycle").status_code == 200
    assert client.get("/reports/movement").status_code == 200
    assert client.get("/reports/locations").status_code == 200


def test_asset_label_6x3(client, app):
    login(client)
    client.post("/assets/new", data={
        "tag": "LBL-1", "name": "Label Asset", "status": "Available",
        "condition": "Good", "depreciation_years": "5", "branch": "Mada 3",
        "location_name": "IT", "serial": "SN-8842-XJ01"})
    with app.app_context():
        asset_id = db.session.scalar(db.select(Asset.id).where(Asset.tag == "LBL-1"))
    resp = client.get(f"/assets/{asset_id}/label")
    assert resp.status_code == 200
    body = resp.data.decode()
    # 6 x 3 in is the default, now expressed in mm so any stock size works
    assert "@page { size: 152.4mm 76.2mm; margin: 0; }" in body
    assert "LBL-1" in body                   # tag under QR
    assert "Mada 3" in body and "SN-8842-XJ01" in body
    assert "/qr.svg" in body                 # QR image embedded


def test_procurement_removed(client):
    login(client)
    assert client.get("/procurement").status_code == 404
    assert b"Procurement" not in client.get("/").data


def test_employee_excel_export_and_import(client, app):
    import io
    from openpyxl import load_workbook
    from itam.models import Employee
    login(client)
    resp = client.get("/employees/export.xlsx")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.data))
    assert wb.active["A1"].value == "Name"

    # Real-world sheet: "Employee Type"/"Job Title" headers, SHARED emails across
    # distinct people, custom types, and a department that doesn't exist yet.
    csv_data = (
        "Name,Employee ID,Employee Type,Email,Job Title,Department\n"
        "Laith 1,Emp001,IT Technical,shared@mada.edu,IT Technical,IT\n"
        "Ayham 1,Emp002,IT Manager,shared@mada.edu,IT Manager,IT\n"
        "Rama 1,Emp003,Teacher,shared@mada.edu,Teacher,National\n"
    )
    resp = client.post("/employees/import",
                       data={"file": (io.BytesIO(csv_data.encode()), "e.csv")},
                       content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        from itam.models import Department
        people = db.session.scalars(
            db.select(Employee).where(Employee.emp_code.in_(["Emp001", "Emp002", "Emp003"]))).all()
        assert len(people) == 3                       # shared email did NOT collapse them
        e1 = db.session.scalar(db.select(Employee).where(Employee.emp_code == "Emp001"))
        assert e1.emp_type == "IT Technical"          # custom type kept
        assert e1.title == "IT Technical"             # "Job Title" mapped
        assert e1.department.name == "IT"             # department auto-created
        assert db.session.scalar(db.select(Department).where(Department.name == "National"))


def test_license_and_maintenance_exports(client):
    login(client)
    assert client.get("/licenses/export.xlsx").status_code == 200
    assert client.get("/licenses/export.csv").status_code == 200
    assert client.get("/maintenance/export.xlsx").status_code == 200
    assert client.get("/inventory/export.xlsx").status_code == 200


def test_arabic_language_switch(client):
    login(client)
    resp = client.get("/lang/ar", follow_redirects=True)
    assert 'dir="rtl"'.encode() in resp.data
    assert "لوحة التحكم".encode() in resp.data


def test_upgrading_over_an_older_database_adds_missing_columns(tmp_path):
    """A database made by an older build must survive the upgrade.

    db.create_all() only creates missing tables, so without _sync_schema()
    every page touching an asset fails with "no such column".
    """
    import sqlite3

    instance = tmp_path / "instance"
    app = create_app(instance_path=str(instance))
    with app.app_context():
        db.session.add(Category(name="Laptops"))
        db.session.commit()
        db.session.add(Asset(tag="LT-0001", name="ThinkPad", branch="Mada 1",
                             floor="F1", status="Available", condition="Good"))
        db.session.commit()

    # Strip columns that later releases introduced, as an older install lacks.
    path = instance / "itam.sqlite"
    con = sqlite3.connect(path)
    for column in ("branch", "building", "floor", "updated_by", "cpu"):
        con.execute(f"ALTER TABLE asset DROP COLUMN {column}")
    con.commit()
    con.close()

    # Starting the current app over that database must repair it, not fail.
    upgraded = create_app(instance_path=str(instance))
    with upgraded.app_context():
        asset = db.session.scalar(db.select(Asset).where(Asset.tag == "LT-0001"))
        assert asset is not None, "existing rows must survive the upgrade"
        assert asset.name == "ThinkPad"
        assert asset.branch is None      # re-added, empty for old rows
        asset.branch = "Mada 2"          # and writable again
        db.session.commit()

    client = upgraded.test_client()
    client.post("/login", data={"username": "admin", "password": "admin123"},
                follow_redirects=True)
    for url in ("/", "/assets/", "/reports/assets", "/search?q=think"):
        assert client.get(url).status_code == 200, f"{url} broke after upgrade"


def test_schema_sync_is_idempotent(tmp_path):
    from itam import _sync_schema

    app = create_app(instance_path=str(tmp_path / "instance"))
    with app.app_context():
        added, skipped = _sync_schema()
        assert added == [], "a current database needs no changes"
        assert skipped == []


@pytest.mark.parametrize("w,h", [(152.4, 76.2), (101.6, 152.4), (101.6, 50.8),
                                 (70, 38), (50, 30), (40, 20)])
def test_label_layout_fits_every_offered_size(w, h):
    """Nothing may be sized past the sticker it prints on."""
    from itam.utils import label_layout

    L = label_layout(w, h, org_name="Mada Asset Management System (AMS)")
    assert L["width"] == round(w, 2) and L["height"] == round(h, 2)

    tag_line = L["fs_tag"] * 1.25 + L["pad"] * 0.3
    if L["portrait"]:
        assert L["qr"] <= w - 2 * L["pad"] + 0.01
        used = L["qr"] + tag_line + 2 * L["pad"]
    else:
        # QR column is the tall one on a landscape label.
        used = L["qr"] + tag_line + 2 * L["pad"]
        assert L["qr"] <= w * 0.42 + 0.01
    assert used <= h + 0.01, f"QR column {used:.1f}mm overflows a {h}mm label"
    assert L["fs_label"] >= 1.0 and L["fs_value"] > 0


def test_tiny_labels_drop_detail_fields():
    from itam.utils import label_layout

    assert label_layout(40, 20, org_name="Mada AMS")["fields"] == []
    assert label_layout(40, 20, org_name="Mada AMS")["show_org"] is False
    assert label_layout(152.4, 76.2, org_name="Mada AMS")["fields"]


def test_label_size_setting_drives_the_printed_page(client, app):
    from itam.models import Category
    from itam.utils import set_setting

    with app.app_context():
        asset = Asset(tag="LT-9001", name="ThinkPad", status="Available",
                      condition="Good",
                      category=db.session.scalar(db.select(Category)))
        db.session.add(asset)
        set_setting("label_width_mm", "50")
        set_setting("label_height_mm", "30")
        db.session.commit()
        asset_id = asset.id

    login(client)
    page = client.get(f"/assets/{asset_id}/label").data.decode()
    assert "@page { size: 50.0mm 30.0mm; margin: 0; }" in page
    assert "width: 50.0mm; height: 30.0mm" in page


def test_label_size_is_clamped_to_something_printable(app):
    from itam.utils import label_size_mm, set_setting

    with app.app_context():
        set_setting("label_width_mm", "0")
        set_setting("label_height_mm", "99999")
        db.session.commit()
        w, h = label_size_mm()
        assert w == 15.0 and h == 300.0

        set_setting("label_width_mm", "not a number")
        db.session.commit()
        assert label_size_mm()[0] == 152.4      # falls back to the default


def test_label_prints_the_organisation_not_the_software_name(client, app):
    """The sticker carries the school's name; AMS is the software."""
    from itam.models import Category, Department
    from itam.utils import set_setting

    with app.app_context():
        dept = Department(name="IT")
        db.session.add(dept)
        db.session.add(Asset(tag="LT-9100", name="ThinkPad", serial="SN-8842-XJ01",
                             branch="Mada 3", department=dept, status="Available",
                             condition="Good",
                             category=db.session.scalar(db.select(Category))))
        set_setting("label_org", "Mada International Academy")
        db.session.commit()
        asset_id = db.session.scalar(db.select(Asset.id).where(Asset.tag == "LT-9100"))

    login(client)
    page = client.get(f"/assets/{asset_id}/label").data.decode()
    assert "Mada International Academy" in page
    assert "(AMS)" not in page                 # software name stays off the label
    for text in ("Branch", "Mada 3", "Department", "IT", "Serial", "SN-8842-XJ01"):
        assert text in page, f"{text} missing from the label"


def test_label_org_is_editable_from_settings(client, app):
    from itam.utils import get_setting

    login(client)
    assert b"Organisation printed on labels" in client.get("/admin/settings").data
    client.post("/admin/settings", data={
        "app_name": "Mada Asset Management System (AMS)",
        "label_org": "Another School", "label_width_mm": "50",
        "label_height_mm": "30", "qr_prefix": "", "custom_asset_fields": "",
        "checkout_days": "30", "warranty_alert_days": "90",
        "license_alert_days": "90", "smtp_host": "", "smtp_port": "587",
        "smtp_user": "", "smtp_password": "", "smtp_from": "",
        "audit_retention_days": "365"}, follow_redirects=True)
    with app.app_context():
        assert get_setting("label_org") == "Another School"
