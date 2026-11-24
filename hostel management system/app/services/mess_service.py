import os
import hashlib
import qrcode
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from app.models import (
    db, Student, User, Hostel, BedAllocation, LeaveApplication,
    MessProfile, Supplier, MealMenu, MealBooking, MealAttendance,
    MealFeedback, MessInventory, InventoryTransaction, MessExpense,
    MessStaffProfile, MessNotice, MessBillingRecord
)
from app.services.notification_service import NotificationService

SECRET_MESS_KEY = "hostelease-secure-mess-qr-salt-2026"

WEEKLY_MENU_TEMPLATE = [
    # Day 0: Monday
    {
        'day_name': 'Monday',
        'meals': [
            {
                'type': 'Breakfast',
                'title': 'Poha, Milk, Banana',
                'desc': 'Fluffy seasoned poha garnished with roasted peanuts and fresh coriander, served with warm milk and fresh banana.',
                'timing': '7:30 AM - 9:30 AM',
                'category': 'Vegetarian',
                'special_dish': None
            },
            {
                'type': 'Lunch',
                'title': 'Dal, Rice, Roti, Salad',
                'desc': 'Nutritious yellow toor dal tadka, steamed basmati rice, freshly baked whole wheat rotis, and fresh seasonal green salad.',
                'timing': '12:30 PM - 2:30 PM',
                'category': 'Vegetarian',
                'special_dish': None
            },
            {
                'type': 'Snacks',
                'title': 'Samosa, Tea',
                'desc': 'Crispy potato-stuffed samosas served with tangy tamarind chutney and freshly brewed spiced masala chai.',
                'timing': '5:00 PM - 6:00 PM',
                'category': 'Vegetarian',
                'special_dish': None
            },
            {
                'type': 'Dinner',
                'title': 'Paneer, Roti, Rice',
                'desc': 'Rich paneer butter masala gravy, warm tawa rotis, fragrant jeera rice, and sliced cucumber salad.\nSpecial Dish: Paneer Butter Masala',
                'timing': '7:30 PM - 9:30 PM',
                'category': 'Vegetarian',
                'special_dish': 'Paneer Butter Masala'
            }
        ]
    },
    # Day 1: Tuesday
    {
        'day_name': 'Tuesday',
        'meals': [
            {
                'type': 'Breakfast',
                'title': 'Aloo Paratha, Curd',
                'desc': 'Hot spiced aloo parathas served with creamy fresh curd, mixed pickle, and tea.\nSpecial Dish: Stuffed Aloo Paratha',
                'timing': '7:30 AM - 9:30 AM',
                'category': 'Vegetarian',
                'special_dish': 'Stuffed Aloo Paratha'
            },
            {
                'type': 'Lunch',
                'title': 'Rajma, Rice, Salad',
                'desc': 'Authentic North Indian rajma masala cooked in thick tomato-onion gravy, steamed basmati rice, roasted papad, and fresh salad.',
                'timing': '12:30 PM - 2:30 PM',
                'category': 'Vegetarian',
                'special_dish': None
            },
            {
                'type': 'Snacks',
                'title': 'Sandwich, Tea',
                'desc': 'Toasted grilled vegetable sandwich filled with cucumber, tomato, green mint chutney, served with hot ginger tea.',
                'timing': '5:00 PM - 6:00 PM',
                'category': 'Vegetarian',
                'special_dish': None
            },
            {
                'type': 'Dinner',
                'title': 'Mix Veg, Dal, Roti',
                'desc': 'Homestyle mixed seasonal vegetable sabzi, yellow moong dal fry, soft tawa rotis, and steamed rice.',
                'timing': '7:30 PM - 9:30 PM',
                'category': 'Vegetarian',
                'special_dish': None
            }
        ]
    },
    # Day 2: Wednesday
    {
        'day_name': 'Wednesday',
        'meals': [
            {
                'type': 'Breakfast',
                'title': 'Idli, Sambar',
                'desc': 'Soft steamed rice idlis served with piping hot vegetable sambar and freshly ground coconut chutney.',
                'timing': '7:30 AM - 9:30 AM',
                'category': 'Vegetarian',
                'special_dish': None
            },
            {
                'type': 'Lunch',
                'title': 'Chole, Rice, Roti',
                'desc': 'Spiced Amritsari chole masala, steamed basmati rice, warm whole wheat rotis, and onion-lemon salad.',
                'timing': '12:30 PM - 2:30 PM',
                'category': 'Vegetarian',
                'special_dish': None
            },
            {
                'type': 'Snacks',
                'title': 'Bread Pakora, Tea',
                'desc': 'Crispy deep-fried bread pakoras stuffed with savory spiced potatoes, served with mint chutney and tea.',
                'timing': '5:00 PM - 6:00 PM',
                'category': 'Vegetarian',
                'special_dish': None
            },
            {
                'type': 'Dinner',
                'title': 'Shahi Paneer, Roti',
                'desc': 'Creamy royal shahi paneer cooked with cashew gravy and aromatic spices, hot tawa phulkas, steamed rice, and gulab jamun.\nSpecial Dish: Shahi Paneer',
                'timing': '7:30 PM - 9:30 PM',
                'category': 'Vegetarian',
                'special_dish': 'Shahi Paneer'
            }
        ]
    },
    # Day 3: Thursday
    {
        'day_name': 'Thursday',
        'meals': [
            {
                'type': 'Breakfast',
                'title': 'Sandwich, Milk',
                'desc': 'Nutritious toasted vegetable club sandwich with cheese slice, served with warm sweetened dairy milk.',
                'timing': '7:30 AM - 9:30 AM',
                'category': 'Vegetarian',
                'special_dish': None
            },
            {
                'type': 'Lunch',
                'title': 'Kadhi, Rice, Roti',
                'desc': 'Traditional Punjabi pakora kadhi cooked in sour buttermilk, steamed basmati rice, soft rotis, and roasted papad.',
                'timing': '12:30 PM - 2:30 PM',
                'category': 'Vegetarian',
                'special_dish': None
            },
            {
                'type': 'Snacks',
                'title': 'Dhokla, Tea',
                'desc': 'Spongy steamed Gujarati nylon dhokla tempered with mustard seeds and curry leaves, served with green chutney and tea.',
                'timing': '5:00 PM - 6:00 PM',
                'category': 'Vegetarian',
                'special_dish': None
            },
            {
                'type': 'Dinner',
                'title': 'Dal Makhani, Rice',
                'desc': 'Slow-cooked creamy dal makhani with butter and aromatic spices, steamed jeera rice, soft whole wheat rotis, and salad.\nSpecial Dish: Dal Makhani',
                'timing': '7:30 PM - 9:30 PM',
                'category': 'Vegetarian',
                'special_dish': 'Dal Makhani'
            }
        ]
    },
    # Day 4: Friday
    {
        'day_name': 'Friday',
        'meals': [
            {
                'type': 'Breakfast',
                'title': 'Poori, Aloo Sabzi',
                'desc': 'Puffy golden pooris served with halwai-style spicy aloo rasedaar sabzi, sweet semolina sooji halwa, and pickle.\nSpecial Dish: Poori Aloo Halwa',
                'timing': '7:30 AM - 9:30 AM',
                'category': 'Vegetarian',
                'special_dish': 'Poori Aloo Halwa'
            },
            {
                'type': 'Lunch',
                'title': 'Dal, Rice, Roti, Salad',
                'desc': 'Yellow dal fry with cumin tempering, steamed basmati rice, tawa rotis, roasted papad, and fresh sliced green salad.',
                'timing': '12:30 PM - 2:30 PM',
                'category': 'Vegetarian',
                'special_dish': None
            },
            {
                'type': 'Snacks',
                'title': 'Pasta, Juice',
                'desc': 'Italian herb vegetable penne pasta with sweet corn, bell peppers, served with chilled fruit juice.',
                'timing': '5:00 PM - 6:00 PM',
                'category': 'Vegetarian',
                'special_dish': None
            },
            {
                'type': 'Dinner',
                'title': 'Kadai Paneer, Roti',
                'desc': 'Spicy kadai paneer tossed with capsicum and freshly ground whole spices, soft butter rotis, steamed rice.\nSpecial Dish: Kadai Paneer',
                'timing': '7:30 PM - 9:30 PM',
                'category': 'Vegetarian',
                'special_dish': 'Kadai Paneer'
            }
        ]
    },
    # Day 5: Saturday
    {
        'day_name': 'Saturday',
        'meals': [
            {
                'type': 'Breakfast',
                'title': 'Upma, Tea',
                'desc': 'Roasted rava upma cooked with vegetables, curry leaves, and mustard seeds, served with coconut chutney and hot tea.',
                'timing': '7:30 AM - 9:30 AM',
                'category': 'Vegetarian',
                'special_dish': None
            },
            {
                'type': 'Lunch',
                'title': 'Chole Bhature, Salad',
                'desc': 'Fluffy hot bhature served with rich spiced Punjabi chole, pickled onions, fried green chili, and boondi raita.\nSpecial Dish: Chole Bhature',
                'timing': '12:30 PM - 2:30 PM',
                'category': 'Vegetarian',
                'special_dish': 'Chole Bhature'
            },
            {
                'type': 'Snacks',
                'title': 'Spring Rolls, Tea',
                'desc': 'Golden crispy vegetable spring rolls served with sweet garlic chili dipping sauce and hot masala tea.',
                'timing': '5:00 PM - 6:00 PM',
                'category': 'Vegetarian',
                'special_dish': None
            },
            {
                'type': 'Dinner',
                'title': 'Veg Pulao, Raita',
                'desc': 'Fragrant basmati vegetable pulao prepared with green peas and carrots, served with chilled vegetable raita and roasted papad.',
                'timing': '7:30 PM - 9:30 PM',
                'category': 'Vegetarian',
                'special_dish': None
            }
        ]
    },
    # Day 6: Sunday
    {
        'day_name': 'Sunday',
        'meals': [
            {
                'type': 'Breakfast',
                'title': 'Masala Dosa, Sambar',
                'desc': 'Crisp golden South Indian masala dosa with potato stuffing, served with hot sambar and fresh coconut chutney.\nSpecial Dish: Masala Dosa',
                'timing': '7:30 AM - 9:30 AM',
                'category': 'Vegetarian',
                'special_dish': 'Masala Dosa'
            },
            {
                'type': 'Lunch',
                'title': 'Special Thali',
                'desc': 'Grand Sunday Royal Thali: Paneer Lababdar, Dal Makhani, Seasonal Veg, Steamed Basmati Rice, Butter Naan/Roti, Boondi Raita, Papad, and Sweet Dessert.\nSpecial Dish: Special Thali',
                'timing': '12:30 PM - 2:30 PM',
                'category': 'Vegetarian',
                'special_dish': 'Special Thali'
            },
            {
                'type': 'Snacks',
                'title': 'Burger, Juice',
                'desc': 'Crispy vegetable burger with cheese slice and fresh tomatoes, served with chilled mango fruit juice.',
                'timing': '5:00 PM - 6:00 PM',
                'category': 'Vegetarian',
                'special_dish': None
            },
            {
                'type': 'Dinner',
                'title': 'Special Dinner, Ice Cream',
                'desc': 'Weekend Special Dinner: Malai Kofta, Jeera Rice, Tawa Butter Roti, Dal Fry, Fresh Salad, followed by Premium Ice Cream.\nSpecial Dish: Special Dinner, Ice Cream',
                'timing': '7:30 PM - 9:30 PM',
                'category': 'Vegetarian',
                'special_dish': 'Special Dinner, Ice Cream'
            }
        ]
    }
]

