from datetime import datetime
from app.models import db

class Hostel(db.Model):
    """
    Hostel Model - Represents physical building blocks (e.g. Block A, Block B)
    """
    __tablename__ = 'hostels'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    hostel_type = db.Column(db.Enum('boys', 'girls', 'co-ed', name='hostel_type_enum'), nullable=False, default='boys')
    total_floors = db.Column(db.Integer, default=3, nullable=False)
    total_rooms = db.Column(db.Integer, default=0, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    rooms = db.relationship('Room', backref='hostel', lazy='dynamic', cascade='all, delete-orphan')
    wardens = db.relationship('Warden', backref='assigned_hostel', lazy='dynamic')
    allocations = db.relationship('BedAllocation', backref='hostel', lazy='dynamic')
    attendance_records = db.relationship('Attendance', backref='hostel', lazy='dynamic')

    @property
    def total_capacity(self):
        """Returns sum of bed capacity across all rooms"""
        return sum(room.capacity for room in self.rooms)

    @property
    def occupied_beds_count(self):
        """Returns total occupied beds in this hostel"""
        count = 0
        for room in self.rooms:
            count += room.occupied_beds_count
        return count

    @property
    def available_beds_count(self):
        return max(0, self.total_capacity - self.occupied_beds_count)

    def __repr__(self):
        return f"<Hostel {self.name} ({self.hostel_type})>"


class Room(db.Model):
    """
    Room Model - Represents individual rooms inside a hostel block
    """
    __tablename__ = 'rooms'

    id = db.Column(db.Integer, primary_key=True)
    hostel_id = db.Column(db.Integer, db.ForeignKey('hostels.id', ondelete='CASCADE'), nullable=False)
    room_number = db.Column(db.String(20), nullable=False)
    floor = db.Column(db.Integer, default=1, nullable=False)
    room_type = db.Column(db.Enum('single', 'double', 'triple', 'four', name='room_type_enum'), nullable=False, default='double')
    capacity = db.Column(db.Integer, default=2, nullable=False)
    monthly_fee = db.Column(db.Numeric(10, 2), default=5000.00, nullable=False)
    status = db.Column(db.Enum('active', 'maintenance', name='room_status_enum'), default='active', nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('hostel_id', 'room_number', name='uq_hostel_room'),
    )

    # Relationships
    beds = db.relationship('Bed', backref='room', lazy='dynamic', cascade='all, delete-orphan')
    allocations = db.relationship('BedAllocation', backref='room', lazy='dynamic')
    complaints = db.relationship('Complaint', backref='room', lazy='dynamic')

    @property
    def occupied_beds_count(self):
        return self.beds.filter_by(status='occupied').count()

    @property
    def available_beds_count(self):
        return self.beds.filter_by(status='available').count()

    @property
    def is_full(self):
        return self.available_beds_count == 0

    def __repr__(self):
        return f"<Room {self.room_number} [{self.room_type}]>"


class Bed(db.Model):
    """
    Bed Model - Represents individual beds inside a room
    """
    __tablename__ = 'beds'

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id', ondelete='CASCADE'), nullable=False)
    bed_number = db.Column(db.String(10), nullable=False)
    status = db.Column(db.Enum('available', 'occupied', 'maintenance', name='bed_status_enum'), default='available', nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('room_id', 'bed_number', name='uq_room_bed'),
    )

    # Relationships
    allocations = db.relationship('BedAllocation', backref='bed', lazy='dynamic')

    @property
    def current_allocation(self):
        return self.allocations.filter_by(status='active').first()

    def __repr__(self):
        return f"<Bed {self.bed_number} ({self.status})>"

