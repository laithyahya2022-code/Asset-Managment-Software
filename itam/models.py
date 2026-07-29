import json
from datetime import datetime, date

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

ASSET_STATUSES = ["Available", "Checked Out", "In Use", "Reserved", "In Storage",
                  "Under Maintenance", "Lost", "Damaged", "Missing", "Retired", "Disposed"]
BLOCKED_CHECKOUT_STATUSES = ("Retired", "Disposed", "Lost", "Missing")
ASSET_CONDITIONS = ["New", "Excellent", "Good", "Fair", "Poor", "Damaged", "Broken"]
ROLES = ["superadmin", "admin", "it_manager", "it_staff", "asset_manager",
         "inventory_manager", "data_entry", "dept_manager", "employee",
         "viewer", "auditor",
         # kept for compatibility with earlier installs
         "manager", "technician"]
EMPLOYEE_TYPES = ["Administrative Staff", "Teacher"]
BRANCHES = ["Mada 1", "Mada 2", "Mada 3"]
BUILDINGS = ["Building 1", "Building 2", "Building 3"]
FLOORS = ["B1", "GF", "F1", "F2", "F3", "F4", "F5"]
PLACES = ["Reception", "Admin Office", "Registration office", "Teachers Room",
          "Supervisor Room", "Principal", "Secretary Office", "Class Room"]
LOCATION_KINDS = ["Branch", "Building", "Floor", "Room", "Storage Area"]
# Suggestions for the asset form's Operating system box. The field stays free
# text, so anything not listed here (or already imported) is still accepted.
OPERATING_SYSTEMS = [
    "Windows 11 Pro", "Windows 11 Home", "Windows 10 Pro", "Windows 10 Home",
    "Windows Server 2022", "Windows Server 2019",
    "macOS", "iOS", "iPadOS", "Android", "ChromeOS",
    "Ubuntu Linux", "Debian Linux", "Fedora Linux", "Red Hat Enterprise Linux",
    "Linux (other)", "Printer firmware", "Switch firmware", "Embedded / none",
]
MAINTENANCE_KINDS = ["Preventive", "Corrective"]
MAINTENANCE_STATUSES = ["Scheduled", "In Progress", "Completed", "Cancelled"]
PO_STATUSES = ["Requested", "Approved", "Ordered", "Received", "Cancelled"]

PERMISSIONS = [
    "assets.view", "assets.manage", "checkout.manage", "maintenance.manage",
    "licenses.manage", "people.manage", "org.manage", "procurement.manage",
    "inventory.manage", "reports.view", "admin.users", "admin.settings", "api.access",
]

_OPS = [p for p in PERMISSIONS if not p.startswith("admin.")]
DEFAULT_ROLE_PERMS = {
    "superadmin": PERMISSIONS,
    "admin": PERMISSIONS,
    "it_manager": _OPS,
    "it_staff": ["assets.view", "assets.manage", "checkout.manage",
                 "maintenance.manage", "inventory.manage", "reports.view"],
    "asset_manager": ["assets.view", "assets.manage", "checkout.manage",
                      "licenses.manage", "procurement.manage", "org.manage",
                      "people.manage", "reports.view"],
    "inventory_manager": ["assets.view", "inventory.manage", "checkout.manage",
                          "reports.view"],
    "data_entry": ["assets.view", "assets.manage"],
    "dept_manager": ["assets.view", "reports.view"],
    "employee": ["assets.view"],
    "viewer": ["assets.view", "reports.view"],
    "auditor": ["assets.view", "reports.view"],
    "manager": _OPS,
    "technician": ["assets.view", "assets.manage", "checkout.manage",
                   "maintenance.manage", "inventory.manage", "reports.view"],
}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="viewer")
    active = db.Column(db.Boolean, nullable=False, default=True)
    language = db.Column(db.String(5), nullable=False, default="en")
    api_key = db.Column(db.String(64), unique=True)
    reset_token = db.Column(db.String(64))
    reset_expires = db.Column(db.DateTime)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class RolePermission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False)
    permission = db.Column(db.String(40), nullable=False)
    __table_args__ = (db.UniqueConstraint("role", "permission"),)


class Setting(db.Model):
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.Text)


class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    action = db.Column(db.String(40), nullable=False)
    entity_type = db.Column(db.String(40))
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User")


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(30), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    link = db.Column(db.String(255))
    dedupe_key = db.Column(db.String(120), unique=True)
    read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class SavedSearch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    query = db.Column(db.String(500), nullable=False)  # URL query string
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    prefix = db.Column(db.String(10))  # auto-numbering prefix, e.g. PC -> PC-000001
    assets = db.relationship("Asset", back_populates="category")

    @property
    def tag_prefix(self):
        if self.prefix:
            return self.prefix.upper()
        return "".join(c for c in self.name.upper() if c.isalnum())[:3] or "AST"


