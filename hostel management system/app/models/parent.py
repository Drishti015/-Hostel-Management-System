from datetime import datetime
from app.models import db

class ParentProfile(db.Model):
    """
    Parent Profile Model - Demographics, relationship, and student link.
    """
    __tablename__ = 'parent_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    parent_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    relationship_to_student = db.Column(db.String(50), nullable=False, default='Father')  # Father, Mother, Legal Guardian, Other
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=True)
    account_status = db.Column(db.String(20), default='active', nullable=False)  # 'active', 'inactive'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    student = db.relationship('Student', backref=db.backref('parent_profiles', lazy='dynamic', cascade='all, delete-orphan'))
    inquiries = db.relationship('ParentInquiry', backref='parent', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def is_active(self):
        return self.account_status == 'active' and self.user_account.is_active

    @property
    def linked_student(self):
        return self.student if self.student and self.is_active else None

    def __repr__(self):
        return f"<ParentProfile {self.parent_name} (User #{self.user_id}) -> Student #{self.student_id}>"


class ParentInquiry(db.Model):
    """
    Parent Inquiry / Communication Model for direct communication with assigned Warden.
    """
    __tablename__ = 'parent_inquiries'

    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('parent_profiles.id', ondelete='CASCADE'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    warden_id = db.Column(db.Integer, db.ForeignKey('wardens.id', ondelete='SET NULL'), nullable=True)
    subject = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='Pending', nullable=False)  # 'Pending', 'In Progress', 'Resolved'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    student = db.relationship('Student', backref=db.backref('inquiries', lazy='dynamic'))
    warden = db.relationship('Warden', backref=db.backref('parent_inquiries', lazy='dynamic'))

    def __repr__(self):
        return f"<ParentInquiry #{self.id} '{self.subject}' [{self.status}]>"

