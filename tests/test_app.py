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
    ws.append(["XL-0001", "Duplicate row", "", "", ""])   # dup: skipped
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    resp = client.post("/assets/import",
                       data={"file": (buf, "assets.xlsx")},
                       content_type="multipart/form-data")
    assert b"Import preview" in resp.data
    assert b"duplicate tag" in resp.data
    import re
    token = re.search(rb'name="token" value="([^"]+)"', resp.data).group(1).decode()
    client.post("/assets/import", data={"token": token}, follow_redirects=True)
    with app.app_context():
        a = db.session.scalar(db.select(Asset).where(Asset.tag == "XL-0001"))
        assert a is not None and a.name == "Excel Laptop"
        assert float(a.purchase_cost) == 999.5
        assert a.category.name == "Laptops"

    resp = client.get("/assets/export.xlsx")
    assert resp.status_code == 200
    out = load_workbook(io.BytesIO(resp.data))
    tags = [row[0].value for row in out.active.iter_rows(min_row=2)]
    assert "XL-0001" in tags


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
    assert "size: 6in 3in" in body          # exact 6x3 label size
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

    csv_data = ("name,employee id,type,email,phone,title,department\n"
                "Imported Person,EMP-7001,Teacher,imp@example.com,555,Teacher,\n")
    resp = client.post("/employees/import",
                       data={"file": (io.BytesIO(csv_data.encode()), "e.csv")},
                       content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        e = db.session.scalar(db.select(Employee).where(Employee.email == "imp@example.com"))
        assert e is not None and e.emp_code == "EMP-7001"


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
