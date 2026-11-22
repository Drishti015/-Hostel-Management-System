from flask_sqlalchemy import SQLAlchemy

# Global SQLAlchemy database instance
db = SQLAlchemy()

# Import all models to register with metadata
from app.models.user import User
from app.models.hostel import Hostel, Room, Bed
from app.models.student import Student, Warden
from app.models.allocation import BedAllocation
from app.models.fee import FeeRecord
from app.models.attendance import Attendance
from app.models.complaint import Complaint, ComplaintResponse
from app.models.notice import Notice
from app.models.leave import LeaveApplication
from app.models.notification import Notification
from app.models.outpass import DigitalOutPass, GateTransaction
from app.models.parent import ParentProfile, ParentInquiry

__all__ = [
    'db',
    'User',
    'Hostel',
    'Room',
    'Bed',
    'Student',
    'Warden',
    'BedAllocation',
    'FeeRecord',
    'Attendance',
    'Complaint',
    'ComplaintResponse',
    'Notice',
    'LeaveApplication',
    'Notification',
    'DigitalOutPass',
    'GateTransaction',
    'ParentProfile',
    'ParentInquiry'
]

