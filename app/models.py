# app/models.py
# SQLAlchemy моделі CRM: Users, Companies, Owners, Checks, Events, Subscriptions

from datetime import datetime
from .extensions import db

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String, unique=True, nullable=False)
    full_name = db.Column(db.String)
    role = db.Column(db.String, default="user")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Company(db.Model):
    __tablename__ = "companies"
    id = db.Column(db.Integer, primary_key=True)
    vat_number = db.Column(db.String, index=True)
    registration_number = db.Column(db.String, index=True)
    name = db.Column(db.String, index=True)
    country = db.Column(db.String, index=True)
    address = db.Column(db.String)
    website = db.Column(db.String)
    # who initiated the lookup (optional)
    requester_name = db.Column(db.String)
    requester_email = db.Column(db.String)
    requester_org = db.Column(db.String)
    requester_vat_number = db.Column(db.String)
    requester_country_code = db.Column(db.String)
    raw_source = db.Column(db.JSON)
    current_status = db.Column(db.String, index=True)  # active/dissolved/insolvency/unknown
    confidence_score = db.Column(db.Integer, default=0)
    last_checked = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owners = db.relationship("CompanyOwner", backref="company", cascade="all, delete-orphan")
    checks = db.relationship("Check", backref="company", cascade="all, delete-orphan")
    events = db.relationship("CheckEvent", backref="company", cascade="all, delete-orphan")

class CompanyOwner(db.Model):
    __tablename__ = "company_owners"
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"))
    owner_name = db.Column(db.String, index=True)
    ownership_share = db.Column(db.Numeric)
    source = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Check(db.Model):
    __tablename__ = "checks"
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"))
    status = db.Column(db.String, index=True)      # ok/warning/critical/unknown/error
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    results = db.relationship("CheckResult", backref="check", cascade="all, delete-orphan")

class CheckResult(db.Model):
    __tablename__ = "check_results"
    id = db.Column(db.Integer, primary_key=True)
    check_id = db.Column(db.Integer, db.ForeignKey("checks.id"))
    adapter_name = db.Column(db.String, index=True)
    status = db.Column(db.String, index=True)
    details = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CheckEvent(db.Model):
    __tablename__ = "check_events"
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"))
    event_type = db.Column(db.String, index=True)  # status_changed/new_sanction/owner_changed
    payload = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MonitoringSubscription(db.Model):
    __tablename__ = "monitoring_subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    notify_by = db.Column(db.String)               # email/telegram/signal/json
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)