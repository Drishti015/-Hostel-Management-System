from datetime import datetime
from app.models import db

class Notice(db.Model):
    """
    Notice Model - Digital announcements and bulletins for hostel residents.
    """
    __tablename__ = 'notices'

    id = db.Column(db.Integer, primary_key=True)
    posted_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.Enum('announcement', 'event', 'urgent', 'maintenance', name='notice_category_enum'), default='announcement', nullable=False)
    target_audience = db.Column(db.Enum('all', 'boys', 'girls', 'wardens', name='notice_audience_enum'), default='all', nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Notice #{self.id}: {self.title} ({self.target_audience})>"

