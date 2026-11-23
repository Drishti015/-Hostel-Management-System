-- =====================================================================
-- HOSTELEASE HMS - SUPABASE POSTGRESQL PRODUCTION SCHEMA
-- Normalized Relational Schema for PostgreSQL 14+ / Supabase
-- Covers all 30 Normalized Entities and 33 Named ENUM Types
-- 100% Non-Destructive & Idempotent (IF NOT EXISTS syntax)
-- =====================================================================

-- Step 1: Create Custom Enum Types (Idempotent)
DO $$ BEGIN
    CREATE TYPE hostel_type_enum AS ENUM ('boys', 'girls', 'co-ed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE user_roles AS ENUM ('admin', 'warden', 'student', 'security', 'parent', 'mess_manager', 'mess_staff');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE mess_status_enum AS ENUM ('Active', 'Inactive', 'Maintenance');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE mess_meal_policy_enum AS ENUM ('booking_required', 'walk_in');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE notice_category_enum AS ENUM ('announcement', 'event', 'urgent', 'maintenance');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE notice_audience_enum AS ENUM ('all', 'boys', 'girls', 'wardens');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE room_type_enum AS ENUM ('single', 'double', 'triple', 'four');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE room_status_enum AS ENUM ('active', 'maintenance');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE student_gender_enum AS ENUM ('male', 'female', 'other');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE student_status_enum AS ENUM ('active', 'suspended', 'vacated');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE attendance_status_enum AS ENUM ('present', 'absent', 'leave');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE bed_status_enum AS ENUM ('available', 'occupied', 'maintenance');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE complaint_cat_enum AS ENUM ('electrical', 'plumbing', 'cleanliness', 'internet', 'mess', 'other');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE complaint_prio_enum AS ENUM ('low', 'medium', 'high', 'emergency');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE complaint_status_enum AS ENUM ('pending', 'in_progress', 'resolved');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE payment_method_enum AS ENUM ('UPI', 'Cash', 'Net Banking', 'Cheque/DD');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE fee_status_enum AS ENUM ('paid', 'pending', 'overdue');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE leave_status_enum AS ENUM ('Pending', 'Approved', 'Rejected', 'Cancelled');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE meal_type_enum AS ENUM ('Breakfast', 'Lunch', 'Snacks', 'Dinner');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE food_category_enum AS ENUM ('Vegetarian', 'Non-Vegetarian', 'Vegan', 'Other');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE mess_bill_status_enum AS ENUM ('pending', 'paid', 'overdue');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE mess_expense_category_enum AS ENUM ('Vegetables & Groceries', 'Dairy & Milk', 'Gas & Fuel', 'Kitchen Maintenance', 'Cleaning & Hygiene', 'Staff Salary / Wages', 'Utensils & Equipment', 'Other');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE inventory_category_enum AS ENUM ('Grains & Cereals', 'Vegetables', 'Dairy', 'Spices & Oils', 'Pulses & Legumes', 'Snacks & Beverages', 'Gas & Kitchen Supplies', 'Other');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE mess_notice_type_enum AS ENUM ('General', 'Timing_Change', 'Special_Menu', 'Maintenance', 'Holiday');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE staff_employment_status_enum AS ENUM ('Active', 'On Leave', 'Terminated');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE allocation_status_enum AS ENUM ('active', 'vacated', 'transferred');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE outpass_status_enum AS ENUM ('Active', 'Used', 'Expired', 'Revoked', 'Completed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE inventory_tx_type_enum AS ENUM ('Purchase', 'Consumption', 'Adjustment', 'Wastage');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE meal_booking_status_enum AS ENUM ('Booked', 'Cancelled', 'Consumed', 'Missed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE gate_event_type_enum AS ENUM ('EXIT', 'ENTRY');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE gate_verification_enum AS ENUM ('Success', 'Failed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE meal_attendance_status_enum AS ENUM ('Present', 'Walk-in', 'Duplicate_Attempt');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE meal_verification_method_enum AS ENUM ('QR_Scan', 'Manual_ID');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Step 2: Create Tables in Topological Order (IF NOT EXISTS)
CREATE TABLE IF NOT EXISTS hostels (
	id SERIAL NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	hostel_type hostel_type_enum NOT NULL, 
	total_floors INTEGER NOT NULL, 
	total_rooms INTEGER NOT NULL, 
	description VARCHAR(255), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS suppliers (
	id SERIAL NOT NULL, 
	supplier_name VARCHAR(150) NOT NULL, 
	contact_person VARCHAR(100), 
	phone_number VARCHAR(20), 
	email VARCHAR(120), 
	address TEXT, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS users (
	id SERIAL NOT NULL, 
	username VARCHAR(50) NOT NULL, 
	email VARCHAR(120) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	role user_roles NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS mess_profiles (
	id SERIAL NOT NULL, 
	hostel_id INTEGER, 
	mess_name VARCHAR(100) NOT NULL, 
	description TEXT, 
	contact_number VARCHAR(20), 
	operating_status mess_status_enum NOT NULL, 
	meal_policy mess_meal_policy_enum NOT NULL, 
	daily_capacity INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(hostel_id) REFERENCES hostels (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS notices (
	id SERIAL NOT NULL, 
	posted_by_user_id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	content TEXT NOT NULL, 
	category notice_category_enum NOT NULL, 
	target_audience notice_audience_enum NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(posted_by_user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	title VARCHAR(150) NOT NULL, 
	message TEXT NOT NULL, 
	type VARCHAR(20) NOT NULL, 
	is_read BOOLEAN NOT NULL, 
	link VARCHAR(255), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rooms (
	id SERIAL NOT NULL, 
	hostel_id INTEGER NOT NULL, 
	room_number VARCHAR(20) NOT NULL, 
	floor INTEGER NOT NULL, 
	room_type room_type_enum NOT NULL, 
	capacity INTEGER NOT NULL, 
	monthly_fee NUMERIC(10, 2) NOT NULL, 
	status room_status_enum NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_hostel_room UNIQUE (hostel_id, room_number), 
	FOREIGN KEY(hostel_id) REFERENCES hostels (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS students (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	enrollment_no VARCHAR(30) NOT NULL, 
	roll_no VARCHAR(30), 
	full_name VARCHAR(100) NOT NULL, 
	phone VARCHAR(15) NOT NULL, 
	gender student_gender_enum NOT NULL, 
	branch VARCHAR(50) NOT NULL, 
	year INTEGER NOT NULL, 
	semester INTEGER NOT NULL, 
	guardian_name VARCHAR(100) NOT NULL, 
	guardian_phone VARCHAR(15) NOT NULL, 
	emergency_phone VARCHAR(15), 
	address TEXT NOT NULL, 
	blood_group VARCHAR(10), 
	status student_status_enum NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS wardens (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	employee_id VARCHAR(30) NOT NULL, 
	full_name VARCHAR(100) NOT NULL, 
	phone VARCHAR(15) NOT NULL, 
	designation VARCHAR(50) NOT NULL, 
	assigned_hostel_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	UNIQUE (employee_id), 
	FOREIGN KEY(assigned_hostel_id) REFERENCES hostels (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS attendance (
	id SERIAL NOT NULL, 
	student_id INTEGER NOT NULL, 
	hostel_id INTEGER NOT NULL, 
	date DATE NOT NULL, 
	status attendance_status_enum NOT NULL, 
	marked_by_warden_id INTEGER, 
	remarks VARCHAR(200), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_student_daily_attendance UNIQUE (student_id, date), 
	FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE, 
	FOREIGN KEY(hostel_id) REFERENCES hostels (id) ON DELETE CASCADE, 
	FOREIGN KEY(marked_by_warden_id) REFERENCES wardens (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS beds (
	id SERIAL NOT NULL, 
	room_id INTEGER NOT NULL, 
	bed_number VARCHAR(10) NOT NULL, 
	status bed_status_enum NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_room_bed UNIQUE (room_id, bed_number), 
	FOREIGN KEY(room_id) REFERENCES rooms (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS complaints (
	id SERIAL NOT NULL, 
	student_id INTEGER NOT NULL, 
	room_id INTEGER, 
	title VARCHAR(150) NOT NULL, 
	category complaint_cat_enum NOT NULL, 
	priority complaint_prio_enum NOT NULL, 
	description TEXT NOT NULL, 
	status complaint_status_enum NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE, 
	FOREIGN KEY(room_id) REFERENCES rooms (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS fee_records (
	id SERIAL NOT NULL, 
	student_id INTEGER NOT NULL, 
	receipt_no VARCHAR(50) NOT NULL, 
	amount NUMERIC(10, 2) NOT NULL, 
	payment_date DATE NOT NULL, 
	payment_method payment_method_enum NOT NULL, 
	transaction_id VARCHAR(100), 
	fee_type VARCHAR(50) NOT NULL, 
	status fee_status_enum NOT NULL, 
	remarks VARCHAR(255), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS leave_applications (
	id SERIAL NOT NULL, 
	student_id INTEGER NOT NULL, 
	hostel_id INTEGER, 
	leave_type VARCHAR(50) NOT NULL, 
	from_date DATE NOT NULL, 
	to_date DATE NOT NULL, 
	reason TEXT NOT NULL, 
	destination VARCHAR(255) NOT NULL, 
	emergency_contact VARCHAR(20) NOT NULL, 
	supporting_document VARCHAR(255), 
	status leave_status_enum NOT NULL, 
	reviewed_by INTEGER, 
	review_comment TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	reviewed_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE, 
	FOREIGN KEY(hostel_id) REFERENCES hostels (id) ON DELETE SET NULL, 
	FOREIGN KEY(reviewed_by) REFERENCES wardens (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS meal_menus (
	id SERIAL NOT NULL, 
	mess_id INTEGER NOT NULL, 
	meal_date DATE NOT NULL, 
	meal_type meal_type_enum NOT NULL, 
	title VARCHAR(150) NOT NULL, 
	description TEXT, 
	food_image VARCHAR(255), 
	food_category food_category_enum NOT NULL, 
	meal_timing VARCHAR(100) NOT NULL, 
	booking_deadline TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	capacity INTEGER NOT NULL, 
	is_published BOOLEAN NOT NULL, 
	created_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_mess_meal_date_type UNIQUE (mess_id, meal_date, meal_type), 
	FOREIGN KEY(mess_id) REFERENCES mess_profiles (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mess_billing_records (
	id SERIAL NOT NULL, 
	student_id INTEGER NOT NULL, 
	mess_id INTEGER NOT NULL, 
	billing_month VARCHAR(7) NOT NULL, 
	total_meals_booked INTEGER NOT NULL, 
	total_meals_consumed INTEGER NOT NULL, 
	base_fee NUMERIC(10, 2) NOT NULL, 
	extra_charges NUMERIC(10, 2) NOT NULL, 
	rebate_amount NUMERIC(10, 2) NOT NULL, 
	total_amount NUMERIC(10, 2) NOT NULL, 
	status mess_bill_status_enum NOT NULL, 
	due_date DATE NOT NULL, 
	paid_date DATE, 
	payment_reference VARCHAR(100), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_student_mess_billing_month UNIQUE (student_id, billing_month), 
	FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE, 
	FOREIGN KEY(mess_id) REFERENCES mess_profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mess_expenses (
	id SERIAL NOT NULL, 
	mess_id INTEGER NOT NULL, 
	expense_category mess_expense_category_enum NOT NULL, 
	description VARCHAR(255) NOT NULL, 
	amount NUMERIC(10, 2) NOT NULL, 
	transaction_date DATE NOT NULL, 
	receipt_reference VARCHAR(100), 
	recorded_by INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(mess_id) REFERENCES mess_profiles (id) ON DELETE CASCADE, 
	FOREIGN KEY(recorded_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mess_inventories (
	id SERIAL NOT NULL, 
	mess_id INTEGER NOT NULL, 
	item_name VARCHAR(150) NOT NULL, 
	category inventory_category_enum NOT NULL, 
	quantity NUMERIC(10, 2) NOT NULL, 
	unit VARCHAR(20) NOT NULL, 
	minimum_stock_level NUMERIC(10, 2) NOT NULL, 
	purchase_price NUMERIC(10, 2) NOT NULL, 
	expiry_date DATE, 
	supplier_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(mess_id) REFERENCES mess_profiles (id) ON DELETE CASCADE, 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mess_notices (
	id SERIAL NOT NULL, 
	mess_id INTEGER, 
	title VARCHAR(150) NOT NULL, 
	message TEXT NOT NULL, 
	notice_type mess_notice_type_enum NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	expires_at DATE, 
	posted_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(mess_id) REFERENCES mess_profiles (id) ON DELETE CASCADE, 
	FOREIGN KEY(posted_by) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mess_staff_profiles (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	mess_id INTEGER NOT NULL, 
	staff_name VARCHAR(100) NOT NULL, 
	phone_number VARCHAR(20), 
	role_designation VARCHAR(100) NOT NULL, 
	employment_status staff_employment_status_enum NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(mess_id) REFERENCES mess_profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS parent_profiles (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	parent_name VARCHAR(100) NOT NULL, 
	phone_number VARCHAR(20) NOT NULL, 
	relationship_to_student VARCHAR(50) NOT NULL, 
	student_id INTEGER, 
	account_status VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS allocations (
	id SERIAL NOT NULL, 
	student_id INTEGER NOT NULL, 
	bed_id INTEGER NOT NULL, 
	room_id INTEGER NOT NULL, 
	hostel_id INTEGER NOT NULL, 
	allocated_from DATE NOT NULL, 
	allocated_to DATE, 
	status allocation_status_enum NOT NULL, 
	vacated_reason VARCHAR(255), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE, 
	FOREIGN KEY(bed_id) REFERENCES beds (id) ON DELETE CASCADE, 
	FOREIGN KEY(room_id) REFERENCES rooms (id) ON DELETE CASCADE, 
	FOREIGN KEY(hostel_id) REFERENCES hostels (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS complaint_responses (
	id SERIAL NOT NULL, 
	complaint_id INTEGER NOT NULL, 
	responder_user_id INTEGER NOT NULL, 
	response_text TEXT NOT NULL, 
	status_updated_to complaint_status_enum NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(complaint_id) REFERENCES complaints (id) ON DELETE CASCADE, 
	FOREIGN KEY(responder_user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS digital_out_passes (
	id SERIAL NOT NULL, 
	leave_application_id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	pass_token_hash VARCHAR(64) NOT NULL, 
	status outpass_status_enum NOT NULL, 
	departure_date DATE NOT NULL, 
	expected_return_date DATE NOT NULL, 
	generated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	is_outside BOOLEAN NOT NULL, 
	actual_departure_time TIMESTAMP WITHOUT TIME ZONE, 
	actual_return_time TIMESTAMP WITHOUT TIME ZONE, 
	qr_code_file VARCHAR(255), 
	revoked_reason VARCHAR(255), 
	revoked_at TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(leave_application_id) REFERENCES leave_applications (id) ON DELETE CASCADE, 
	FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS inventory_transactions (
	id SERIAL NOT NULL, 
	inventory_id INTEGER NOT NULL, 
	transaction_type inventory_tx_type_enum NOT NULL, 
	quantity NUMERIC(10, 2) NOT NULL, 
	unit_price NUMERIC(10, 2) NOT NULL, 
	total_price NUMERIC(10, 2) NOT NULL, 
	supplier_id INTEGER, 
	reference VARCHAR(100), 
	remarks VARCHAR(255), 
	recorded_by INTEGER, 
	transaction_date DATE NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(inventory_id) REFERENCES mess_inventories (id) ON DELETE CASCADE, 
	FOREIGN KEY(supplier_id) REFERENCES suppliers (id) ON DELETE SET NULL, 
	FOREIGN KEY(recorded_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS meal_bookings (
	id SERIAL NOT NULL, 
	student_id INTEGER NOT NULL, 
	meal_menu_id INTEGER NOT NULL, 
	booking_status meal_booking_status_enum NOT NULL, 
	booking_date TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	cancellation_date TIMESTAMP WITHOUT TIME ZONE, 
	remarks VARCHAR(255), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_student_meal_booking UNIQUE (student_id, meal_menu_id), 
	FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE, 
	FOREIGN KEY(meal_menu_id) REFERENCES meal_menus (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS meal_feedbacks (
	id SERIAL NOT NULL, 
	student_id INTEGER NOT NULL, 
	meal_menu_id INTEGER NOT NULL, 
	rating INTEGER NOT NULL, 
	food_quality_rating INTEGER NOT NULL, 
	taste_rating INTEGER NOT NULL, 
	hygiene_rating INTEGER NOT NULL, 
	portion_rating INTEGER NOT NULL, 
	comments TEXT, 
	is_anonymous BOOLEAN NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_student_meal_feedback UNIQUE (student_id, meal_menu_id), 
	FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE, 
	FOREIGN KEY(meal_menu_id) REFERENCES meal_menus (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS parent_inquiries (
	id SERIAL NOT NULL, 
	parent_id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	warden_id INTEGER, 
	subject VARCHAR(150) NOT NULL, 
	message TEXT NOT NULL, 
	response TEXT, 
	responded_at TIMESTAMP WITHOUT TIME ZONE, 
	status VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(parent_id) REFERENCES parent_profiles (id) ON DELETE CASCADE, 
	FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE, 
	FOREIGN KEY(warden_id) REFERENCES wardens (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS gate_transactions (
	id SERIAL NOT NULL, 
	outpass_id INTEGER NOT NULL, 
	student_id INTEGER NOT NULL, 
	security_user_id INTEGER, 
	event_type gate_event_type_enum NOT NULL, 
	scanned_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	gate_location VARCHAR(100) NOT NULL, 
	verification_status gate_verification_enum NOT NULL, 
	remarks TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(outpass_id) REFERENCES digital_out_passes (id) ON DELETE CASCADE, 
	FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE, 
	FOREIGN KEY(security_user_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS meal_attendances (
	id SERIAL NOT NULL, 
	student_id INTEGER NOT NULL, 
	meal_menu_id INTEGER NOT NULL, 
	meal_booking_id INTEGER, 
	attendance_status meal_attendance_status_enum NOT NULL, 
	check_in_time TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	recorded_by INTEGER, 
	verification_method meal_verification_method_enum NOT NULL, 
	remarks VARCHAR(255), 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_student_meal_attendance UNIQUE (student_id, meal_menu_id), 
	FOREIGN KEY(student_id) REFERENCES students (id) ON DELETE CASCADE, 
	FOREIGN KEY(meal_menu_id) REFERENCES meal_menus (id) ON DELETE CASCADE, 
	FOREIGN KEY(meal_booking_id) REFERENCES meal_bookings (id) ON DELETE SET NULL, 
	FOREIGN KEY(recorded_by) REFERENCES users (id) ON DELETE SET NULL
);

-- Step 3: Create Additional Indexes (IF NOT EXISTS)
CREATE INDEX IF NOT EXISTS ix_suppliers_supplier_name ON suppliers (supplier_name);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_role ON users (role);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username);
CREATE INDEX IF NOT EXISTS ix_mess_profiles_operating_status ON mess_profiles (operating_status);
CREATE INDEX IF NOT EXISTS ix_mess_profiles_hostel_id ON mess_profiles (hostel_id);
CREATE INDEX IF NOT EXISTS ix_notices_target_audience ON notices (target_audience);
CREATE INDEX IF NOT EXISTS ix_notifications_is_read ON notifications (is_read);
CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications (user_id);
CREATE INDEX IF NOT EXISTS ix_rooms_status ON rooms (status);
CREATE INDEX IF NOT EXISTS ix_students_branch ON students (branch);
CREATE UNIQUE INDEX IF NOT EXISTS ix_students_enrollment_no ON students (enrollment_no);
CREATE INDEX IF NOT EXISTS ix_attendance_date ON attendance (date);
CREATE INDEX IF NOT EXISTS ix_beds_status ON beds (status);
CREATE INDEX IF NOT EXISTS ix_complaints_status ON complaints (status);
CREATE INDEX IF NOT EXISTS ix_fee_records_status ON fee_records (status);
CREATE UNIQUE INDEX IF NOT EXISTS ix_fee_records_receipt_no ON fee_records (receipt_no);
CREATE INDEX IF NOT EXISTS ix_leave_applications_status ON leave_applications (status);
CREATE INDEX IF NOT EXISTS ix_leave_applications_hostel_id ON leave_applications (hostel_id);
CREATE INDEX IF NOT EXISTS ix_leave_applications_student_id ON leave_applications (student_id);
CREATE INDEX IF NOT EXISTS ix_meal_menus_meal_date ON meal_menus (meal_date);
CREATE INDEX IF NOT EXISTS ix_meal_menus_is_published ON meal_menus (is_published);
CREATE INDEX IF NOT EXISTS ix_meal_menus_mess_id ON meal_menus (mess_id);
CREATE INDEX IF NOT EXISTS ix_meal_menus_meal_type ON meal_menus (meal_type);
CREATE INDEX IF NOT EXISTS ix_mess_billing_records_status ON mess_billing_records (status);
CREATE INDEX IF NOT EXISTS ix_mess_billing_records_mess_id ON mess_billing_records (mess_id);
CREATE INDEX IF NOT EXISTS ix_mess_billing_records_student_id ON mess_billing_records (student_id);
CREATE INDEX IF NOT EXISTS ix_mess_billing_records_billing_month ON mess_billing_records (billing_month);
CREATE INDEX IF NOT EXISTS ix_mess_expenses_expense_category ON mess_expenses (expense_category);
CREATE INDEX IF NOT EXISTS ix_mess_expenses_mess_id ON mess_expenses (mess_id);
CREATE INDEX IF NOT EXISTS ix_mess_expenses_transaction_date ON mess_expenses (transaction_date);
CREATE INDEX IF NOT EXISTS ix_mess_inventories_category ON mess_inventories (category);
CREATE INDEX IF NOT EXISTS ix_mess_inventories_item_name ON mess_inventories (item_name);
CREATE INDEX IF NOT EXISTS ix_mess_inventories_expiry_date ON mess_inventories (expiry_date);
CREATE INDEX IF NOT EXISTS ix_mess_inventories_mess_id ON mess_inventories (mess_id);
CREATE INDEX IF NOT EXISTS ix_mess_notices_mess_id ON mess_notices (mess_id);
CREATE INDEX IF NOT EXISTS ix_mess_staff_profiles_mess_id ON mess_staff_profiles (mess_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_mess_staff_profiles_user_id ON mess_staff_profiles (user_id);
CREATE INDEX IF NOT EXISTS ix_allocations_status ON allocations (status);
CREATE INDEX IF NOT EXISTS ix_digital_out_passes_status ON digital_out_passes (status);
CREATE INDEX IF NOT EXISTS ix_digital_out_passes_student_id ON digital_out_passes (student_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_digital_out_passes_leave_application_id ON digital_out_passes (leave_application_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_digital_out_passes_pass_token_hash ON digital_out_passes (pass_token_hash);
CREATE INDEX IF NOT EXISTS ix_digital_out_passes_is_outside ON digital_out_passes (is_outside);
CREATE INDEX IF NOT EXISTS ix_inventory_transactions_transaction_type ON inventory_transactions (transaction_type);
CREATE INDEX IF NOT EXISTS ix_inventory_transactions_inventory_id ON inventory_transactions (inventory_id);
CREATE INDEX IF NOT EXISTS ix_inventory_transactions_transaction_date ON inventory_transactions (transaction_date);
CREATE INDEX IF NOT EXISTS ix_meal_bookings_meal_menu_id ON meal_bookings (meal_menu_id);
CREATE INDEX IF NOT EXISTS ix_meal_bookings_booking_status ON meal_bookings (booking_status);
CREATE INDEX IF NOT EXISTS ix_meal_bookings_student_id ON meal_bookings (student_id);
CREATE INDEX IF NOT EXISTS ix_meal_feedbacks_meal_menu_id ON meal_feedbacks (meal_menu_id);
CREATE INDEX IF NOT EXISTS ix_meal_feedbacks_student_id ON meal_feedbacks (student_id);
CREATE INDEX IF NOT EXISTS ix_gate_transactions_outpass_id ON gate_transactions (outpass_id);
CREATE INDEX IF NOT EXISTS ix_gate_transactions_scanned_at ON gate_transactions (scanned_at);
CREATE INDEX IF NOT EXISTS ix_gate_transactions_event_type ON gate_transactions (event_type);
CREATE INDEX IF NOT EXISTS ix_gate_transactions_student_id ON gate_transactions (student_id);
CREATE INDEX IF NOT EXISTS ix_gate_transactions_security_user_id ON gate_transactions (security_user_id);
CREATE INDEX IF NOT EXISTS ix_meal_attendances_meal_menu_id ON meal_attendances (meal_menu_id);
CREATE INDEX IF NOT EXISTS ix_meal_attendances_student_id ON meal_attendances (student_id);
CREATE INDEX IF NOT EXISTS ix_meal_attendances_attendance_status ON meal_attendances (attendance_status);

-- =====================================================================
-- Step 4: Enable Row Level Security (RLS)
-- Default-Deny posture: Seals PostgREST public HTTP access while allowing
-- the Flask backend (connecting via the privileged postgres role) full access.
-- =====================================================================

ALTER TABLE public.hostels ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.suppliers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mess_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.students ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.wardens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.beds ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.complaints ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fee_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.leave_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.meal_menus ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mess_billing_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mess_expenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mess_inventories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mess_notices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mess_staff_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.parent_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.allocations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.complaint_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.digital_out_passes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inventory_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.meal_bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.meal_feedbacks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.parent_inquiries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.gate_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.meal_attendances ENABLE ROW LEVEL SECURITY;
