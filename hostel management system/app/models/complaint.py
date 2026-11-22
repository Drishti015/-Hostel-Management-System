from datetime import datetime
from app.models import db

class Complaint(db.Model):
    """
    Complaint Model - Grievance tickets filed by hostel students.
    """
    __tablename__ = 'complaints'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id', ondelete='SET NULL'), nullable=True)
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.Enum('electrical', 'plumbing', 'cleanliness', 'internet', 'mess', 'other', name='complaint_cat_enum'), default='other', nullable=False)
    priority = db.Column(db.Enum('low', 'medium', 'high', 'emergency', name='complaint_prio_enum'), default='medium', nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.Enum('pending', 'in_progress', 'resolved', name='complaint_status_enum'), default='pending', nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    responses = db.relationship('ComplaintResponse', backref='complaint', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Complaint #{self.id}: {self.title} [{self.status}]>"


class ComplaintResponse(db.Model):
    """
    ComplaintResponse Model - Audit response trail by Wardens or Admins.
    """
    __tablename__ = 'complaint_responses'

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey('complaints.id', ondelete='CASCADE'), nullable=False)
    responder_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    response_text = db.Column(db.Text, nullable=False)
    status_updated_to = db.Column(db.Enum('pending', 'in_progress', 'resolved', name='complaint_status_enum'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ComplaintResponse #{self.id} for Complaint #{self.complaint_id}>"

