from datetime import datetime
from app.models import db

class BedAllocation(db.Model):
    """
    BedAllocation Model - Tracks which student occupies which bed in which room and hostel.
    Enforces referential integrity and historic records.
    """
    __tablename__ = 'allocations'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    bed_id = db.Column(db.Integer, db.ForeignKey('beds.id', ondelete='CASCADE'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id', ondelete='CASCADE'), nullable=False)
    hostel_id = db.Column(db.Integer, db.ForeignKey('hostels.id', ondelete='CASCADE'), nullable=False)
    allocated_from = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    allocated_to = db.Column(db.Date, nullable=True)
    status = db.Column(db.Enum('active', 'vacated', 'transferred', name='allocation_status_enum'), default='active', nullable=False, index=True)
    vacated_reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def vacate(self, reason='Standard Checkout'):
        """Vacates the bed atomically"""
        self.status = 'vacated'
        self.allocated_to = datetime.utcnow().date()
        self.vacated_reason = reason
        self.bed.status = 'available'

    def __repr__(self):
        return f"<Allocation Student:{self.student_id} -> Bed:{self.bed_id} [{self.status}]>"

