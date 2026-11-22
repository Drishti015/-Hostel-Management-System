from datetime import datetime
from app.models import db

class Student(db.Model):
    """
    Student Model - Stores complete academic and guardian demographic details.
    """
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    enrollment_no = db.Column(db.String(30), unique=True, nullable=False, index=True)
    roll_no = db.Column(db.String(30), nullable=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    gender = db.Column(db.Enum('male', 'female', 'other', name='student_gender_enum'), default='male', nullable=False)
    branch = db.Column(db.String(50), nullable=False, index=True)
    year = db.Column(db.Integer, default=1, nullable=False)
    semester = db.Column(db.Integer, default=1, nullable=False)
    guardian_name = db.Column(db.String(100), nullable=False)
    guardian_phone = db.Column(db.String(15), nullable=False)
    emergency_phone = db.Column(db.String(15), nullable=True)
    address = db.Column(db.Text, nullable=False)
    blood_group = db.Column(db.String(10), nullable=True)
    status = db.Column(db.Enum('active', 'suspended', 'vacated', name='student_status_enum'), default='active', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    allocations = db.relationship('BedAllocation', backref='student', lazy='dynamic', cascade='all, delete-orphan')
    fee_records = db.relationship('FeeRecord', backref='student', lazy='dynamic', cascade='all, delete-orphan')
    attendance_records = db.relationship('Attendance', backref='student', lazy='dynamic', cascade='all, delete-orphan')
    complaints = db.relationship('Complaint', backref='student', lazy='dynamic', cascade='all, delete-orphan')
    leave_applications = db.relationship('LeaveApplication', backref='student', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def current_allocation(self):
        """Returns the currently active bed allocation if any"""
        return self.allocations.filter_by(status='active').first()

    @property
    def has_active_allocation(self):
        return self.current_allocation is not None

    @property
    def total_fees_paid(self):
        from sqlalchemy import func
        from app.models.fee import FeeRecord
        total = db.session.query(func.sum(FeeRecord.amount)).filter_by(student_id=self.id, status='paid').scalar()
        return total or 0.0

    @property
    def attendance_percentage(self):
        total = self.attendance_records.count()
        if total == 0:
            return 100.0  # Default clean start
        present = self.attendance_records.filter_by(status='present').count()
        return round((present / total) * 100, 1)

    def __repr__(self):
        return f"<Student {self.full_name} ({self.enrollment_no})>"


class Warden(db.Model):
    """
    Warden Model - Profile information and building assignment for hostel wardens.
    """
    __tablename__ = 'wardens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    employee_id = db.Column(db.String(30), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    designation = db.Column(db.String(50), default='Hostel Warden', nullable=False)
    assigned_hostel_id = db.Column(db.Integer, db.ForeignKey('hostels.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    attendance_marked = db.relationship('Attendance', backref='marked_by_warden', lazy='dynamic')

    def __repr__(self):
        return f"<Warden {self.full_name} ({self.employee_id})>"

