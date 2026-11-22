from datetime import datetime
from app.models import db

class Attendance(db.Model):
    """
    Attendance Model - Daily night roll-call record per student.
    Enforces uniqueness of student + date to eliminate double marking.
    """
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    hostel_id = db.Column(db.Integer, db.ForeignKey('hostels.id', ondelete='CASCADE'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date, index=True)
    status = db.Column(db.Enum('present', 'absent', 'leave', name='attendance_status_enum'), default='present', nullable=False)
    marked_by_warden_id = db.Column(db.Integer, db.ForeignKey('wardens.id', ondelete='SET NULL'), nullable=True)
    remarks = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'date', name='uq_student_daily_attendance'),
    )

    def __repr__(self):
        return f"<Attendance Student:{self.student_id} on {self.date}: {self.status}>"

