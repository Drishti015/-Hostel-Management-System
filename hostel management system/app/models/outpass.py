import hashlib
from datetime import datetime, date
from app.models import db

class DigitalOutPass(db.Model):
    """
    DigitalOutPass Model - Digital hostel gate pass tied to an approved leave application.
    Stores cryptographically secure token hash, pass lifecycle state, and timestamps.
    """
    __tablename__ = 'digital_out_passes'

    id = db.Column(db.Integer, primary_key=True)
    leave_application_id = db.Column(db.Integer, db.ForeignKey('leave_applications.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    pass_token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    status = db.Column(
        db.Enum('Active', 'Used', 'Expired', 'Revoked', 'Completed', name='outpass_status_enum'),
        default='Active',
        nullable=False,
        index=True
    )
    departure_date = db.Column(db.Date, nullable=False)
    expected_return_date = db.Column(db.Date, nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_outside = db.Column(db.Boolean, default=False, nullable=False, index=True)
    actual_departure_time = db.Column(db.DateTime, nullable=True)
    actual_return_time = db.Column(db.DateTime, nullable=True)
    qr_code_file = db.Column(db.String(255), nullable=True)
    revoked_reason = db.Column(db.String(255), nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    leave_application = db.relationship('LeaveApplication', backref=db.backref('out_pass', uselist=False, cascade='all, delete-orphan'))
    student = db.relationship('Student', backref=db.backref('out_passes', lazy='dynamic', cascade='all, delete-orphan'))
    transactions = db.relationship('GateTransaction', backref='out_pass', lazy='dynamic', cascade='all, delete-orphan', order_by='GateTransaction.scanned_at.desc()')

    @property
    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    @property
    def is_overdue(self):
        # Overdue if student is still outside past the expected return deadline
        return self.is_outside and datetime.utcnow() > self.expires_at

    @property
    def last_transaction(self):
        return self.transactions.first()

    @property
    def qr_code_url(self):
        if not self.qr_code_file:
            return None
        from flask import url_for
        if self.qr_code_file.startswith('uploads/'):
            return url_for('static', filename=self.qr_code_file)
        return url_for('static', filename=f'uploads/qrcodes/{self.qr_code_file}')

    @property
    def exit_transaction(self):
        return self.transactions.filter_by(event_type='EXIT', verification_status='Success').order_by(GateTransaction.scanned_at.desc()).first()

    @property
    def entry_transaction(self):
        return self.transactions.filter_by(event_type='ENTRY', verification_status='Success').order_by(GateTransaction.scanned_at.desc()).first()

    @property
    def duration_days(self):
        if self.departure_date and self.expected_return_date:
            return max(1, (self.expected_return_date - self.departure_date).days + 1)
        return 0

    def __repr__(self):
        return f"<DigitalOutPass #{self.id} Student:{self.student_id} [{self.status}] Outside:{self.is_outside}>"


class GateTransaction(db.Model):
    """
    GateTransaction Model - Audit log of individual gate scan events (EXIT / ENTRY)
    recorded by security guard stations.
    """
    __tablename__ = 'gate_transactions'

    id = db.Column(db.Integer, primary_key=True)
    outpass_id = db.Column(db.Integer, db.ForeignKey('digital_out_passes.id', ondelete='CASCADE'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    security_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    event_type = db.Column(db.Enum('EXIT', 'ENTRY', name='gate_event_type_enum'), nullable=False, index=True)
    scanned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    gate_location = db.Column(db.String(100), default='Main Campus Gate', nullable=False)
    verification_status = db.Column(db.Enum('Success', 'Failed', name='gate_verification_enum'), default='Success', nullable=False)
    remarks = db.Column(db.Text, nullable=True)

    # Relationships
    student = db.relationship('Student', backref=db.backref('gate_transactions', lazy='dynamic'))

    @property
    def security_user(self):
        return self.scanned_by_guard

    def __repr__(self):
        return f"<GateTransaction #{self.id} Pass:{self.outpass_id} {self.event_type} [{self.verification_status}]>"
