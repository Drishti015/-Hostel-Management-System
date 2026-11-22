from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import db

class User(UserMixin, db.Model):
    """
    User Model - Core Authentication Entity
    Handles Admin, Warden, and Student credentials and session state.
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('admin', 'warden', 'student', 'security', 'parent', 'mess_manager', 'mess_staff', name='user_roles'), nullable=False, default='student', index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    student_profile = db.relationship('Student', backref='user_account', uselist=False, cascade='all, delete-orphan')
    warden_profile = db.relationship('Warden', backref='user_account', uselist=False, cascade='all, delete-orphan')
    parent_profile = db.relationship('ParentProfile', backref='user_account', uselist=False, cascade='all, delete-orphan')
    notices_posted = db.relationship('Notice', backref='author', lazy='dynamic')
    complaint_responses = db.relationship('ComplaintResponse', backref='responder', lazy='dynamic')
    gate_scans = db.relationship('GateTransaction', backref='scanned_by_guard', lazy='dynamic')

    def set_password(self, password):
        """Hashes password using secure scrypt algorithm"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verifies plaintext against stored password hash"""
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_warden(self):
        return self.role == 'warden'

    @property
    def is_student(self):
        return self.role == 'student'

    @property
    def is_security(self):
        return self.role == 'security'

    @property
    def is_parent(self):
        return self.role == 'parent'

    @property
    def is_mess_manager(self):
        return self.role == 'mess_manager'

    @property
    def is_mess_staff(self):
        return self.role == 'mess_staff'

    def __repr__(self):
        return f"<User {self.username} [{self.role}]>"