class MessService:
    """
    Core Business Logic Service for HostelEase Mess & Dining Management System.
    Handles menus, meal reservations, QR verification, attendance, inventory,
    expenses, feedback, and billing integrations.
    """

    @staticmethod
    def get_or_create_default_mess(hostel_id=None):
        """Finds or seeds an initial active mess dining facility"""
        query = MessProfile.query.filter_by(operating_status='Active')
        if hostel_id:
            mess = query.filter_by(hostel_id=hostel_id).first()
            if mess:
                return mess

        mess = query.first()
        if not mess:
            # Fallback to any existing mess profile regardless of operating status
            mess = MessProfile.query.first()
            if mess:
                return mess

            # Seed default central campus dining hall safely with rollback guard
            try:
                mess = MessProfile(
                    mess_name="HostelEase Central Dining Hall",
                    description="Primary student residential dining facility serving nutritious, hygienic vegetarian and non-vegetarian meals.",
                    contact_number="+91-9876543210",
                    operating_status='Active',
                    meal_policy='booking_required',
                    daily_capacity=350,
                    hostel_id=hostel_id
                )
                db.session.add(mess)
                db.session.commit()
            except Exception:
                db.session.rollback()
                mess = MessProfile.query.first()
        return mess

    @staticmethod
    def get_student_mess(student):
        """Identifies the appropriate mess facility for a given student resident"""
        if not student:
            return MessService.get_or_create_default_mess()

        # Check student's current active room allocation (PostgreSQL allocation_status_enum: 'active')
        alloc = student.current_allocation if hasattr(student, 'current_allocation') else None
        if not alloc:
            alloc = BedAllocation.query.filter_by(student_id=student.id, status='active').first()

        if alloc and alloc.hostel_id:
            hostel_mess = MessProfile.query.filter_by(hostel_id=alloc.hostel_id, operating_status='Active').first()
            if hostel_mess:
                return hostel_mess
            hostel_mess = MessProfile.query.filter_by(hostel_id=alloc.hostel_id).first()
            if hostel_mess:
                return hostel_mess

        return MessService.get_or_create_default_mess()

    @staticmethod
    def ensure_weekly_menu_seeded(mess_id, reference_date=None):
        """
        Ensures that all 28 meal slots (Monday-Sunday, 4 meals/day)
        are present in the database for the week containing reference_date.
        """
        if not mess_id:
            return
        if reference_date is None:
            reference_date = date.today()

        monday = reference_date - timedelta(days=reference_date.weekday())
        any_added = False

        for day_offset in range(7):
            meal_day = monday + timedelta(days=day_offset)
            day_template = WEEKLY_MENU_TEMPLATE[day_offset]

            for m in day_template['meals']:
                existing = MealMenu.query.filter_by(
                    mess_id=mess_id,
                    meal_date=meal_day,
                    meal_type=m['type']
                ).first()

                if not existing:
                    # Cutoff deadline is 6 hours after day start (e.g. 6:00 AM on the meal day)
                    deadline = datetime.combine(meal_day, datetime.min.time()) + timedelta(hours=6)
                    menu = MealMenu(
                        mess_id=mess_id,
                        meal_date=meal_day,
                        meal_type=m['type'],
                        title=m['title'],
                        description=m['desc'],
                        food_category=m['category'],
                        meal_timing=m['timing'],
                        booking_deadline=deadline,
                        capacity=300,
                        is_published=True
                    )
                    db.session.add(menu)
                    any_added = True

        if any_added:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

    @staticmethod
    def get_today_menus(mess_id, target_date=None, auto_seed=True):
        """Retrieves published menus for all four slots of a specific day"""
        if not mess_id:
            return []

        if target_date is None:
            target_date = date.today()

        if auto_seed:
            MessService.ensure_weekly_menu_seeded(mess_id, target_date)

        menus = MealMenu.query.filter_by(
            mess_id=mess_id,
            meal_date=target_date,
            is_published=True
        ).all()

        slot_order = {'Breakfast': 1, 'Lunch': 2, 'Snacks': 3, 'Dinner': 4}
        return sorted(menus, key=lambda m: slot_order.get(m.meal_type, 5))

    @staticmethod
    def get_weekly_menus(mess_id, start_date=None, auto_seed=True, published_only=False):
        """
        Retrieves a full 7-day schedule of meals for Monday through Sunday.
        Anchors automatically to the Monday of the week containing start_date.
        """
        if start_date is None:
            start_date = date.today()

        # Anchor to Monday of that week
        monday = start_date - timedelta(days=start_date.weekday())
        sunday = monday + timedelta(days=6)

        if auto_seed and mess_id:
            MessService.ensure_weekly_menu_seeded(mess_id, monday)

        # Organize by date -> meal_type
        calendar_data = {}
        for i in range(7):
            d = monday + timedelta(days=i)
            calendar_data[d] = {'Breakfast': None, 'Lunch': None, 'Snacks': None, 'Dinner': None}

        if not mess_id:
            return calendar_data

        query = MealMenu.query.filter(
            MealMenu.mess_id == mess_id,
            MealMenu.meal_date >= monday,
            MealMenu.meal_date <= sunday
        )
        if published_only:
            query = query.filter(MealMenu.is_published == True)

        menus = query.order_by(MealMenu.meal_date.asc()).all()

        for menu in menus:
            if menu.meal_date in calendar_data and menu.meal_type in calendar_data[menu.meal_date]:
                calendar_data[menu.meal_date][menu.meal_type] = menu

        return calendar_data

    @staticmethod
    def book_meal(student_id, meal_menu_id):
        """
        Processes a meal booking for a student.
        Validates publication, deadlines, capacity, and prevents duplicates.
        """
        student = Student.query.get(student_id)
        if not student:
            return {'success': False, 'message': 'Student record not found.'}

        menu = MealMenu.query.get(meal_menu_id)
        if not menu:
            return {'success': False, 'message': 'Selected meal menu does not exist.'}

        if not menu.is_published:
            return {'success': False, 'message': 'This meal menu has not yet been published for booking.'}

        # Check booking deadline
        if datetime.utcnow() > menu.booking_deadline:
            return {
                'success': False,
                'message': f'Booking closed: Deadline was {menu.booking_deadline.strftime("%d %b %Y, %I:%M %p")}.'
            }

        # Check for existing active booking
        existing_booking = MealBooking.query.filter_by(
            student_id=student_id,
            meal_menu_id=meal_menu_id
        ).first()

        if existing_booking:
            if existing_booking.booking_status == 'Booked':
                return {'success': False, 'message': 'You have already booked this meal.'}
            elif existing_booking.booking_status == 'Consumed':
                return {'success': False, 'message': 'This meal has already been marked as consumed.'}
            elif existing_booking.booking_status == 'Cancelled':
                # Re-activate the cancelled booking if capacity allows
                if menu.is_capacity_full:
                    return {'success': False, 'message': 'Meal capacity has been reached. No seats available.'}
                existing_booking.booking_status = 'Booked'
                existing_booking.booking_date = datetime.utcnow()
                existing_booking.cancellation_date = None
                db.session.commit()
                return {'success': True, 'message': f'Booking for {menu.meal_type} re-activated successfully.', 'booking': existing_booking}

        # Check capacity
        if menu.is_capacity_full:
            return {'success': False, 'message': 'Meal capacity is full. Booking is unavailable.'}

        # Create new booking
        booking = MealBooking(
            student_id=student_id,
            meal_menu_id=meal_menu_id,
            booking_status='Booked',
            booking_date=datetime.utcnow()
        )
        db.session.add(booking)
        db.session.commit()

        # Send in-app notification to student
        if student.user_id:
            NotificationService.create_notification(
                user_id=student.user_id,
                title="Meal Booking Confirmed",
                message=f"Your booking for {menu.meal_type} on {menu.meal_date.strftime('%d %b, %Y')} ({menu.title}) has been confirmed.",
                type="success",
                link="/student/mess/bookings"
            )
            db.session.commit()

        return {'success': True, 'message': f'Booking for {menu.meal_type} confirmed successfully.', 'booking': booking}

    @staticmethod
    def cancel_booking(student_id, booking_id):
        """Allows a student to cancel a booked meal prior to the booking deadline"""
        booking = MealBooking.query.get(booking_id)
        if not booking:
            return {'success': False, 'message': 'Booking record not found.'}

        # IDOR check
        if booking.student_id != student_id:
            return {'success': False, 'message': 'Unauthorized: You can only cancel your own bookings.'}

        if booking.booking_status != 'Booked':
            return {'success': False, 'message': f'Cannot cancel booking with status "{booking.booking_status}".'}

        menu = booking.meal_menu
        if datetime.utcnow() > menu.booking_deadline:
            return {
                'success': False,
                'message': f'Cancellation deadline passed: Cutoff was {menu.booking_deadline.strftime("%d %b %Y, %I:%M %p")}.'
            }

        booking.booking_status = 'Cancelled'
        booking.cancellation_date = datetime.utcnow()
        db.session.commit()

        # Notify student
        student = booking.student
        if student and student.user_id:
            NotificationService.create_notification(
                user_id=student.user_id,
                title="Meal Booking Cancelled",
                message=f"Your booking for {menu.meal_type} on {menu.meal_date.strftime('%d %b, %Y')} has been cancelled.",
                type="warning",
                link="/student/mess/bookings"
            )
            db.session.commit()

        return {'success': True, 'message': 'Meal booking cancelled successfully.'}

    @staticmethod
    def generate_student_qr_payload(student):
        """
        Generates a tamper-proof cryptographic student meal verification payload.
        Format: MESS:<student_id>:<hash(student_id:enrollment_no:salt)>
        Does NOT expose student passwords, phone numbers, or confidential PII.
        """
        raw_signature = f"{student.id}:{student.enrollment_no}:{SECRET_MESS_KEY}"
        token_hash = hashlib.sha256(raw_signature.encode('utf-8')).hexdigest()[:24]
        return f"MESS:{student.id}:{token_hash}"

    @staticmethod
    def verify_student_qr_payload(payload):
        """Validates student QR payload and returns authenticated Student model or None"""
        if not payload or not isinstance(payload, str):
            return None

        payload = payload.strip()
        if payload.startswith("MESS:"):
            parts = payload.split(":")
            if len(parts) == 3:
                try:
                    student_id = int(parts[1])
                    provided_hash = parts[2]
                    student = Student.query.get(student_id)
                    if student:
                        expected_raw = f"{student.id}:{student.enrollment_no}:{SECRET_MESS_KEY}"
                        expected_hash = hashlib.sha256(expected_raw.encode('utf-8')).hexdigest()[:24]
                        if provided_hash == expected_hash:
                            return student
                except Exception:
                    pass

        # Fallback: manual alphanumeric entry of enrollment_no or roll_no
        student = Student.query.filter(
            (Student.enrollment_no == payload) | (Student.roll_no == payload)
        ).first()
        return student

    @staticmethod
    def generate_student_qr_data_uri(student):
        """Generates an in-memory Base64 data URI for serverless-safe QR rendering"""
        import io
        import base64
        payload = MessService.generate_student_qr_payload(student)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0d6efd", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        encoded = base64.b64encode(buf.getvalue()).decode('ascii')
        return f"data:image/png;base64,{encoded}"

    @staticmethod
    def generate_student_qr_image(student, app_root):
        """Generates and saves the student mess QR code PNG file with serverless fallback"""
        try:
            qr_dir = os.path.join(app_root, 'static', 'uploads', 'qrcodes')
            os.makedirs(qr_dir, exist_ok=True)
            filename = f"mess_qr_{student.id}_{student.enrollment_no}.png"
            filepath = os.path.join(qr_dir, filename)

            if not os.path.exists(filepath):
                payload = MessService.generate_student_qr_payload(student)
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_M,
                    box_size=10,
                    border=4,
                )
                qr.add_data(payload)
                qr.make(fit=True)
                img = qr.make_image(fill_color="#0d6efd", back_color="white")
                img.save(filepath)

            return f"uploads/qrcodes/{filename}"
        except OSError:
            # Serverless read-only filesystem fallback
            return None

    @staticmethod
    def record_meal_attendance(student_id, meal_menu_id, staff_user_id, verification_method='QR_Scan', remarks=None):
        """
        Core gatekeeper for dining hall meal service check-in.
        Enforces attendance policy (booking-required vs walk-in), verifies eligibility,
        and guarantees atomic prevention of duplicate meal consumption.
        """
        student = Student.query.get(student_id)
        if not student:
            return {'success': False, 'code': 'STUDENT_NOT_FOUND', 'message': 'Student record not found.'}

        menu = MealMenu.query.get(meal_menu_id)
        if not menu:
            return {'success': False, 'code': 'MENU_NOT_FOUND', 'message': 'Meal menu not found.'}

        mess = menu.mess

        # Check if student is allocated to this hostel / mess
        student_alloc = BedAllocation.query.filter_by(student_id=student.id, status='active').first()
        if mess.hostel_id and student_alloc and student_alloc.hostel_id != mess.hostel_id:
            return {
                'success': False,
                'code': 'UNAUTHORIZED_HOSTEL',
                'message': f'Student is assigned to {student_alloc.hostel.name}, not authorized for {mess.mess_name}.'
            }

        # Check for duplicate attendance
        existing_attendance = MealAttendance.query.filter_by(
            student_id=student_id,
            meal_menu_id=meal_menu_id
        ).first()

        if existing_attendance:
            return {
                'success': False,
                'code': 'DUPLICATE_ATTENDANCE',
                'message': f'Attendance already recorded at {existing_attendance.check_in_time.strftime("%I:%M %p")}.',
                'check_in_time': existing_attendance.check_in_time.strftime('%I:%M %p'),
                'student': student,
                'menu': menu
            }

        # Policy evaluation: booking_required vs walk_in
        booking = MealBooking.query.filter_by(
            student_id=student_id,
            meal_menu_id=meal_menu_id,
            booking_status='Booked'
        ).first()

        if mess.meal_policy == 'booking_required' and not booking:
            return {
                'success': False,
                'code': 'BOOKING_REQUIRED',
                'message': f'Policy Error: No active meal booking found for {student.full_name} for {menu.meal_type}.',
                'student': student,
                'menu': menu
            }

        # Record attendance atomically
        attendance_status = 'Present' if booking else 'Walk-in'
        attendance = MealAttendance(
            student_id=student_id,
            meal_menu_id=meal_menu_id,
            meal_booking_id=booking.id if booking else None,
            attendance_status=attendance_status,
            check_in_time=datetime.utcnow(),
            recorded_by=staff_user_id,
            verification_method=verification_method,
            remarks=remarks
        )
        db.session.add(attendance)

        if booking:
            booking.booking_status = 'Consumed'
            booking.updated_at = datetime.utcnow()

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {
                'success': False,
                'code': 'DUPLICATE_ATTENDANCE',
                'message': 'Concurrent check-in detected. Attendance already recorded.',
                'student': student,
                'menu': menu
            }

        alloc = student.current_allocation
        return {
            'success': True,
            'code': 'ATTENDANCE_RECORDED',
            'message': f'Meal attendance recorded ({attendance_status}).',
            'attendance_status': attendance_status,
            'check_in_time': attendance.check_in_time.strftime('%I:%M %p'),
            'student_name': student.full_name,
            'enrollment_no': student.enrollment_no,
            'roll_no': student.roll_no or 'N/A',
            'branch': student.branch,
            'hostel': alloc.hostel.name if alloc else 'N/A',
            'room': alloc.room.room_number if alloc else 'N/A',
            'meal_type': menu.meal_type,
            'menu_title': menu.title
        }

    @staticmethod
    def record_inventory_transaction(inventory_id, tx_type, quantity, unit_price, supplier_id=None, reference=None, remarks=None, user_id=None):
        """
        Manages inventory changes (Purchase, Consumption, Adjustment, Wastage).
        Synchronizes stock balances safely and enforces non-negative stock policies.
        """
        item = MessInventory.query.get(inventory_id)
        if not item:
            return {'success': False, 'message': 'Inventory item not found.'}

        qty = Decimal(str(quantity))
        price = Decimal(str(unit_price or 0.0))
        total_price = qty * price

        if qty <= 0:
            return {'success': False, 'message': 'Transaction quantity must be greater than zero.'}

        if tx_type in ['Consumption', 'Wastage']:
            if item.quantity < qty:
                return {
                    'success': False,
                    'message': f'Insufficient stock: Available quantity is {item.quantity} {item.unit}, requested {qty} {item.unit}.'
                }
            item.quantity -= qty
        elif tx_type == 'Purchase':
            item.quantity += qty
            if price > 0:
                item.purchase_price = price
        elif tx_type == 'Adjustment':
            item.quantity = qty  # Direct count reconciliation

        tx = InventoryTransaction(
            inventory_id=inventory_id,
            transaction_type=tx_type,
            quantity=qty,
            unit_price=price,
            total_price=total_price,
            supplier_id=supplier_id,
            reference=reference,
            remarks=remarks,
            recorded_by=user_id,
            transaction_date=date.today()
        )
        db.session.add(tx)
        item.updated_at = datetime.utcnow()
        db.session.commit()

        # Check low stock notification trigger
        if item.is_low_stock:
            # Alert mess managers
            managers = User.query.filter_by(role='mess_manager', is_active=True).all()
            for mgr in managers:
                NotificationService.create_notification(
                    user_id=mgr.id,
                    title="Low Stock Alert",
                    message=f"Pantry stock for {item.item_name} has fallen to {item.quantity} {item.unit} (Minimum threshold: {item.minimum_stock_level} {item.unit}).",
                    type="warning",
                    link="/mess-manager/inventory"
                )
            db.session.commit()

        return {'success': True, 'message': f'Inventory {tx_type} recorded successfully.', 'current_quantity': item.quantity}

    @staticmethod
    def record_expense(mess_id, category, description, amount, receipt_reference=None, user_id=None, tx_date=None):
        """Records a verified operational mess expenditure"""
        amt = Decimal(str(amount))
        if amt <= 0:
            return {'success': False, 'message': 'Expense amount must be greater than zero.'}

        expense = MessExpense(
            mess_id=mess_id,
            expense_category=category,
            description=description,
            amount=amt,
            receipt_reference=receipt_reference,
            recorded_by=user_id,
            transaction_date=tx_date or date.today()
        )
        db.session.add(expense)
        db.session.commit()
        return {'success': True, 'message': f'Expense of Rs {amt} recorded successfully.', 'expense': expense}

    @staticmethod
    def submit_feedback(student_id, meal_menu_id, rating, food_quality=5, taste=5, hygiene=5, portion=5, comments=None, is_anonymous=False):
        """Collects multidimensional food feedback from a resident"""
        if not (1 <= rating <= 5):
            return {'success': False, 'message': 'Overall rating must be between 1 and 5 stars.'}

        menu = MealMenu.query.get(meal_menu_id)
        if not menu:
            return {'success': False, 'message': 'Meal menu not found.'}

        # Check for duplicate feedback
        existing = MealFeedback.query.filter_by(student_id=student_id, meal_menu_id=meal_menu_id).first()
        if existing:
            return {'success': False, 'message': 'You have already submitted feedback for this meal.'}

        feedback = MealFeedback(
            student_id=student_id,
            meal_menu_id=meal_menu_id,
            rating=rating,
            food_quality_rating=food_quality,
            taste_rating=taste,
            hygiene_rating=hygiene,
            portion_rating=portion,
            comments=comments,
            is_anonymous=is_anonymous
        )
        db.session.add(feedback)
        db.session.commit()

        # If low rating (<= 2 stars), notify mess manager
        if rating <= 2:
            managers = User.query.filter_by(role='mess_manager', is_active=True).all()
            for mgr in managers:
                NotificationService.create_notification(
                    user_id=mgr.id,
                    title="Low Food Rating Alert",
                    message=f"A {rating}-star rating was submitted for {menu.meal_type} on {menu.meal_date.strftime('%d %b')}. Review comments: \"{comments or 'No text provided'}\".",
                    type="danger",
                    link="/mess-manager/feedback"
                )
            db.session.commit()

        return {'success': True, 'message': 'Thank you! Your food feedback has been recorded.'}

    @staticmethod
    def get_wastage_report(mess_id, target_date=None):
        """
        Comprehensive Food Wastage & Attendance Analytics Report.
        Computes prepared vs consumed portions, unconsumed meals, physical kitchen wastage,
        daily, weekly, and monthly summaries, meal-wise breakdowns, highest wasted items,
        and historical audit logs.
        Guarantees zero-division safety and handles empty records gracefully.
        """
        if target_date is None:
            target_date = date.today()

        empty_report = {
            'date': target_date,
            'target_date': target_date,
            'total_bookings': 0,
            'total_booked': 0,
            'total_attendances': 0,
            'total_present': 0,
            'total_prepared': 0,
            'total_consumed': 0,
            'total_wasted': 0,
            'wastage_percentage': 0.0,
            'unconsumed_booked_meals': 0,
            'estimated_unconsumed_meals': 0,
            'estimated_unconsumed_cost': 0.0,
            'measured_kitchen_wastage_kg': 0.0,
            'measured_kitchen_waste_kg': 0.0,
            'measured_kitchen_wastage_cost': 0.0,
            'slots': [],
            'slot_breakdown': [],
            'daily_summary': {
                'prepared': 0,
                'consumed': 0,
                'wasted': 0,
                'wastage_pct': 0.0,
                'bookings': 0,
                'unconsumed_booked': 0,
                'cost': 0.0,
                'kitchen_waste_kg': 0.0,
                'kitchen_waste_cost': 0.0
            },
            'weekly_summary': {
                'start_date': target_date,
                'end_date': target_date,
                'prepared': 0,
                'consumed': 0,
                'wasted': 0,
                'wastage_pct': 0.0,
                'bookings': 0,
                'kitchen_waste_kg': 0.0,
                'kitchen_waste_cost': 0.0
            },
            'monthly_summary': {
                'month_name': target_date.strftime('%B %Y'),
                'prepared': 0,
                'consumed': 0,
                'wasted': 0,
                'wastage_pct': 0.0,
                'bookings': 0,
                'kitchen_waste_kg': 0.0,
                'kitchen_waste_cost': 0.0
            },
            'highest_wasted_items': [],
            'historical_records': [],
            'chart_labels': [],
            'chart_prepared': [],
            'chart_consumed': [],
            'chart_wasted': [],
            'meal_slot_wastage': {'Breakfast': 0, 'Lunch': 0, 'Snacks': 0, 'Dinner': 0}
        }

        if not mess_id:
            return empty_report

        # 1. Date Horizons
        # Weekly: Monday to Sunday of the target week
        monday = target_date - timedelta(days=target_date.weekday())
        sunday = monday + timedelta(days=6)

        # Monthly: 1st of month to end of month
        month_start = date(target_date.year, target_date.month, 1)
        next_month = (month_start.replace(day=28) + timedelta(days=4))
        month_end = next_month - timedelta(days=next_month.day)

        # 2. Daily calculations for target_date
        daily_menus = MealMenu.query.filter_by(
            mess_id=mess_id,
            meal_date=target_date
        ).all()

        daily_prepared = 0
        daily_booked = 0
        daily_consumed = 0
        slot_order = {'Breakfast': 1, 'Lunch': 2, 'Snacks': 3, 'Dinner': 4}
        sorted_daily_menus = sorted(daily_menus, key=lambda m: slot_order.get(m.meal_type, 5))

        slot_report = []
        meal_slot_wastage = {'Breakfast': 0, 'Lunch': 0, 'Snacks': 0, 'Dinner': 0}

        for m in sorted_daily_menus:
            prep = m.capacity or 0
            bk = m.active_booking_count or 0
            att = m.attendance_count or 0
            uncons = max(0, bk - att)
            wasted_portions = max(0, prep - att)

            daily_prepared += prep
            daily_booked += bk
            daily_consumed += att

            if m.meal_type in meal_slot_wastage:
                meal_slot_wastage[m.meal_type] += uncons

            turnout = round(att / bk * 100, 1) if bk > 0 else (100.0 if att > 0 else 0.0)
            waste_pct = round(uncons / bk * 100, 1) if bk > 0 else 0.0

            slot_item = {
                'slot': m.meal_type,
                'meal_type': m.meal_type,
                'menu_title': m.title,
                'title': m.title,
                'menu_id': m.id,
                'prepared': prep,
                'capacity': prep,
                'bookings': bk,
                'booked': bk,
                'attendances': att,
                'present': att,
                'unconsumed': uncons,
                'estimated_unconsumed': uncons,
                'wasted_portions': wasted_portions,
                'turnout': turnout,
                'turnout_pct': turnout,
                'wastage_pct': waste_pct,
                'timing': m.meal_timing or '7:30 AM - 9:30 AM',
                'food_category': m.food_category
            }
            slot_report.append(slot_item)

        daily_wasted = max(0, daily_booked - daily_consumed)
        daily_waste_pct = round(daily_wasted / daily_booked * 100, 1) if daily_booked > 0 else 0.0
        est_daily_cost = float(Decimal(str(daily_wasted)) * Decimal('50.00'))

        # 3. Weekly calculations (Monday - Sunday)
        weekly_menus = MealMenu.query.filter(
            MealMenu.mess_id == mess_id,
            MealMenu.meal_date >= monday,
            MealMenu.meal_date <= sunday
        ).all()

        weekly_prepared = sum(m.capacity or 0 for m in weekly_menus)
        weekly_booked = sum(m.active_booking_count or 0 for m in weekly_menus)
        weekly_consumed = sum(m.attendance_count or 0 for m in weekly_menus)
        weekly_wasted = max(0, weekly_booked - weekly_consumed)
        weekly_waste_pct = round(weekly_wasted / weekly_booked * 100, 1) if weekly_booked > 0 else 0.0

        # Weekly physical wastage from inventory transactions
        weekly_waste_txs = InventoryTransaction.query.join(MessInventory).filter(
            MessInventory.mess_id == mess_id,
            InventoryTransaction.transaction_type == 'Wastage',
            InventoryTransaction.transaction_date >= monday,
            InventoryTransaction.transaction_date <= sunday
        ).all()
        weekly_kitchen_waste_kg = float(sum(tx.quantity for tx in weekly_waste_txs))
        weekly_kitchen_waste_cost = float(sum(tx.total_price for tx in weekly_waste_txs))

        # 4. Monthly calculations
        monthly_menus = MealMenu.query.filter(
            MealMenu.mess_id == mess_id,
            MealMenu.meal_date >= month_start,
            MealMenu.meal_date <= month_end
        ).all()

        monthly_prepared = sum(m.capacity or 0 for m in monthly_menus)
        monthly_booked = sum(m.active_booking_count or 0 for m in monthly_menus)
        monthly_consumed = sum(m.attendance_count or 0 for m in monthly_menus)
        monthly_wasted = max(0, monthly_booked - monthly_consumed)
        monthly_waste_pct = round(monthly_wasted / monthly_booked * 100, 1) if monthly_booked > 0 else 0.0

        monthly_waste_txs = InventoryTransaction.query.join(MessInventory).filter(
            MessInventory.mess_id == mess_id,
            InventoryTransaction.transaction_type == 'Wastage',
            InventoryTransaction.transaction_date >= month_start,
            InventoryTransaction.transaction_date <= month_end
        ).all()
        monthly_kitchen_waste_kg = float(sum(tx.quantity for tx in monthly_waste_txs))
        monthly_kitchen_waste_cost = float(sum(tx.total_price for tx in monthly_waste_txs))

        # 5. Daily physical wastage from inventory
        daily_waste_txs = [tx for tx in weekly_waste_txs if tx.transaction_date == target_date]
        if not daily_waste_txs:
            daily_waste_txs = InventoryTransaction.query.join(MessInventory).filter(
                MessInventory.mess_id == mess_id,
                InventoryTransaction.transaction_type == 'Wastage',
                InventoryTransaction.transaction_date == target_date
            ).all()

        daily_kitchen_waste_kg = float(sum(tx.quantity for tx in daily_waste_txs))
        daily_kitchen_waste_cost = float(sum(tx.total_price for tx in daily_waste_txs))

        # 6. Food items with the highest wastage
        all_waste_txs = InventoryTransaction.query.join(MessInventory).filter(
            MessInventory.mess_id == mess_id,
            InventoryTransaction.transaction_type == 'Wastage'
        ).all()

        item_waste_map = {}
        for tx in all_waste_txs:
            item_name = tx.inventory_item.item_name if tx.inventory_item else 'General Food Provision'
            unit = tx.inventory_item.unit if tx.inventory_item else 'kg'
            category = tx.inventory_item.category if tx.inventory_item else 'Other'
            if item_name not in item_waste_map:
                item_waste_map[item_name] = {
                    'item_name': item_name,
                    'category': category,
                    'unit': unit,
                    'total_qty': Decimal('0.00'),
                    'total_cost': Decimal('0.00'),
                    'incident_count': 0
                }
            item_waste_map[item_name]['total_qty'] += tx.quantity
            item_waste_map[item_name]['total_cost'] += tx.total_price
            item_waste_map[item_name]['incident_count'] += 1

        highest_wasted_items = sorted(
            item_waste_map.values(),
            key=lambda x: (x['total_cost'], x['total_qty']),
            reverse=True
        )[:5]

        for item in highest_wasted_items:
            item['total_qty_float'] = float(item['total_qty'])
            item['total_cost_float'] = float(item['total_cost'])

        # 7. Historical wastage records (recent 25 logs)
        recent_waste_txs = InventoryTransaction.query.join(MessInventory).filter(
            MessInventory.mess_id == mess_id,
            InventoryTransaction.transaction_type == 'Wastage'
        ).order_by(InventoryTransaction.transaction_date.desc(), InventoryTransaction.id.desc()).limit(25).all()

        historical_records = []
        for tx in recent_waste_txs:
            historical_records.append({
                'id': tx.id,
                'date': tx.transaction_date,
                'item_name': tx.inventory_item.item_name if tx.inventory_item else 'General Food Provision',
                'category': tx.inventory_item.category if tx.inventory_item else 'Pantry',
                'quantity': float(tx.quantity),
                'unit': tx.inventory_item.unit if tx.inventory_item else 'kg',
                'unit_price': float(tx.unit_price),
                'total_price': float(tx.total_price),
                'remarks': tx.remarks or 'Kitchen preparation residue / spoilage',
                'recorded_by': tx.staff.username if tx.staff else 'Kitchen Staff'
            })

        # 8. Chart analytics: 7-day trend
        chart_labels = []
        chart_prepared = []
        chart_consumed = []
        chart_wasted = []

        for i in range(6, -1, -1):
            d = target_date - timedelta(days=i)
            chart_labels.append(d.strftime('%a, %d %b'))

            d_menus = MealMenu.query.filter_by(mess_id=mess_id, meal_date=d).all()
            d_prep = sum(m.capacity or 0 for m in d_menus)
            d_att = sum(m.attendance_count or 0 for m in d_menus)
            d_bk = sum(m.active_booking_count or 0 for m in d_menus)
            d_wst = max(0, d_bk - d_att)

            chart_prepared.append(d_prep if d_prep > 0 else d_bk)
            chart_consumed.append(d_att)
            chart_wasted.append(d_wst)

        return {
            'date': target_date,
            'target_date': target_date,
            'total_bookings': daily_booked,
            'total_booked': daily_booked,
            'total_attendances': daily_consumed,
            'total_present': daily_consumed,
            'total_prepared': daily_prepared,
            'total_consumed': daily_consumed,
            'total_wasted': daily_wasted,
            'wastage_percentage': daily_waste_pct,
            'unconsumed_booked_meals': daily_wasted,
            'estimated_unconsumed_meals': daily_wasted,
            'estimated_unconsumed_cost': est_daily_cost,
            'measured_kitchen_wastage_kg': daily_kitchen_waste_kg,
            'measured_kitchen_waste_kg': daily_kitchen_waste_kg,
            'measured_kitchen_wastage_cost': daily_kitchen_waste_cost,
            'slots': slot_report,
            'slot_breakdown': slot_report,
            'daily_summary': {
                'prepared': daily_prepared,
                'consumed': daily_consumed,
                'wasted': daily_wasted,
                'wastage_pct': daily_waste_pct,
                'bookings': daily_booked,
                'unconsumed_booked': daily_wasted,
                'cost': est_daily_cost,
                'kitchen_waste_kg': daily_kitchen_waste_kg,
                'kitchen_waste_cost': daily_kitchen_waste_cost
            },
            'weekly_summary': {
                'start_date': monday,
                'end_date': sunday,
                'prepared': weekly_prepared,
                'consumed': weekly_consumed,
                'wasted': weekly_wasted,
                'wastage_pct': weekly_waste_pct,
                'bookings': weekly_booked,
                'kitchen_waste_kg': weekly_kitchen_waste_kg,
                'kitchen_waste_cost': weekly_kitchen_waste_cost
            },
            'monthly_summary': {
                'month_name': target_date.strftime('%B %Y'),
                'prepared': monthly_prepared,
                'consumed': monthly_consumed,
                'wasted': monthly_wasted,
                'wastage_pct': monthly_waste_pct,
                'bookings': monthly_booked,
                'kitchen_waste_kg': monthly_kitchen_waste_kg,
                'kitchen_waste_cost': monthly_kitchen_waste_cost
            },
            'highest_wasted_items': highest_wasted_items,
            'historical_records': historical_records,
            'chart_labels': chart_labels,
            'chart_prepared': chart_prepared,
            'chart_consumed': chart_consumed,
            'chart_wasted': chart_wasted,
            'meal_slot_wastage': meal_slot_wastage,
            'wastage_transactions': daily_waste_txs
        }

    @staticmethod
    def generate_monthly_bills(mess_id, billing_month, base_monthly_fee=Decimal('3500.00'), per_day_rebate=Decimal('100.00'), due_date=None):
        """
        Generates and reconciles monthly mess bills for all resident students.
        Integrates with the leave system to compute rebate discounts for approved leaves.
        """
        if due_date is None:
            # 10th of next month
            year, month = map(int, billing_month.split('-'))
            next_month = month + 1 if month < 12 else 1
            next_year = year if month < 12 else year + 1
            due_date = date(next_year, next_month, 10)

        # Query active resident students (from active allocations or active student records)
        allocations = BedAllocation.query.filter_by(status='active').all()
        student_ids = [a.student_id for a in allocations if a.student_id]
        if student_ids:
            students = Student.query.filter(Student.id.in_(student_ids), Student.status == 'active').all()
        else:
            students = Student.query.filter_by(status='active').all()

        generated_count = 0

        for student in students:
            if not student:
                continue

            # Calculate approved leave days during this billing month
            year, month = map(int, billing_month.split('-'))
            first_day = date(year, month, 1)
            last_day = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)

            approved_leaves = LeaveApplication.query.filter(
                LeaveApplication.student_id == student.id,
                LeaveApplication.status == 'Approved',
                LeaveApplication.from_date <= last_day,
                LeaveApplication.to_date >= first_day
            ).all()

            total_leave_days = 0
            for l in approved_leaves:
                start = max(l.from_date, first_day)
                end = min(l.to_date, last_day)
                days = (end - start).days + 1
                if days > 0:
                    total_leave_days += days

            # Leave rebate policy: Rebates applicable for continuous leaves > 2 days
            rebate = Decimal('0.00')
            if total_leave_days >= 3:
                rebate = Decimal(str(total_leave_days)) * per_day_rebate

            total_bill = max(Decimal('0.00'), base_monthly_fee - rebate)

            # Count consumed meals
            consumed_meals = MealAttendance.query.join(MealMenu).filter(
                MealAttendance.student_id == student.id,
                MealMenu.mess_id == mess_id,
                MealMenu.meal_date >= first_day,
                MealMenu.meal_date <= last_day,
                MealAttendance.attendance_status.in_(['Present', 'Walk-in'])
            ).count()

            booked_meals = MealBooking.query.join(MealMenu).filter(
                MealBooking.student_id == student.id,
                MealMenu.mess_id == mess_id,
                MealMenu.meal_date >= first_day,
                MealMenu.meal_date <= last_day,
                MealBooking.booking_status.in_(['Booked', 'Consumed'])
            ).count()

            existing_bill = MessBillingRecord.query.filter_by(
                student_id=student.id,
                billing_month=billing_month
            ).first()

            if not existing_bill:
                bill = MessBillingRecord(
                    student_id=student.id,
                    mess_id=mess_id,
                    billing_month=billing_month,
                    total_meals_booked=booked_meals,
                    total_meals_consumed=consumed_meals,
                    base_fee=base_monthly_fee,
                    rebate_amount=rebate,
                    total_amount=total_bill,
                    status='pending',
                    due_date=due_date
                )
                db.session.add(bill)
                generated_count += 1
            elif existing_bill.status != 'paid':
                existing_bill.total_meals_booked = booked_meals
                existing_bill.total_meals_consumed = consumed_meals
                existing_bill.base_fee = base_monthly_fee
                existing_bill.rebate_amount = rebate
                existing_bill.total_amount = total_bill
                existing_bill.due_date = due_date
                existing_bill.updated_at = datetime.utcnow()

        db.session.commit()
        return {'success': True, 'generated_count': generated_count, 'billing_month': billing_month}

    @staticmethod
    def generate_monthly_billing(month, year, mess_id=None):
        """Wrapper helper to generate monthly billing by month and year"""
        if mess_id is None:
            default_mess = MessService.get_or_create_default_mess()
            mess_id = default_mess.id
        billing_month = f"{year}-{month:02d}"
        res = MessService.generate_monthly_bills(mess_id, billing_month)
        return {
            'success': res.get('success', True),
            'message': f"Monthly dining dues generated for {res.get('generated_count', 0)} students for {billing_month}.",
            'generated_count': res.get('generated_count', 0)
        }
