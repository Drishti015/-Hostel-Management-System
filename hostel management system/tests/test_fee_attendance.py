import unittest
from datetime import date
from app import create_app, db
from app.models import User, Student, Hostel, Room, Bed, FeeRecord, Attendance
from app.services.fee_service import FeeService
from app.services.attendance_service import AttendanceService

class FeeAttendanceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        # Create Student
        u = User(username='test_fee_student', email='fee_std@aktu.ac.in', role='student')
        u.set_password('Pass123')
        db.session.add(u)
        db.session.flush()

        self.hostel = Hostel(name='Test Block', hostel_type='boys')
        db.session.add(self.hostel)
        db.session.flush()

        self.student = Student(
            user_id=u.id,
            enrollment_no='ENR-FEE-01',
            full_name='Test Fee Resident',
            phone='9876543210',
            gender='male',
            branch='CSE',
            year=1,
            semester=1,
            guardian_name='Guardian',
            guardian_phone='9876543210',
            address='Lucknow'
        )
        db.session.add(self.student)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_fee_recording_and_receipt_generation(self):
        # 1. Record payment
        record = FeeService.record_payment(
            student_id=self.student.id,
            amount=15000.0,
            payment_date=date.today(),
            payment_method='UPI',
            fee_type='Hostel & Mess Fee',
            status='paid',
            transaction_id='UPI-TEST-1234'
        )
        self.assertIsNotNone(record.id)
        self.assertTrue(record.receipt_no.startswith('REC-'))
        self.assertEqual(float(record.amount), 15000.0)

        # 2. Check student summary
        summary = FeeService.get_student_fee_summary(self.student.id)
        self.assertEqual(summary['total_paid'], 15000.0)
        self.assertEqual(summary['balance_due'], 12000.0) # 27,000 - 15,000 = 12,000
        self.assertEqual(summary['status'], 'Partial')

    def test_attendance_roll_call_and_upsert(self):
        # 1. Record Roll Call
        d = date(2026, 11, 22)
        status_dict = {str(self.student.id): 'present'}
        count = AttendanceService.record_roll_call(
            hostel_id=self.hostel.id,
            roll_date=d,
            status_dict=status_dict
        )
        self.assertEqual(count, 1)

        # 2. Verify attendance record
        att = Attendance.query.filter_by(student_id=self.student.id, date=d).first()
        self.assertIsNotNone(att)
        self.assertEqual(att.status, 'present')

        # 3. Upsert test: changing status to 'leave' on same date updates existing row, doesn't duplicate
        status_dict_update = {str(self.student.id): 'leave'}
        AttendanceService.record_roll_call(
            hostel_id=self.hostel.id,
            roll_date=d,
            status_dict=status_dict_update
        )
        total_rows = Attendance.query.filter_by(student_id=self.student.id, date=d).count()
        self.assertEqual(total_rows, 1)
        att_updated = Attendance.query.filter_by(student_id=self.student.id, date=d).first()
        self.assertEqual(att_updated.status, 'leave')

if __name__ == '__main__':
    unittest.main()