class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    cost_center = db.Column(db.String(40))
    assets = db.relationship("Asset", back_populates="department")
    employees = db.relationship("Employee", back_populates="department")


class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    kind = db.Column(db.String(20), nullable=False, default="Room")
    parent_id = db.Column(db.Integer, db.ForeignKey("location.id"))
    parent = db.relationship("Location", remote_side=[id], backref="children")
    assets = db.relationship("Asset", back_populates="location")

    @property
    def path(self):
        parts, node, seen = [], self, set()
        while node and node.id not in seen:
            seen.add(node.id)
            parts.append(node.name)
            node = node.parent
        return " / ".join(reversed(parts))


class Vendor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    contact_name = db.Column(db.String(120))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    website = db.Column(db.String(160))
    notes = db.Column(db.Text)
    assets = db.relationship("Asset", back_populates="vendor")
    licenses = db.relationship("License", back_populates="vendor")
    orders = db.relationship("PurchaseOrder", back_populates="vendor")


class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    emp_code = db.Column(db.String(40))          # Employee ID badge number
    emp_type = db.Column(db.String(60))          # Teacher, IT Technical, Supervisor, …
    email = db.Column(db.String(120))            # optional; may repeat (shared inboxes)
    phone = db.Column(db.String(40))
    title = db.Column(db.String(80))
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"))
    active = db.Column(db.Boolean, nullable=False, default=True)

    department = db.relationship("Department", back_populates="employees")
    assignments = db.relationship("Assignment", back_populates="employee")

    @property
    def current_assets(self):
        return [a.asset for a in self.assignments if a.returned_at is None]


class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    asset_type = db.Column(db.String(60))
    serial = db.Column(db.String(120))
    manufacturer = db.Column(db.String(80))
    model = db.Column(db.String(120))
    # technical specifications
    os_name = db.Column(db.String(60))
    os_version = db.Column(db.String(60))
    cpu = db.Column(db.String(80))
    ram = db.Column(db.String(40))
    storage = db.Column(db.String(60))
    gpu = db.Column(db.String(80))
    hostname = db.Column(db.String(80))
    mac_address = db.Column(db.String(40))
    ip_address = db.Column(db.String(45))
    invoice_number = db.Column(db.String(60))
    branch = db.Column(db.String(40))     # Mada 1 / Mada 2 / Mada 3
    building = db.Column(db.String(40))   # Building 1 / 2 / 3
    floor = db.Column(db.String(10))      # B1 / GF / F1..F5
    location_name = db.Column(db.String(120))  # Reception, Class Room, … (free text)
    updated_by = db.Column(db.String(120))     # data-entry person's name
    parent_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
    status = db.Column(db.String(25), nullable=False, default="Available")
    condition = db.Column(db.String(15), nullable=False, default="Good")
    location_id = db.Column(db.Integer, db.ForeignKey("location.id"))
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"))
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendor.id"))
    purchase_date = db.Column(db.Date)
    purchase_cost = db.Column(db.Numeric(12, 2))
    depreciation_years = db.Column(db.Integer, default=5)
    warranty_expiry = db.Column(db.Date)
    notes = db.Column(db.Text)
    custom_fields = db.Column(db.Text)  # JSON dict
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = db.relationship("Category", back_populates="assets")
    parent = db.relationship("Asset", remote_side="Asset.id", backref="components")
    location = db.relationship("Location", back_populates="assets")
    department = db.relationship("Department", back_populates="assets")
    vendor = db.relationship("Vendor", back_populates="assets")
    assignments = db.relationship("Assignment", back_populates="asset",
                                  order_by="Assignment.assigned_at.desc()",
                                  cascade="all, delete-orphan")
    maintenance = db.relationship("Maintenance", back_populates="asset",
                                  order_by="Maintenance.created_at.desc()",
                                  cascade="all, delete-orphan")
    files = db.relationship("AssetFile", back_populates="asset", cascade="all, delete-orphan")
    transfers = db.relationship("Transfer", back_populates="asset",
                                order_by="Transfer.at.desc()", cascade="all, delete-orphan")
    reservations = db.relationship("Reservation", back_populates="asset",
                                   cascade="all, delete-orphan")

    @property
    def current_assignment(self):
        for a in self.assignments:
            if a.returned_at is None:
                return a
        return None

    @property
    def warranty_expired(self):
        return self.warranty_expiry is not None and self.warranty_expiry < date.today()

    @property
    def custom(self):
        try:
            return json.loads(self.custom_fields or "{}")
        except ValueError:
            return {}

    @property
    def current_value(self):
        if self.purchase_cost is None:
            return None
        years = self.depreciation_years or 5
        if not self.purchase_date or years <= 0:
            return float(self.purchase_cost)
        age = (date.today() - self.purchase_date).days / 365.25
        return round(float(self.purchase_cost) * max(0.0, 1 - age / years), 2)


class AssetFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    stored_name = db.Column(db.String(160), nullable=False)
    orig_name = db.Column(db.String(160), nullable=False)
    kind = db.Column(db.String(20), nullable=False, default="document")
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    asset = db.relationship("Asset", back_populates="files")


class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    due_at = db.Column(db.Date)
    returned_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    return_condition = db.Column(db.String(15))   # condition observed at check-in
    return_notes = db.Column(db.Text)             # damage / inspection notes
    asset = db.relationship("Asset", back_populates="assignments")
    employee = db.relationship("Employee", back_populates="assignments")

    @property
    def overdue(self):
        return self.returned_at is None and self.due_at is not None and self.due_at < date.today()


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(15), nullable=False, default="Active")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    asset = db.relationship("Asset", back_populates="reservations")
    employee = db.relationship("Employee")


class Transfer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    from_location_id = db.Column(db.Integer, db.ForeignKey("location.id"))
    to_location_id = db.Column(db.Integer, db.ForeignKey("location.id"))
    by_user = db.Column(db.Integer, db.ForeignKey("user.id"))
    at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    notes = db.Column(db.Text)
    asset = db.relationship("Asset", back_populates="transfers")
    from_location = db.relationship("Location", foreign_keys=[from_location_id])
    to_location = db.relationship("Location", foreign_keys=[to_location_id])


class Maintenance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    kind = db.Column(db.String(15), nullable=False, default="Corrective")
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    solution = db.Column(db.Text)
    status = db.Column(db.String(15), nullable=False, default="Scheduled")
    scheduled_for = db.Column(db.Date)
    completed_at = db.Column(db.DateTime)
    technician_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    cost = db.Column(db.Numeric(12, 2))
    parts = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    asset = db.relationship("Asset", back_populates="maintenance")
    technician = db.relationship("User")


class License(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendor.id"))
    key = db.Column(db.String(255))
    seats = db.Column(db.Integer, nullable=False, default=1)
    purchase_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    cost = db.Column(db.Numeric(12, 2))
    notes = db.Column(db.Text)
    vendor = db.relationship("Vendor", back_populates="licenses")
    assignments = db.relationship("LicenseAssignment", back_populates="license",
                                  cascade="all, delete-orphan")

    @property
    def seats_used(self):
        return len([a for a in self.assignments if a.revoked_at is None])

    @property
    def compliant(self):
        return self.seats_used <= self.seats

    @property
    def expired(self):
        return self.expiry_date is not None and self.expiry_date < date.today()


class LicenseAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    license_id = db.Column(db.Integer, db.ForeignKey("license.id"), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"))
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = db.Column(db.DateTime)
    license = db.relationship("License", back_populates="assignments")
    asset = db.relationship("Asset")
    employee = db.relationship("Employee")


class PurchaseOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(30), unique=True, nullable=False)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendor.id"))
    status = db.Column(db.String(15), nullable=False, default="Requested")
    description = db.Column(db.String(200), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    qty = db.Column(db.Integer, nullable=False, default=1)
    unit_cost = db.Column(db.Numeric(12, 2))
    expected_date = db.Column(db.Date)
    requested_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    received_at = db.Column(db.DateTime)
    vendor = db.relationship("Vendor", back_populates="orders")
    category = db.relationship("Category")
    requester = db.relationship("User")

    @property
    def total(self):
        if self.unit_cost is None:
            return None
        return float(self.unit_cost) * self.qty


class InventoryAudit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime)
    by_user = db.Column(db.Integer, db.ForeignKey("user.id"))
    checks = db.relationship("InventoryCheck", back_populates="audit",
                             cascade="all, delete-orphan")
    user = db.relationship("User")

    @property
    def verified_count(self):
        return len([c for c in self.checks if c.status == "Verified"])

    @property
    def missing_count(self):
        return len([c for c in self.checks if c.status == "Missing"])


class InventoryCheck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    audit_id = db.Column(db.Integer, db.ForeignKey("inventory_audit.id"), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    status = db.Column(db.String(10), nullable=False)  # Verified | Missing
    checked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    audit = db.relationship("InventoryAudit", back_populates="checks")
    asset = db.relationship("Asset")
    __table_args__ = (db.UniqueConstraint("audit_id", "asset_id"),)
