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


BULK_PAGES = [
    ("/employees", "org.employees_bulk_delete"),
    ("/departments", "org.departments_bulk_delete"),
    ("/locations", "org.locations_bulk_delete"),
    ("/licenses", "ops.licenses_bulk_delete"),
    ("/maintenance", "ops.maintenance_bulk_delete"),
    ("/checkouts", "ops.checkouts_bulk_checkin"),
]


@pytest.mark.parametrize("url,endpoint", BULK_PAGES)
def test_list_pages_offer_select_all(client, app, url, endpoint):
    """The toolbar only appears once a page has rows, so give each one."""
    from itam.models import (Assignment, Category, Department, Employee,
                             License, Location, Maintenance)

    with app.app_context():
        cat = db.session.scalar(db.select(Category))
        emp = db.session.scalar(db.select(Employee))
        db.session.add_all([Department(name="Dept One"),
                            Location(name="Room One", kind="Room"),
                            License(name="Office", seats=5)])
        asset = Asset(tag="BK-9", name="Rig", status="Checked Out",
                      condition="Good", category=cat)
        db.session.add(asset)
        db.session.flush()
        db.session.add_all([Maintenance(asset=asset, title="Service"),
                            Assignment(asset=asset, employee=emp)])
        db.session.commit()

    login(client)
    body = client.get(url).data.decode()
    assert 'class="bulk-form"' in body, f"{url} has no bulk form"
    assert 'id="bulk"' in body, f"{url} bulk form needs an id for the button to target"
    assert 'form="bulk"' in body, f"{url} action button must point at the form"


