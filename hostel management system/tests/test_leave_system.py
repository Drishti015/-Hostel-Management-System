import unittest
from datetime import date, timedelta, datetime
from app import create_app, db
from app.models import User, Student, Warden, Hostel, Room, Bed, BedAllocation, LeaveApplication, Notification

class LeaveSystemTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        # Create Hostels
        self.hostel_boys = Hostel(name='Boys Block A', hostel_type='boys', total_floors=2, total_rooms=5)
        self.hostel_girls = Hostel(name='Girls Block B', hostel_type='girls', total_floors=2, total_rooms=5)
        db.session.add_all([self.hostel_boys, self.hostel_girls])
        db.session.flush()

        # Create Rooms & Beds
        self.room_a = Room(hostel_id=self.hostel_boys.id, room_number='A-101', floor=1, capacity=2)
        self.room_b = Room(hostel_id=self.hostel_girls.id, room_number='B-101', floor=1, capacity=2)
        db.session.add_all([self.room_a, self.room_b])
        db.session.flush()

        self.bed_a = Bed(room_id=self.room_a.id, bed_number='Bed-1')
        self.bed_b = Bed(room_id=self.room_b.id, bed_number='Bed-1')
        db.session.add_all([self.bed_a, self.bed_b])
        db.session.flush()

        # Create Users
        # Admin
        self.admin_user = User(username='test_admin', email='admin@test.edu', role='admin')
        self.admin_user.set_password('Admin@123')

        # Warden Boys
        self.warden_user_boys = User(username='warden_b', email='warden.b@test.edu', role='warden')
        self.warden_user_boys.set_password('Warden@123')

        # Warden Girls
        self.warden_user_girls = User(username='warden_g', email='warden.g@test.edu', role='warden')
        self.warden_user_girls.set_password('Warden@123')

        # Student 1 (Boys)
        self.student_user_1 = User(username='rahul', email='rahul@test.edu', role='student')
        self.student_user_1.set_password('Student@123')

        # Student 2 (Girls)
        self.student_user_2 = User(username='priya', email='priya@test.edu', role='student')
        self.student_user_2.set_password('Student@123')

        db.session.add_all([self.admin_user, self.warden_user_boys, self.warden_user_girls, self.student_user_1, self.student_user_2])
        db.session.flush()

        # Create Profiles
        self.warden_boys = Warden(user_id=self.warden_user_boys.id, employee_id='WRD-B-01', full_name='Warden Boys', phone='9876543210', assigned_hostel_id=self.hostel_boys.id)
        self.warden_girls = Warden(user_id=self.warden_user_girls.id, employee_id='WRD-G-01', full_name='Warden Girls', phone='9876543211', assigned_hostel_id=self.hostel_girls.id)

        self.student_1 = Student(
            user_id=self.student_user_1.id,
            enrollment_no='ENR001',
            full_name='Rahul Student',
            phone='9123456780',
            gender='male',
            branch='CSE',
            year=3,
            guardian_name='Guardian 1',
            guardian_phone='9123456789',
            address='City A',
            status='active'
        )

        self.student_2 = Student(
            user_id=self.student_user_2.id,
            enrollment_no='ENR002',
            full_name='Priya Student',
            phone='9123456781',
            gender='female',
            branch='IT',
            year=2,
            guardian_name='Guardian 2',
            guardian_phone='9123456788',
            address='City B',
            status='active'
        )

        db.session.add_all([self.warden_boys, self.warden_girls, self.student_1, self.student_2])
        db.session.flush()

        # Bed Allocations
        self.alloc_1 = BedAllocation(student_id=self.student_1.id, bed_id=self.bed_a.id, room_id=self.room_a.id, hostel_id=self.hostel_boys.id, status='active')
        self.alloc_2 = BedAllocation(student_id=self.student_2.id, bed_id=self.bed_b.id, room_id=self.room_b.id, hostel_id=self.hostel_girls.id, status='active')
        db.session.add_all([self.alloc_1, self.alloc_2])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def login(self, username, password):
        return self.client.post('/auth/login', data={
            'identity': username,
            'password': password
        }, follow_redirects=True)

    def logout(self):
        return self.client.get('/auth/logout', follow_redirects=True)

    # =========================================================================
    # 1. STUDENT TESTS
    # =========================================================================

    def test_student_submit_leave_success(self):
        """Student can successfully submit a valid leave application and notifications are generated"""
        self.login('rahul', 'Student@123')
        from_date = (date.today() + timedelta(days=2)).strftime('%Y-%m-%d')
        to_date = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')

        response = self.client.post('/student/leaves/apply', data={
            'leave_type': 'Home Visit',
            'from_date': from_date,
            'to_date': to_date,
            'reason': 'Visiting parents in hometown for weekend.',
            'destination': 'Prayagraj, UP',
            'emergency_contact': '9123456789'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Leave application #', response.data)

        # Check DB record
        leave = LeaveApplication.query.filter_by(student_id=self.student_1.id).first()
        self.assertIsNotNone(leave)
        self.assertEqual(leave.leave_type, 'Home Visit')
        self.assertEqual(leave.status, 'Pending')
        self.assertEqual(leave.hostel_id, self.hostel_boys.id)
        self.assertEqual(leave.number_of_days, 4)

        # Verify Student Notification
        student_notif = Notification.query.filter_by(user_id=self.student_user_1.id).first()
        self.assertIsNotNone(student_notif)
        self.assertIn('Leave Application Submitted', student_notif.title)

        # Verify Warden Notification
        warden_notif = Notification.query.filter_by(user_id=self.warden_user_boys.id).first()
        self.assertIsNotNone(warden_notif)
        self.assertIn('New Leave Application', warden_notif.title)

    def test_student_submit_invalid_date_range(self):
        """Application is rejected if to_date is earlier than from_date"""
        self.login('rahul', 'Student@123')
        from_date = (date.today() + timedelta(days=5)).strftime('%Y-%m-%d')
        to_date = (date.today() + timedelta(days=2)).strftime('%Y-%m-%d')

        response = self.client.post('/student/leaves/apply', data={
            'leave_type': 'Home Visit',
            'from_date': from_date,
            'to_date': to_date,
            'reason': 'Visiting parents in hometown.',
            'destination': 'Prayagraj, UP',
            'emergency_contact': '9123456789'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Return date cannot be earlier than departure date', response.data)
        self.assertEqual(LeaveApplication.query.count(), 0)

    def test_student_submit_past_date(self):
        """Application is rejected if departure date is in the past"""
        self.login('rahul', 'Student@123')
        from_date = (date.today() - timedelta(days=2)).strftime('%Y-%m-%d')
        to_date = (date.today() + timedelta(days=2)).strftime('%Y-%m-%d')

        response = self.client.post('/student/leaves/apply', data={
            'leave_type': 'Medical Leave',
            'from_date': from_date,
            'to_date': to_date,
            'reason': 'Medical checkup past date test.',
            'destination': 'Hospital',
            'emergency_contact': '9123456789'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Departure date cannot be in the past', response.data)
        self.assertEqual(LeaveApplication.query.count(), 0)

    def test_student_cannot_view_other_student_leave(self):
        """IDOR Security Check: Student 1 cannot view Student 2's leave application"""
        # Create a leave for Student 2
        leave2 = LeaveApplication(
            student_id=self.student_2.id,
            hostel_id=self.hostel_girls.id,
            leave_type='Medical Leave',
            from_date=date.today() + timedelta(days=1),
            to_date=date.today() + timedelta(days=3),
            reason='Dental clinic surgery and checkup.',
            destination='Lucknow Clinic',
            emergency_contact='9123456788',
            status='Pending'
        )
        db.session.add(leave2)
        db.session.commit()

        # Login as Student 1 (Rahul) and try to access leave2
        self.login('rahul', 'Student@123')
        response = self.client.get(f'/student/leaves/{leave2.id}')
        self.assertEqual(response.status_code, 403)

    def test_student_can_cancel_pending_leave(self):
        """Student can cancel their own pending application"""
        leave = LeaveApplication(
            student_id=self.student_1.id,
            hostel_id=self.hostel_boys.id,
            leave_type='Home Visit',
            from_date=date.today() + timedelta(days=1),
            to_date=date.today() + timedelta(days=3),
            reason='Family gathering at home.',
            destination='Prayagraj',
            emergency_contact='9123456789',
            status='Pending'
        )
        db.session.add(leave)
        db.session.commit()

        self.login('rahul', 'Student@123')
        response = self.client.post(f'/student/leaves/{leave.id}/cancel', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'cancelled', response.data.lower())

        # Check DB
        updated_leave = LeaveApplication.query.get(leave.id)
        self.assertEqual(updated_leave.status, 'Cancelled')

    def test_student_cannot_cancel_approved_leave(self):
        """Approved application cannot be cancelled directly by student"""
        leave = LeaveApplication(
            student_id=self.student_1.id,
            hostel_id=self.hostel_boys.id,
            leave_type='Home Visit',
            from_date=date.today() + timedelta(days=1),
            to_date=date.today() + timedelta(days=3),
            reason='Family visit.',
            destination='Prayagraj',
            emergency_contact='9123456789',
            status='Approved'
        )
        db.session.add(leave)
        db.session.commit()

        self.login('rahul', 'Student@123')
        response = self.client.post(f'/student/leaves/{leave.id}/cancel', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Only pending leave applications can be cancelled', response.data)

        updated_leave = LeaveApplication.query.get(leave.id)
        self.assertEqual(updated_leave.status, 'Approved')

    # =========================================================================
    # 2. WARDEN TESTS
    # =========================================================================

    def test_warden_can_view_assigned_hostel_leaves_only(self):
        """Warden can view requests for their assigned hostel, but not other hostels"""
        # Leave for Boys Hostel
        leave_b = LeaveApplication(
            student_id=self.student_1.id,
            hostel_id=self.hostel_boys.id,
            leave_type='Home Visit',
            from_date=date.today() + timedelta(days=1),
            to_date=date.today() + timedelta(days=3),
            reason='Boys hostel leave request.',
            destination='City A',
            emergency_contact='9123456780',
            status='Pending'
        )
        # Leave for Girls Hostel
        leave_g = LeaveApplication(
            student_id=self.student_2.id,
            hostel_id=self.hostel_girls.id,
            leave_type='Medical Leave',
            from_date=date.today() + timedelta(days=1),
            to_date=date.today() + timedelta(days=3),
            reason='Girls hostel leave request.',
            destination='City B',
            emergency_contact='9123456781',
            status='Pending'
        )
        db.session.add_all([leave_b, leave_g])
        db.session.commit()

        # Login as Warden Boys
        self.login('warden_b', 'Warden@123')
        response = self.client.get('/warden/leaves')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Rahul Student', response.data)
        self.assertNotIn(b'Priya Student', response.data)

        # Try to view Girls Hostel leave directly -> 403 Forbidden
        response = self.client.get(f'/warden/leaves/{leave_g.id}')
        self.assertEqual(response.status_code, 403)

    def test_warden_approve_leave(self):
        """Warden can approve a pending leave request"""
        leave = LeaveApplication(
            student_id=self.student_1.id,
            hostel_id=self.hostel_boys.id,
            leave_type='Home Visit',
            from_date=date.today() + timedelta(days=1),
            to_date=date.today() + timedelta(days=3),
            reason='Need to travel home for family function.',
            destination='Prayagraj',
            emergency_contact='9123456780',
            status='Pending'
        )
        db.session.add(leave)
        db.session.commit()

        self.login('warden_b', 'Warden@123')
        response = self.client.post(f'/warden/leaves/{leave.id}/action', data={
            'action': 'approve',
            'review_comment': 'Approved. Report back before 8 PM.'
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'approved successfully', response.data.lower())

        updated = LeaveApplication.query.get(leave.id)
        self.assertEqual(updated.status, 'Approved')
        self.assertEqual(updated.reviewed_by, self.warden_boys.id)
        self.assertIsNotNone(updated.reviewed_at)
        self.assertIn('Report back before 8 PM', updated.review_comment)

        # Student notification verified
        notif = Notification.query.filter_by(user_id=self.student_user_1.id, title='Leave Application Approved').first()
        self.assertIsNotNone(notif)

    def test_warden_reject_requires_reason(self):
        """Warden cannot reject without providing a reason or remarks"""
        leave = LeaveApplication(
            student_id=self.student_1.id,
            hostel_id=self.hostel_boys.id,
            leave_type='Personal Leave',
            from_date=date.today() + timedelta(days=1),
            to_date=date.today() + timedelta(days=3),
            reason='Personal reasons.',
            destination='Unknown',
            emergency_contact='9123456780',
            status='Pending'
        )
        db.session.add(leave)
        db.session.commit()

        self.login('warden_b', 'Warden@123')
        # Empty comment
        response = self.client.post(f'/warden/leaves/{leave.id}/action', data={
            'action': 'reject',
            'review_comment': ''
        }, follow_redirects=True)

        self.assertIn(b'rejection reason or remark is required', response.data)
        updated = LeaveApplication.query.get(leave.id)
        self.assertEqual(updated.status, 'Pending')

        # With comment
        response = self.client.post(f'/warden/leaves/{leave.id}/action', data={
            'action': 'reject',
            'review_comment': 'Insufficient justification during exams.'
        }, follow_redirects=True)

        self.assertIn(b'rejected', response.data.lower())
        updated = LeaveApplication.query.get(leave.id)
        self.assertEqual(updated.status, 'Rejected')
        self.assertEqual(updated.reviewed_by, self.warden_boys.id)

    # =========================================================================
    # 3. ADMIN TESTS
    # =========================================================================

    def test_admin_can_view_all_and_filter(self):
        """Admin has global oversight and can filter by hostel or status"""
        l1 = LeaveApplication(student_id=self.student_1.id, hostel_id=self.hostel_boys.id, leave_type='Home Visit', from_date=date.today()+timedelta(days=1), to_date=date.today()+timedelta(days=2), reason='Home visit reason 12345.', destination='City A', emergency_contact='9123456780', status='Approved')
        l2 = LeaveApplication(student_id=self.student_2.id, hostel_id=self.hostel_girls.id, leave_type='Medical Leave', from_date=date.today()+timedelta(days=1), to_date=date.today()+timedelta(days=2), reason='Medical checkup reason 12345.', destination='City B', emergency_contact='9123456781', status='Pending')
        db.session.add_all([l1, l2])
        db.session.commit()

        self.login('test_admin', 'Admin@123')
        # View all
        response = self.client.get('/admin/leaves')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Rahul Student', response.data)
        self.assertIn(b'Priya Student', response.data)

        # Filter by boys hostel
        response = self.client.get(f'/admin/leaves?hostel_id={self.hostel_boys.id}')
        self.assertIn(b'Rahul Student', response.data)
        self.assertNotIn(b'Priya Student', response.data)

        # Filter by status
        response = self.client.get('/admin/leaves?status=Pending')
        self.assertNotIn(b'Rahul Student', response.data)
        self.assertIn(b'Priya Student', response.data)

if __name__ == '__main__':
    unittest.main()

