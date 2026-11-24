from datetime import datetime, date, timedelta
from decimal import Decimal
from app import create_app, db
from app.models import User, Hostel, Room, Bed, Student, Warden, BedAllocation, FeeRecord, Attendance, Complaint, ComplaintResponse, Notice, LeaveApplication, Notification, DigitalOutPass, GateTransaction, ParentProfile, ParentInquiry
from app.models.mess import MessProfile, MessStaffProfile, Supplier, MessInventory, MealMenu, MessNotice
from app.services.outpass_service import OutPassService
from app.services.mess_service import MessService

app = create_app()

def seed():
    with app.app_context():
        print(f"Connecting to database: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print("Creating all tables from SQLAlchemy models...")
        db.create_all()

        # Check if guard_main exists, if not create
        guard_user = User.query.filter_by(username='guard_main').first()
        if not guard_user:
            print("Creating default security guard account (guard_main)...")
            guard_user = User(username='guard_main', email='guard.main@aktu-hostel.edu.in', role='security')
            guard_user.set_password('Guard@123')
            db.session.add(guard_user)
            db.session.commit()
            print("✓ Guard account guard_main created.")

        # Check if already seeded
        if User.query.filter_by(username='admin').first():
            print("Database already contains core seed data. Checking for missing outpasses...")
            # If Priya has approved leave l2 but no outpass, generate one
            approved_leaves = LeaveApplication.query.filter_by(status='Approved').all()
            for al in approved_leaves:
                if not al.out_pass:
                    print(f"Generating missing outpass for approved leave #{al.id}...")
                    OutPassService.generate_outpass(al)
            print("✓ Out-pass check complete.")

            # Check if demo parent exists
            parent_user = User.query.filter_by(username='parent_rahul').first()
            if not parent_user:
                student_rahul = Student.query.join(User).filter(User.username == 'rahul_sharma').first()
                if student_rahul:
                    print(f"Creating demo parent account (parent_rahul) linked to {student_rahul.full_name}...")
                    parent_user = User(username='parent_rahul', email='ramesh.sharma@parent.aktu.ac.in', role='parent')
                    parent_user.set_password('Parent@123')
                    db.session.add(parent_user)
                    db.session.flush()

                    parent_profile = ParentProfile(
                        user_id=parent_user.id,
                        parent_name='Ramesh Sharma',
                        phone_number='9876543210',
                        relationship_to_student='Father',
                        student_id=student_rahul.id,
                        account_status='active'
                    )
                    db.session.add(parent_profile)
                    db.session.commit()
                    print("✓ Demo parent account parent_rahul created.")
            seed_mess_demo_data()
            return

        print("Seeding initial administrator, wardens, and students...")

        # 1. Users
        admin_user = User(username='admin', email='admin@aktu-hostel.edu.in', role='admin')
        admin_user.set_password('Admin@123')

        warden_user_boys = User(username='warden_boys', email='warden.boys@aktu-hostel.edu.in', role='warden')
        warden_user_boys.set_password('Warden@123')

        warden_user_girls = User(username='warden_girls', email='warden.girls@aktu-hostel.edu.in', role='warden')
        warden_user_girls.set_password('Warden@123')

        student_user_1 = User(username='rahul_sharma', email='rahul.cse@aktu.ac.in', role='student')
        student_user_1.set_password('Student@123')

        student_user_2 = User(username='priya_verma', email='priya.it@aktu.ac.in', role='student')
        student_user_2.set_password('Student@123')

        student_user_3 = User(username='amit_kumar', email='amit.ece@aktu.ac.in', role='student')
        student_user_3.set_password('Student@123')

        db.session.add_all([admin_user, warden_user_boys, warden_user_girls, student_user_1, student_user_2, student_user_3])
        db.session.flush()

        # 2. Hostels
        hostel_boys = Hostel(name='Aryabhatta Boys Hostel (Block A)', hostel_type='boys', total_floors=3, total_rooms=15, description='Main Boys Hostel with Wi-Fi and solar geyser facility')
        hostel_girls = Hostel(name='Gargi Girls Hostel (Block B)', hostel_type='girls', total_floors=3, total_rooms=12, description='Girls Hostel block with 24/7 security and reading hall')
        db.session.add_all([hostel_boys, hostel_girls])
        db.session.flush()

        # 3. Wardens
        w1 = Warden(user_id=warden_user_boys.id, employee_id='EMP-WRD-001', full_name='Dr. Ramesh Chandra', phone='+91 9876543210', designation='Senior Chief Warden', assigned_hostel_id=hostel_boys.id)
        w2 = Warden(user_id=warden_user_girls.id, employee_id='EMP-WRD-002', full_name='Prof. Sunita Mishra', phone='+91 9876543211', designation='Associate Warden', assigned_hostel_id=hostel_girls.id)
        db.session.add_all([w1, w2])

        # 4. Students
        s1 = Student(
            user_id=student_user_1.id,
            enrollment_no='AKTU2023CSE0101',
            roll_no='23000101001',
            full_name='Rahul Sharma',
            phone='+91 9123456780',
            gender='male',
            branch='Computer Science & Engineering',
            year=3,
            semester=5,
            guardian_name='Mr. Suresh Sharma',
            guardian_phone='+91 9123456789',
            emergency_phone='+91 9123456789',
            address='H.No 45, Civil Lines, Prayagraj, UP',
            blood_group='B+',
            status='active'
        )

        s2 = Student(
            user_id=student_user_2.id,
            enrollment_no='AKTU2023IT0204',
            roll_no='23000102004',
            full_name='Priya Verma',
            phone='+91 9123456781',
            gender='female',
            branch='Information Technology',
            year=2,
            semester=3,
            guardian_name='Mr. Vinod Verma',
            guardian_phone='+91 9123456788',
            emergency_phone='+91 9123456788',
            address='Sector 12, Indiranagar, Lucknow, UP',
            blood_group='O+',
            status='active'
        )

        s3 = Student(
            user_id=student_user_3.id,
            enrollment_no='AKTU2023ECE0315',
            roll_no='23000103015',
            full_name='Amit Kumar',
            phone='+91 9123456782',
            gender='male',
            branch='Electronics & Communication',
            year=3,
            semester=5,
            guardian_name='Mr. Rajender Kumar',
            guardian_phone='+91 9123456787',
            emergency_phone='+91 9123456787',
            address='Near Clock Tower, Kanpur, UP',
            blood_group='A+',
            status='active'
        )
        db.session.add_all([s1, s2, s3])
        db.session.flush()

        # 5. Rooms
        r1 = Room(hostel_id=hostel_boys.id, room_number='A-101', floor=1, room_type='double', capacity=2, monthly_fee=4500.0, status='active')
        r2 = Room(hostel_id=hostel_boys.id, room_number='A-102', floor=1, room_type='double', capacity=2, monthly_fee=4500.0, status='active')
        r3 = Room(hostel_id=hostel_girls.id, room_number='B-101', floor=1, room_type='double', capacity=2, monthly_fee=4500.0, status='active')
        db.session.add_all([r1, r2, r3])
        db.session.flush()

        # 6. Beds
        b1 = Bed(room_id=r1.id, bed_number='Bed-A', status='occupied')
        b2 = Bed(room_id=r1.id, bed_number='Bed-B', status='available')
        b3 = Bed(room_id=r2.id, bed_number='Bed-A', status='occupied')
        b4 = Bed(room_id=r2.id, bed_number='Bed-B', status='available')
        b5 = Bed(room_id=r3.id, bed_number='Bed-A', status='occupied')
        b6 = Bed(room_id=r3.id, bed_number='Bed-B', status='available')
        db.session.add_all([b1, b2, b3, b4, b5, b6])
        db.session.flush()

        # 7. Active Allocations
        a1 = BedAllocation(student_id=s1.id, bed_id=b1.id, room_id=r1.id, hostel_id=hostel_boys.id, allocated_from=date(2026, 8, 1), status='active')
        a2 = BedAllocation(student_id=s2.id, bed_id=b5.id, room_id=r3.id, hostel_id=hostel_girls.id, allocated_from=date(2026, 8, 1), status='active')
        a3 = BedAllocation(student_id=s3.id, bed_id=b3.id, room_id=r2.id, hostel_id=hostel_boys.id, allocated_from=date(2026, 8, 1), status='active')
        db.session.add_all([a1, a2, a3])

        # 8. Fees
        f1 = FeeRecord(student_id=s1.id, receipt_no='REC-2026-001', amount=27000.0, payment_date=date(2026, 8, 5), payment_method='UPI', transaction_id='UPI/20260805123498/SBI', status='paid', remarks='Semester 5 Full Fee')
        f2 = FeeRecord(student_id=s2.id, receipt_no='REC-2026-002', amount=27000.0, payment_date=date(2026, 8, 6), payment_method='Net Banking', transaction_id='HDFC-NB-98127391', status='paid', remarks='Semester 3 Full Fee')
        f3 = FeeRecord(student_id=s3.id, receipt_no='REC-2026-003', amount=15000.0, payment_date=date(2026, 8, 10), payment_method='UPI', transaction_id='UPI/20260810998822/PNB', status='paid', remarks='Installment 1')
        db.session.add_all([f1, f2, f3])

        # 9. Attendance
        att1 = Attendance(student_id=s1.id, hostel_id=hostel_boys.id, date=date(2026, 11, 20), status='present', marked_by_warden_id=w1.id)
        att2 = Attendance(student_id=s2.id, hostel_id=hostel_girls.id, date=date(2026, 11, 20), status='present', marked_by_warden_id=w2.id)
        att3 = Attendance(student_id=s3.id, hostel_id=hostel_boys.id, date=date(2026, 11, 20), status='present', marked_by_warden_id=w1.id)
        db.session.add_all([att1, att2, att3])

        # 10. Complaints
        c1 = Complaint(student_id=s1.id, room_id=r1.id, title='Ceiling fan making squeaking noise', category='electrical', priority='medium', description='Fan regulator works but motor squeaks at night', status='in_progress')
        c2 = Complaint(student_id=s2.id, room_id=r3.id, title='Bathroom water tap leaking', category='plumbing', priority='high', description='Tap in attached washroom is dripping continuously', status='pending')
        db.session.add_all([c1, c2])
        db.session.flush()

        cr1 = ComplaintResponse(complaint_id=c1.id, responder_user_id=warden_user_boys.id, response_text='Electrician assigned for maintenance between 4-6 PM.', status_updated_to='in_progress')
        db.session.add(cr1)

        # 11. Notices
        n1 = Notice(posted_by_user_id=admin_user.id, title='Hostel Mess Menu Revision for Winter Semester', content='Revised menu comes into effect from next Monday. Please review noticeboard.', category='announcement', target_audience='all')
        n2 = Notice(posted_by_user_id=warden_user_boys.id, title='Night Curfew & Gate Closing Timing Notice', content='All boys hostel residents are strictly advised to report back by 9:30 PM.', category='urgent', target_audience='boys')
        db.session.add_all([n1, n2])

        # 12. Leave Applications & Notifications
        l1 = LeaveApplication(
            student_id=s1.id,
            hostel_id=hostel_boys.id,
            leave_type='Home Visit',
            from_date=date(2026, 11, 25),
            to_date=date(2026, 11, 28),
            reason='Visiting hometown in Prayagraj for family reunion over the weekend.',
            destination='H.No 45, Civil Lines, Prayagraj, UP',
            emergency_contact='+91 9123456789',
            status='Pending'
        )
        l2 = LeaveApplication(
            student_id=s2.id,
            hostel_id=hostel_girls.id,
            leave_type='Medical Leave',
            from_date=date(2026, 11, 15),
            to_date=date(2026, 11, 17),
            reason='Dental surgery and dental checkup appointment in Lucknow.',
            destination='Indiranagar, Lucknow, UP',
            emergency_contact='+91 9123456788',
            status='Approved',
            reviewed_by=w2.id,
            review_comment='Approved. Please submit doctor discharge slip upon return.',
            reviewed_at=datetime(2026, 11, 14, 15, 30)
        )
        l3 = LeaveApplication(
            student_id=s3.id,
            hostel_id=hostel_boys.id,
            leave_type='Personal Leave',
            from_date=date(2026, 11, 10),
            to_date=date(2026, 11, 12),
            reason='Attending friend birthday party outside campus.',
            destination='Varanasi Cantt, UP',
            emergency_contact='+91 9123456782',
            status='Rejected',
            reviewed_by=w1.id,
            review_comment='Rejected. Non-academic personal out-station party leave not permitted during mid-semester exams.',
            reviewed_at=datetime(2026, 11, 9, 11, 0)
        )
        db.session.add_all([l1, l2, l3])

        # Notifications
        notif1 = Notification(
            user_id=student_user_1.id,
            title='Leave Application Submitted',
            message='Your Home Visit leave application (#LVE-1) is currently pending warden review.',
            type='info'
        )
        notif2 = Notification(
            user_id=student_user_2.id,
            title='Leave Application Approved',
            message='Your Medical Leave (#LVE-2) was approved by Warden Prof. Sunita Mishra.',
            type='success'
        )
        notif3 = Notification(
            user_id=warden_user_boys.id,
            title='New Leave Application',
            message='Student Rahul Sharma submitted a Home Visit leave application (4 Days).',
            type='warning'
        )
        db.session.add_all([notif1, notif2, notif3])

        db.session.commit()
        print("✓ All demo data seeded successfully!")
        seed_mess_demo_data()


def seed_mess_demo_data():
    """Seeds Mess Manager, Mess Staff, default MessProfile, sample menus, and pantry stock"""
    print("Checking and seeding Mess Management System demo accounts and datasets...")

    # 1. Mess Manager Account
    manager_user = User.query.filter_by(username='mess_manager').first()
    if not manager_user:
        print("Creating demo Mess Manager account (mess_manager)...")
        manager_user = User(
            username='mess_manager',
            email='manager.mess@aktu-hostel.edu.in',
            role='mess_manager',
            is_active=True
        )
        manager_user.set_password('Manager@123')
        db.session.add(manager_user)
        db.session.commit()
        print("✓ Mess Manager mess_manager created.")

    # 2. Mess Facility Profile
    mess = MessService.get_or_create_default_mess()

    # 3. Mess Staff Account & Profile
    staff_user = User.query.filter_by(username='mess_staff').first()
    if not staff_user:
        print("Creating demo Mess Staff account (mess_staff)...")
        staff_user = User(
            username='mess_staff',
            email='staff.counter@aktu-hostel.edu.in',
            role='mess_staff',
            is_active=True
        )
        staff_user.set_password('Staff@123')
        db.session.add(staff_user)
        db.session.flush()

        staff_profile = MessStaffProfile(
            user_id=staff_user.id,
            mess_id=mess.id,
            staff_name='Dinesh Kumar',
            role_designation='Head Counter Attendant',
            employment_status='Active'
        )
        db.session.add(staff_profile)
        db.session.commit()
        print("✓ Mess Staff mess_staff created.")

    # 4. Sample Suppliers
    if Supplier.query.count() == 0:
        print("Seeding sample food suppliers...")
        s1 = Supplier(
            supplier_name='Apex Agro Wholesale Provisions',
            contact_person='Sunil Aggarwal',
            phone_number='+91 9811223344',
            email='supply@apexagro.com',
            address='Mandi Yard Shop #14, Sector 18, Lucknow'
        )
        s2 = Supplier(
            supplier_name='Amul & Mother Dairy Depot',
            contact_person='Rakesh Yadav',
            phone_number='+91 9822334455',
            email='dairy.dist@amullko.in',
            address='Cold Storage Complex, Transport Nagar, Lucknow'
        )
        db.session.add_all([s1, s2])
        db.session.commit()
        print("✓ Suppliers seeded.")

    # 5. Sample Inventory
    if MessInventory.query.count() == 0:
        print("Seeding sample pantry inventory...")
        sup1 = Supplier.query.first()
        items = [
            MessInventory(mess_id=mess.id, item_name='Basmati Rice', category='Grains & Cereals', quantity=Decimal('250.00'), unit='kg', minimum_stock_level=Decimal('50.00'), purchase_price=Decimal('62.50'), supplier_id=sup1.id if sup1 else None),
            MessInventory(mess_id=mess.id, item_name='Sharbati Wheat Flour (Atta)', category='Grains & Cereals', quantity=Decimal('300.00'), unit='kg', minimum_stock_level=Decimal('60.00'), purchase_price=Decimal('34.00'), supplier_id=sup1.id if sup1 else None),
            MessInventory(mess_id=mess.id, item_name='Full Cream Pasteurized Milk', category='Dairy', quantity=Decimal('80.00'), unit='litres', minimum_stock_level=Decimal('30.00'), purchase_price=Decimal('56.00'), supplier_id=sup1.id if sup1 else None),
            MessInventory(mess_id=mess.id, item_name='Toor / Arhar Dal', category='Pulses & Legumes', quantity=Decimal('120.00'), unit='kg', minimum_stock_level=Decimal('25.00'), purchase_price=Decimal('135.00'), supplier_id=sup1.id if sup1 else None),
            MessInventory(mess_id=mess.id, item_name='Mustard Cooking Oil', category='Spices & Oils', quantity=Decimal('60.00'), unit='litres', minimum_stock_level=Decimal('20.00'), purchase_price=Decimal('140.00'), supplier_id=sup1.id if sup1 else None),
            MessInventory(mess_id=mess.id, item_name='Commercial LPG Cylinder 19kg', category='Gas & Kitchen Supplies', quantity=Decimal('8.00'), unit='cylinders', minimum_stock_level=Decimal('3.00'), purchase_price=Decimal('1750.00'), supplier_id=sup1.id if sup1 else None),
        ]
        db.session.add_all(items)
        db.session.commit()
        print("✓ Pantry stock seeded.")

    # 6. Sample Menus for Today and the Complete Monday-Sunday Week
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    if MealMenu.query.filter_by(mess_id=mess.id, meal_date=today).count() == 0:
        print("Seeding complete 7-day Monday-Sunday weekly dining menus...")
        MessService.ensure_weekly_menu_seeded(mess.id, monday)
        print("✓ Complete weekly Monday-Sunday meal schedules seeded.")

    # 7. Sample Notice
    if MessNotice.query.count() == 0:
        print("Posting welcome dining notice...")
        notice = MessNotice(
            mess_id=mess.id,
            title='HostelEase Digital QR Mess System Active',
            message='Residents are requested to pre-book meals in advance on the portal and present their digital dining QR code at the counter scanner.',
            notice_type='General',
            expires_at=today + timedelta(days=30),
            posted_by=manager_user.id if manager_user else 1
        )
        db.session.add(notice)
        db.session.commit()
        print("✓ Dining notice posted.")

    print("✓ Mess Management System seed verification complete.")

if __name__ == '__main__':
    seed()

