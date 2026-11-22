import unittest
from datetime import date, timedelta, datetime
from app import create_app, db
from app.models import User, Student, Warden, Hostel, Room, Bed, BedAllocation, LeaveApplication, DigitalOutPass, GateTransaction, Notification
from app.services.outpass_service import OutPassService

class GateSystemTestCase(unittest.TestCase):
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

        # Create Users
        self.admin_user = User(username='test_admin', email='admin@test.edu', role='admin')
        self.admin_user.set_password('Admin@123')

        self.warden_user = User(username='warden_b', email='warden.b@test.edu', role='warden')
        self.warden_user.set_password('Warden@123')

        self.guard_user = User(username='guard_main', email='guard.main@test.edu', role='security')
        self.guard_user.set_password('Guard@123')

        self.student_user_1 = User(username='rahul', email='rahul@test.edu', role='student')
        self.student_user_1.set_password('Student@123')

        self.student_user_2 = User(username='priya', email='priya@test.edu', role='student')
        self.student_user_2.set_password('Student@123')

        db.session.add_all([self.admin_user, self.warden_user, self.guard_user, self.student_user_1, self.student_user_2])
        db.session.flush()

        # Create Profiles
        self.warden = Warden(
            user_id=self.warden_user.id,
            employee_id='WRD-001',
            full_name='Dr. Warden',
            phone='9876543210',
            assigned_hostel_id=self.hostel_boys.id
        )
        self.student_1 = Student(
            user_id=self.student_user_1.id,
            enrollment_no='ENR001',
            roll_no='230001',
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
            roll_no='230002',
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
        db.session.add_all([self.warden, self.student_1, self.student_2])
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

    def _create_approved_leave(self, student, departure_date=None, return_date=None):
        if not departure_date:
            departure_date = date.today()
        if not return_date:
            return_date = date.today() + timedelta(days=2)

        leave = LeaveApplication(
            student_id=student.id,
            hostel_id=self.hostel_boys.id,
            leave_type='Home Visit',
            from_date=departure_date,
            to_date=return_date,
            reason='Family gathering at home village.',
            destination='Prayagraj',
            emergency_contact='9123456789',
            status='Approved',
            reviewed_by=self.warden.id,
            reviewed_at=datetime.utcnow()
        )
        db.session.add(leave)
        db.session.commit()
        return leave

    def test_outpass_generation_on_leave_approval(self):
        """Test automatic digital out-pass generation when leave is approved"""
        leave = self._create_approved_leave(self.student_1)
        outpass = OutPassService.generate_outpass(leave)

        self.assertIsNotNone(outpass)
        raw_token = outpass.raw_token
        self.assertIsNotNone(raw_token)
        self.assertEqual(outpass.leave_application_id, leave.id)
        self.assertEqual(outpass.student_id, self.student_1.id)
        self.assertEqual(outpass.status, 'Active')
        self.assertFalse(outpass.is_outside)
        self.assertEqual(len(outpass.pass_token_hash), 64)  # SHA-256 hex length
        self.assertNotIn(raw_token, outpass.pass_token_hash)  # Raw token not saved bare in DB

        # Student notification should exist
        notif = Notification.query.filter_by(user_id=self.student_user_1.id, type='success').first()
        self.assertIsNotNone(notif)
        self.assertIn('Digital Out-Pass Issued', notif.title)

    def test_duplicate_outpass_prevention(self):
        """Test that calling generate_outpass multiple times returns same pass"""
        leave = self._create_approved_leave(self.student_1)
        outpass1 = OutPassService.generate_outpass(leave)
        outpass2 = OutPassService.generate_outpass(leave)

        self.assertEqual(outpass1.id, outpass2.id)
        self.assertEqual(DigitalOutPass.query.filter_by(leave_application_id=leave.id).count(), 1)

    def test_student_outpass_access_and_idor_protection(self):
        """Test student can view own pass, but cannot view another student's pass"""
        leave1 = self._create_approved_leave(self.student_1)
        outpass1 = OutPassService.generate_outpass(leave1)

        leave2 = self._create_approved_leave(self.student_2)
        outpass2 = OutPassService.generate_outpass(leave2)

        # Student 1 logs in
        self.login('rahul', 'Student@123')

        # Can access own list
        res = self.client.get('/student/outpasses')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'#OP-', res.data)

        # Can view own pass
        res = self.client.get(f'/student/outpasses/{outpass1.id}')
        self.assertEqual(res.status_code, 200)

        # Cannot view Student 2 pass (Forbidden 403)
        res = self.client.get(f'/student/outpasses/{outpass2.id}')
        self.assertEqual(res.status_code, 403)

    def test_guard_portal_access_control(self):
        """Test that only security role can access security portal"""
        # Unauthenticated access redirects to login
        res = self.client.get('/security/dashboard')
        self.assertEqual(res.status_code, 302)

        # Student cannot access security dashboard
        self.login('rahul', 'Student@123')
        res = self.client.get('/security/dashboard')
        self.assertEqual(res.status_code, 403)
        self.logout()

        # Guard can access security dashboard
        self.login('guard_main', 'Guard@123')
        res = self.client.get('/security/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Hostel Gate & Security Portal', res.data)

    def test_guard_exit_and_entry_full_lifecycle(self):
        """Test complete gate workflow: EXIT approval, perimeter tracking, ENTRY check-in"""
        leave = self._create_approved_leave(self.student_1)
        outpass = OutPassService.generate_outpass(leave)
        raw_token = outpass.raw_token

        self.login('guard_main', 'Guard@123')

        # 1. First EXIT scan
        res1 = OutPassService.verify_and_record_scan(
            raw_token_input=raw_token,
            guard_user_id=self.guard_user.id,
            gate_location='Main Campus Gate',
            expected_event_type='EXIT'
        )
        self.assertTrue(res1['success'])
        self.assertEqual(res1.get('code'), 'EXIT_APPROVED')
        pass_obj = res1.get('outpass')
        self.assertTrue(pass_obj.is_outside)
        self.assertIsNotNone(pass_obj.actual_departure_time)

        # Verify transaction logged
        tx = GateTransaction.query.filter_by(outpass_id=outpass.id, event_type='EXIT').first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.verification_status, 'Success')

        # 2. Duplicate EXIT should be blocked
        res2 = OutPassService.verify_and_record_scan(
            raw_token_input=raw_token,
            guard_user_id=self.guard_user.id,
            gate_location='Main Campus Gate',
            expected_event_type='EXIT'
        )
        self.assertFalse(res2['success'])
        self.assertEqual(res2.get('code'), 'ALREADY_OUTSIDE')

        # 3. ENTRY scan
        res3 = OutPassService.verify_and_record_scan(
            raw_token_input=raw_token,
            guard_user_id=self.guard_user.id,
            gate_location='Main Campus Gate',
            expected_event_type='ENTRY'
        )
        self.assertTrue(res3['success'])
        self.assertEqual(res3.get('code'), 'ENTRY_APPROVED')
        pass_obj2 = res3.get('outpass')
        self.assertFalse(pass_obj2.is_outside)
        self.assertEqual(pass_obj2.status, 'Completed')
        self.assertIsNotNone(pass_obj2.actual_return_time)

        # 4. Attempting another ENTRY after completion should fail
        res4 = OutPassService.verify_and_record_scan(
            raw_token_input=raw_token,
            guard_user_id=self.guard_user.id,
            gate_location='Main Campus Gate',
            expected_event_type='ENTRY'
        )
        self.assertFalse(res4['success'])
        self.assertIn(res4.get('code'), ['NOT_OUTSIDE', 'PASS_NOT_ACTIVE', 'ALREADY_COMPLETED'])

    def test_entry_without_prior_exit_rejected(self):
        """Test that a student cannot check in if they never checked out"""
        leave = self._create_approved_leave(self.student_1)
        outpass = OutPassService.generate_outpass(leave)
        raw_token = outpass.raw_token

        res = OutPassService.verify_and_record_scan(
            raw_token_input=raw_token,
            guard_user_id=self.guard_user.id,
            gate_location='Main Gate',
            expected_event_type='ENTRY'
        )
        self.assertFalse(res['success'])
        self.assertEqual(res.get('code'), 'NOT_OUTSIDE')

    def test_revoked_pass_cannot_exit(self):
        """Test that a revoked outpass is blocked at the gate"""
        leave = self._create_approved_leave(self.student_1)
        outpass = OutPassService.generate_outpass(leave)
        raw_token = outpass.raw_token

        # Warden revokes the pass
        OutPassService.revoke_outpass(outpass, revoked_by_warden_id=self.warden_user.id, reason='Disciplinary hold')
        self.assertEqual(outpass.status, 'Revoked')

        # Guard scan attempt
        res = OutPassService.verify_and_record_scan(
            raw_token_input=raw_token,
            guard_user_id=self.guard_user.id,
            gate_location='Main Gate',
            expected_event_type='EXIT'
        )
        self.assertFalse(res['success'])
        self.assertEqual(res.get('code'), 'PASS_REVOKED')

    def test_expired_pass_cannot_exit(self):
        """Test that an expired outpass is blocked at the gate"""
        past_date = date.today() - timedelta(days=5)
        leave = self._create_approved_leave(self.student_1, departure_date=past_date, return_date=past_date + timedelta(days=1))
        outpass = OutPassService.generate_outpass(leave)
        raw_token = outpass.raw_token

        # Manually backdate expiration to test expiry check
        outpass.expires_at = datetime.utcnow() - timedelta(hours=2)
        db.session.commit()

        res = OutPassService.verify_and_record_scan(
            raw_token_input=raw_token,
            guard_user_id=self.guard_user.id,
            gate_location='Main Gate',
            expected_event_type='EXIT'
        )
        self.assertFalse(res['success'])
        self.assertEqual(res.get('code'), 'PASS_EXPIRED')

    def test_warden_outpass_management_and_revocation(self):
        """Test warden outpass desk routes and revocation form"""
        leave = self._create_approved_leave(self.student_1)
        outpass = OutPassService.generate_outpass(leave)

        self.login('warden_b', 'Warden@123')

        # View outpasses list
        res = self.client.get('/warden/outpasses')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Hostel Digital Out-Pass Register', res.data)

        # View specific outpass
        res = self.client.get(f'/warden/outpasses/{outpass.id}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Resident & Leave Particulars', res.data)

        # Revoke outpass via POST
        res = self.client.post(f'/warden/outpasses/{outpass.id}/revoke', data={
            'revocation_reason': 'Emergency campus lockdown ordered by Proctor'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify status is now Revoked
        db.session.refresh(outpass)
        self.assertEqual(outpass.status, 'Revoked')
        self.assertEqual(outpass.revoked_reason, 'Emergency campus lockdown ordered by Proctor')

    def test_admin_outpass_and_export_csv(self):
        """Test admin outpass register and CSV transaction export"""
        leave = self._create_approved_leave(self.student_1)
        outpass = OutPassService.generate_outpass(leave)
        raw_token = outpass.raw_token

        # Record a gate transaction
        OutPassService.verify_and_record_scan(
            raw_token_input=raw_token,
            guard_user_id=self.guard_user.id,
            gate_location='North Gate',
            expected_event_type='EXIT'
        )

        self.login('test_admin', 'Admin@123')

        # Outpass list
        res = self.client.get('/admin/outpasses')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Campus-Wide Digital Out-Pass Register', res.data)

        # Gate transactions log
        res = self.client.get('/admin/gate-transactions')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Campus Gate Security Log', res.data)

        # Export CSV
        res = self.client.get('/admin/gate-transactions/export')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'text/csv')
        self.assertIn(b'Transaction ID,Out-Pass ID,Student Name', res.data)
        self.assertIn(b'North Gate', res.data)

if __name__ == '__main__':
    unittest.main()