def test_bulk_delete_skips_rows_still_in_use(client, app):
    """A department with people in it must survive a bulk delete."""
    from itam.models import Department, Employee

    with app.app_context():
        busy = Department(name="Busy")
        spare = Department(name="Spare")
        db.session.add_all([busy, spare])
        db.session.flush()
        db.session.add(Employee(name="Someone", department=busy))
        db.session.commit()
        busy_id, spare_id = busy.id, spare.id

    login(client)
    resp = client.post("/departments/bulk-delete",
                       data={"ids": [busy_id, spare_id]}, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert db.session.get(Department, busy_id) is not None, "in-use row was deleted"
        assert db.session.get(Department, spare_id) is None, "free row was not deleted"


def test_bulk_delete_with_nothing_selected_is_harmless(client, app):
    from itam.models import Department

    with app.app_context():
        db.session.add(Department(name="Untouched"))
        db.session.commit()
    login(client)
    resp = client.post("/departments/bulk-delete", data={}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Nothing selected" in resp.data
    with app.app_context():
        assert db.session.scalar(db.select(Department).where(Department.name == "Untouched"))


def test_departments_and_locations_can_be_edited(client, app):
    """Both screens had no edit path at all before."""
    from itam.models import Department, Location

    login(client)
    client.post("/departments", data={"name": "Science", "cost_center": "CC-1"},
                follow_redirects=True)
    with app.app_context():
        dep = db.session.scalar(db.select(Department).where(Department.name == "Science"))
        dep_id = dep.id
    client.post("/departments", data={"id": dep_id, "name": "Science Lab",
                                      "cost_center": "CC-2"}, follow_redirects=True)
    with app.app_context():
        dep = db.session.get(Department, dep_id)
        assert (dep.name, dep.cost_center) == ("Science Lab", "CC-2")

    client.post("/locations", data={"name": "Wing A", "kind": "Building"},
                follow_redirects=True)
    with app.app_context():
        loc = db.session.scalar(db.select(Location).where(Location.name == "Wing A"))
        loc_id = loc.id
    client.post("/locations", data={"id": loc_id, "name": "Wing B", "kind": "Floor"},
                follow_redirects=True)
    with app.app_context():
        loc = db.session.get(Location, loc_id)
        assert (loc.name, loc.kind) == ("Wing B", "Floor")


def test_bulk_checkin_returns_several_loans(client, app):
    from itam.models import Assignment, Category, Employee

    with app.app_context():
        emp = db.session.scalar(db.select(Employee))
        cat = db.session.scalar(db.select(Category))
        ids = []
        for tag in ("BK-1", "BK-2"):
            asset = Asset(tag=tag, name=tag, status="Checked Out", condition="Good",
                          category=cat)
            db.session.add(asset)
            db.session.flush()
            asg = Assignment(asset=asset, employee=emp)
            db.session.add(asg)
            db.session.flush()
            ids.append(asg.id)
        db.session.commit()

    login(client)
    client.post("/checkouts/bulk-checkin", data={"ids": ids}, follow_redirects=True)
    with app.app_context():
        for asg_id in ids:
            asg = db.session.get(Assignment, asg_id)
            assert asg.returned_at is not None, "loan was not returned"
            assert asg.asset.status == "Available"


def test_asset_form_has_no_parent_field(client):
    """"Part of (parent asset)" was removed from the asset form."""
    login(client)
    body = client.get("/assets/new").data.decode()
    assert 'name="parent_id"' not in body
    assert "Part of (parent asset)" not in body


def test_editing_keeps_an_existing_parent_link(client, app):
    """The field is gone, so a save must leave the stored link alone."""
    from itam.models import Category

    with app.app_context():
        cat = db.session.scalar(db.select(Category))
        parent = Asset(tag="PA-1", name="Dock", status="Available",
                       condition="Good", category=cat)
        db.session.add(parent)
        db.session.flush()
        child = Asset(tag="CH-1", name="Monitor", status="Available",
                      condition="Good", category=cat, parent_id=parent.id)
        db.session.add(child)
        db.session.commit()
        child_id, parent_id = child.id, parent.id

    login(client)
    client.post(f"/assets/{child_id}/edit", data={
        "name": "Monitor", "tag": "CH-1", "status": "Available",
        "condition": "Good", "depreciation_years": "5"}, follow_redirects=True)
    with app.app_context():
        assert db.session.get(Asset, child_id).parent_id == parent_id, \
            "saving the form unlinked an asset from its parent"


def test_new_asset_form_defaults_purchase_date_to_today(client, app):
    from datetime import date

    login(client)
    assert date.today().isoformat() in client.get("/assets/new").data.decode()

    # An existing asset keeps its own date rather than being reset to today.
    with app.app_context():
        from itam.models import Category
        a = Asset(tag="PD-1", name="Old", status="Available", condition="Good",
                  category=db.session.scalar(db.select(Category)),
                  purchase_date=date(2020, 1, 15))
        db.session.add(a)
        db.session.commit()
        aid = a.id
    body = client.get(f"/assets/{aid}/edit").data.decode()
    assert "2020-01-15" in body


def test_operating_system_is_a_combo_box(client):
    """A datalist, so the listed systems are offered but free text still works."""
    from itam.models import OPERATING_SYSTEMS

    login(client)
    body = client.get("/assets/new").data.decode()
    assert 'list="os-list"' in body and '<datalist id="os-list">' in body
    for name in ("Windows 11 Pro", "macOS", "Android", "iOS", "ChromeOS"):
        assert name in body, f"{name} missing from the OS list"
    assert len(OPERATING_SYSTEMS) >= 10


def test_asset_detail_still_renders(client, app):
    """Regression: a `today` name clash in the form lookups 500'd this page."""
    from itam.models import Category

    with app.app_context():
        a = Asset(tag="DT-1", name="Rig", status="Available", condition="Good",
                  category=db.session.scalar(db.select(Category)))
        db.session.add(a)
        db.session.commit()
        aid = a.id
    login(client)
    assert client.get(f"/assets/{aid}").status_code == 200


# ----------------------------------------------------------------- updater

def test_version_parsing_and_comparison():
    from itam.updater import is_newer, parse_version

    assert parse_version("2026.07.19") == (2026, 7, 19)
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("") is None and parse_version(None) is None
    assert parse_version("nightly") is None

    assert is_newer("2026.07.20", "2026.07.19")
    assert is_newer("2026.08.01", "2026.07.31")
    assert not is_newer("2026.07.19", "2026.07.19")     # same build
    assert not is_newer("2026.07.18", "2026.07.19")     # older
    # Anything unparseable, or a different scheme, must never trigger an update.
    assert not is_newer("nightly", "2026.07.19")
    assert not is_newer(None, "2026.07.19")
    assert not is_newer("v1.0.0", "2026.07.19")


def test_update_check_is_silent_when_github_is_unreachable(tmp_path, monkeypatch):
    """No internet must be a no-op, not an error."""
    from itam import updater

    monkeypatch.setattr(updater, "latest_release", lambda repo, token=None: None)
    assert updater.check_for_update("o/r", "2026.07.19", str(tmp_path)) == "unavailable"
    assert list(tmp_path.iterdir()) == []                # nothing written


def test_update_check_does_nothing_when_already_current(tmp_path, monkeypatch):
    from itam import updater

    release = {"name": "Mada AMS 2026.07.19", "assets": []}
    monkeypatch.setattr(updater, "latest_release", lambda repo, token=None: release)
    monkeypatch.setattr(updater, "remote_version", lambda r, token=None: "2026.07.19")
    called = []
    monkeypatch.setattr(updater, "download_update",
                        lambda *a, **k: called.append(1) or True)

    assert updater.check_for_update("o/r", "2026.07.19", str(tmp_path)) == "up-to-date"
    assert not called, "downloaded an update that was not newer"


def test_update_downloads_beside_the_exe_and_never_touches_instance(tmp_path, monkeypatch):
    """The whole point: data must come through an update untouched."""
    import hashlib

    from itam import updater

    exe = tmp_path / "AMS.exe"
    exe.write_bytes(b"old build")
    instance = tmp_path / "instance"
    (instance / "uploads").mkdir(parents=True)
    (instance / "backups").mkdir()
    db_file = instance / "itam.sqlite"
    db_file.write_bytes(b"SQLite format 3\x00" + b"important data" * 100)
    upload = instance / "uploads" / "invoice.pdf"
    upload.write_bytes(b"a scanned invoice")

    def fingerprint():
        out = {}
        for path in sorted(instance.rglob("*")):
            if path.is_file():
                out[str(path.relative_to(instance))] = hashlib.sha256(
                    path.read_bytes()).hexdigest()
        return out

    before = fingerprint()

    release = {"name": "Mada AMS 2026.07.20",
               "assets": [{"name": "AMS.exe",
                           "browser_download_url": "https://example/AMS.exe"}]}
    monkeypatch.setattr(updater, "latest_release", lambda repo, token=None: release)
    monkeypatch.setattr(updater, "remote_version", lambda r, token=None: "2026.07.20")
    monkeypatch.setattr(updater, "download_update",
                        lambda rel, base, ex=None, token=None:
                        (updater.pending_path(base, ex),
                         open(updater.pending_path(base, ex), "wb").write(b"new build"),
                         True)[-1])

    status = updater.check_for_update("o/r", "2026.07.19", str(tmp_path), exe=str(exe))
    assert status == "downloaded"
    assert (tmp_path / "AMS.exe.new").read_bytes() == b"new build"
    assert exe.read_bytes() == b"old build", "the running exe was replaced too early"
    assert fingerprint() == before, "an update modified the instance folder"


def test_applying_an_update_swaps_the_exe_and_leaves_data_alone(tmp_path):
    import hashlib

    from itam import updater

    exe = tmp_path / "AMS.exe"
    exe.write_bytes(b"old build")
    (tmp_path / "AMS.exe.new").write_bytes(b"new build")
    instance = tmp_path / "instance"
    instance.mkdir()
    db_file = instance / "itam.sqlite"
    db_file.write_bytes(b"rows and rows")
    before = hashlib.sha256(db_file.read_bytes()).hexdigest()

    assert updater.pending_update(str(tmp_path), str(exe)) is True
    assert updater.apply_pending_update(str(tmp_path), str(exe)) is True

    assert exe.read_bytes() == b"new build"
    assert (tmp_path / "AMS.exe.old").read_bytes() == b"old build"
    assert not (tmp_path / "AMS.exe.new").exists()
    assert hashlib.sha256(db_file.read_bytes()).hexdigest() == before

    # The retired build is cleared away on the following start.
    updater.cleanup_retired(str(tmp_path), str(exe))
    assert not (tmp_path / "AMS.exe.old").exists()


def test_apply_is_a_no_op_without_a_pending_download(tmp_path):
    from itam import updater

    exe = tmp_path / "AMS.exe"
    exe.write_bytes(b"only build")
    assert updater.pending_update(str(tmp_path), str(exe)) is False
    assert updater.apply_pending_update(str(tmp_path), str(exe)) is False
    assert exe.read_bytes() == b"only build"


def test_a_truncated_download_is_discarded(tmp_path, monkeypatch):
    """A dropped connection must not leave a stub that gets 'installed'."""
    import io

    from itam import updater

    exe = tmp_path / "AMS.exe"
    exe.write_bytes(b"old build")

    class Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(updater, "_request",
                        lambda url, token=None, accept=None: Resp(b"truncated"))
    release = {"assets": [{"name": "AMS.exe",
                           "browser_download_url": "https://example/AMS.exe"}]}
    assert updater.download_update(release, str(tmp_path), str(exe)) is False
    assert not (tmp_path / "AMS.exe.new").exists()
    assert not (tmp_path / "AMS.exe.new.part").exists()


def test_update_settings_expose_an_on_off_toggle(client, app):
    from itam.utils import get_setting

    login(client)
    page = client.get("/admin/settings").data.decode()
    assert "Check for updates automatically" in page
    assert 'name="update_auto"' in page

    form = {"app_name": "Mada Asset Management System (AMS)", "qr_prefix": "",
            "custom_asset_fields": "", "checkout_days": "30",
            "label_org": "Mada International Academy", "label_width_mm": "152.4",
            "label_height_mm": "76.2", "warranty_alert_days": "90",
            "license_alert_days": "90", "smtp_host": "", "smtp_port": "587",
            "smtp_user": "", "smtp_password": "", "smtp_from": "",
            "audit_retention_days": "365", "update_repo": "o/r", "update_token": ""}
    client.post("/admin/settings", data=form, follow_redirects=True)   # toggle off
    with app.app_context():
        assert get_setting("update_auto") == "0"

    client.post("/admin/settings", data={**form, "update_auto": "1"},
                follow_redirects=True)
    with app.app_context():
        assert get_setting("update_auto") == "1"


def test_pending_update_shows_a_restart_note(client, app):
    from itam.utils import set_setting

    login(client)
    assert b"Update ready" not in client.get("/").data
    with app.app_context():
        set_setting("update_pending", "2026.08.01")
        db.session.commit()
    page = client.get("/").data.decode()
    assert "Update ready" in page and "2026.08.01" in page


def test_asset_list_pages_instead_of_rendering_everything(client, app):
    """A 3,000-asset register produced a 1 MB page and a query per row."""
    from itam.blueprints.assets import PAGE_SIZE
    from itam.models import Category

    with app.app_context():
        cat = db.session.scalar(db.select(Category))
        db.session.add_all([
            Asset(tag=f"PG-{i:04d}", name=f"Device {i}", category=cat,
                  status="Available", condition="Good")
            for i in range(PAGE_SIZE + 25)])
        db.session.commit()

    login(client)
    body = client.get("/assets/").data.decode()
    assert body.count('data-id=') <= PAGE_SIZE + 1, "more than one page of rows"
    assert "Page 1 /" in body and "Next" in body

    page2 = client.get("/assets/?page=2").data.decode()
    assert "PG-0050" in page2 and "PG-0000" not in page2
    # An out-of-range page clamps rather than 500s or shows nothing.
    assert client.get("/assets/?page=999").status_code == 200
    assert client.get("/assets/?page=abc").status_code == 200


def test_export_still_covers_every_page(client, app):
    from itam.blueprints.assets import PAGE_SIZE
    from itam.models import Category

    with app.app_context():
        cat = db.session.scalar(db.select(Category))
        db.session.add_all([
            Asset(tag=f"EX-{i:04d}", name=f"Device {i}", category=cat,
                  status="Available", condition="Good")
            for i in range(PAGE_SIZE + 10)])
        db.session.commit()

    login(client)
    rows = client.get("/assets/export.csv").data.decode().strip().splitlines()
    assert len(rows) - 1 >= PAGE_SIZE + 10, "export was truncated to one page"


def test_asset_list_does_not_query_per_row(client, app):
    """Guards the eager loading: rows must not each fetch their own lookups."""
    from sqlalchemy import event

    from itam.models import Category

    with app.app_context():
        cat = db.session.scalar(db.select(Category))
        db.session.add_all([
            Asset(tag=f"NP-{i:03d}", name=f"Device {i}", category=cat,
                  status="Available", condition="Good") for i in range(40)])
        db.session.commit()
        engine = db.engine

    counter = {"n": 0}

    def count(*args, **kwargs):
        counter["n"] += 1

    login(client)
    event.listen(engine, "before_cursor_execute", count)
    try:
        client.get("/assets/")
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert counter["n"] < 40, f"one query per row is back ({counter['n']} queries)"


def test_standard_locations_are_idempotent(client, app):
    from itam.models import Location

    login(client)
    assert client.post("/locations/standard", follow_redirects=True).status_code == 200
    with app.app_context():
        first = db.session.scalar(db.select(db.func.count(Location.id)))
        kinds = {l.kind for l in db.session.scalars(db.select(Location))}
    assert first > 100, "the standard tree was not created"
    assert {"Branch", "Building", "Floor", "Room"} <= kinds

    client.post("/locations/standard", follow_redirects=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(Location.id))) == first, \
            "running it twice duplicated locations"


def test_os_version_is_gone_from_the_form_but_kept_in_the_data(client, app):
    from itam.models import Category

    with app.app_context():
        a = Asset(tag="OSV-1", name="Imported", status="Available",
                  condition="Good", os_name="Windows 11 Pro", os_version="23H2",
                  category=db.session.scalar(db.select(Category)))
        db.session.add(a)
        db.session.commit()
        aid = a.id

    login(client)
    body = client.get(f"/assets/{aid}/edit").data.decode()
    assert 'name="os_version"' not in body, "OS version is still on the form"

    client.post(f"/assets/{aid}/edit", data={
        "name": "Imported", "tag": "OSV-1", "status": "Available",
        "condition": "Good", "depreciation_years": "5",
        "os_name": "Windows 11 Pro"}, follow_redirects=True)
    with app.app_context():
        assert db.session.get(Asset, aid).os_version == "23H2", \
            "saving the form wiped the imported OS version"


def test_lending_lists_only_assets_that_are_free(client, app):
    """The picker must offer free assets and hide the ones already out."""
    from itam.models import Assignment, Category, Employee

    with app.app_context():
        cat = db.session.scalar(db.select(Category))
        emp = db.session.scalar(db.select(Employee))
        free = Asset(tag="LEND-FREE", name="Spare laptop", status="Available",
                     condition="Good", category=cat, serial="SN-FREE")
        out = Asset(tag="LEND-OUT", name="Loaned laptop", status="Checked Out",
                    condition="Good", category=cat)
        retired = Asset(tag="LEND-GONE", name="Retired laptop", status="Retired",
                        condition="Poor", category=cat)
        db.session.add_all([free, out, retired])
        db.session.flush()
        db.session.add(Assignment(asset=out, employee=emp))
        db.session.commit()

    login(client)
    body = client.get("/checkouts").data.decode()
    picker = body.split('id="co-asset"', 1)[1].split("</select>", 1)[0]
    assert "LEND-FREE" in picker
    assert "LEND-OUT" not in picker, "an asset already on loan was offered"
    assert "LEND-GONE" not in picker, "a retired asset was offered"

    # The search box and the read-only detail card share the same filter.
    with app.app_context():
        free_id = db.session.scalar(db.select(Asset.id).where(Asset.tag == "LEND-FREE"))
    hits = client.get("/lend/assets.json?q=SN-FREE").get_json()
    assert [h["id"] for h in hits] == [free_id]
    assert client.get("/lend/assets.json?q=LEND-OUT").get_json() == []
    facts = client.get(f"/lend/assets/{free_id}.json").get_json()
    assert facts["serial"] == "SN-FREE" and facts["tag"] == "LEND-FREE"


def test_lending_picker_does_not_render_the_whole_register(client, app):
    """A few thousand <option> tags made this page a megabyte of HTML."""
    from itam.blueprints.operations import PICKER_LIMIT
    from itam.models import Category

    with app.app_context():
        cat = db.session.scalar(db.select(Category))
        db.session.add_all([
            Asset(tag=f"BULK-{i:04d}", name=f"Bulk {i}", status="Available",
                  condition="Good", category=cat)
            for i in range(PICKER_LIMIT + 50)])
        db.session.commit()

    login(client)
    body = client.get("/checkouts").data.decode()
    picker = body.split('id="co-asset"', 1)[1].split("</select>", 1)[0]
    assert picker.count("<option") == PICKER_LIMIT
    assert f"of {PICKER_LIMIT + 50}" in body, "the full count is not reported"


def test_lending_records_assign_to_and_edited_by(client, app):
    from itam.models import Assignment, Category, Employee

    with app.app_context():
        a = Asset(tag="LEND-1", name="Trolley", status="Available",
                  condition="Good", category=db.session.scalar(db.select(Category)))
        db.session.add(a)
        db.session.commit()
        aid, eid = a.id, db.session.scalar(db.select(Employee)).id

    login(client)
    resp = client.post("/lend", data={"asset_id": aid, "employee_id": eid,
                                      "handled_by": "Sara N."},
                       follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        asg = db.session.scalar(db.select(Assignment).where(Assignment.asset_id == aid))
        assert asg.employee_id == eid, "assign-to was not recorded"
        assert asg.handled_by == "Sara N.", "edited-by was not recorded"
        assert db.session.get(Asset, aid).status == "Checked Out"
    assert b"Sara N." in client.get("/checkouts").data


def test_asset_form_shows_assignment_but_cannot_change_it(client, app):
    """Assignment lives in Lending; the asset form only mirrors it."""
    from itam.models import Assignment, Category, Employee

    with app.app_context():
        emp = db.session.scalar(db.select(Employee))
        a = Asset(tag="RO-1", name="Beamer", status="Checked Out", condition="Good",
                  category=db.session.scalar(db.select(Category)))
        db.session.add(a)
        db.session.flush()
        db.session.add(Assignment(asset=a, employee=emp))
        db.session.commit()
        aid, emp_name = a.id, emp.name

    login(client)
    body = client.get(f"/assets/{aid}/edit").data.decode()
    assert 'name="assign_employee_id"' not in body, "Assign to is still editable"
    assert 'name="updated_by"' not in body, "Updated by is still editable"
    assert emp_name in body, "the current holder is no longer shown"

    # Saving the form must not disturb the loan Lending created.
    client.post(f"/assets/{aid}/edit", data={
        "name": "Beamer", "tag": "RO-1", "status": "Checked Out",
        "condition": "Good", "depreciation_years": "5"}, follow_redirects=True)
    with app.app_context():
        asg = db.session.scalar(db.select(Assignment).where(Assignment.asset_id == aid))
        assert asg.returned_at is None, "saving the asset ended the loan"
        assert db.session.get(Asset, aid).updated_by == "Administrator", \
            "the saving user was not stamped"


def test_locations_are_paged_and_searchable(client, app):
    """"Add standard locations" makes ~600 rows; printing them all was 354 KB."""
    from itam.blueprints.org import LOCATION_PAGE_SIZE
    from itam.models import Location

    login(client)
    client.post("/locations/standard", follow_redirects=True)
    with app.app_context():
        total = db.session.scalar(db.select(db.func.count(Location.id)))
    assert total > LOCATION_PAGE_SIZE

    body = client.get("/locations").data.decode()
    table = body.split('class="bulk-form"', 1)[1].split("</table>", 1)[0]
    assert table.count("<tr>") == LOCATION_PAGE_SIZE + 1, "the whole tree is still printed"
    assert f"of {total}" in body, "the full count is not reported"
    assert len(body) < 120_000, "the page is still oversized"

    # Page 2 shows different rows, and searching narrows the table.
    assert client.get("/locations?page=2").data != client.get("/locations").data
    hit = client.get("/locations?q=Mada").data.decode()
    hit_table = hit.split('class="bulk-form"', 1)[1].split("</table>", 1)[0]
    assert "Mada" in hit_table
    assert "No location matches" in client.get("/locations?q=zzzznope").data.decode()
    # Out-of-range and junk page numbers must not blow up.
    assert client.get("/locations?page=9999").status_code == 200
    assert client.get("/locations?page=abc").status_code == 200


def test_service_worker_cache_is_versioned(client):
    """A fixed cache name meant an installed PWA served last release's CSS."""
    from itam import APP_VERSION

    resp = client.get("/static/sw.js")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert f'"{APP_VERSION}"' in body, "the worker does not carry the build number"
    assert "no-store" in resp.headers.get("Cache-Control", ""), \
        "the worker itself may be cached, pinning the old one in place"

    login(client)
    page = client.get("/assets/").data.decode()
    assert f"style.css?v={APP_VERSION}" in page
    assert f"app.js?v={APP_VERSION}" in page


def test_every_way_of_lending_records_who_did_it(client, app):
    """"Edited by" must not depend on which screen the loan came from."""
    from itam.models import Assignment, Category, Employee

    with app.app_context():
        cat = db.session.scalar(db.select(Category))
        db.session.add_all([
            Asset(tag=f"WAY-{i}", name=f"Way {i}", status="Available",
                  condition="Good", category=cat) for i in (1, 2, 3)])
        db.session.commit()
        ids = {a.tag: a.id for a in db.session.scalars(
            db.select(Asset).where(Asset.tag.like("WAY-%")))}
        eid = db.session.scalar(db.select(Employee)).id

    login(client)
    client.post("/lend", data={"asset_id": ids["WAY-1"], "employee_id": eid},
                follow_redirects=True)
    client.post(f"/assets/{ids['WAY-2']}/checkout", data={"employee_id": eid},
                follow_redirects=True)
    client.post("/assets/bulk", data={"action": "assign", "employee_id": eid,
                                      "id": [ids["WAY-3"]]}, follow_redirects=True)
    with app.app_context():
        for tag, aid in ids.items():
            asg = db.session.scalar(
                db.select(Assignment).where(Assignment.asset_id == aid))
            assert asg is not None, f"{tag} was never lent"
            assert asg.handled_by == "Administrator", f"{tag} recorded no Edited by"


def test_asset_filters_offer_only_locations_in_use(client, app):
    """The standard tree is ~600 rows; a filter <select> of all of them was 39 KB."""
    from itam.models import Category, Location

    login(client)
    client.post("/locations/standard", follow_redirects=True)
    with app.app_context():
        used, empty = db.session.scalars(
            db.select(Location).where(Location.kind == "Room").limit(2)).all()
        db.session.add(Asset(tag="LOC-1", name="Desk PC", status="Available",
                             condition="Good", location_id=used.id,
                             category=db.session.scalar(db.select(Category))))
        db.session.commit()
        used_id, empty_id, total = used.id, empty.id, db.session.scalar(
            db.select(db.func.count(Location.id)))

    body = client.get("/assets/").data.decode()
    picker = body.split('name="location"', 1)[1].split("</select>", 1)[0]
    assert f'value="{used_id}"' in picker
    assert f'value="{empty_id}"' not in picker, "an empty location was offered"
    assert picker.count("<option") < total

    # An active filter must never disappear from its own box.
    still = client.get(f"/assets/?location={empty_id}").data.decode()
    still_picker = still.split('name="location"', 1)[1].split("</select>", 1)[0]
    assert f'value="{empty_id}"' in still_picker
    assert client.get("/assets/?location=notanumber").status_code == 200

    # Transfers may target an empty location, so that list is fetched on demand.
    assert 'id="bulk-loc-q"' in body
    hits = client.get("/assets/locations.json").get_json()
    assert {h["id"] for h in hits} >= {used_id, empty_id}
    named = client.get(f"/assets/locations.json?q={empty.name}").get_json()
    assert any(h["id"] == empty_id for h in named)


def test_location_report_totals_survive_the_rewrite(client, app):
    """The per-location loop became one grouped query; the numbers must match."""
    from itam.models import Category, Location

    login(client)
    with app.app_context():
        cat = db.session.scalar(db.select(Category))
        room = Location(name="Lab 7", kind="Room")
        wing = Location(name="North Wing", kind="Building")
        db.session.add_all([wing, room])
        db.session.flush()
        room.parent_id = wing.id
        empty = Location(name="Nobody's Room", kind="Room")
        db.session.add(empty)
        db.session.add_all([
            Asset(tag="RP-1", name="A", status="Available", condition="Good",
                  category=cat, location_id=room.id, purchase_cost=100),
            Asset(tag="RP-2", name="B", status="Available", condition="Good",
                  category=cat, location_id=room.id, purchase_cost=250.50),
        ])
        db.session.commit()

    body = client.get("/reports/locations").data.decode()
    assert "North Wing / Lab 7" in body, "the full path is no longer shown"
    assert "350.50" in body, "purchase cost was not totalled"
    assert "Nobody" not in body, "a location holding nothing was listed"

    csv = client.get("/reports/locations?format=csv").data.decode()
    row = [l for l in csv.splitlines() if "Lab 7" in l][0]
    assert ",2," in row or '"2"' in row or ",2," in row.replace('"', "")


def test_junk_query_arguments_do_not_crash_pages(client, app):
    """A hand-edited URL or stale bookmark used to return a 500."""
    login(client)
    for url in ("/assets/?location=notanumber", "/assets/?category=x&department=y",
                "/assets/?page=abc", "/assets/new?clone=abc",
                "/reports/custom?category=zzz", "/reports/custom?department=zzz",
                "/locations?page=abc"):
        assert client.get(url).status_code == 200, f"{url} did not survive"
