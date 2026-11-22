import unittest
from datetime import date
from app import create_app, db
from app.models import User, Student, Hostel, Room, Bed, BedAllocation
from app.services.allocation_service import AllocationService

class RoomAllocationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        # Create Admin
        self.admin = User(username='admin_test', email='adm@aktu.ac.in', role='admin')
        self.admin.set_password('Admin@123')
        db.session.add(self.admin)

        # Create Hostels
        self.boys_hostel = Hostel(name='Boys Block A', hostel_type='boys', total_floors=2, total_rooms=2)
        self.girls_hostel = Hostel(name='Girls Block B', hostel_type='girls', total_floors=2, total_rooms=2)
        db.session.add_all([self.boys_hostel, self.girls_hostel])
        db.session.flush()

        # Create Rooms
        self.room_boys = Room(hostel_id=self.boys_hostel.id, room_number='A-101', floor=1, room_type='double', capacity=2)
        self.room_girls = Room(hostel_id=self.girls_hostel.id, room_number='B-101', floor=1, room_type='double', capacity=2)
        db.session.add_all([self.room_boys, self.room_girls])
        db.session.flush()

        # Create Beds
        self.bed_b1 = Bed(room_id=self.room_boys.id, bed_number='Bed-A', status='available')
        self.bed_b2 = Bed(room_id=self.room_boys.id, bed_number='Bed-B', status='available')
        self.bed_g1 = Bed(room_id=self.room_girls.id, bed_number='Bed-A', status='available')
        db.session.add_all([self.bed_b1, self.bed_b2, self.bed_g1])

        # Create Male & Female Students
        u_male = User(username='student_m', email='male@aktu.ac.in', role='student')
        u_male.set_password('Pass123')
        u_female = User(username='student_f', email='female@aktu.ac.in', role='student')
        u_female.set_password('Pass123')
        db.session.add_all([u_male, u_female])
        db.session.flush()

        self.s_male = Student(user_id=u_male.id, enrollment_no='ENR-M-01', full_name='Male Student', phone='9876543210', gender='male', branch='CSE', year=1, semester=1, guardian_name='G-M', guardian_phone='9876543210', address='Delhi')
        self.s_female = Student(user_id=u_female.id, enrollment_no='ENR-F-01', full_name='Female Student', phone='9876543211', gender='female', branch='IT', year=1, semester=1, guardian_name='G-F', guardian_phone='9876543211', address='Lucknow')
        db.session.add_all([self.s_male, self.s_female])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_gender_constraint_enforcement(self):
        # Male student attempting allocation to Girls hostel should FAIL
        success, msg = AllocationService.allocate_bed(self.s_male.id, self.bed_g1.id)
        self.assertFalse(success)
        self.assertIn("Constraint Violation", msg)

        # Female student attempting allocation to Boys hostel should FAIL
        success, msg = AllocationService.allocate_bed(self.s_female.id, self.bed_b1.id)
        self.assertFalse(success)
        self.assertIn("Constraint Violation", msg)

    def test_successful_allocation_and_overbooking_prevention(self):
        # 1. Allocate Male student to Boys bed
        success, msg = AllocationService.allocate_bed(self.s_male.id, self.bed_b1.id)
        self.assertTrue(success)
        self.assertEqual(self.bed_b1.status, 'occupied')

        # 2. Overbooking test: Trying to allocate another student to bed_b1 must fail
        u_another = User(username='another', email='another@aktu.ac.in', role='student')
        u_another.set_password('Pass123')
        db.session.add(u_another)
        db.session.flush()
        s_another = Student(user_id=u_another.id, enrollment_no='ENR-A-02', full_name='Another Student', phone='9876543219', gender='male', branch='ECE', year=1, semester=1, guardian_name='GA', guardian_phone='9876543219', address='Noida')
        db.session.add(s_another)
        db.session.commit()

        success2, msg2 = AllocationService.allocate_bed(s_another.id, self.bed_b1.id)
        self.assertFalse(success2)
        self.assertIn("occupied", msg2.lower())

    def test_auto_allocation_algorithm(self):
        # Female student auto allocation should pick Girls Hostel bed_g1
        success, msg = AllocationService.auto_allocate_student(self.s_female.id)
        self.assertTrue(success)
        self.assertEqual(self.bed_g1.status, 'occupied')
        self.assertEqual(self.s_female.current_allocation.bed_id, self.bed_g1.id)

    def test_vacate_bed(self):
        # Allocate then vacate
        AllocationService.allocate_bed(self.s_male.id, self.bed_b2.id)
        self.assertEqual(self.bed_b2.status, 'occupied')

        alloc = self.s_male.current_allocation
        success, msg = AllocationService.vacate_bed(alloc.id, reason="Graduation")
        self.assertTrue(success)
        self.assertEqual(self.bed_b2.status, 'available')
        self.assertFalse(self.s_male.has_active_allocation)

if __name__ == '__main__':
    unittest.main()

