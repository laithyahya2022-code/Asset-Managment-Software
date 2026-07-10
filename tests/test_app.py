import pytest

from itam import create_app
from itam.models import Asset, Category, Employee, db


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        db.create_all()
        db.session.add(Category(name="Laptops"))
        db.session.add(
            Employee(name="Alice Hart", email="alice@example.com", department="Eng")
        )
        db.session.commit()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def test_dashboard_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Dashboard" in resp.data


def test_create_asset(client, app):
    resp = client.post(
        "/assets/new",
        data={
            "asset_tag": "LT-0001",
            "name": "Test Laptop",
            "category_id": "1",
            "status": "Available",
            "purchase_date": "2026-01-15",
            "purchase_cost": "1200.50",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        asset = db.session.scalar(db.select(Asset).where(Asset.asset_tag == "LT-0001"))
        assert asset is not None
        assert asset.name == "Test Laptop"
        assert asset.status == "Available"


def test_duplicate_asset_tag_rejected(client, app):
    for _ in range(2):
        client.post(
            "/assets/new",
            data={"asset_tag": "LT-0002", "name": "Laptop", "status": "Available"},
        )
    with app.app_context():
        count = db.session.query(Asset).filter_by(asset_tag="LT-0002").count()
        assert count == 1


def test_checkout_and_checkin(client, app):
    client.post(
        "/assets/new",
        data={"asset_tag": "LT-0003", "name": "Laptop", "status": "Available"},
    )
    with app.app_context():
        asset_id = db.session.scalar(
            db.select(Asset.id).where(Asset.asset_tag == "LT-0003")
        )

    resp = client.post(
        f"/assets/{asset_id}/checkout",
        data={"employee_id": "1", "notes": "onboarding"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        asset = db.session.get(Asset, asset_id)
        assert asset.status == "Assigned"
        assert asset.current_assignment is not None
        assert asset.current_assignment.employee.email == "alice@example.com"

    # A second checkout while assigned must be rejected
    client.post(f"/assets/{asset_id}/checkout", data={"employee_id": "1"})
    with app.app_context():
        asset = db.session.get(Asset, asset_id)
        assert len(asset.assignments) == 1

    resp = client.post(f"/assets/{asset_id}/checkin", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        asset = db.session.get(Asset, asset_id)
        assert asset.status == "Available"
        assert asset.current_assignment is None
        assert asset.assignments[0].returned_at is not None


def test_retired_asset_cannot_be_checked_out(client, app):
    client.post(
        "/assets/new",
        data={"asset_tag": "KB-0001", "name": "Old keyboard", "status": "Retired"},
    )
    with app.app_context():
        asset_id = db.session.scalar(
            db.select(Asset.id).where(Asset.asset_tag == "KB-0001")
        )
    client.post(f"/assets/{asset_id}/checkout", data={"employee_id": "1"})
    with app.app_context():
        asset = db.session.get(Asset, asset_id)
        assert asset.status == "Retired"
        assert asset.current_assignment is None


def test_employee_with_assets_cannot_be_deleted(client, app):
    client.post(
        "/assets/new",
        data={"asset_tag": "LT-0004", "name": "Laptop", "status": "Available"},
    )
    with app.app_context():
        asset_id = db.session.scalar(
            db.select(Asset.id).where(Asset.asset_tag == "LT-0004")
        )
    client.post(f"/assets/{asset_id}/checkout", data={"employee_id": "1"})
    client.post("/employees/1/delete")
    with app.app_context():
        assert db.session.get(Employee, 1) is not None

    client.post(f"/assets/{asset_id}/checkin")
    client.post("/employees/1/delete")
    with app.app_context():
        assert db.session.get(Employee, 1) is None


def test_asset_search_and_filter(client):
    # follow redirects so the "created" flash messages are consumed and don't
    # leak asset tags into the search page response
    client.post(
        "/assets/new",
        data={"asset_tag": "LT-0005", "name": "Zebra Laptop", "status": "Available"},
        follow_redirects=True,
    )
    client.post(
        "/assets/new",
        data={"asset_tag": "MN-0001", "name": "Monitor", "status": "In Repair"},
        follow_redirects=True,
    )
    resp = client.get("/assets?q=Zebra")
    assert b"LT-0005" in resp.data
    assert b"MN-0001" not in resp.data

    resp = client.get("/assets?status=In+Repair")
    assert b"MN-0001" in resp.data
    assert b"LT-0005" not in resp.data
