import unittest
from datetime import date, timedelta, datetime
from app import create_app, db
from app.models import User, Student, Warden, Hostel, Room, Bed, BedAllocation, LeaveApplication, DigitalOutPass, GateTransaction, Notification, FeeRecord, Attendance, ParentProfile, ParentInquiry
from app.services.outpass_service import OutPassService
from app.services.fee_service import FeeService
from app.services.attendance_service import AttendanceService
from app.services.parent_service import ParentService

class ParentPortalTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        # Hostels
        self.hostel_boys = Hostel(name='Boys Block Alpha', hostel_type='boys', total_floors=2, total_rooms=5)
        self.hostel_girls = Hostel(name='Girls Block Beta', hostel_type='girls', total_floors=2, total_rooms=5)
        db.session.add_all([self.hostel_boys, self.hostel_girls])
        db.session.flush()

        # Rooms & Beds
        self.room1 = Room(hostel_id=self.hostel_boys.id, room_number='101', floor=1, room_type='double', capacity=2, monthly_fee=4500.00)
        self.room2 = Room(hostel_id=self.hostel_girls.id, room_number='201', floor=2, room_type='double', capacity=2, monthly_fee=4500.00)
        db.session.add_all([self.room1, self.room2])
        db.session.flush()

        self.bed1 = Bed(room_id=self.room1.id, bed_number='Bed-A')
        self.bed2 = Bed(room_id=self.room2.id, bed_number='Bed-A')
        db.session.add_all([self.bed1, self.bed2])
        db.session.flush()

        # Users
        self.admin_user = User(username='test_admin', email='admin@parent.test.edu', role='admin')
        self.admin_user.set_password('Admin@123')

        self.warden_user = User(username='test_warden', email='warden@parent.test.edu', role='warden')
        self.warden_user.set_password('Warden@123')

        self.guard_user = User(username='test_guard', email='guard@parent.test.edu', role='security')
        self.guard_user.set_password('Guard@123')

        self.student_user_1 = User(username='student_rahul', email='rahul@parent.test.edu', role='student')
        self.student_user_1.set_password('Student@123')

        self.student_user_2 = User(username='student_priya', email='priya@parent.test.edu', role='student')
        self.student_user_2.set_password('Student@123')

        self.parent_user_1 = User(username='parent_ramesh', email='ramesh@parent.test.edu', role='parent')
        self.parent_user_1.set_password('Parent@123')

        self.parent_user_2 = User(username='parent_sunita', email='sunita@parent.test.edu', role='parent')
        self.parent_user_2.set_password('Parent@123')

        db.session.add_all([
            self.admin_user, self.warden_user, self.guard_user,
            self.student_user_1, self.student_user_2,
            self.parent_user_1, self.parent_user_2
        ])
        db.session.flush()

        # Profiles
        self.warden = Warden(
            user_id=self.warden_user.id,
            employee_id='WRD-P01',
            full_name='Dr. Sharma',
            phone='9876543210',
            assigned_hostel_id=self.hostel_boys.id
        )

        self.student_1 = Student(
            user_id=self.student_user_1.id,
            enrollment_no='ENR-P01',
            roll_no='240001',
            full_name='Rahul Sharma',
            phone='9123456780',
            gender='male',
            branch='Computer Science & Engineering',
            year=2,
            semester=3,
            guardian_name='Ramesh Sharma',
            guardian_phone='9876543211',
            emergency_phone='9876543212',
            address='123 Civil Lines, Lucknow',
            blood_group='O+',
            status='active'
        )

        self.student_2 = Student(
            user_id=self.student_user_2.id,
            enrollment_no='ENR-P02',
            roll_no='240002',
            full_name='Priya Verma',
            phone='9123456781',
            gender='female',
            branch='Information Technology',
            year=1,
            semester=1,
            guardian_name='Sunita Verma',
            guardian_phone='9876543222',
            address='456 Gomti Nagar, Lucknow',
            status='active'
        )

        db.session.add_all([self.warden, self.student_1, self.student_2])
        db.session.flush()

        # Allocations
        self.alloc1 = BedAllocation(student_id=self.student_1.id, bed_id=self.bed1.id, hostel_id=self.hostel_boys.id, room_id=self.room1.id, status='active')
        self.alloc2 = BedAllocation(student_id=self.student_2.id, bed_id=self.bed2.id, hostel_id=self.hostel_girls.id, room_id=self.room2.id, status='active')
        db.session.add_all([self.alloc1, self.alloc2])
        db.session.flush()

        # Parent Profiles
        self.parent_profile_1 = ParentProfile(
            user_id=self.parent_user_1.id,
            parent_name='Ramesh Sharma',
            phone_number='9876543211',
            relationship_to_student='Father',
            student_id=self.student_1.id,
            account_status='active'
        )
        self.parent_profile_2 = ParentProfile(
            user_id=self.parent_user_2.id,
            parent_name='Sunita Verma',
            phone_number='9876543222',
            relationship_to_student='Mother',
            student_id=self.student_2.id,
            account_status='active'
        )
        db.session.add_all([self.parent_profile_1, self.parent_profile_2])
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
    # 1. AUTHENTICATION & ROLE ACCESS RESTRICTIONS
    # =========================================================================
    def test_parent_authentication_and_role_isolation(self):
        """Test parent login, dashboard redirect, and restriction from unauthorized roles"""
        # Login success
        res = self.login('parent_ramesh', 'Parent@123')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Parent & Guardian Desk', res.data)
        self.assertIn(b'Rahul Sharma', res.data)

        # Parent cannot access admin dashboard (403)
        res_admin = self.client.get('/admin/dashboard')
        self.assertEqual(res_admin.status_code, 403)

        # Parent cannot access warden dashboard (403)
        res_warden = self.client.get('/warden/dashboard')
        self.assertEqual(res_warden.status_code, 403)

        # Parent cannot access security dashboard (403)
        res_sec = self.client.get('/security/dashboard')
        self.assertEqual(res_sec.status_code, 403)

        # Parent cannot access student-only dashboard (403)
        res_student = self.client.get('/student/dashboard')
        self.assertEqual(res_student.status_code, 403)

        # Logout works
        self.logout()
        res_after = self.client.get('/parent/dashboard')
        self.assertEqual(res_after.status_code, 302)  # Redirected to login

    def test_inactive_parent_cannot_access(self):
        """Test deactivated parent account is blocked from login"""
        self.parent_user_1.is_active = False
        db.session.commit()

        res = self.login('parent_ramesh', 'Parent@123')
        self.assertIn(b'deactivated', res.data.lower())

    # =========================================================================
    # 2. STUDENT DATA ISOLATION & IDOR PROTECTION
    # =========================================================================
    def test_parent_child_data_isolation(self):
        """Parent 1 can view child 1's profile, but cannot view child 2's data (IDOR checks)"""
        # Create leaves for both students
        l1 = LeaveApplication(
            student_id=self.student_1.id,
            hostel_id=self.hostel_boys.id,
            leave_type='Home Visit',
            from_date=date.today(),
            to_date=date.today() + timedelta(days=2),
            reason='Family event',
            destination='Lucknow Home',
            emergency_contact='9876543211',
            status='Approved'
        )
        l2 = LeaveApplication(
            student_id=self.student_2.id,
            hostel_id=self.hostel_girls.id,
            leave_type='Medical Leave',
            from_date=date.today(),
            to_date=date.today() + timedelta(days=1),
            reason='Doctor checkup',
            destination='Clinic',
            emergency_contact='9876543222',
            status='Approved'
        )
        db.session.add_all([l1, l2])
        db.session.commit()

        op1 = OutPassService.generate_outpass(l1)
        op2 = OutPassService.generate_outpass(l2)

        fee1 = FeeService.record_payment(self.student_1.id, 10000.0, date.today(), 'UPI', 'Hostel Semester Fee')
        fee2 = FeeService.record_payment(self.student_2.id, 10000.0, date.today(), 'Net Banking', 'Hostel Semester Fee')

        # Login Parent 1 (linked to Student 1)
        self.login('parent_ramesh', 'Parent@123')

        # Can view Child 1's profile
        res = self.client.get('/parent/child')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Rahul Sharma', res.data)
        self.assertNotIn(b'Priya Verma', res.data)

        # Can view Child 1's leave application
        res = self.client.get(f'/parent/leave-applications/{l1.id}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'#LV-', res.data)

        # IDOR: Cannot view Child 2's leave application (403 Forbidden)
        res_idor_leave = self.client.get(f'/parent/leave-applications/{l2.id}')
        self.assertEqual(res_idor_leave.status_code, 403)

        # Can view Child 1's out-pass
        res = self.client.get(f'/parent/outpasses/{op1.id}')
        self.assertEqual(res.status_code, 200)

        # IDOR: Cannot view Child 2's out-pass (403 Forbidden)
        res_idor_op = self.client.get(f'/parent/outpasses/{op2.id}')
        self.assertEqual(res_idor_op.status_code, 403)

        # Can view Child 1's fee receipt
        res = self.client.get(f'/parent/fees/receipt/{fee1.id}')
        self.assertEqual(res.status_code, 200)

        # IDOR: Cannot view Child 2's fee receipt (403 Forbidden)
        res_idor_fee = self.client.get(f'/parent/fees/receipt/{fee2.id}')
        self.assertEqual(res_idor_fee.status_code, 403)

    # =========================================================================
    # 3. LEAVE APPLICATIONS TRACKING
    # =========================================================================
    def test_parent_leave_application_tracking(self):
        """Parent views leave history and filters; cannot approve/reject leaves"""
        l_pending = LeaveApplication(
            student_id=self.student_1.id,
            hostel_id=self.hostel_boys.id,
            leave_type='Personal Leave',
            from_date=date.today() + timedelta(days=5),
            to_date=date.today() + timedelta(days=7),
            reason='Festival preparation',
            destination='Home',
            emergency_contact='9876543211',
            status='Pending'
        )
        db.session.add(l_pending)
        db.session.commit()

        self.login('parent_ramesh', 'Parent@123')
        res = self.client.get('/parent/leave-applications')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Ward Leave Applications', res.data)
        self.assertIn(b'Personal Leave', res.data)
        self.assertIn(b'Home', res.data)

        # Check detail view contains reason
        res_detail = self.client.get(f'/parent/leave-applications/{l_pending.id}')
        self.assertEqual(res_detail.status_code, 200)
        self.assertIn(b'Festival preparation', res_detail.data)

        # Parent cannot approve leaves (POST to warden review endpoint fails with 403)
        res_approve = self.client.post(f'/warden/leaves/{l_pending.id}/action', data={
            'action': 'approve',
            'review_comment': 'Parent trying to approve'
        })
        self.assertEqual(res_approve.status_code, 403)
        db.session.refresh(l_pending)
        self.assertEqual(l_pending.status, 'Pending')  # Status unchanged

    # =========================================================================
    # 4. DIGITAL OUT-PASS & MOVEMENT MONITORING
    # =========================================================================
    def test_parent_movement_status_transitions(self):
        """Test movement status: Inside -> Approved Pending Exit -> Outside -> Returned"""
        l = LeaveApplication(
            student_id=self.student_1.id,
            hostel_id=self.hostel_boys.id,
            leave_type='Home Visit',
            from_date=date.today(),
            to_date=date.today() + timedelta(days=2),
            reason='Family visit',
            destination='Lucknow',
            emergency_contact='9876543211',
            status='Approved'
        )
        db.session.add(l)
        db.session.commit()

        outpass = OutPassService.generate_outpass(l)
        raw_token = outpass.raw_token

        # 1. State: Approved – Not Yet Exited
        status1 = ParentService.get_student_movement_status(self.student_1.id)
        self.assertEqual(status1['code'], 'APPROVED_PENDING_EXIT')
        self.assertFalse(status1['is_outside'])

        # 2. Gate EXIT scan occurs
        res_exit = OutPassService.verify_and_record_scan(
            raw_token_input=raw_token,
            guard_user_id=self.guard_user.id,
            gate_location='North Campus Gate',
            expected_event_type='EXIT'
        )
        self.assertTrue(res_exit['success'])

        # State: Currently Outside Hostel
        status2 = ParentService.get_student_movement_status(self.student_1.id)
        self.assertEqual(status2['code'], 'OUTSIDE')
        self.assertTrue(status2['is_outside'])

        # Verify parent portal reflects actual departure time
        self.login('parent_ramesh', 'Parent@123')
        res_op = self.client.get('/parent/outpasses')
        self.assertEqual(res_op.status_code, 200)
        self.assertIn(b'Currently Outside Hostel', res_op.data)

        # 3. Gate ENTRY scan occurs
        res_entry = OutPassService.verify_and_record_scan(
            raw_token_input=raw_token,
            guard_user_id=self.guard_user.id,
            gate_location='North Campus Gate',
            expected_event_type='ENTRY'
        )
        self.assertTrue(res_entry['success'])

        # State: Returned Successfully / Inside
        status3 = ParentService.get_student_movement_status(self.student_1.id)
        self.assertEqual(status3['code'], 'RETURNED')
        self.assertFalse(status3['is_outside'])

        res_op_done = self.client.get('/parent/outpasses')
        self.assertEqual(res_op_done.status_code, 200)
        self.assertIn(b'Returned Successfully', res_op_done.data)

    # =========================================================================
    # 5. ATTENDANCE & FEE MONITORING
    # =========================================================================
    def test_attendance_and_fee_monitoring(self):
        """Test parent attendance statistics and fee ledger calculations"""
        # Record attendance: 3 present, 1 absent
        AttendanceService.record_roll_call(self.hostel_boys.id, date.today() - timedelta(days=3), {str(self.student_1.id): 'present'})
        AttendanceService.record_roll_call(self.hostel_boys.id, date.today() - timedelta(days=2), {str(self.student_1.id): 'present'})
        AttendanceService.record_roll_call(self.hostel_boys.id, date.today() - timedelta(days=1), {str(self.student_1.id): 'present'})
        AttendanceService.record_roll_call(self.hostel_boys.id, date.today(), {str(self.student_1.id): 'absent'})

        # Record fee payment
        FeeService.record_payment(self.student_1.id, 15000.0, date.today(), 'UPI', 'Mess & Room Advance', status='paid')

        self.login('parent_ramesh', 'Parent@123')

        # Attendance view
        res_att = self.client.get('/parent/attendance')
        self.assertEqual(res_att.status_code, 200)
        self.assertIn(b'75.0% Overall Attendance', res_att.data)
        self.assertIn(b'3', res_att.data)  # 3 present days

        # Fee view
        res_fee = self.client.get('/parent/fees')
        self.assertEqual(res_fee.status_code, 200)
        self.assertIn(b'15,000', res_fee.data)

    # =========================================================================
    # 6. CONTACT WARDEN & INQUIRY LIFECYCLE
    # =========================================================================
    def test_parent_inquiry_workflow(self):
        """Parent sends inquiry -> Warden views and responds -> Parent sees resolution"""
        self.login('parent_ramesh', 'Parent@123')

        # Submit inquiry
        res = self.client.post('/parent/inquiries', data={
            'subject': 'Special Dietary Request',
            'message': 'Kindly permit warm milk at night due to seasonal asthma medication.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Special Dietary Request', res.data)

        inq = ParentInquiry.query.filter_by(subject='Special Dietary Request').first()
        self.assertIsNotNone(inq)
        self.assertEqual(inq.status, 'Pending')
        self.logout()

        # Warden logs in to review inquiries
        self.login('test_warden', 'Warden@123')
        res_w = self.client.get('/warden/inquiries')
        self.assertEqual(res_w.status_code, 200)
        self.assertIn(b'Special Dietary Request', res_w.data)

        # Warden responds
        res_reply = self.client.post(f'/warden/inquiries/{inq.id}/reply', data={
            'response': 'Noted and mess supervisor has been instructed to assist Rahul.',
            'status': 'Resolved'
        }, follow_redirects=True)
        self.assertEqual(res_reply.status_code, 200)

        db.session.refresh(inq)
        self.assertEqual(inq.status, 'Resolved')
        self.assertIn('mess supervisor', inq.response)
        self.logout()

        # Parent logs back in and verifies response is visible
        self.login('parent_ramesh', 'Parent@123')
        res_p = self.client.get('/parent/inquiries')
        self.assertIn(b'Resolved', res_p.data)
        self.assertIn(b'mess supervisor has been instructed', res_p.data)

    # =========================================================================
    # 7. ADMIN PARENT MANAGEMENT
    # =========================================================================
    def test_admin_parent_management_crud(self):
        """Admin can list, create, edit, deactivate, and reset parent accounts"""
        self.login('test_admin', 'Admin@123')

        # 1. Directory
        res = self.client.get('/admin/parents')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Ramesh Sharma', res.data)

        # 2. Create new parent account
        res_create = self.client.post('/admin/parents/create', data={
            'username': 'parent_new',
            'email': 'newparent@parent.test.edu',
            'password': 'Password@123',
            'parent_name': 'Anita Verma',
            'phone_number': '9876543333',
            'relationship_to_student': 'Mother',
            'student_id': self.student_2.id,
            'account_status': 'active'
        }, follow_redirects=True)
        self.assertEqual(res_create.status_code, 200)

        new_parent_user = User.query.filter_by(username='parent_new').first()
        self.assertIsNotNone(new_parent_user)
        self.assertEqual(new_parent_user.role, 'parent')
        self.assertEqual(new_parent_user.parent_profile.parent_name, 'Anita Verma')

        # 3. Deactivate parent
        res_toggle = self.client.post(f'/admin/parents/{new_parent_user.parent_profile.id}/toggle-status', follow_redirects=True)
        self.assertEqual(res_toggle.status_code, 200)
        db.session.refresh(new_parent_user.parent_profile)
        self.assertEqual(new_parent_user.parent_profile.account_status, 'inactive')
        self.assertFalse(new_parent_user.is_active)

        # 4. Reset password
        res_reset = self.client.post(f'/admin/parents/{new_parent_user.parent_profile.id}/reset-password', data={
            'new_password': 'NewPassword@999',
            'confirm_password': 'NewPassword@999'
        }, follow_redirects=True)
        self.assertEqual(res_reset.status_code, 200)
        self.assertTrue(new_parent_user.check_password('NewPassword@999'))

    # =========================================================================
    # 8. AUTOMATIC NOTIFICATION DISPATCH TO PARENTS
    # =========================================================================
    def test_automatic_parent_notifications(self):
        """Verify notifications dispatched to parent on leave submit, approve, and gate events"""
        # Student submits leave
        self.login('student_rahul', 'Student@123')
        self.client.post('/student/leaves/apply', data={
            'leave_type': 'Family Function',
            'from_date': (date.today() + timedelta(days=3)).strftime('%Y-%m-%d'),
            'to_date': (date.today() + timedelta(days=5)).strftime('%Y-%m-%d'),
            'reason': 'Cousin wedding ceremony in hometown.',
            'destination': 'Kanpur',
            'emergency_contact': '9876543211'
        }, follow_redirects=True)
        self.logout()

        # Check notification arrived for parent_user_1
        notif_submit = Notification.query.filter_by(user_id=self.parent_user_1.id, title='Leave Application Submitted').first()
        self.assertIsNotNone(notif_submit)
        self.assertIn('Rahul Sharma', notif_submit.message)

        # Warden approves leave
        leave = LeaveApplication.query.filter_by(student_id=self.student_1.id, destination='Kanpur').first()
        self.login('test_warden', 'Warden@123')
        self.client.post(f'/warden/leaves/{leave.id}/action', data={
            'action': 'approve',
            'review_comment': 'Approved with parental intimation.'
        }, follow_redirects=True)
        self.logout()

        notif_approve = Notification.query.filter_by(user_id=self.parent_user_1.id, title='Leave Application Approved').first()
        self.assertIsNotNone(notif_approve)

        # Gate EXIT notification to parent
        l_gate = LeaveApplication(
            student_id=self.student_1.id,
            hostel_id=self.hostel_boys.id,
            leave_type='Home Visit',
            from_date=date.today(),
            to_date=date.today() + timedelta(days=2),
            reason='Weekend trip',
            destination='Home Town',
            emergency_contact='9876543211',
            status='Approved'
        )
        db.session.add(l_gate)
        db.session.commit()
        op_gate = OutPassService.generate_outpass(l_gate)

        OutPassService.verify_and_record_scan(
            raw_token_input=op_gate.raw_token,
            guard_user_id=self.guard_user.id,
            gate_location='Main Campus Gate',
            expected_event_type='EXIT'
        )

        notif_exit = Notification.query.filter_by(user_id=self.parent_user_1.id, title='Campus Exit Recorded').first()
        self.assertIsNotNone(notif_exit)
        self.assertIn('Main Campus Gate', notif_exit.message)

    def test_parent_leaves_alias_route_consistency(self):
        """Test both /parent/leaves and /parent/leave-applications endpoints render cleanly"""
        self.login('parent_ramesh', 'Parent@123')

        # Test /parent/leave-applications
        res1 = self.client.get('/parent/leave-applications')
        self.assertEqual(res1.status_code, 200)
        self.assertIn(b'Leave Application History', res1.data)

        # Test /parent/leaves alias
        res2 = self.client.get('/parent/leaves')
        self.assertEqual(res2.status_code, 200)
        self.assertIn(b'Leave Application History', res2.data)

if __name__ == '__main__':
    unittest.main()
