from . import db
from flask_login import UserMixin
from datetime import datetime


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CookieResult(db.Model):
    __tablename__ = 'cookie_results'
    id = db.Column(db.Integer, primary_key=True)

    # Cookie raw data
    service_type = db.Column(db.String(20), default='netflix', index=True)
    filename = db.Column(db.String(255))
    cookie_text = db.Column(db.Text, nullable=False)

    # Account classification
    plan_key = db.Column(db.String(50), index=True)       # premium, standard, basic, mobile, free
    plan_name = db.Column(db.String(100))                  # display label
    country = db.Column(db.String(10), index=True)         # 2-letter country code
    is_on_hold = db.Column(db.Boolean, default=False)

    # Account details
    email = db.Column(db.String(200))
    account_name = db.Column(db.String(200))
    quality = db.Column(db.String(50))                     # UHD, HD, SD
    max_streams = db.Column(db.String(20))
    plan_price = db.Column(db.String(50))
    next_billing = db.Column(db.String(100))
    payment_method = db.Column(db.String(100))
    member_since = db.Column(db.String(100))
    extra_members = db.Column(db.String(20))
    profiles = db.Column(db.Text)
    hold_status = db.Column(db.String(20))
    membership_status = db.Column(db.String(100))

    # Metadata
    checked_at = db.Column(db.DateTime, default=datetime.utcnow)
    source_file = db.Column(db.String(255))
