from datetime import date, datetime, timedelta

from .models import Asset, Assignment, Category, Employee, db


def seed():
    """Populate the database with sample data (idempotent-ish: skips if data exists)."""
    if db.session.scalar(db.select(Asset).limit(1)):
        print("Database already contains assets; skipping seed.")
        return

    laptops = Category(name="Laptops")
    monitors = Category(name="Monitors")
    phones = Category(name="Phones")
    peripherals = Category(name="Peripherals")
    db.session.add_all([laptops, monitors, phones, peripherals])

    alice = Employee(name="Alice Hart", email="alice.hart@example.com", department="Engineering")
    omar = Employee(name="Omar Khalil", email="omar.khalil@example.com", department="Finance")
    dana = Employee(name="Dana Reyes", email="dana.reyes@example.com", department="Design")
    db.session.add_all([alice, omar, dana])

    today = date.today()
    assets = [
        Asset(asset_tag="LT-0001", name='MacBook Pro 14"', category=laptops,
              manufacturer="Apple", model="A2779", serial_number="C02XL0AAJGH5",
              status="Assigned", location="HQ – Floor 2",
              purchase_date=today - timedelta(days=400), purchase_cost=2399,
              warranty_expiry=today + timedelta(days=330)),
        Asset(asset_tag="LT-0002", name="ThinkPad X1 Carbon", category=laptops,
              manufacturer="Lenovo", model="Gen 11", serial_number="PF3XKQ7T",
              status="Available", location="IT storage",
              purchase_date=today - timedelta(days=200), purchase_cost=1650,
              warranty_expiry=today + timedelta(days=895)),
        Asset(asset_tag="LT-0003", name="Dell XPS 13", category=laptops,
              manufacturer="Dell", model="9340", serial_number="8HTQZY3",
              status="In Repair", location="Vendor RMA",
              purchase_date=today - timedelta(days=700), purchase_cost=1299,
              warranty_expiry=today - timedelta(days=30)),
        Asset(asset_tag="MN-0001", name='Dell UltraSharp 27"', category=monitors,
              manufacturer="Dell", model="U2723QE", serial_number="CN0H1MON01",
              status="Assigned", location="HQ – Floor 2",
              purchase_date=today - timedelta(days=380), purchase_cost=549),
        Asset(asset_tag="PH-0001", name="iPhone 15", category=phones,
              manufacturer="Apple", model="A3090", serial_number="F2LLD0AAPHN1",
              status="Available", location="IT storage",
              purchase_date=today - timedelta(days=150), purchase_cost=799,
              warranty_expiry=today + timedelta(days=215)),
        Asset(asset_tag="KB-0001", name="MX Keys keyboard", category=peripherals,
              manufacturer="Logitech", model="MX Keys S",
              status="Retired", location="Disposed",
              purchase_date=today - timedelta(days=1200), purchase_cost=99),
    ]
    db.session.add_all(assets)

    now = datetime.utcnow()
    db.session.add_all([
        Assignment(asset=assets[0], employee=alice,
                   assigned_at=now - timedelta(days=90), notes="New hire kit"),
        Assignment(asset=assets[3], employee=alice,
                   assigned_at=now - timedelta(days=90)),
        Assignment(asset=assets[1], employee=omar,
                   assigned_at=now - timedelta(days=300),
                   returned_at=now - timedelta(days=10), notes="Returned on team switch"),
    ])
    db.session.commit()
