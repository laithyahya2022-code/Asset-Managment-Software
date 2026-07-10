from datetime import datetime, date

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

ASSET_STATUSES = ["Available", "Assigned", "In Repair", "Retired"]


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    assets = db.relationship("Asset", back_populates="category")

    def __repr__(self):
        return f"<Category {self.name}>"


class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    department = db.Column(db.String(80))

    assignments = db.relationship("Assignment", back_populates="employee")

    @property
    def current_assets(self):
        return [a.asset for a in self.assignments if a.returned_at is None]

    def __repr__(self):
        return f"<Employee {self.email}>"


class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_tag = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("category.id"))
    serial_number = db.Column(db.String(120))
    manufacturer = db.Column(db.String(80))
    model = db.Column(db.String(120))
    status = db.Column(db.String(20), nullable=False, default="Available")
    location = db.Column(db.String(120))
    purchase_date = db.Column(db.Date)
    purchase_cost = db.Column(db.Numeric(12, 2))
    warranty_expiry = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    category = db.relationship("Category", back_populates="assets")
    assignments = db.relationship(
        "Assignment",
        back_populates="asset",
        order_by="Assignment.assigned_at.desc()",
        cascade="all, delete-orphan",
    )

    @property
    def current_assignment(self):
        for a in self.assignments:
            if a.returned_at is None:
                return a
        return None

    @property
    def warranty_expired(self):
        return self.warranty_expiry is not None and self.warranty_expiry < date.today()

    def __repr__(self):
        return f"<Asset {self.asset_tag}>"


class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    returned_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)

    asset = db.relationship("Asset", back_populates="assignments")
    employee = db.relationship("Employee", back_populates="assignments")

    def __repr__(self):
        return f"<Assignment asset={self.asset_id} employee={self.employee_id}>"
