# HostelEase HMS — Modern Hostel Management System
## 🚀 Live Demo

[Live Demo – HostelEase HMS](https://hms-ruby-beta.vercel.app/)

> **B.Tech Computer Science & Engineering Mini Project**  
> Affiliation: **Dr. A.P.J. Abdul Kalam Technical University (AKTU)**  
> Architecture: **Layered MVC (Model - View - Controller / Service Architecture)**  
> Tech Stack: **Python 3.12 | Flask | Flask-SQLAlchemy | PostgreSQL / MySQL / SQLite | Bootstrap 5 | Chart.js**

---

## 1. Project Overview
**HostelEase HMS** is an enterprise-grade, database-driven web application built to digitize college campus hostel administration. It completely eliminates manual paperwork, physical ledger registers, duplicate room bookings, untracked fee receipts, and unmonitored night roll-calls.

### Key Capabilities
- **Multi-Tier Role-Based Access Control (RBAC):** Admin, Warden (Boys & Girls), Student, Parent/Guardian, Security Guard, Mess Manager, and Mess Staff portals with strict session authorization and route guarding.
- **Granular Bed Management:** Multi-hostel, multi-floor, and individual bed tracking (`Bed-A`, `Bed-B`) preventing overbooking.
- **Smart Allocation Engine:** Atomic room booking, re-allocation, and checkout with historical auditing.
- **Fee Ledger & Receipt Generation:** Record transactions, calculate remaining dues, and print official fee slips.
- **Daily Night Roll-Call Attendance:** Quick warden mobile interface with student monthly attendance percentage calculations.
- **Grievance Redressal (Complaint) System:** Categorized maintenance ticketing with priority flags and warden audit trails.
- **Digital Notice Board:** Target circulars to all residents or specific hostel blocks.
- **Student Leave & Out-Pass Management System:** End-to-end paperless leave applications with auto-verified resident profile binding, multi-day calendar validation, medical document uploads, host-based warden review desks, cancellation safeguards, and instant in-app notifications.
- **Enterprise Mess & Dining Management:** Weekly menu scheduling, dynamic QR meal attendance, food wastage tracking, pantry inventory control, vendor management, and leave-based dining rebates.

---

## 2. Directory Structure

```text
hostel_management_system/
├── app/
│   ├── __init__.py           # Application Factory (create_app, extensions, blueprints)
│   ├── config.py             # Multi-environment configuration (Dev, Test, Prod)
│   ├── models/               # SQLAlchemy ORM Data Models (Normalized Entities)
│   │   ├── __init__.py
│   │   ├── user.py           # User entity & Werkzeug password hashing
│   │   ├── hostel.py         # Hostel, Room, and Bed entities
│   │   ├── student.py        # Student and Warden profile entities
│   │   ├── allocation.py     # BedAllocation history & status
│   │   ├── fee.py            # FeeRecord ledger & receipts
│   │   ├── attendance.py     # Attendance roll-call entity
│   │   ├── complaint.py      # Complaints & ComplaintResponse
│   │   ├── notice.py         # Digital Bulletin Board notices
│   │   ├── parent.py         # ParentProfile & communication
│   │   └── mess.py           # 12 Mess models (Menu, Bookings, Attendance, Inventory, etc.)
│   ├── routes/               # Modular Flask Blueprints
│   │   ├── __init__.py
│   │   ├── main.py           # Public landing, about, emergency directory
│   │   ├── auth.py           # Login, student self-registration, logout
│   │   ├── admin.py          # Admin dashboard, master management, analytics
│   │   ├── warden.py         # Warden dashboard, attendance, complaints, mess review
│   │   ├── student.py        # Student dashboard, profile, fees, QR dining, bookings
│   │   ├── parent.py         # Parent portal & ward monitoring
│   │   ├── mess_manager.py   # Mess Manager dashboard, menu, inventory, reports
│   │   └── mess_staff.py     # Mess Staff camera QR scanner & manual check-in
│   ├── services/             # Core Business Logic services
│   │   ├── mess_service.py   # Atomic dining checks, inventory, rebates, analytics
│   │   └── outpass_service.py# Cryptographic out-pass token engine
│   ├── forms/                # Flask-WTF validation forms
│   ├── utils/                # Custom decorators (@admin_required, @mess_manager_required, etc.)
│   ├── templates/            # Jinja2 Modular HTML5 Templates
│   │   ├── base.html         # Master application layout
│   │   ├── components/       # Reusable UI elements (navbar, sidebar, alerts, errors)
│   │   ├── auth/             # Login and Registration views
│   │   ├── admin/            # Admin dashboard and data tables
│   │   ├── warden/           # Warden desk and operations
│   │   ├── student/          # Student portal and grievance views
│   │   ├── parent/           # Parent ward monitoring views
│   │   ├── mess_manager/     # Mess Manager operations, menus, pantry, reports
│   │   └── mess_staff/       # Mess Staff QR scanner and attendance register
│   └── static/               # Assets (CSS, JS, Fonts, Images)
│       ├── css/style.css     # Clean SaaS design system
│       └── js/main.js        # Dynamic UI interactions & confirmations
├── database/
│   ├── schema.sql            # Normalized MySQL 8.0 DDL script
│   └── seed.sql              # Realistic seed data for demonstration
├── tests/
│   ├── test_basic.py         # Core unit testing suite
│   ├── test_parent_portal.py # Parent portal test suite
│   └── test_mess_system.py   # Mess management test suite (9 comprehensive tests)
├── .env                      # Local environment configuration
├── .env.example              # Template environment configuration
├── requirements.txt          # Python package dependencies
├── test_db.py                # Database connectivity diagnostic tool
├── init_database.py          # Direct MySQL schema & seed runner
├── seed_db.py                # Universal ORM seed runner
└── run.py                    # Application launch entry point
```

---

## 3. Quick Start & Installation Guide

### Step 1: Clone Repository & Create Virtual Environment
```powershell
git clone https://github.com/Drishti015/-Hostel-Management-System.git
cd "-Hostel-Management-System"

# Create Python virtual environment
python -m venv venv

# Activate virtual environment (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activate virtual environment (Linux / macOS)
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Environment Configuration
Copy `.env.example` to `.env` and configure your local or production environment variables:
```powershell
cp .env.example .env
```

#### Configuration Options (Placeholders):
```ini
# Flask Core Configuration
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your_secure_random_secret_key_here

# Database Configuration (Option A: PostgreSQL / Production Supabase)
DATABASE_URL=postgresql://<DB_USER>:<DB_PASSWORD>@<DB_HOST>:<PORT>/<DB_NAME>?sslmode=require

# Database Configuration (Option B: Development MySQL)
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_local_mysql_password
MYSQL_DB=hostel_db

# Database Configuration (Option C: Local SQLite Fallback)
# If neither DATABASE_URL nor MYSQL_PASSWORD is provided in development,
# the system automatically defaults to a local instance/hostel.sqlite3 database.
```

### Step 3: Database Initialization & Seeding
For initial development setup or running database seeds:
```powershell
python init_database.py
python seed_db.py
```

### Step 4: Launch Application Server
```powershell
python run.py
```
Open your web browser and visit: **`http://127.0.0.1:5000`**

### Step 5: Execute Test Suites
Run the complete automated test suite (114 tests across all 6 test modules):
```powershell
# Run Python syntax and bytecode compilation verification
python -m compileall -q app tests migrate_demo_accounts_prod.py

# Execute full automated test suite with isolated in-memory database
python -m unittest discover tests -v
```

---

## 4. Demonstration User Accounts & Role Matrix

The system provides 8 distinct user roles for comprehensive campus administration:

| Role | Demo Username | Portal Route | Access Scope & Responsibilities |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `/admin/dashboard` | Full System Administration, Hostel Configuration, Room & Bed Allocations, Tariffs, Master Security Logs, Mess Management, System Audits. |
| **Warden (Boys)** | `warden_boys` | `/warden/dashboard` | Block A Boys Hostel Administration, Night Roll-Call Attendance, Grievance Redressal, Leave & Out-Pass Review Desk, Dining Quality Inspection. |
| **Warden (Girls)** | `warden_girls` | `/warden/dashboard` | Block B Girls Hostel Administration, Night Roll-Call Attendance, Grievance Redressal, Leave & Out-Pass Review Desk, Dining Quality Inspection. |
| **Student** | `rahul_sharma` | `/student/dashboard` | Resident Portal, Room Particulars, Leave Applications, Digital Out-Pass Wallet (QR), Dining QR Wallet, Meal Reservations, Feedback, Fee Receipts. |
| **Parent / Guardian** | `parent_rahul` | `/parent/dashboard` | Real-Time Ward Safety Tracking (Inside/Outside Campus Badge), Gate Passage Log, Leave Verification, Attendance Charts, Fee Ledger, Warden Inquiries. |
| **Security Guard** | `guard_main` | `/security/scan` | Campus Gate QR Scanner Terminal, Live Ingress/Egress Verification (EXIT/ENTRY Modes), Overdue Curfew Alerts, Perimeter Tracking Roster. |
| **Mess Manager** | `mess_manager` | `/mess-manager/dashboard` | Dynamic Weekly Menu Planning, Kitchen Inventory with Low-Stock Alerts, Supplier Directory, Expense Tracking, Wastage Analytics, Billing Reports. |
| **Mess Staff** | `mess_staff` | `/mess-staff/scanner` | Dining Hall Live Camera QR Scanner, Cryptographic Token Verification, Atomic Attendance Check-in, Duplicate Scan Prevention, Manual Roll Search. |

> **Security Notice**: In accordance with enterprise security standards, plaintext passwords are never committed to version control. Passwords for all accounts are hashed using salted Werkzeug `scrypt` algorithms. In production or local demonstration setups, credentials are securely provisioned via runtime environment variables (`DEMO_PASSWORD_<ROLE>`) or initial onboarding prompts.

---

## 5. Security & Engineering Best Practices
- **Password Hashing:** Passwords hashed with salted `scrypt` (via `werkzeug.security`). Plaintext passwords are never stored in databases or version control.
- **CSRF Protection:** Every POST request is protected with CSRF token generation via `Flask-WTF`.
- **SQL Injection Prevention:** 100% of queries use SQLAlchemy ORM with parameterized binding.
- **Fail-Closed Production Safety:** Production migration utilities require explicit flags (`--execute-production-migration`) and interactive confirmation; preflight inspection operates under strict database-enforced read-only mode (`SET TRANSACTION READ ONLY`).
- **Test Database Isolation:** Test suites strictly enforce isolated in-memory SQLite databases (`sqlite:///:memory:`), guarded by pre-execution URI validators to prevent accidental execution against development or production databases.
- **Zero-Downtime Fallback:** Built-in dynamic database resolution that falls back gracefully to SQLite if local MySQL is unconfigured, ensuring resilient local demonstration without crashing.
- **IDOR Protection & Authorization Guards:** In-flight session identity binding ensures students can never inspect or manipulate another resident's records, parents can only monitor their verified linked ward, and wardens can only process actions for their assigned hostel block.
- **Cryptographic Gate & Dining Tokens:** QR codes contain HMAC-SHA256 hashed tokens with 32-byte secure entropy rather than exposing database IDs or PII.
- **Secure File Storage:** Strict MIME-type and extension whitelisting (`.pdf`, `.png`, `.jpg`, `.jpeg`), size enforcement (5MB max), secure timestamped UUID filenames, and authorized serving routes.

---

## 6. Student Leave Application & Out-Pass System

### 6.1 Architecture & Workflow Overview
1. **Student Application Workflow:**
   - Logged-in student navigates to **Leave Application** in the sidebar.
   - Resident and room allocation details are automatically verified from their active profile.
   - The student selects a category (*Home Visit, Medical Leave, Family Function, Personal Leave, Other*), departure and return dates, reason, destination, and emergency contact phone number.
   - Optional supporting medical prescription or parent letter can be attached.
   - On submission, duplicate submission prevention safeguards prevent accidental multiple submissions.
   - An in-app notification is automatically delivered to the student and routed to the assigned hostel's warden desk.

2. **Warden Review Workflow:**
   - Warden accesses **Leave Requests** in their operational dashboard.
   - The request queue is strictly scoped to the warden's assigned hostel building block.
   - The warden reviews student profile, contact numbers, destination, reason, and supporting documents.
   - **Approval:** Warden grants approval with optional departure instructions or curfew conditions.
   - **Rejection:** Warden is required to record a formal rejection justification or reason.
   - Automated notification is instantly dispatched to the student's dashboard feed.

3. **Student Cancellation Safeguard:**
   - Students may cancel their own applications only while the status remains `Pending`.
   - Approved or rejected applications are locked against direct cancellation.
   - Both student and warden receive cancellation audit notifications.

---

### 6.2 Database Models & Entity Relations

#### `LeaveApplication` Model (`leave_applications`)
| Column | Type | Constraints / Relations | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INT` | Primary Key, Auto-Increment | Unique Leave / Out-pass identifier |
| `student_id` | `INT` | `FOREIGN KEY (students.id)` | Link to applicant student entity |
| `hostel_id` | `INT` | `FOREIGN KEY (hostels.id)` | Scoped hostel block at application time |
| `leave_type` | `VARCHAR(50)` | Not Null | Home Visit, Medical Leave, etc. |
| `from_date` | `DATE` | Not Null | Departure date |
| `to_date` | `DATE` | Not Null | Expected return date |
| `reason` | `TEXT` | Not Null | Student's stated reason (min 10 chars) |
| `destination` | `VARCHAR(255)` | Not Null | Travel address / city |
| `emergency_contact`| `VARCHAR(20)` | Not Null | Verified phone number |
| `supporting_document`| `VARCHAR(255)`| Nullable | Secure uploaded file path |
| `status` | `ENUM` | `Pending`, `Approved`, `Rejected`, `Cancelled` | Lifecycle status flag |
| `reviewed_by` | `INT` | `FOREIGN KEY (wardens.id)` | Reviewing warden profile ID |
| `review_comment`| `TEXT` | Nullable | Warden remarks / rejection reason |
| `created_at` | `DATETIME` | Default `CURRENT_TIMESTAMP` | Application submission timestamp |
| `updated_at` | `DATETIME` | Default `CURRENT_TIMESTAMP` | Last modified timestamp |
| `reviewed_at` | `DATETIME` | Nullable | Review decision timestamp |

#### `Notification` Model (`notifications`)
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `INT` (PK) | Unique notification identifier |
| `user_id` | `INT` (FK) | Target user recipient |
| `title` | `VARCHAR(150)` | Notification headline |
| `message` | `TEXT` | Detailed notification message |
| `type` | `VARCHAR(20)` | Alert category (`info`, `success`, `warning`, `danger`) |
| `is_read` | `BOOLEAN` | Read status tracking |
| `link` | `VARCHAR(255)` | Deep-link to resource |
| `created_at`| `DATETIME` | Timestamp |

---

### 6.3 Leave System Route Endpoints

| Endpoint | Method | Role | Description |
| :--- | :--- | :--- | :--- |
| `/student/leaves` | `GET` | Student | Student leave management dashboard, status metrics & history |
| `/student/leaves/apply` | `GET, POST` | Student | Apply for leave with auto-filled profile & document upload |
| `/student/leaves/<id>` | `GET` | Student | Inspect application details, warden remarks & timeline |
| `/student/leaves/<id>/cancel` | `POST` | Student | Cancel pending leave application |
| `/warden/leaves` | `GET` | Warden | Warden leave review queue scoped to assigned hostel |
| `/warden/leaves/<id>` | `GET` | Warden | Detailed leave inspection & review decision desk |
| `/warden/leaves/<id>/action` | `POST` | Warden | Process approval or rejection with mandatory remarks |
| `/admin/leaves` | `GET` | Admin | System-wide leave oversight, metrics & multi-filter search |
| `/admin/leaves/<id>` | `GET` | Admin | Administrator full audit inspection |
| `/notifications/mark-read/<id>`| `GET` | Authenticated | Mark notification as read and navigate |
| `/notifications/mark-all-read` | `GET` | Authenticated | Mark all user notifications as read |
| `/leaves/document/<filename>` | `GET` | Authenticated | Secure file server with role-based access validation |

---

### 6.4 Running Automated Tests

To run the complete test suite including all leave and gate system tests:
```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```
To run only the leave system test suite:
```powershell
python -m unittest tests/test_leave_system.py -v
```
To run only the digital out-pass & gate management test suite:
```powershell
python -m unittest tests/test_gate_system.py -v
```

---

## 7. QR Code Digital Out-Pass & Hostel Gate Management System

### 7.1 Architecture & Workflow Overview
1. **Automatic QR Out-Pass Generation:**
   - When a warden approves a student's leave application, `OutPassService.generate_outpass()` automatically creates a cryptographic digital out-pass.
   - A high-entropy 32-byte secure token is generated via Python's `secrets` module.
   - The SHA-256 hash of this token is stored in the database (`pass_token_hash`).
   - The QR code contains only a secure protocol-prefixed token payload (`HOSTELPASS:<token>`), preventing exposure of sensitive PII or raw database primary keys.
   - High-resolution QR images are dynamically rendered and stored in `static/uploads/qrcodes/`.
   - **Serverless Resilience & In-Memory QR Generation:** To guarantee full compatibility with serverless environments (such as Vercel AWS Lambda containers where local filesystems are read-only or ephemeral), the `DigitalOutPass` model incorporates:
     - `get_qr_image_bytes()`: Generates the cryptographic PNG image dynamically in-memory via `io.BytesIO`.
     - `qr_code_data_uri`: Encodes the QR PNG as an inline Base64 data URI (`data:image/png;base64,...`), allowing zero-disk-dependency template rendering in student, warden, and admin portals.
     - Dynamic streaming endpoint `/student/outpasses/<id>/qr-image` and `/student/outpasses/<id>/download` using `send_file()` with `BytesIO` fallback to ensure QR codes are always accessible regardless of container disk persistence.
   - The student instantly receives an in-app notification linking to their digital pass wallet.

2. **Student Digital Pass Wallet:**
   - Accessible via **Digital Out-Pass** in the student sidebar.
   - Features stat counters (Total, Active, Outside Campus, Completed, Expired), active filter pills, and mobile-responsive pass slips.
   - Students can view their prominent QR code on their smartphone screen or download the QR image for offline gate presentation.
   - Strict IDOR safeguards prevent any student from viewing or manipulating another resident's pass.

3. **Security Guard Ingress/Egress Terminal:**
   - Dedicated role-based portal for campus security guards (username: `guard_main`).
   - **Live Camera QR Scanning:** Integrates `html5-qrcode` to drive mobile or webcam scanning with live camera selector and audio-visual feedback.
   - **Mode-Enforced Verification:** Guards toggle between **EXIT** (departure) and **ENTRY** (arrival).
   - **Manual Fallback:** If a student's screen is cracked or battery is low, guards can manually verify the token.
   - **Server-Side Gate Engine:**
     - Constant-time verification using `hmac.compare_digest` against SHA-256 hash.
     - **EXIT Rule:** Pass must be `Active`, student must not already be outside, departure window must be open, pass must not be revoked or expired. Sets `is_outside=True`, updates status to `Used`, records `actual_departure_time`.
     - **ENTRY Rule:** Student must currently be outside (`is_outside=True`). Sets `is_outside=False`, marks status `Completed`, records `actual_return_time`.
     - **Overdue Monitoring:** Returns past curfew (expected date + 2-hour grace period) are automatically flagged as overdue in red, logging audit remarks and notifying the warden.

4. **Warden Out-Pass Desk:**
   - Wardens can monitor all generated passes scoped to their assigned hostel block.
   - Filters: *All, Outside, Overdue, Active, Completed, Revoked*.
   - Revocation capability with mandatory justification field; revoking immediately invalidates the QR code at all campus gates and notifies the resident.

5. **Admin Master Oversight & CSV Export:**
   - Complete visibility over campus-wide out-passes across all hostel buildings.
   - Full audit trail log of gate transactions with student details, checkpoint name, timestamp, guard ID, and remarks.
   - Real-time one-click CSV export (`/admin/gate-transactions/export`) for proctorial reporting and compliance audits.

---

### 7.2 Database Models

#### `DigitalOutPass` Model (`digital_out_passes`)
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INT` | Primary Key | Unique out-pass identifier |
| `leave_application_id` | `INT` | Foreign Key (unique) | Linked approved leave application |
| `student_id` | `INT` | Foreign Key | Linked student entity |
| `pass_token_hash` | `VARCHAR(64)` | Unique, Not Null | SHA-256 hash of cryptographic token |
| `status` | `ENUM` | `Active`, `Used`, `Expired`, `Revoked`, `Completed` | Pass lifecycle state |
| `departure_date` | `DATE` | Not Null | Approved departure date |
| `expected_return_date` | `DATE` | Not Null | Scheduled return date |
| `expires_at` | `DATETIME` | Not Null | Strict expiration deadline with grace period |
| `is_outside` | `BOOLEAN` | Not Null, Default `False` | Real-time perimeter tracking flag |
| `actual_departure_time`| `DATETIME` | Nullable | Timestamp of EXIT scan |
| `actual_return_time` | `DATETIME` | Nullable | Timestamp of ENTRY scan |
| `qr_code_file` | `VARCHAR(255)` | Nullable | Path to generated QR image |
| `revoked_reason` | `VARCHAR(255)` | Nullable | Justification if revoked |
| `revoked_at` | `DATETIME` | Nullable | Revocation timestamp |

#### `GateTransaction` Model (`gate_transactions`)
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INT` | Primary Key | Unique transaction ID |
| `outpass_id` | `INT` | Foreign Key | Linked out-pass record |
| `student_id` | `INT` | Foreign Key | Resident student |
| `security_user_id` | `INT` | Foreign Key | Security guard account |
| `event_type` | `ENUM` | `EXIT`, `ENTRY` | Gate passage direction |
| `scanned_at` | `DATETIME` | Default `CURRENT_TIMESTAMP` | Scan timestamp |
| `gate_location` | `VARCHAR(100)`| Not Null | Checkpoint (e.g. Main Campus Gate) |
| `verification_status`| `ENUM` | `Success`, `Failed` | Verification outcome |
| `remarks` | `TEXT` | Nullable | Guard observations or failure reasons |

---

### 7.3 Gate & Out-Pass Route Endpoints

| Endpoint | Method | Role | Description |
| :--- | :--- | :--- | :--- |
| `/student/outpasses` | `GET` | Student | Student out-pass wallet with active status pills & QR cards |
| `/student/outpasses/<id>` | `GET` | Student | High-resolution QR pass slip with gate movement trail |
| `/student/outpasses/<id>/download` | `GET` | Student | Download official QR code image file |
| `/security/dashboard` | `GET` | Security | Security guard station overview, live counts & recent activity |
| `/security/scan` | `GET` | Security | Live camera QR scanner terminal (EXIT / ENTRY toggle) |
| `/security/verify` | `POST` | Security | Verification API endpoint (handles AJAX & HTML submissions) |
| `/security/outside` | `GET` | Security | Live roster of students currently outside campus |
| `/security/transactions` | `GET` | Security | Security guard gate activity audit log with search & filters |
| `/warden/outpasses` | `GET` | Warden | Warden out-pass register scoped to hostel block |
| `/warden/outpasses/<id>` | `GET` | Warden | Detailed out-pass inspection & gate trail |
| `/warden/outpasses/<id>/revoke` | `POST` | Warden | Revoke out-pass with mandatory justification |
| `/admin/outpasses` | `GET` | Admin | Campus-wide out-pass management across all blocks |
| `/admin/outpasses/<id>` | `GET` | Admin | Administrative out-pass inspection |
| `/admin/gate-transactions` | `GET` | Admin | Master gate security log with date and status filters |
| `/admin/gate-transactions/export` | `GET` | Admin | Stream complete gate log as CSV file |

---

## 8. Parent & Guardian Portal (`/parent`)

### 8.1 Architecture & Security Overview
The **Parent Portal** is a dedicated, role-isolated submodule designed to provide parents and legal guardians with transparent, real-time oversight of their child's residential life, safety, academic attendance, and financial standing.

#### Security & Privacy Principles:
1. **Role-Based Isolation (`parent_required`):** Parents are isolated from Student, Warden, Security Guard, and Administrator portal views. Attempts to access other dashboards return HTTP 403 Forbidden.
2. **Strict Identity Isolation & IDOR Protection:** A parent is strictly linked to their own child's record. Every endpoint checks that the queried entity (leave application, digital out-pass, fee receipt, attendance log) belongs to the authenticated parent's linked student. Cross-student access is blocked with HTTP 403 Forbidden.
3. **Verified Admin-Driven Linking:** Parents cannot self-link to arbitrary student accounts. Administrators create and verify parent accounts, assign relationships, and link them to students.
4. **Read-Only Gate Oversight:** Parents can monitor movements, exit/entry timestamps, and out-pass statuses in real time. They cannot generate, modify, approve, or revoke passes.

---

### 8.2 Database Models

#### `ParentProfile` (`parent_profiles`)
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Primary Key, Auto-increment | Internal identifier |
| `user_id` | `INTEGER` | Foreign Key (`users.id`), Unique, Not Null | Associated parent user authentication record |
| `parent_name` | `VARCHAR(100)` | Not Null | Parent / Guardian full legal name |
| `phone_number` | `VARCHAR(20)` | Not Null | Primary contact phone number |
| `relationship_to_student` | `VARCHAR(50)` | Not Null, Default `'Father'` | Relationship (Father, Mother, Legal Guardian) |
| `student_id` | `INTEGER` | Foreign Key (`students.id`), Cascade | Linked student resident record |
| `account_status` | `VARCHAR(20)` | Not Null, Default `'active'` | Portal access status (`active`, `inactive`) |
| `created_at` / `updated_at` | `DATETIME` | Not Null, Timestamp | Audit timestamps |

#### `ParentInquiry` (`parent_inquiries`)
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | Primary Key, Auto-increment | Internal identifier |
| `parent_id` | `INTEGER` | Foreign Key (`parent_profiles.id`), Cascade | Submitting parent record |
| `student_id` | `INTEGER` | Foreign Key (`students.id`), Cascade | Resident child reference |
| `warden_id` | `INTEGER` | Foreign Key (`wardens.id`), Set Null | Assigned hostel warden recipient |
| `subject` | `VARCHAR(150)` | Not Null | Inquiry topic / subject line |
| `message` | `TEXT` | Not Null | Detailed message from parent |
| `response` | `TEXT` | Nullable | Official written reply from hostel warden |
| `responded_at` | `DATETIME` | Nullable | Timestamp of warden's response |
| `status` | `VARCHAR(20)` | Not Null, Default `'Pending'` | Status (`Pending`, `In Progress`, `Resolved`) |
| `created_at` / `updated_at` | `DATETIME` | Not Null, Timestamp | Audit timestamps |

---

### 8.3 Parent Portal Route Endpoints

| Endpoint | Method | Role | Description |
| :--- | :--- | :--- | :--- |
| `/parent/dashboard` | `GET` | Parent | Consolidated dashboard: real-time movement badge, stats, and feeds |
| `/parent/child` | `GET` | Parent | Complete residential, academic, and warden particulars for child |
| `/parent/leave-applications` | `GET` | Parent | Ward leave requests history with status filters (Pending, Approved, etc.) |
| `/parent/leave-applications/<id>` | `GET` | Parent | Detailed read-only view of a child's leave slip and warden remarks |
| `/parent/outpasses` | `GET` | Parent | Real-time movement status and historical digital out-pass slips |
| `/parent/outpasses/<id>` | `GET` | Parent | Detailed out-pass slip with gate scan timestamps and checkpoint audit trail |
| `/parent/attendance` | `GET` | Parent | Daily night roll-call compliance logs, metrics, and monthly Chart.js graph |
| `/parent/fees` | `GET` | Parent | Financial ledger: semester tariff, cleared payments, and outstanding dues |
| `/parent/fees/receipt/<id>` | `GET` | Parent | Official printable accounts receipt slip with watermark |
| `/parent/inquiries` | `GET`, `POST` | Parent | Communication desk: contact assigned warden and view response history |
| `/parent/notifications` | `GET` | Parent | In-app notification center for all ward movements, leaves, and bulletins |
| `/warden/inquiries` | `GET` | Warden | Review parent inquiries from residents in the warden's assigned block |
| `/warden/inquiries/<id>/reply` | `POST` | Warden | Submit official warden response to a parent inquiry |
| `/admin/parents` | `GET` | Admin | Master parent directory with search, hostel filters, and status controls |
| `/admin/parents/create` | `GET`, `POST` | Admin | Provision new parent user account and link to an active student |
| `/admin/parents/<id>/edit` | `GET`, `POST` | Admin | Edit parent particulars, relationship, or reassign student link |
| `/admin/parents/<id>/toggle-status`| `POST` | Admin | Instantly activate or suspend parent portal access |
| `/admin/parents/<id>/reset-password`| `POST` | Admin | Secure administrator password reset for parent user account |

---

### 8.4 Parent-Student Account Provisioning Workflow
1. **Administrator Creation:**
   * Navigate to `/admin/parents` and click **Create & Link Parent Account**.
   * Provide unique username, parent email, temporary password, parent full name, contact phone number, relationship, and select the student from the verified resident dropdown.
2. **Account Verification:**
   * The system automatically generates a `User` (role: `'parent'`) and an associated `ParentProfile` securely linked to `Student.id`.
   * If an account is deactivated via the Admin toggle, portal login is rejected immediately.
3. **Parent Login:**
   * Parent navigates to `/auth/login` and enters credentials.
   * Authentication routes the user directly to `/parent/dashboard`.

---

### 8.5 Automated Parent Notifications
The system dispatches in-app notifications to all active linked parents upon:
* **Leave Application Submission:** Informs parents of dates, reason, and destination.
* **Warden Leave Decision:** Alerts parents immediately whether leave was Approved or Rejected.
* **Campus Gate Departure (EXIT):** Real-time alert specifying the gate terminal and exit timestamp.
* **Campus Gate Return (ENTRY):** Real-time alert confirming safe arrival (with Late Arrival flags if overdue).
* **Warden Inquiry Response:** Notifies parents when the warden replies to their message.

---

### 8.6 Automated Verification & Testing
Execute the complete test suite including Parent Portal verification:

```bash
# Run parent portal test suite
python -m unittest tests/test_parent_portal.py -v

# Run mess management test suite (9 tests)
python -m unittest tests/test_mess_system.py -v

# Run complete application test suite (52 tests across all modules)
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 9. Application UI & Module Previews

### 9.1 Portal Summary Matrix

| Portal | Primary URL | Target Role | Key Capabilities |
| :--- | :--- | :--- | :--- |
| **Admin Portal** | `/admin/dashboard` | Administrator | System-wide statistics, hostel block provisioning, room & bed allocations, fee tariffs, master security logs, mess profiles & staff allocation, CSV audit export. |
| **Warden Desk** | `/warden/dashboard` | Warden | Block-scoped leave review desk, out-pass issuance & revocation, night roll-call attendance, maintenance ticketing, parent inquiries, mess dining quality oversight. |
| **Student Portal** | `/student/dashboard` | Student | Leave applications with file uploads, digital QR out-pass wallet, night attendance percentage, fee dues & receipts, dining QR wallet, meal bookings, food feedback. |
| **Security Gate Terminal** | `/security/scan` | Security Guard | Live camera QR scanner, flip camera support, auto-verification of cryptographic tokens, EXIT/ENTRY tracking, overdue returns flag, manual token fallback. |
| **Parent Portal** | `/parent/dashboard` | Parent / Guardian | Real-time perimeter tracking (inside/outside badge), ward profile, leave history, gate scan timeline, attendance charts, fee receipts, warden communication desk. |
| **Mess Manager Portal** | `/mess-manager/dashboard` | Mess Manager | Dynamic weekly menu scheduling, pantry inventory tracking with reorder thresholds, supplier database, kitchen expense accounting, multidimensional feedback analysis, physical vs unconsumed wastage metrics, attendance CSV exports. |
| **Mess Staff Portal** | `/mess-staff/scanner` | Mess Staff | Live HTML5 dining camera scanner, front/rear camera flip, cryptographic student token verification, atomic meal check-in, duplicate scan rejection, manual enrollment search. |

### 9.2 Key Workflow Previews

```
==================================================================================
  STUDENT DIGITAL OUT-PASS WORKFLOW
==================================================================================
 [ Student Submits Leave ]  -->  [ Warden Reviews & Approves ]
                                            |
                                            v
                                 [ Cryptographic Out-Pass Generated ]
                                 [ SHA-256 Token & High-Res QR Code ]
                                            |
                                            v
 [ Security Guard Scans at Gate ]  <--  [ Student Shows QR on Mobile ]
       |                  |
   (EXIT Mode)       (ENTRY Mode)
       |                  |
       v                  v
 [ Student Leaves ]   [ Student Arrives ]
 [ Status: Used ]     [ Status: Completed ]
 [ is_outside: True]  [ is_outside: False ]
                      [ Checks Overdue Curfew ]

==================================================================================
  STUDENT DINING QR & MEAL ATTENDANCE WORKFLOW
==================================================================================
 [ Manager Publishes Menu ]  -->  [ Student Books Meal / Walk-in ]
                                             |
                                             v
                                  [ Cryptographic Dining QR ]
                                  [ "MESS:<id>:<hash>" Token ]
                                             |
                                             v
 [ Mess Staff Camera Scanner ]  <--  [ Student Displays QR at Mess Gate ]
       |
       +---> [ Cryptographic Verification (HMAC-SHA256) ]
       +---> [ Policy Check: Walk-in Allowed OR Active Booking Validated ]
       +---> [ Duplicate Scan Prevention: Checks if Already Availed Today ]
       |
       v
 [ Check-in Granted (GREEN) ]  -->  [ Atomic Attendance Record Created ]
                               -->  [ Real-Time Wastage Analytics Updated ]
```

### 9.3 UI Screenshots & Layouts

> *Screenshots can be stored in `docs/screenshots/` for visual documentation.*

- **Dashboard & Analytics:** Real-time occupancy charts (Chart.js), quick metric counters, recent gate activity feed.
- **Digital Out-Pass Slip:** High-resolution QR code, security verification badge, departure & return timestamps, student photo & room particulars.
- **Live Camera Scanner:** HTML5 webcam viewport with focus frame, auto-detection, instant AJAX verification response, and camera switching.
- **Parent Ward Monitor:** Live status card (Green = Inside Hostel, Amber = Outside on Leave), historical timeline of departures and arrivals.
- **Mess Staff Live QR Scanner:** Instant WebRTC video viewport, rear-camera priority for mobile tablets, desktop fallback, real-time audio/visual alert badges (GREEN = Granted, YELLOW = Duplicate, RED = Invalid).
- **Mess Management Analytics:** Chart.js meal attendance trend charts, monthly expense breakdown pie chart, and physical kitchen scrap vs unconsumed meal wastage comparison.

---

## 10. Complete Mess Management System Implementation

HostelEase features an enterprise-grade, integrated **Mess Management System** designed to streamline campus dining, optimize food procurement, eliminate unconsumed meal wastage, and automate student billing with leave-based rebates.

### 10.1 Key System Features

1. **Two Dedicated User Roles (RBAC):**
   - **Mess Manager (`mess_manager`):** Full operational control over weekly menus, meal capacities, dietary flags, pantry inventory with minimum threshold alerts, vendor profiles, kitchen operational expenses, multidimensional food feedback, dining notices, and monthly billing generation.
   - **Mess Staff (`mess_staff`):** Fast-paced dining entrance desk operations, featuring an HTML5 live camera QR scanner, rear/front camera switching, cryptographic student QR token verification, atomic meal check-in, duplicate scan prevention, and manual roll/enrollment number search.

2. **12 Normalized SQLAlchemy Database Models (`app/models/mess.py`):**
   - `MessProfile`: Hostel dining facilities with operational status, daily capacity, and booking policies (`walk_in` vs `booking_required`).
   - `Supplier`: Vendor directory with GSTIN, contact numbers, supply categories, and active contract status.
   - `MealMenu`: Date and meal type (`Breakfast`, `Lunch`, `Snacks`, `Dinner`) schedule with dish items, calorie counts, dietary flags (`Vegetarian`, `Non-Vegetarian`, `Vegan`, `Jain`), booking cutoffs, and maximum capacity.
   - `MealBooking`: Student meal reservations with validation deadlines, status tracking (`booked`, `cancelled`, `availed`, `no_show`), and dietary preferences.
   - `MealAttendance`: High-throughput dining check-in ledger recording student ID, menu ID, scanning staff ID, check-in method (`qr_scan`, `manual`), verification status, and timestamps.
   - `MealFeedback`: Student rating engine supporting 1–5 star ratings across overall taste, hygiene, quantity, and preparation, with optional anonymity.
   - `MessInventory`: Pantry stock ledger tracking items, categories (`Grains`, `Vegetables`, `Dairy`, `Spices`, `Oil`, `Gas`), units, quantities, unit prices, and auto-flagged reorder threshold levels.
   - `InventoryTransaction`: Inflow/outflow audit trail logging stock receipts, daily cooking kitchen consumption, spoilage write-offs, and wastage.
   - `MessExpense`: Comprehensive accounting ledger capturing vegetable market runs, milk supply, pantry groceries, fuel, maintenance, staff wages, and utility bills.
   - `MessStaffProfile`: Auxiliary staff details including shift timings, assigned mess hall, phone numbers, and active service status.
   - `MessNotice`: Dining circulars and notices displayed on the student dining dashboard.
   - `MessBillingRecord`: Monthly dining bills factoring base subscription rates, extra a-la-carte meal charges, and automatically calculated approved leave rebates.

3. **Cryptographic Dining QR Identity (`app/services/mess_service.py`):**
   - Students receive an instant, self-refreshing digital dining token encoded as `MESS:<student_id>:<token_hash>`.
   - The token hash is derived using HMAC-SHA256 seeded with secret application entropy, protecting against screenshot sharing, tampering, and impersonation without leaking sensitive student PII.

4. **Fast HTML5 Webcam Dining Scanner (`/mess-staff/scanner`):**
   - Built on `html5-qrcode` 2.3.8 WebRTC engine.
   - Priority selection for mobile/tablet rear cameras (`facingMode: "environment"`) with seamless desktop webcam fallback and a dynamic camera toggle switch.
   - Instant visual response cards:
     - **GREEN (Success):** Valid meal entitlement verified. Displays student name, roll number, room number, and meal type.
     - **YELLOW (Warning):** Duplicate scan detected! Clearly shows the exact prior check-in timestamp to prevent double-dipping.
     - **RED (Error):** Invalid QR token, wrong meal window, or unbooked meal under strict booking policy.
   - Manual search fallback by Student Roll Number or Enrollment Number for damaged phone screens or dead batteries.

5. **Food Wastage Analytics & Differentiated Metrics:**
   - Separates **Physical Kitchen Wastage** (measured in kilograms from vegetable peels, expired raw ingredients, and prepared leftover food recorded via inventory transactions) from **Unconsumed Booked Meals** (students who reserved a meal but did not attend).
   - Generates visual comparison bar charts in the Mess Manager and Warden dashboards to assist chefs in adjusting preparation portions.

6. **Automated Leave Rebate & Billing Engine:**
   - Seamlessly integrates with the **Student Leave Application** system.
   - Calculates total continuous days for all `Approved` leave requests during the billing month.
   - If approved leave duration is 3 or more days, the engine applies a daily rebate formula:
     $$\text{Total Rebate} = \text{Leave Days} \times \text{Daily Rebate Rate}$$
   - Deducts the rebate from base mess fees and adds any approved extra meals to calculate the net payable amount.

7. **Warden & Admin Oversight:**
   - **Warden Portal (`/warden/mess`):** Read-only transparency dashboard showing today's dining menus, real-time student check-in counters, pantry low-stock warnings, and student food satisfaction metrics.
   - **Admin Master Desk (`/admin/mess`):** Ability to configure hostel dining halls, toggle booking policies (`walk_in` vs `booking_required`), create Mess Staff accounts, and execute batch monthly billing generations.

### 10.2 Mess Management Route Matrix

| Endpoint | HTTP Method | Protected Role | Functionality |
| :--- | :--- | :--- | :--- |
| `/student/mess` | GET | `student` | Student dining home: today's menu, active bookings, dining notice bulletin |
| `/student/mess/menu` | GET | `student` | Weekly menu calendar with dietary tags, calories, and booking buttons |
| `/student/mess/book/<id>` | POST | `student` | Reserve meal slot within cutoff deadline |
| `/student/mess/cancel-booking/<id>` | POST | `student` | Cancel booked meal before preparation cutoff |
| `/student/mess/bookings` | GET | `student` | Personal booking history and status ledger |
| `/student/mess/qr` | GET | `student` | Digital Dining QR Wallet with high-resolution token |
| `/student/mess/attendance` | GET | `student` | Personal dining check-in history and timestamps |
| `/student/mess/feedback` | GET, POST | `student` | Submit multidimensional meal ratings and reviews |
| `/student/mess/billing` | GET | `student` | View monthly mess bills, breakdown, and leave rebates |
| `/mess-staff/dashboard` | GET | `mess_staff` | Quick shift overview, today's check-in metrics |
| `/mess-staff/scanner` | GET | `mess_staff` | Live WebRTC camera QR scanner & manual check-in form |
| `/mess-staff/verify` | POST (AJAX) | `mess_staff` | Cryptographic QR validation and atomic attendance registration |
| `/mess-staff/attendance` | GET | `mess_staff` | Today's complete dining attendance roll |
| `/mess-manager/dashboard` | GET | `mess_manager` | Operational analytics, attendance trends, low stock alerts |
| `/mess-manager/menu` | GET | `mess_manager` | Weekly menu management overview |
| `/mess-manager/menu/create` | GET, POST | `mess_manager` | Schedule new breakfast, lunch, snacks, or dinner menu |
| `/mess-manager/menu/<id>/edit` | GET, POST | `mess_manager` | Modify menu items, capacity, and deadlines |
| `/mess-manager/menu/<id>/delete`| POST | `mess_manager` | Remove unpublished or obsolete menu entry |
| `/mess-manager/bookings` | GET | `mess_manager` | Live booking status table with student details |
| `/mess-manager/attendance` | GET | `mess_manager` | Real-time attendance ledger with check-in timestamps |
| `/mess-manager/inventory` | GET | `mess_manager` | Pantry stock management and reorder status indicators |
| `/mess-manager/inventory/add` | GET, POST | `mess_manager` | Add new pantry raw material / stock item |
| `/mess-manager/inventory/transaction` | GET, POST | `mess_manager` | Record stock received, daily kitchen issue, or spoilage |
| `/mess-manager/suppliers` | GET, POST | `mess_manager` | Vendor directory and contract management |
| `/mess-manager/expenses` | GET, POST | `mess_manager` | Record kitchen operational costs, grocery invoices, fuel bills |
| `/mess-manager/feedback` | GET | `mess_manager` | Student feedback review desk with average rating breakdowns |
| `/mess-manager/notices` | GET, POST | `mess_manager` | Publish dining circulars to student portals |
| `/mess-manager/reports` | GET | `mess_manager` | Chart.js wastage analysis, meal popularity, and financial totals |
| `/mess-manager/reports/export-attendance` | GET | `mess_manager` | Download attendance log as standardized CSV spreadsheet |
| `/mess-manager/staff` | GET | `mess_manager` | View mess kitchen personnel and shift allocations |
| `/warden/mess` | GET | `warden` | Warden dining oversight, food quality review, inventory status |
| `/admin/mess` | GET | `admin` | Mess facility list, policy controls, dining overview |
| `/admin/mess/create` | GET, POST | `admin` | Register a new hostel dining mess hall |
| `/admin/mess/<id>/edit` | GET, POST | `admin` | Update mess hall profile and capacity |
| `/admin/mess/<id>/toggle-policy` | POST | `admin` | Toggle between Walk-in Allowed and Mandatory Pre-Booking |
| `/admin/mess/staff/create` | GET, POST | `admin` | Provision user account for Mess Staff or Mess Manager |
| `/admin/mess/billing/generate` | POST | `admin` | Batch generate monthly mess billing with leave rebates |

---

## 11. Technology Stack Reference

- **Backend:** Python 3.12, Flask 3.0.3, Flask-Login 0.6.3, Flask-WTF 1.2.1, Flask-SQLAlchemy 3.1.1
- **Database Support:**
  - **Production:** PostgreSQL (Supabase Transaction Pooler over SSL with NullPool / Serverless compatibility)
  - **Development:** MySQL 8.0 (PyMySQL) / Local SQLite 3
  - **Automated Testing:** In-memory SQLite (`sqlite:///:memory:`) with strict test isolation guards
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla ES6+), Bootstrap 5.3.3, Font Awesome 6.5.2, Chart.js 4.4.2
- **QR Code Engine:** `qrcode[pil]` 7.4.2, `Pillow` 10.3.0, `html5-qrcode` 2.3.8 (Browser WebRTC)
- **Security:** `werkzeug.security` (salted `scrypt` password hashing), `secrets` (32-byte cryptographic entropy), `hmac` (constant-time token comparison)
- **Deployment:** Vercel WSGI Serverless / Standard WSGI (Gunicorn)

---

## 12. Quality Assurance, Security Audits & Release Reports

HostelEase HMS has undergone comprehensive end-to-end quality assurance, vulnerability mitigation, and regression testing. The repository includes two exhaustive audit reports:

1. **[`HOSTELEASE_COMPLETE_QA_REPORT.md`](file:///HOSTELEASE_COMPLETE_QA_REPORT.md):**
   - Complete feature inventory across all 8 user roles and 7 major workflows.
   - Comprehensive test execution results (114 automated unit and integration tests passing).
   - In-depth security analysis covering RBAC, IDOR protection, session boundaries, and CSRF defense.
   - Database schema and entity relationship consistency audit.
   - Vercel serverless deployment assessment and header verification.

2. **[`HOSTELEASE_FINAL_RELEASE_QA_REPORT.md`](file:///HOSTELEASE_FINAL_RELEASE_QA_REPORT.md):**
   - Executive release readiness assessment and verification sign-off.
   - Serverless ephemeral filesystem remediation (in-memory QR streams and Base64 data URIs).
   - Cross-role route and template hardening audit.
   - Production migration fail-closed safety verification (`--execute-production-migration` flag requirement, interactive confirmation, read-only preflight).
   - Final release checklist and deployment guidelines.

