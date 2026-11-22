from datetime import datetime
from app.models import db

class LeaveApplication(db.Model):
    """
    LeaveApplication Model - Tracks student out-of-hostel leave requests,
    approval workflows, warden remarks, and audit trails.
    """
    __tablename__ = 'leave_applications'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    hostel_id = db.Column(db.Integer, db.ForeignKey('hostels.id', ondelete='SET NULL'), nullable=True, index=True)
    leave_type = db.Column(db.String(50), nullable=False)
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    destination = db.Column(db.String(255), nullable=False)
    emergency_contact = db.Column(db.String(20), nullable=False)
    supporting_document = db.Column(db.String(255), nullable=True)
    status = db.Column(
        db.Enum('Pending', 'Approved', 'Rejected', 'Cancelled', name='leave_status_enum'),
        default='Pending',
        nullable=False,
        index=True
    )
    reviewed_by = db.Column(db.Integer, db.ForeignKey('wardens.id', ondelete='SET NULL'), nullable=True)
    review_comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    reviewer = db.relationship('Warden', foreign_keys=[reviewed_by], backref=db.backref('reviewed_leaves', lazy='dynamic'))
    hostel = db.relationship('Hostel', foreign_keys=[hostel_id], backref=db.backref('leaves', lazy='dynamic'))

    @property
    def number_of_days(self):
        """Calculates total number of calendar leave days inclusive"""
        if self.from_date and self.to_date:
            return max(1, (self.to_date - self.from_date).days + 1)
        return 0

    @property
    def is_pending(self):
        return self.status == 'Pending'

    @property
    def is_approved(self):
        return self.status == 'Approved'

    @property
    def outpass(self):
        return getattr(self, 'out_pass', None)

    @property
    def is_rejected(self):
        return self.status == 'Rejected'

    @property
    def is_cancelled(self):
        return self.status == 'Cancelled'

    def __repr__(self):
        return f"<LeaveApplication #{self.id} Student:{self.student_id} [{self.status}]>"

