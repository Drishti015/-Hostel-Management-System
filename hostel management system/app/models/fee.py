from datetime import datetime
from app.models import db

class FeeRecord(db.Model):
    """
    FeeRecord Model - Financial transactions, receipts, and dues status.
    """
    __tablename__ = 'fee_records'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    receipt_no = db.Column(db.String(50), unique=True, nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    payment_method = db.Column(db.Enum('UPI', 'Cash', 'Net Banking', 'Cheque/DD', name='payment_method_enum'), default='UPI', nullable=False)
    transaction_id = db.Column(db.String(100), nullable=True)
    fee_type = db.Column(db.String(50), default='Hostel & Mess Fee', nullable=False)
    status = db.Column(db.Enum('paid', 'pending', 'overdue', name='fee_status_enum'), default='paid', nullable=False, index=True)
    remarks = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<FeeRecord {self.receipt_no}: Rs {self.amount} ({self.status})>"

