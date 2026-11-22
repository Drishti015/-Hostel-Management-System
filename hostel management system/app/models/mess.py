from datetime import datetime, date
from decimal import Decimal
from app.models import db

class MessProfile(db.Model):
    """
    MessProfile Model - Physical or organizational dining hall attached to a hostel or campus.
    Supports multi-hostel messes, status toggles, and attendance policy configuration.
    """
    __tablename__ = 'mess_profiles'

    id = db.Column(db.Integer, primary_key=True)
    hostel_id = db.Column(db.Integer, db.ForeignKey('hostels.id', ondelete='SET NULL'), nullable=True, index=True)
    mess_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    contact_number = db.Column(db.String(20), nullable=True)
    operating_status = db.Column(
        db.Enum('Active', 'Inactive', 'Maintenance', name='mess_status_enum'),
        default='Active',
        nullable=False,
        index=True
    )
    # Configurable attendance verification policy: booking_required vs walk_in
    meal_policy = db.Column(
        db.Enum('booking_required', 'walk_in', name='mess_meal_policy_enum'),
        default='booking_required',
        nullable=False
    )
    daily_capacity = db.Column(db.Integer, default=300, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    hostel = db.relationship('Hostel', backref=db.backref('messes', lazy='dynamic'))
    menus = db.relationship('MealMenu', backref='mess', lazy='dynamic', cascade='all, delete-orphan')
    inventories = db.relationship('MessInventory', backref='mess', lazy='dynamic', cascade='all, delete-orphan')
    expenses = db.relationship('MessExpense', backref='mess', lazy='dynamic', cascade='all, delete-orphan')
    staff_members = db.relationship('MessStaffProfile', backref='assigned_mess', lazy='dynamic', cascade='all, delete-orphan')
    notices = db.relationship('MessNotice', backref='mess', lazy='dynamic', cascade='all, delete-orphan')
    billing_records = db.relationship('MessBillingRecord', backref='mess', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<MessProfile {self.mess_name} [{self.operating_status}]>"


class Supplier(db.Model):
    """
    Supplier Model - Registered wholesale food, ingredient, and grocery vendors.
    """
    __tablename__ = 'suppliers'

    id = db.Column(db.Integer, primary_key=True)
    supplier_name = db.Column(db.String(150), nullable=False, index=True)
    contact_person = db.Column(db.String(100), nullable=True)
    phone_number = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    inventories = db.relationship('MessInventory', backref='preferred_supplier', lazy='dynamic')
    transactions = db.relationship('InventoryTransaction', backref='supplier', lazy='dynamic')

    def __repr__(self):
        return f"<Supplier {self.supplier_name}>"


class MealMenu(db.Model):
    """
    MealMenu Model - Daily schedule for breakfast, lunch, snacks, and dinner.
    Stores food categorization, images, booking deadlines, and capacity limits.
    """
    __tablename__ = 'meal_menus'

    id = db.Column(db.Integer, primary_key=True)
    mess_id = db.Column(db.Integer, db.ForeignKey('mess_profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    meal_date = db.Column(db.Date, nullable=False, index=True)
    meal_type = db.Column(
        db.Enum('Breakfast', 'Lunch', 'Snacks', 'Dinner', name='meal_type_enum'),
        nullable=False,
        index=True
    )
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    food_image = db.Column(db.String(255), nullable=True)
    food_category = db.Column(
        db.Enum('Vegetarian', 'Non-Vegetarian', 'Vegan', 'Other', name='food_category_enum'),
        default='Vegetarian',
        nullable=False
    )
    meal_timing = db.Column(db.String(100), default='8:00 AM - 10:00 AM', nullable=False)
    booking_deadline = db.Column(db.DateTime, nullable=False)
    capacity = db.Column(db.Integer, default=250, nullable=False)
    is_published = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    bookings = db.relationship('MealBooking', backref='meal_menu', lazy='dynamic', cascade='all, delete-orphan')
    attendances = db.relationship('MealAttendance', backref='meal_menu', lazy='dynamic', cascade='all, delete-orphan')
    feedbacks = db.relationship('MealFeedback', backref='meal_menu', lazy='dynamic', cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by], backref='created_menus')

    __table_args__ = (
        db.UniqueConstraint('mess_id', 'meal_date', 'meal_type', name='uq_mess_meal_date_type'),
    )

    @property
    def is_booking_open(self):
        """Checks if meal is currently published and before the booking cutoff deadline"""
        return self.is_published and datetime.utcnow() <= self.booking_deadline

    @property
    def active_booking_count(self):
        """Returns the number of active bookings (excluding cancelled ones)"""
        return self.bookings.filter(MealBooking.booking_status.in_(['Booked', 'Consumed'])).count()

    @property
    def is_capacity_full(self):
        """Checks if active bookings reached the configured capacity"""
        return self.active_booking_count >= self.capacity

    @property
    def attendance_count(self):
        """Number of actual checked-in students"""
        return self.attendances.filter_by(attendance_status='Present').count()

    @property
    def average_rating(self):
        """Calculates average rating for this meal"""
        feedbacks = self.feedbacks.all()
        if not feedbacks:
            return 0.0
        return round(sum(f.rating for f in feedbacks) / len(feedbacks), 1)

    def __repr__(self):
        return f"<MealMenu {self.meal_date} {self.meal_type}: {self.title}>"


class MealBooking(db.Model):
    """
    MealBooking Model - Pre-ordered meal reservation made by an authenticated resident student.
    Enforces capacity limits and prevents duplicate bookings per meal slot.
    """
    __tablename__ = 'meal_bookings'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    meal_menu_id = db.Column(db.Integer, db.ForeignKey('meal_menus.id', ondelete='CASCADE'), nullable=False, index=True)
    booking_status = db.Column(
        db.Enum('Booked', 'Cancelled', 'Consumed', 'Missed', name='meal_booking_status_enum'),
        default='Booked',
        nullable=False,
        index=True
    )
    booking_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    cancellation_date = db.Column(db.DateTime, nullable=True)
    remarks = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    student = db.relationship('Student', backref=db.backref('meal_bookings', lazy='dynamic', cascade='all, delete-orphan'))
    attendance = db.relationship('MealAttendance', backref='linked_booking', uselist=False)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'meal_menu_id', name='uq_student_meal_booking'),
    )

    def __repr__(self):
        return f"<MealBooking #{self.id} Student:{self.student_id} Status:{self.booking_status}>"


class MealAttendance(db.Model):
    """
    MealAttendance Model - Verifiable dining hall entry log recorded at meal service.
    Ensures zero duplicate meals and supports both QR code scans and manual fallback.
    """
    __tablename__ = 'meal_attendances'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    meal_menu_id = db.Column(db.Integer, db.ForeignKey('meal_menus.id', ondelete='CASCADE'), nullable=False, index=True)
    meal_booking_id = db.Column(db.Integer, db.ForeignKey('meal_bookings.id', ondelete='SET NULL'), nullable=True)
    attendance_status = db.Column(
        db.Enum('Present', 'Walk-in', 'Duplicate_Attempt', name='meal_attendance_status_enum'),
        default='Present',
        nullable=False,
        index=True
    )
    check_in_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    verification_method = db.Column(
        db.Enum('QR_Scan', 'Manual_ID', name='meal_verification_method_enum'),
        default='QR_Scan',
        nullable=False
    )
    remarks = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    student = db.relationship('Student', backref=db.backref('meal_attendances', lazy='dynamic', cascade='all, delete-orphan'))
    staff = db.relationship('User', foreign_keys=[recorded_by], backref='recorded_meal_attendances')

    __table_args__ = (
        db.UniqueConstraint('student_id', 'meal_menu_id', name='uq_student_meal_attendance'),
    )

    def __repr__(self):
        return f"<MealAttendance #{self.id} Student:{self.student_id} Menu:{self.meal_menu_id} [{self.attendance_status}]>"


class MealFeedback(db.Model):
    """
    MealFeedback Model - Student ratings and reviews for consumed meals.
    Supports granular dimensional ratings (Quality, Taste, Hygiene, Portion) and anonymity.
    """
    __tablename__ = 'meal_feedbacks'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    meal_menu_id = db.Column(db.Integer, db.ForeignKey('meal_menus.id', ondelete='CASCADE'), nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=False)  # 1 to 5 overall star rating
    food_quality_rating = db.Column(db.Integer, default=5, nullable=False)
    taste_rating = db.Column(db.Integer, default=5, nullable=False)
    hygiene_rating = db.Column(db.Integer, default=5, nullable=False)
    portion_rating = db.Column(db.Integer, default=5, nullable=False)
    comments = db.Column(db.Text, nullable=True)
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    student = db.relationship('Student', backref=db.backref('meal_feedbacks', lazy='dynamic', cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('student_id', 'meal_menu_id', name='uq_student_meal_feedback'),
    )

    def __repr__(self):
        return f"<MealFeedback #{self.id} Rating:{self.rating} by Student:{self.student_id}>"


class MessInventory(db.Model):
    """
    MessInventory Model - Kitchen pantry ingredients, raw provisions, and utilities.
    Tracks real-time stock balances, threshold minimums, and shelf-life expiration dates.
    """
    __tablename__ = 'mess_inventories'

    id = db.Column(db.Integer, primary_key=True)
    mess_id = db.Column(db.Integer, db.ForeignKey('mess_profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    item_name = db.Column(db.String(150), nullable=False, index=True)
    category = db.Column(
        db.Enum(
            'Grains & Cereals', 'Vegetables', 'Dairy', 'Spices & Oils',
            'Pulses & Legumes', 'Snacks & Beverages', 'Gas & Kitchen Supplies', 'Other',
            name='inventory_category_enum'
        ),
        default='Grains & Cereals',
        nullable=False,
        index=True
    )
    quantity = db.Column(db.Numeric(10, 2), default=Decimal('0.00'), nullable=False)
    unit = db.Column(db.String(20), default='kg', nullable=False)  # kg, liter, packets, bags
    minimum_stock_level = db.Column(db.Numeric(10, 2), default=Decimal('10.00'), nullable=False)
    purchase_price = db.Column(db.Numeric(10, 2), default=Decimal('0.00'), nullable=False)
    expiry_date = db.Column(db.Date, nullable=True, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    transactions = db.relationship('InventoryTransaction', backref='inventory_item', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def is_low_stock(self):
        """Flagged when on-hand stock falls below safety replenishment threshold"""
        return self.quantity <= self.minimum_stock_level

    @property
    def is_near_expiry(self):
        """Flagged when perishable inventory is expiring within 3 days"""
        if not self.expiry_date:
            return False
        days_left = (self.expiry_date - date.today()).days
        return 0 <= days_left <= 3

    @property
    def is_expired(self):
        """Flagged when item has passed its safe consumption date"""
        if not self.expiry_date:
            return False
        return self.expiry_date < date.today()

    def __repr__(self):
        return f"<MessInventory {self.item_name}: {self.quantity} {self.unit}>"


class InventoryTransaction(db.Model):
    """
    InventoryTransaction Model - Immutable audit trail of stock inward, usage, and wastage.
    """
    __tablename__ = 'inventory_transactions'

    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('mess_inventories.id', ondelete='CASCADE'), nullable=False, index=True)
    transaction_type = db.Column(
        db.Enum('Purchase', 'Consumption', 'Adjustment', 'Wastage', name='inventory_tx_type_enum'),
        nullable=False,
        index=True
    )
    quantity = db.Column(db.Numeric(10, 2), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), default=Decimal('0.00'), nullable=False)
    total_price = db.Column(db.Numeric(10, 2), default=Decimal('0.00'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id', ondelete='SET NULL'), nullable=True)
    reference = db.Column(db.String(100), nullable=True)  # Invoice / Delivery memo number
    remarks = db.Column(db.String(255), nullable=True)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    transaction_date = db.Column(db.Date, default=datetime.utcnow().date, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    staff = db.relationship('User', foreign_keys=[recorded_by], backref='recorded_inventory_transactions')

    def __repr__(self):
        return f"<InventoryTransaction #{self.id} {self.transaction_type}: {self.quantity}>"


class MessExpense(db.Model):
    """
    MessExpense Model - Operational expenditures (groceries, dairy, fuel, wages, upkeep).
    Enforces precise numeric precision without floating-point inaccuracies.
    """
    __tablename__ = 'mess_expenses'

    id = db.Column(db.Integer, primary_key=True)
    mess_id = db.Column(db.Integer, db.ForeignKey('mess_profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    expense_category = db.Column(
        db.Enum(
            'Vegetables & Groceries', 'Dairy & Milk', 'Gas & Fuel',
            'Kitchen Maintenance', 'Cleaning & Hygiene', 'Staff Salary / Wages',
            'Utensils & Equipment', 'Other',
            name='mess_expense_category_enum'
        ),
        nullable=False,
        index=True
    )
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    transaction_date = db.Column(db.Date, default=datetime.utcnow().date, nullable=False, index=True)
    receipt_reference = db.Column(db.String(100), nullable=True)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    author = db.relationship('User', foreign_keys=[recorded_by], backref='recorded_mess_expenses')

    def __repr__(self):
        return f"<MessExpense #{self.id} [{self.expense_category}]: Rs {self.amount}>"


class MessStaffProfile(db.Model):
    """
    MessStaffProfile Model - Chef, pantry manager, and dining hall counter attendant.
    """
    __tablename__ = 'mess_staff_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    mess_id = db.Column(db.Integer, db.ForeignKey('mess_profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    staff_name = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), nullable=True)
    role_designation = db.Column(db.String(100), default='Counter Attendant', nullable=False)
    employment_status = db.Column(
        db.Enum('Active', 'On Leave', 'Terminated', name='staff_employment_status_enum'),
        default='Active',
        nullable=False
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # User account relationship
    user_account = db.relationship('User', backref=db.backref('mess_staff_profile', uselist=False, cascade='all, delete-orphan'))

    def __repr__(self):
        return f"<MessStaffProfile {self.staff_name} [{self.role_designation}]>"


class MessNotice(db.Model):
    """
    MessNotice Model - Official announcements (curfew shifts, special festive feast, maintenance).
    """
    __tablename__ = 'mess_notices'

    id = db.Column(db.Integer, primary_key=True)
    mess_id = db.Column(db.Integer, db.ForeignKey('mess_profiles.id', ondelete='CASCADE'), nullable=True, index=True)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notice_type = db.Column(
        db.Enum('General', 'Timing_Change', 'Special_Menu', 'Maintenance', 'Holiday', name='mess_notice_type_enum'),
        default='General',
        nullable=False
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    expires_at = db.Column(db.Date, nullable=True)
    posted_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    author = db.relationship('User', foreign_keys=[posted_by], backref='posted_mess_notices')

    def __repr__(self):
        return f"<MessNotice #{self.id} {self.title}>"


class MessBillingRecord(db.Model):
    """
    MessBillingRecord Model - Monthly student dining invoices integrated with Fee module.
    Maintains billing periods, meal count reconciliations, rebates, and settlement tracking.
    """
    __tablename__ = 'mess_billing_records'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False, index=True)
    mess_id = db.Column(db.Integer, db.ForeignKey('mess_profiles.id', ondelete='CASCADE'), nullable=False, index=True)
    billing_month = db.Column(db.String(7), nullable=False, index=True)  # Format: YYYY-MM
    total_meals_booked = db.Column(db.Integer, default=0, nullable=False)
    total_meals_consumed = db.Column(db.Integer, default=0, nullable=False)
    base_fee = db.Column(db.Numeric(10, 2), default=Decimal('0.00'), nullable=False)
    extra_charges = db.Column(db.Numeric(10, 2), default=Decimal('0.00'), nullable=False)
    rebate_amount = db.Column(db.Numeric(10, 2), default=Decimal('0.00'), nullable=False)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(
        db.Enum('pending', 'paid', 'overdue', name='mess_bill_status_enum'),
        default='pending',
        nullable=False,
        index=True
    )
    due_date = db.Column(db.Date, nullable=False)
    paid_date = db.Column(db.Date, nullable=True)
    payment_reference = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    student = db.relationship('Student', backref=db.backref('mess_bills', lazy='dynamic', cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('student_id', 'billing_month', name='uq_student_mess_billing_month'),
    )

    def __repr__(self):
        return f"<MessBillingRecord Student:{self.student_id} Month:{self.billing_month} Amount:Rs {self.total_amount}>"
