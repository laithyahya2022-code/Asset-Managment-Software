from datetime import date, datetime, timedelta

from .models import (Asset, Assignment, Category, Department, Employee,
                     License, LicenseAssignment, Location, Maintenance,
                     PurchaseOrder, User, Vendor, db)


def seed():
    """Populate the database with realistic sample data. Skips if assets exist."""
    if db.session.scalar(db.select(Asset).limit(1)):
        print("Database already contains assets; skipping seed.")
        return

    today = date.today()
    now = datetime.utcnow()

    # users
    admin = db.session.scalar(db.select(User).where(User.username == "admin"))
    if not admin:
        admin = User(username="admin", name="Administrator",
                     email="admin@example.com", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
    tech = User(username="tech", name="Sami Odeh", email="tech@example.com",
                role="technician")
    tech.set_password("tech1234")
    viewer = User(username="viewer", name="Reem Nasser", email="viewer@example.com",
                  role="viewer")
    viewer.set_password("viewer123")
    db.session.add_all([tech, viewer])

    # org structure (spec sections 6, 10 and 12)
    cat_defs = [
        ("Desktop Computers", "PC"), ("Laptops", "LPT"), ("Tablets", "TAB"),
        ("Monitors", "MON"), ("Printers", "PR"), ("Projectors", "DS"),
        ("Servers", "SRV"), ("Switches", "SW"), ("Routers", "RTR"),
        ("Firewalls", "FW"), ("Access Points", "AP"), ("UPS Devices", "UPS"),
        ("CCTV", "CCTV"), ("Telephones", "TEL"), ("Accessories", "ACC"),
        ("Peripherals", "PER"), ("Software Licenses", "SWL"),
        # kept for the sample data below
        ("Desktops", "DT"), ("Phones", "PH"), ("Networking", "NW"),
    ]
    cats = {n: Category(name=n, prefix=p) for n, p in cat_defs}
    deps = {n: Department(name=n, cost_center=cc) for n, cc in
            [("Admissions & Registration", "CC-100"), ("Accounting", "CC-200"),
             ("Secretariat", "CC-300"), ("Information Technology", "CC-400"),
             ("International Section", "CC-500"),
             ("National Section – Primary", "CC-600"),
             ("National Section – Secondary", "CC-700"),
             # kept for the sample data below
             ("IT", "CC-401"), ("Administration", "CC-201"),
             ("Science Lab", "CC-800"), ("Library", "CC-900")]}
    mada2 = Location(name="Mada 2", kind="Branch")
    mada3 = Location(name="Mada 3", kind="Branch")
    branch = Location(name="Mada 1", kind="Branch")
    bldg = Location(name="Building 1", kind="Building", parent=branch)
    floor1 = Location(name="Floor 1", kind="Floor", parent=bldg)
    lab = Location(name="Computer Lab", kind="Room", parent=floor1)
    office = Location(name="Admin Office", kind="Room", parent=floor1)
    storage = Location(name="IT Storage", kind="Storage Area", parent=floor1)
    bldg2 = Location(name="Building 2", kind="Building", parent=mada2)
    floor2 = Location(name="Floor 2", kind="Floor", parent=bldg2)
    staffroom = Location(name="Staff Room", kind="Room", parent=floor2)
    lab2 = Location(name="Science Lab", kind="Room", parent=floor2)
    db.session.add_all([mada2, mada3, bldg2, floor2, staffroom, lab2])
    vend = {
        "Dell": Vendor(name="Dell Technologies", contact_name="Sales Team",
                       email="sales@dell.com", website="https://dell.com"),
        "Apple": Vendor(name="Apple", email="business@apple.com",
                        website="https://apple.com"),
        "TechMart": Vendor(name="TechMart Local Supplier", contact_name="Abu Fadi",
                           phone="+962-6-000-0000"),
        "Microsoft": Vendor(name="Microsoft", website="https://microsoft.com"),
    }
    db.session.add_all(list(cats.values()) + list(deps.values())
                       + [branch, bldg, floor1, lab, office, storage]
                       + list(vend.values()))

    emps = [
        Employee(name="Alice Hart", email="alice.hart@example.com",
                 emp_code="EMP-1001", emp_type="Teacher",
                 title="Teacher", department=deps["Science Lab"]),
        Employee(name="Omar Khalil", email="omar.khalil@example.com",
                 emp_code="EMP-1002", emp_type="Administrative Staff",
                 title="Accountant", department=deps["Accounting"]),
        Employee(name="Dana Reyes", email="dana.reyes@example.com",
                 emp_code="EMP-1003", emp_type="Administrative Staff",
                 title="Librarian", department=deps["Library"]),
        Employee(name="Yousef Haddad", email="yousef.haddad@example.com",
                 emp_code="EMP-1004", emp_type="Administrative Staff",
                 title="IT Support", department=deps["Information Technology"]),
    ]
    db.session.add_all(emps)

    # Derive Branch/Building/Floor from where the location sits in the hierarchy,
    # so seeded assets exercise those columns and filters too.
    def place_of(loc):
        found = {}
        node = loc
        while node is not None:
            found[node.kind] = node.name
            node = node.parent
        floor = found.get("Floor", "")
        return {
            "branch": found.get("Branch"),
            "building": found.get("Building"),
            "floor": "F" + floor.split()[-1] if floor.startswith("Floor ") else None,
        }

    def mk(tag, name, cat, dep, loc, vendor, status="Available", cond="Good", **kw):
        for field, value in place_of(loc).items():
            kw.setdefault(field, value)
        return Asset(tag=tag, name=name, category=cats[cat], department=deps[dep],
                     location=loc, vendor=vend[vendor], status=status,
                     condition=cond, **kw)

    assets = [
        mk("LT-0001", 'MacBook Pro 14"', "Laptops", "IT", office, "Apple",
           status="Checked Out", serial="C02XL0AAJGH5", manufacturer="Apple",
           model="A2779", purchase_date=today - timedelta(days=400),
           purchase_cost=2399, warranty_expiry=today + timedelta(days=330)),
        mk("LT-0002", "ThinkPad X1 Carbon", "Laptops", "Administration", storage,
           "TechMart", serial="PF3XKQ7T", manufacturer="Lenovo", model="Gen 11",
           purchase_date=today - timedelta(days=200), purchase_cost=1650,
           warranty_expiry=today + timedelta(days=895)),
        mk("LT-0003", "Dell XPS 13", "Laptops", "Science Lab", lab2, "Dell",
           status="Under Maintenance", cond="Fair", serial="8HTQZY3", model="9340",
           manufacturer="Dell", purchase_date=today - timedelta(days=700),
           purchase_cost=1299, warranty_expiry=today - timedelta(days=30)),
        mk("DT-0001", "Dell OptiPlex 7010", "Desktops", "Library", office, "Dell",
           manufacturer="Dell", model="OptiPlex 7010",
           purchase_date=today - timedelta(days=300), purchase_cost=849,
           warranty_expiry=today + timedelta(days=65)),
        mk("MN-0001", 'Dell UltraSharp 27"', "Monitors", "IT", office, "Dell",
           status="Checked Out", serial="CN0H1MON01", manufacturer="Dell",
           model="U2723QE", purchase_date=today - timedelta(days=380),
           purchase_cost=549),
        mk("PH-0001", "iPhone 15", "Phones", "Administration", staffroom, "Apple",
           serial="F2LLD0AAPHN1", manufacturer="Apple", model="A3090",
           purchase_date=today - timedelta(days=150), purchase_cost=799,
           warranty_expiry=today + timedelta(days=215)),
        mk("PR-0001", "HP LaserJet Pro", "Printers", "Administration", staffroom,
           "TechMart", manufacturer="HP", model="M404dn",
           purchase_date=today - timedelta(days=600), purchase_cost=329),
        mk("NW-0001", "Cisco Switch 24p", "Networking", "IT", storage, "TechMart",
           manufacturer="Cisco", model="CBS250",
           purchase_date=today - timedelta(days=500), purchase_cost=419),
        mk("KB-0001", "MX Keys keyboard", "Peripherals", "IT", storage, "TechMart",
           status="Retired", cond="Broken", manufacturer="Logitech",
           purchase_date=today - timedelta(days=1200), purchase_cost=99),
    ]
    db.session.add_all(assets)

    db.session.add_all([
        Assignment(asset=assets[0], employee=emps[3], assigned_by=1,
                   assigned_at=now - timedelta(days=90),
                   due_at=today + timedelta(days=30), notes="Primary work laptop"),
        Assignment(asset=assets[4], employee=emps[3], assigned_by=1,
                   assigned_at=now - timedelta(days=90),
                   due_at=today - timedelta(days=5)),
        Assignment(asset=assets[1], employee=emps[1], assigned_by=1,
                   assigned_at=now - timedelta(days=300),
                   returned_at=now - timedelta(days=10), notes="Returned after audit"),
    ])

    db.session.add_all([
        Maintenance(asset=assets[2], kind="Corrective", title="Screen flicker repair",
                    status="In Progress", technician=None, cost=120,
                    scheduled_for=today + timedelta(days=3),
                    description="Panel replacement under RMA."),
        Maintenance(asset=assets[6], kind="Preventive", title="Annual printer service",
                    status="Scheduled", scheduled_for=today + timedelta(days=14),
                    parts="Toner, rollers", cost=45),
        Maintenance(asset=assets[7], kind="Preventive", title="Firmware update",
                    status="Completed", completed_at=now - timedelta(days=40), cost=0),
    ])

    lic_m365 = License(name="Microsoft 365 Business", vendor=vend["Microsoft"],
                       seats=10, cost=1250, purchase_date=today - timedelta(days=200),
                       expiry_date=today + timedelta(days=165))
    lic_av = License(name="Antivirus Endpoint", vendor=vend["TechMart"], seats=5,
                     cost=300, expiry_date=today + timedelta(days=45))
    lic_adobe = License(name="Adobe Creative Cloud", vendor=vend["TechMart"], seats=2,
                        cost=600, expiry_date=today + timedelta(days=300))
    db.session.add_all([lic_m365, lic_av, lic_adobe])
    db.session.add_all([
        LicenseAssignment(license=lic_m365, employee=emps[0]),
        LicenseAssignment(license=lic_m365, employee=emps[1]),
        LicenseAssignment(license=lic_m365, asset=assets[0]),
        LicenseAssignment(license=lic_av, asset=assets[1]),
        LicenseAssignment(license=lic_av, asset=assets[3]),
    ])

    db.session.add_all([
        PurchaseOrder(number="PO-2026-0001", vendor=vend["Dell"], status="Ordered",
                      description="Dell Latitude 5550 laptop",
                      category=cats["Laptops"], qty=5, unit_cost=1150,
                      expected_date=today + timedelta(days=20), requested_by=1),
        PurchaseOrder(number="PO-2026-0002", vendor=vend["TechMart"], status="Requested",
                      description='24" monitors for the computer lab',
                      category=cats["Monitors"], qty=10, unit_cost=180,
                      requested_by=1),
    ])

    db.session.commit()
