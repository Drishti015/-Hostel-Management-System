import unittest
from datetime import datetime, date, timedelta
from decimal import Decimal
from app import create_app, db
from app.models import User, Student, Hostel, LeaveApplication
from app.models.mess import (
    MessProfile, Supplier, MealMenu, MealBooking, MealAttendance,
    MealFeedback, MessInventory, InventoryTransaction, MessExpense,
    MessStaffProfile, MessNotice, MessBillingRecord
)
from app.services.mess_service import MessService

class MessSystemTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        # Seed essential users
        # 1. Admin
        self.admin = User(username='admin_test', email='admin@test.com', role='admin')
        self.admin.set_password('Admin@123')

        # 2. Warden
        self.warden = User(username='warden_test', email='warden@test.com', role='warden')
        self.warden.set_password('Warden@123')

        # 3. Mess Manager
        self.manager = User(username='manager_test', email='manager@test.com', role='mess_manager')
        self.manager.set_password('Manager@123')

        # 4. Mess Staff
        self.staff = User(username='staff_test', email='staff@test.com', role='mess_staff')
        self.staff.set_password('Staff@123')

        # 5. Student
        self.student_user = User(username='student_test', email='student@test.com', role='student')
        self.student_user.set_password('Student@123')

        db.session.add_all([self.admin, self.warden, self.manager, self.staff, self.student_user])
        db.session.flush()

        # Student Profile
        self.student = Student(
            user_id=self.student_user.id,
            enrollment_no='TESTENROLL01',
            roll_no='2300099',
            full_name='Test Student',
            phone='9999999999',
            gender='male',
            branch='Computer Science',
            year=2,
            semester=3,
            guardian_name='Test Guardian',
            guardian_phone='9999999998',
            address='Room 101, Aryabhatta Hostel',
            status='active'
        )
        db.session.add(self.student)

        # Mess Facility
        self.mess = MessProfile(
            mess_name='Central Test Dining',
            description='Test dining hall',
            contact_number='+91-9999999999',
            operating_status='Active',
            meal_policy='booking_required',
            daily_capacity=300
        )
        db.session.add(self.mess)
        db.session.flush()

        # Staff profile
        self.staff_profile = MessStaffProfile(
            user_id=self.staff.id,
            mess_id=self.mess.id,
            staff_name='Test Counter Staff',
            role_designation='Counter Attendant',
            employment_status='Active'
        )
        db.session.add(self.staff_profile)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self, username, password):
        self.client.get('/auth/logout', follow_redirects=True)
        return self.client.post('/auth/login', data={
            'identity': username,
            'password': password
        }, follow_redirects=True)

    # -------------------------------------------------------------
    # 1. Role Access & Authorization
    # -------------------------------------------------------------
    def test_mess_manager_access_guard(self):
        # Unauthenticated access redirects to login
        res = self.client.get('/mess-manager/dashboard')
        self.assertEqual(res.status_code, 302)

        # Student cannot access mess manager portal (403 forbidden)
        self._login('student_test', 'Student@123')
        res = self.client.get('/mess-manager/dashboard')
        self.assertEqual(res.status_code, 403)

        # Mess Manager can access mess manager portal
        self._login('manager_test', 'Manager@123')
        res = self.client.get('/mess-manager/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Mess Manager Operations Center', res.data)

    def test_mess_staff_access_guard(self):
        # Unauthenticated access redirects
        res = self.client.get('/mess-staff/dashboard')
        self.assertEqual(res.status_code, 302)

        # Student cannot access mess staff scanner
        self._login('student_test', 'Student@123')
        res = self.client.get('/mess-staff/scanner')
        self.assertEqual(res.status_code, 403)

        # Mess Staff can access terminal
        self._login('staff_test', 'Staff@123')
        res = self.client.get('/mess-staff/scanner')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Dining Counter QR Scanner', res.data)

    # -------------------------------------------------------------
    # 2. Menu Scheduling & Capacity
    # -------------------------------------------------------------
    def test_menu_creation_and_capacity(self):
        self._login('manager_test', 'Manager@123')
        tomorrow = date.today() + timedelta(days=1)
        res = self.client.post('/mess-manager/menu/create', data={
            'meal_date': tomorrow.strftime('%Y-%m-%d'),
            'meal_type': 'Lunch',
            'title': 'Chole Bhature & Lassi',
            'description': 'Delicious Punjabi chole bhature with sweet lassi',
            'food_category': 'Vegetarian',
            'meal_timing': '12:30 PM - 2:30 PM',
            'booking_deadline': (datetime.combine(tomorrow, datetime.min.time()) + timedelta(hours=6)).strftime('%Y-%m-%dT%H:%M'),
            'capacity': 150,
            'is_published': 'y'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        menu = MealMenu.query.filter_by(mess_id=self.mess.id, meal_type='Lunch').first()
        self.assertIsNotNone(menu)
        self.assertEqual(menu.title, 'Chole Bhature & Lassi')
        self.assertEqual(menu.capacity, 150)
        self.assertTrue(menu.is_published)

    # -------------------------------------------------------------
    # 3. Student Meal Booking & Cancellation
    # -------------------------------------------------------------
    def test_student_meal_booking_and_cancel(self):
        # Create a published meal menu for tomorrow
        tomorrow = date.today() + timedelta(days=1)
        menu = MealMenu(
            mess_id=self.mess.id,
            meal_date=tomorrow,
            meal_type='Dinner',
            title='Dal Makhani & Naan',
            food_category='Vegetarian',
            meal_timing='8:00 PM - 10:00 PM',
            booking_deadline=datetime.utcnow() + timedelta(hours=12),
            capacity=100,
            is_published=True,
            created_by=self.manager.id
        )
        db.session.add(menu)
        db.session.commit()

        # Login as student and book
        self._login('student_test', 'Student@123')
        res = self.client.post(f'/student/mess/book/{menu.id}', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify booking in database
        booking = MealBooking.query.filter_by(student_id=self.student.id, meal_menu_id=menu.id).first()
        self.assertIsNotNone(booking)
        self.assertEqual(booking.booking_status, 'Booked')

        # Test duplicate booking prevention
        res = self.client.post(f'/student/mess/book/{menu.id}', follow_redirects=True)
        self.assertIn(b'You have already booked this meal', res.data)

        # Cancel the booking
        res = self.client.post(f'/student/mess/cancel-booking/{booking.id}', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        db.session.refresh(booking)
        self.assertEqual(booking.booking_status, 'Cancelled')

    # -------------------------------------------------------------
    # 4. Cryptographic Student QR Token Generation & Verification
    # -------------------------------------------------------------
    def test_qr_token_generation_and_tamper_detection(self):
        token = MessService.generate_student_qr_payload(self.student)
        self.assertTrue(token.startswith(f"MESS:{self.student.id}:"))

        # Valid token decodes correctly
        decoded_student = MessService.verify_student_qr_payload(token)
        self.assertIsNotNone(decoded_student)
        self.assertEqual(decoded_student.id, self.student.id)

        # Tampered token fails verification
        tampered_token = token[:-4] + "ffff"
        self.assertIsNone(MessService.verify_student_qr_payload(tampered_token))

        # Invalid format fails
        self.assertIsNone(MessService.verify_student_qr_payload("INVALID_TOKEN"))

    # -------------------------------------------------------------
    # 5. QR Attendance Check-In & Duplicate Prevention
    # -------------------------------------------------------------
    def test_qr_attendance_scan_and_duplicate_rejection(self):
        today = date.today()
        menu = MealMenu(
            mess_id=self.mess.id,
            meal_date=today,
            meal_type='Lunch',
            title='Rajma Chawal',
            food_category='Vegetarian',
            meal_timing='12:30 PM - 2:30 PM',
            booking_deadline=datetime.utcnow() + timedelta(hours=2),
            capacity=200,
            is_published=True,
            created_by=self.manager.id
        )
        db.session.add(menu)
        db.session.commit()

        # Student books the meal
        booking = MealBooking(
            student_id=self.student.id,
            meal_menu_id=menu.id,
            booking_status='Booked'
        )
        db.session.add(booking)
        db.session.commit()

        # Staff scans valid QR token
        self._login('staff_test', 'Staff@123')
        valid_qr = MessService.generate_student_qr_payload(self.student)

        res = self.client.post('/mess-staff/verify', json={
            'qr_data': valid_qr,
            'slot': 'Lunch'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], 'VALID')

        # Verify attendance record created
        att = MealAttendance.query.filter_by(student_id=self.student.id, meal_menu_id=menu.id).first()
        self.assertIsNotNone(att)
        self.assertEqual(att.attendance_status, 'Present')

        # Second scan attempt is REJECTED as DUPLICATE
        res = self.client.post('/mess-staff/verify', json={
            'qr_data': valid_qr,
            'slot': 'Lunch'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['status'], 'DUPLICATE')

    # -------------------------------------------------------------
    # 6. Pantry Inventory Transactions & Low Stock Alerts
    # -------------------------------------------------------------
    def test_inventory_transactions_and_low_stock(self):
        item = MessInventory(
            mess_id=self.mess.id,
            item_name='Sugar Crystal',
            category='Grains & Cereals',
            quantity=Decimal('50.00'),
            unit='kg',
            minimum_stock_level=Decimal('20.00'),
            purchase_price=Decimal('42.00')
        )
        db.session.add(item)
        db.session.commit()

        # Consumption transaction
        tx = MessService.record_inventory_transaction(
            inventory_id=item.id,
            tx_type='Consumption',
            quantity=Decimal('35.00'),
            unit_price=Decimal('42.00'),
            remarks='Kitchen daily consumption',
            user_id=self.manager.id
        )
        self.assertTrue(tx['success'])
        db.session.refresh(item)
        self.assertEqual(item.quantity, Decimal('15.00'))

        # Check low stock detection (15.00 <= 20.00 threshold)
        self.assertTrue(item.is_low_stock)
        low_items = MessInventory.query.filter(
            MessInventory.mess_id == self.mess.id,
            MessInventory.quantity <= MessInventory.minimum_stock_level
        ).all()
        self.assertTrue(any(i.id == item.id for i in low_items))

    # -------------------------------------------------------------
    # 7. Student Food Feedback
    # -------------------------------------------------------------
    def test_student_meal_feedback(self):
        today = date.today()
        menu = MealMenu(
            mess_id=self.mess.id,
            meal_date=today,
            meal_type='Breakfast',
            title='Poha & Jalebi',
            food_category='Vegetarian',
            meal_timing='8:00 AM - 10:00 AM',
            booking_deadline=datetime.utcnow() + timedelta(hours=1),
            capacity=100,
            is_published=True,
            created_by=self.manager.id
        )
        db.session.add(menu)
        db.session.commit()

        self._login('student_test', 'Student@123')
        res = self.client.post('/student/mess/feedback', data={
            'meal_menu_id': menu.id,
            'rating': 5,
            'taste_rating': 5,
            'quantity_rating': 4,
            'hygiene_rating': 5,
            'comments': 'Crispy jalebi and great hot poha!'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        fb = MealFeedback.query.filter_by(student_id=self.student.id, meal_menu_id=menu.id).first()
        self.assertIsNotNone(fb)
        self.assertEqual(fb.rating, 5)
        self.assertEqual(fb.taste_rating, 5)
        self.assertFalse(fb.is_anonymous)

    # -------------------------------------------------------------
    # 8. Monthly Billing & Approved Leave Rebates
    # -------------------------------------------------------------
    def test_monthly_billing_and_leave_rebate(self):
        # Create approved leave for 4 days (qualifies for daily rebate)
        today = date.today()
        leave = LeaveApplication(
            student_id=self.student.id,
            leave_type='Home Visit',
            from_date=date(today.year, today.month, 1),
            to_date=date(today.year, today.month, 5),
            reason='Family Function',
            destination='Lucknow Home',
            emergency_contact='9999999999',
            status='Approved'
        )
        db.session.add(leave)
        db.session.commit()

        # Generate monthly billing
        result = MessService.generate_monthly_billing(month=today.month, year=today.year)
        self.assertTrue(result['success'])

        bill = MessBillingRecord.query.filter_by(
            student_id=self.student.id,
            billing_month=f"{today.year}-{today.month:02d}"
        ).first()
        self.assertIsNotNone(bill)
        # Verify rebate has been computed and subtracted from base fee
        self.assertGreater(bill.rebate_amount, Decimal('0.00'))
        self.assertEqual(bill.total_amount, bill.base_fee - bill.rebate_amount)

    # -------------------------------------------------------------
    # 9. Student Mess Dashboard & Resilience Test Suite
    # -------------------------------------------------------------
    def test_student_mess_dashboard_empty_menus_and_bookings(self):
        """Test GET /student/mess loads cleanly (HTTP 200) when no bookings exist"""
        self._login('student_test', 'Student@123')
        res = self.client.get('/student/mess')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Hostel Mess & Dining Desk', res.data)
        self.assertIn(b"Today's Dining Schedule", res.data)
        self.assertIn(b'No upcoming meal reservations', res.data)

    def test_student_mess_dashboard_with_menus_and_bookings(self):
        """Test GET /student/mess loads cleanly with published menus and active bookings"""
        today = date.today()
        menu = MealMenu(
            mess_id=self.mess.id,
            meal_date=today,
            meal_type='Lunch',
            title='Paneer Butter Masala',
            description='Creamy paneer curry with rotis',
            food_category='Vegetarian',
            meal_timing='12:30 PM - 2:30 PM',
            booking_deadline=datetime.utcnow() + timedelta(hours=3),
            capacity=200,
            is_published=True,
            created_by=self.manager.id
        )
        db.session.add(menu)
        db.session.commit()

        # Book the meal
        booking = MealBooking(
            student_id=self.student.id,
            meal_menu_id=menu.id,
            booking_status='Booked'
        )
        db.session.add(booking)
        db.session.commit()

        self._login('student_test', 'Student@123')
        res = self.client.get('/student/mess')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Paneer Butter Masala', res.data)
        self.assertIn(b'Confirmed', res.data)
        self.assertIn(b'Booked', res.data)

    def test_student_mess_dashboard_unallocated_student(self):
        """Test GET /student/mess for student without an active bed allocation"""
        self._login('student_test', 'Student@123')
        # Student has no active BedAllocation in setUp
        res = self.client.get('/student/mess')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Central Test Dining', res.data)

    def test_student_mess_dashboard_resilience_when_mess_profile_is_none(self):
        """Test GET /student/mess resilience when no MessProfile records exist at all"""
        # Delete mess profile
        MessStaffProfile.query.filter_by(mess_id=self.mess.id).delete()
        MealMenu.query.filter_by(mess_id=self.mess.id).delete()
        MessProfile.query.filter_by(id=self.mess.id).delete()
        db.session.commit()

        self._login('student_test', 'Student@123')
        res = self.client.get('/student/mess')
        # Should gracefully resolve or seed default without 500
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Hostel Mess & Dining Desk', res.data)

    def test_student_mess_menu_views(self):
        """Test GET /student/mess/menu daily and weekly calendar views"""
        self._login('student_test', 'Student@123')
        res = self.client.get('/student/mess/menu')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Weekly Dining Schedule', res.data)
        self.assertIn(b'Breakfast', res.data)
        self.assertIn(b'Lunch', res.data)
        self.assertIn(b'Dinner', res.data)

    def test_student_mess_qr_data_uri_generation(self):
        """Test GET /student/mess/qr renders without serverless disk dependencies"""
        # Test in-memory Base64 data URI method directly
        data_uri = MessService.generate_student_qr_data_uri(self.student)
        self.assertTrue(data_uri.startswith('data:image/png;base64,'))

        self._login('student_test', 'Student@123')
        res = self.client.get('/student/mess/qr')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Student Mess Dining Identity', res.data)
        self.assertIn(b'Cryptographic Token Active', res.data)

    def test_postgresql_allocation_status_enum_consistency(self):
        """Verify allocation queries strictly enforce lowercase status='active' for PostgreSQL enum compatibility"""
        from app.models.allocation import BedAllocation
        from app.models.hostel import Hostel, Room, Bed

        # Create hostel, room, bed, and allocation with status='active'
        hostel = Hostel(name='Shastri Hostel', hostel_type='Boys', total_floors=2, total_rooms=10)
        db.session.add(hostel)
        db.session.flush()

        room = Room(hostel_id=hostel.id, room_number='101', floor=1, room_type='Double', capacity=2)
        db.session.add(room)
        db.session.flush()

        bed = Bed(room_id=room.id, bed_number='Bed-A', status='occupied')
        db.session.add(bed)
        db.session.flush()

        alloc = BedAllocation(
            student_id=self.student.id,
            bed_id=bed.id,
            room_id=room.id,
            hostel_id=hostel.id,
            status='active'
        )
        db.session.add(alloc)
        db.session.commit()

        # Verify MessService resolves mess using lowercase 'active' allocation
        mess = MessService.get_student_mess(self.student)
        self.assertIsNotNone(mess)

        # Verify MessService.record_meal_attendance uses lowercase 'active'
        menu = MealMenu(
            mess_id=self.mess.id,
            meal_date=date.today(),
            meal_type='Dinner',
            title='Dinner Menu',
            booking_deadline=datetime.utcnow() + timedelta(hours=2),
            capacity=50,
            is_published=True,
            created_by=self.manager.id
        )
        db.session.add(menu)
        db.session.commit()

        att = MessService.record_meal_attendance(self.student.id, menu.id, self.staff.id)
        # Should not throw DataError or InvalidTextRepresentation
        self.assertIn('success', att)

    # -------------------------------------------------------------
    # 7. Complete Weekly Mess Menu (Monday - Sunday) Tests
    # -------------------------------------------------------------
    def test_ensure_weekly_menu_seeded_full_28_slots(self):
        """Verify ensure_weekly_menu_seeded generates all 28 slots for Monday through Sunday"""
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)

        MessService.ensure_weekly_menu_seeded(self.mess.id, today)

        # Check all 7 days have 4 meals each
        weekly_calendar = MessService.get_weekly_menus(self.mess.id, today, auto_seed=False)
        self.assertEqual(len(weekly_calendar), 7)

        total_meals = 0
        for day_date, slots in weekly_calendar.items():
            self.assertIn('Breakfast', slots)
            self.assertIn('Lunch', slots)
            self.assertIn('Snacks', slots)
            self.assertIn('Dinner', slots)
            for m_type in ['Breakfast', 'Lunch', 'Snacks', 'Dinner']:
                self.assertIsNotNone(slots[m_type], f"Missing {m_type} on {day_date}")
                self.assertTrue(slots[m_type].is_published)
                total_meals += 1

        self.assertEqual(total_meals, 28)

        # Check sample menu values for Monday
        mon_slots = weekly_calendar[monday]
        self.assertEqual(mon_slots['Breakfast'].title, 'Poha, Milk, Banana')
        self.assertEqual(mon_slots['Lunch'].title, 'Dal, Rice, Roti, Salad')
        self.assertEqual(mon_slots['Snacks'].title, 'Samosa, Tea')
        self.assertEqual(mon_slots['Dinner'].title, 'Paneer, Roti, Rice')
        self.assertEqual(mon_slots['Dinner'].special_dish, 'Paneer Butter Masala')

        # Check sample menu values for Sunday
        sun_slots = weekly_calendar[sunday]
        self.assertEqual(sun_slots['Breakfast'].title, 'Masala Dosa, Sambar')
        self.assertEqual(sun_slots['Lunch'].title, 'Special Thali')
        self.assertEqual(sun_slots['Snacks'].title, 'Burger, Juice')
        self.assertEqual(sun_slots['Dinner'].title, 'Special Dinner, Ice Cream')
        self.assertEqual(sun_slots['Dinner'].special_dish, 'Special Dinner, Ice Cream')

    def test_meal_menu_special_dish_and_items_properties(self):
        """Verify MealMenu extracts special_dish and formats food_items_display cleanly"""
        menu = MealMenu(
            mess_id=self.mess.id,
            meal_date=date.today(),
            meal_type='Dinner',
            title='Paneer, Roti, Rice',
            description='Paneer Butter Masala\nTawa Phulka\nJeera Rice\nSpecial Dish: Chef Paneer Butter Masala',
            booking_deadline=datetime.utcnow() + timedelta(hours=4),
            capacity=200,
            is_published=True
        )
        self.assertEqual(menu.special_dish, 'Chef Paneer Butter Masala')
        self.assertNotIn('Special Dish', menu.food_items_display)
        self.assertIn('Paneer Butter Masala', menu.food_items_display)

    def test_student_mess_dashboard_weekly_menu_view(self):
        """Verify Student Mess Dashboard renders 7-day navigation tabs and today's highlighted menu"""
        self._login('student_test', 'Student@123')
        res = self.client.get('/student/mess')
        self.assertEqual(res.status_code, 200)

        # Verify 7-day Monday through Sunday navigation exists
        self.assertIn(b'Weekly Dining Menu & Daily Schedule', res.data)
        self.assertIn(b'Today', res.data)
        # Check meal types
        self.assertIn(b'Breakfast', res.data)
        self.assertIn(b'Lunch', res.data)
        self.assertIn(b'Snacks', res.data)
        self.assertIn(b'Dinner', res.data)

    def test_student_weekly_menu_schedule_page(self):
        """Verify Student Weekly Menu page (/student/mess/menu) renders all 7 days with today highlighted"""
        self._login('student_test', 'Student@123')
        res = self.client.get('/student/mess/menu')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Full 7-Day Food Menu (Monday', res.data)
        self.assertIn(b'Today', res.data)

    def test_mess_manager_menu_create_edit_delete(self):
        """Verify Mess Manager can create with special dish, edit, and delete an unused meal"""
        self._login('manager_test', 'Manager@123')

        future_date = date.today() + timedelta(days=20)
        # 1. Create a new meal menu
        res = self.client.post('/mess-manager/menu/create', data={
            'meal_date': future_date.strftime('%Y-%m-%d'),
            'meal_type': 'Lunch',
            'title': 'Chole Bhature Feast',
            'special_dish': 'Punjabi Chole Bhature',
            'description': 'Amritsari Chole, Puffed Bhature, Pickle, Lassi',
            'food_category': 'Vegetarian',
            'meal_timing': '12:30 PM - 2:30 PM',
            'booking_deadline': (datetime.combine(future_date, datetime.min.time()) + timedelta(hours=6)).strftime('%Y-%m-%dT%H:%M'),
            'capacity': 250,
            'is_published': '1'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Chole Bhature Feast', res.data)

        # Verify saved in DB with special dish
        created_menu = MealMenu.query.filter_by(mess_id=self.mess.id, meal_date=future_date, meal_type='Lunch').first()
        self.assertIsNotNone(created_menu)
        self.assertEqual(created_menu.title, 'Chole Bhature Feast')
        self.assertEqual(created_menu.special_dish, 'Punjabi Chole Bhature')

        # 2. Edit the meal menu
        res = self.client.post(f'/mess-manager/menu/{created_menu.id}/edit', data={
            'title': 'Grand Chole Bhature Feast',
            'special_dish': 'Royal Punjabi Chole Bhature',
            'description': 'Updated items: Amritsari Chole, 2 Bhature, Boondi Raita',
            'food_category': 'Vegetarian',
            'meal_timing': '12:00 PM - 2:30 PM',
            'booking_deadline': (datetime.combine(future_date, datetime.min.time()) + timedelta(hours=7)).strftime('%Y-%m-%dT%H:%M'),
            'capacity': 280,
            'is_published': '1'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        db.session.refresh(created_menu)
        self.assertEqual(created_menu.title, 'Grand Chole Bhature Feast')
        self.assertEqual(created_menu.special_dish, 'Royal Punjabi Chole Bhature')

        # 3. Delete the meal menu
        res = self.client.post(f'/mess-manager/menu/{created_menu.id}/delete', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        deleted = MealMenu.query.get(created_menu.id)
        self.assertIsNone(deleted)

    def test_existing_manager_edits_preserved_during_seeding(self):
        """Verify ensure_weekly_menu_seeded does not overwrite custom meals set by Mess Manager"""
        today = date.today()
        monday = today - timedelta(days=today.weekday())

        # Manager creates custom meal on Monday breakfast before auto-seed
        custom_menu = MealMenu(
            mess_id=self.mess.id,
            meal_date=monday,
            meal_type='Breakfast',
            title='Custom Manager Special Breakfast',
            description='Special Fruit Platter\nSpecial Dish: Exotic Fruit Platter',
            food_category='Vegetarian',
            meal_timing='7:00 AM - 9:30 AM',
            booking_deadline=datetime.combine(monday, datetime.min.time()) + timedelta(hours=6),
            capacity=150,
            is_published=True
        )
        db.session.add(custom_menu)
        db.session.commit()

        # Run ensure_weekly_menu_seeded
        MessService.ensure_weekly_menu_seeded(self.mess.id, today)

        # Verify the custom meal was NOT replaced
        mon_b = MealMenu.query.filter_by(mess_id=self.mess.id, meal_date=monday, meal_type='Breakfast').first()
        self.assertEqual(mon_b.title, 'Custom Manager Special Breakfast')
        self.assertEqual(mon_b.special_dish, 'Exotic Fruit Platter')

    # -------------------------------------------------------------
    # 8. Food Wastage Reports & Analytics Test Suite
    # -------------------------------------------------------------
    def test_mess_manager_reports_empty_records_returns_200(self):
        """Verify Wastage Reports returns HTTP 200 and safe zero totals when no records exist"""
        self._login('manager_test', 'Manager@123')
        res = self.client.get('/mess-manager/reports')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Food Wastage & Turnout Analytics', res.data)
        self.assertIn(b'Total Food Prepared', res.data)
        self.assertIn(b'Total Food Consumed', res.data)
        self.assertIn(b'Total Food Wasted', res.data)
        self.assertIn(b'Wastage Percentage', res.data)
        self.assertIn(b'Daily Summary', res.data)
        self.assertIn(b'Weekly Summary', res.data)
        self.assertIn(b'Monthly Summary', res.data)
        self.assertIn(b'0.0%', res.data)

    def test_mess_manager_reports_populated_records_and_kpis(self):
        """Verify Wastage Reports accurately computes prepared, consumed, and unconsumed food metrics"""
        self._login('manager_test', 'Manager@123')
        today = date.today()

        # Create menu: capacity 200
        menu = MealMenu(
            mess_id=self.mess.id,
            meal_date=today,
            meal_type='Lunch',
            title='Deluxe Rajma Chawal',
            booking_deadline=datetime.utcnow() + timedelta(hours=3),
            capacity=200,
            is_published=True,
            created_by=self.manager.id
        )
        db.session.add(menu)
        db.session.flush()

        # Create 10 student bookings
        booking = MealBooking(
            student_id=self.student.id,
            meal_menu_id=menu.id,
            booking_status='Booked'
        )
        db.session.add(booking)
        db.session.flush()

        # Create 1 attendance check-in
        attendance = MealAttendance(
            student_id=self.student.id,
            meal_menu_id=menu.id,
            recorded_by=self.staff.id,
            verification_method='QR_Scan',
            attendance_status='Present'
        )
        db.session.add(attendance)

        # Create inventory item and wastage transaction
        inv_item = MessInventory(
            mess_id=self.mess.id,
            item_name='Fresh Tomatoes',
            category='Vegetables',
            quantity=Decimal('45.00'),
            unit='kg',
            minimum_stock_level=Decimal('10.00'),
            purchase_price=Decimal('35.00')
        )
        db.session.add(inv_item)
        db.session.flush()

        waste_tx = InventoryTransaction(
            inventory_id=inv_item.id,
            transaction_type='Wastage',
            quantity=Decimal('5.50'),
            unit_price=Decimal('35.00'),
            total_price=Decimal('192.50'),
            transaction_date=today,
            remarks='Spoiled during storage humidity',
            recorded_by=self.staff.id
        )
        db.session.add(waste_tx)
        db.session.commit()

        # Fetch report
        res = self.client.get('/mess-manager/reports')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Deluxe Rajma Chawal', res.data)
        self.assertIn(b'Fresh Tomatoes', res.data)
        self.assertIn(b'5.5 kg', res.data)
        self.assertIn(b'Spoiled during storage humidity', res.data)

    def test_mess_manager_reports_date_filtering_and_invalid_date_fallback(self):
        """Verify date parameter filtering and resilience against malformed date strings"""
        self._login('manager_test', 'Manager@123')

        # Valid date in past
        res = self.client.get('/mess-manager/reports?date=2026-11-15')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'15 Nov, 2026', res.data)

        # Invalid date string (should fallback to today safely without 500)
        res_invalid = self.client.get('/mess-manager/reports?date=not-a-valid-date')
        self.assertEqual(res_invalid.status_code, 200)
        self.assertIn(date.today().strftime('%d %b, %Y').encode('utf-8'), res_invalid.data)

    def test_mess_manager_reports_rbac_access_control(self):
        """Verify student and unauthenticated users cannot access Mess Manager wastage reports"""
        # 1. Unauthenticated -> 302 to login
        self.client.get('/auth/logout', follow_redirects=True)
        res_guest = self.client.get('/mess-manager/reports')
        self.assertEqual(res_guest.status_code, 302)
        self.assertIn('/auth/login', res_guest.headers.get('Location', ''))

        # 2. Student -> 403 Forbidden
        self._login('student_test', 'Student@123')
        res_student = self.client.get('/mess-manager/reports')
        self.assertEqual(res_student.status_code, 403)

    def test_mess_manager_export_attendance_csv(self):
        """Verify export_attendance_csv produces valid CSV response"""
        self._login('manager_test', 'Manager@123')
        res = self.client.get('/mess-manager/reports/export-attendance')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Attendance ID', res.data)
        self.assertIn(b'Meal Slot', res.data)
        self.assertIn(b'Student Name', res.data)

if __name__ == '__main__':
    unittest.main()
