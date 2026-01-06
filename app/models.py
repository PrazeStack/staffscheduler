from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from .extensions import db

class Admin(UserMixin, db.Model):
    __tablename__ = "admins"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

# We will flesh these out next step (CRUD), but define now so migrations are stable
class Staff(db.Model):
    __tablename__ = "staff"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False, index=True)

    gender = db.Column(db.String(10), nullable=False)  
    # e.g. "Male", "Female", "Other"

    phone = db.Column(db.String(40), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Unit(db.Model):
    __tablename__ = "units"
    id = db.Column(db.Integer, primary_key=True)
    unit_name = db.Column(db.String(140), nullable=False, index=True)
    address = db.Column(db.String(220), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Request(db.Model):
    __tablename__ = "requests"
    id = db.Column(db.Integer, primary_key=True)

    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=False)
    unit = db.relationship("Unit", backref=db.backref("requests", lazy=True))

    coordinator_name = db.Column(db.String(140), nullable=False)
    staff_needed = db.Column(db.Integer, nullable=False)

    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)

    status = db.Column(db.String(20), nullable=False, default="Open")  # Open/Satisfied/Canceled

    created_by_admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=False)
    created_by = db.relationship("Admin", backref=db.backref("requests_created", lazy=True))

    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    recurring_id = db.Column(db.Integer, db.ForeignKey("recurring_requests.id"), nullable=True)
    occurrence_date = db.Column(db.Date, nullable=True)

    recurring = db.relationship("RecurringRequest", backref="occurrences")

    __table_args__ = (
    db.UniqueConstraint("recurring_id", "occurrence_date", name="uq_request_recurring_occurrence"),
)

class Assignment(db.Model):
    __tablename__ = "assignments"
    id = db.Column(db.Integer, primary_key=True)

    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=False)
    staff = db.relationship("Staff", backref=db.backref("assignments", lazy=True))

    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=False)
    unit = db.relationship("Unit", backref=db.backref("assignments", lazy=True))

    request_id = db.Column(db.Integer, db.ForeignKey("requests.id"), nullable=True)
    request = db.relationship("Request", backref=db.backref("assignments", lazy=True))

    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)

    status = db.Column(db.String(20), nullable=False, default="Scheduled")  # Scheduled/Confirmed/Canceled
    notes = db.Column(db.Text, nullable=True)

    created_by_admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=False)
    created_by = db.relationship("Admin", backref=db.backref("assignments_created", lazy=True))

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    recurring_id = db.Column(db.Integer, nullable=True)      # keep FK out for SQLite sanity
    occurrence_date = db.Column(db.Date, nullable=True)

    __table_args__ = (
    db.UniqueConstraint("recurring_id", "occurrence_date", name="uq_assignment_recurring_occurrence"),
    )



class RecurringRequest(db.Model):
    __tablename__ = "recurring_requests"

    id = db.Column(db.Integer, primary_key=True)

    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=False)
    unit = db.relationship("Unit", backref="recurring_requests")

    coordinator_name = db.Column(db.String(120), nullable=False)
    staff_needed = db.Column(db.Integer, nullable=False)

    # store "time only"
    start_time = db.Column(db.String(5), nullable=False)  # "HH:MM"
    end_time = db.Column(db.String(5), nullable=False)    # "HH:MM"

    # bitmask: Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64
    days_mask = db.Column(db.Integer, nullable=False, default=0)

    start_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date, nullable=True)  # NULL => until changed

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    notes = db.Column(db.Text, nullable=True)

    created_by_admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class RecurringAssignment(db.Model):
    __tablename__ = "recurring_assignments"

    id = db.Column(db.Integer, primary_key=True)

    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=False)
    staff = db.relationship("Staff", backref="recurring_assignments")

    unit_id = db.Column(db.Integer, db.ForeignKey("units.id"), nullable=False)
    unit = db.relationship("Unit", backref="recurring_assignments")

    # store "time only"
    start_time = db.Column(db.String(5), nullable=False)  # "HH:MM"
    end_time = db.Column(db.String(5), nullable=False)    # "HH:MM"

    # bitmask: Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64
    days_mask = db.Column(db.Integer, nullable=False, default=0)

    start_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date, nullable=True)  # NULL => until changed

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    created_by_admin_id = db.Column(db.Integer, db.ForeignKey("admins.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

   