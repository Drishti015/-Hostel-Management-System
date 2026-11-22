import uuid
from datetime import datetime
from app.models import db, FeeRecord, Student

class FeeService:
    """Business logic for hostel fee management and receipt generation"""

    @staticmethod
    def generate_receipt_number():
        """Generates a unique, official-looking receipt number e.g. REC-2026-9F3B"""
        year = datetime.now().year
        suffix = uuid.uuid4().hex[:6].upper()
        return f"REC-{year}-{suffix}"

    @staticmethod
    def record_payment(student_id, amount, payment_date, payment_method, fee_type, status='paid', transaction_id=None, remarks=None):
        """Records a fee transaction with an auto-generated unique receipt number"""
        receipt_no = FeeService.generate_receipt_number()
        
        # Ensure unique receipt number
        while FeeRecord.query.filter_by(receipt_no=receipt_no).first():
            receipt_no = FeeService.generate_receipt_number()

        record = FeeRecord(
            student_id=student_id,
            receipt_no=receipt_no,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
            transaction_id=transaction_id or f"TXN-{uuid.uuid4().hex[:10].upper()}",
            fee_type=fee_type,
            status=status,
            remarks=remarks
        )
        db.session.add(record)
        db.session.commit()
        return record

    @staticmethod
    def get_student_fee_summary(student_id):
        """
        Calculates fee financial summary for a student.
        Standard semester fee is inferred from allocated room's monthly fee * 6 + Mess Fee (approx ₹27,000).
        """
        student = Student.query.get(student_id)
        if not student:
            return None

        alloc = student.current_allocation
        if alloc and alloc.room:
            # 6 months semester base fee
            base_fee = float(alloc.room.monthly_fee) * 6
        else:
            base_fee = 27000.0  # Standard fallback semester fee

        total_paid = float(student.total_fees_paid)
        balance_due = max(0.0, base_fee - total_paid)
        status = "Paid" if balance_due == 0 else ("Partial" if total_paid > 0 else "Due")

        return {
            'total_fee': base_fee,
            'total_paid': total_paid,
            'balance_due': balance_due,
            'status': status,
            'records': student.fee_records.order_by(FeeRecord.payment_date.desc()).all()
        }

