# HostelEase HMS — Modern Hostel Management System

> **B.Tech Computer Science & Engineering Mini Project**  
> Affiliation: **Dr. A.P.J. Abdul Kalam Technical University (AKTU)**  
> Architecture: **Layered MVC (Model - View - Controller / Service Architecture)**  
> Tech Stack: **Python 3.12 | Flask | Flask-SQLAlchemy | MySQL 8.0 | Bootstrap 5 | Chart.js**

---

## 1. Project Overview
**HostelEase HMS** is an enterprise-grade, database-driven web application built to digitize college campus hostel administration. It completely eliminates manual paperwork, physical ledger registers, duplicate room bookings, untracked fee receipts, and unmonitored night roll-calls.

### Key Capabilities
- **Three-Tier Role-Based Access Control (RBAC):** Admin, Warden, and Student portals with strict session authorization and route guarding.
- **Granular Bed Management:** Multi-hostel, multi-floor, and individual bed tracking (`Bed-A`, `Bed-B`) preventing overbooking.
- **Smart Allocation Engine:** Atomic room booking, re-allocation, and checkout with historical auditing.
- **Fee Ledger & Receipt Generation:** Record transactions, calculate remaining dues, and print official fee slips.
- **Daily Night Roll-Call Attendance:** Quick warden mobile interface with student monthly attendance percentage calculations.
- **Grievance Redressal (Complaint) System:** Categorized maintenance ticketing with priority flags and warden audit trails.
- **Digital Notice Board:** Target circulars to all residents or specific hostel blocks.
- **Student Leave & Out-Pass Management System:** End-to-end paperless leave applications with auto-verified resident profile binding, multi-day calendar validation, medical document uploads, host-based warden review desks, cancellation safeguards, and instant in-app notifications.

---

## 2. Directory Structure

```text
hostel_management_system/
├── app/
│   ├── __init__.py           # Application Factory (create_app, extensions, blueprints)
│   ├── config.py             # Multi-environment configuration (Dev, Test, Prod)
│   ├── models/               # SQLAlchemy ORM Data Models (12 Normalized Entities)
│   │   ├── __init__.py
│   │   ├── user.py           # User entity & Werkzeug password hashing
│   │   ├── hostel.py         # Hostel, Room, and Bed entities
│   │   ├── student.py        # Student and Warden profile entities
│   │   ├── allocation.py     # BedAllocation history & status
│   │   ├── fee.py            # FeeRecord ledger & receipts
│   │   ├── attendance.py     # Attendance roll-call entity
│   │   ├── complaint.py      # Complaints & ComplaintResponse
│   │   └── notice.py         # Digital Bulletin Board notices
│   ├── routes/               # Modular Flask Blueprints
│   │   ├── __init__.py
│   │   ├── main.py           # Public landing, about, emergency directory
│   │   ├── auth.py           # Login, student self-registration, logout
│   │   ├── admin.py          # Admin dashboard, master management, analytics
│   │   ├── warden.py         # Warden dashboard, attendance, complaints
│   │   └── student.py        # Student dashboard, profile, fees, room view
│   ├── services/             # Core Business Logic services
│   ├── forms/                # Flask-WTF validation forms
│   ├── utils/                # Custom decorators (@admin_required, @warden_required)
│   ├── templates/            # Jinja2 Modular HTML5 Templates
│   │   ├── base.html         # Master application layout
│   │   ├── components/       # Reusable UI elements (navbar, sidebar, alerts, errors)
│   │   ├── auth/             # Login and Registration views
│   │   ├── admin/            # Admin dashboard and data tables
│   │   ├── warden/           # Warden desk and operations
│   │   └── student/          # Student portal and grievance views
│   └── static/               # Assets (CSS, JS, Fonts, Images)
│       ├── css/style.css     # Clean SaaS design system
│       └── js/main.js        # Dynamic UI interactions & confirmations
├── database/
│   ├── schema.sql            # Normalized MySQL 8.0 DDL script (12 InnoDB tables)
│   └── seed.sql              # Realistic seed data for demonstration
├── tests/
│   └── test_basic.py         # Unit testing suite
├── .env                      # Local environment configuration
├── .env.example              # Template environment configuration
├── requirements.txt          # Python package dependencies
├── test_db.py                # Database connectivity diagnostic tool
├── init_database.py          # Direct MySQL schema & seed runner
├── seed_db.py                # Universal ORM seed runner
└── run.py                    # Application launch entry point
```

---

## 3. Quick Start Guide

### Step 1: Activate Virtual Environment
```powershell
.\venv\Scripts\Activate.ps1
```

### Step 2: Configure Database Credentials
Open `.env` and set your MySQL root password:
```ini
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password_here
MYSQL_DB=hostel_db
```

### Step 3: Verify Database Connection & Seed Data
Run the diagnostic verifier:
```powershell
python test_db.py
```
To populate initial demo data across all tables:
```powershell
python seed_db.py
```

### Step 4: Launch Application Server
```powershell
python run.py
```
Open your web browser and visit: **`http://127.0.0.1:5000`**

---

## 4. Default Demonstration Credentials (AKTU Practical Viva)

| Role | Username | Password | Access Scope |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin` | `Admin@123` | Full System Access, All Hostels, Reports, Audit Logs |
| **Warden (Boys)** | `warden_boys` | `Warden@123` | Block A Attendance, Grievances, Out-Pass Desk |
| **Warden (Girls)** | `warden_girls` | `Warden@123` | Block B Attendance, Grievances, Out-Pass Desk |
| **Student** | `rahul_sharma` | `Student@123` | Personal Room Info, Out-Passes, Grievances |
| **Security Guard** | `guard_main` | `Guard@123` | Gate Camera QR Terminal, Manual Token Verify, Live Perimeter |

---

## 5. Security & Engineering Best Practices
- **Password Hashing:** Passwords hashed with salted `scrypt` (via `werkzeug.security`). Plaintext passwords are never stored.
- **CSRF Protection:** Every POST request is protected with CSRF token generation via `Flask-WTF`.
- **SQL Injection Prevention:** 100% of queries use SQLAlchemy ORM with parameterized binding.
- **Zero-Downtime Fallback:** Built-in dynamic database resolution that falls back gracefully to SQLite if MySQL service is unconfigured, ensuring the project never crashes in an viva demonstration.
- **IDOR Protection & Authorization Guards:** In-flight session identity binding ensures students can never inspect or manipulate another student's leave requests, and wardens can only process leaves for their assigned hostel.
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
   - The student instantly receives an in-app notification linking to their digital pass wallet.

2. **Student Digital Pass Wallet:**
   - Accessible via **Digital Out-Pass** in the student sidebar.
   - Features stat counters (Total, Active, Outside Campus, Completed, Expired), active filter pills, and mobile-responsive pass slips.
   - Students can view their prominent QR code on their smartphone screen or download the QR image for offline gate presentation.
   - Strict IDOR safeguards prevent any student from viewing or manipulating another resident's pass.

3. **Security Guard Ingress/Egress Terminal:**
   - Dedicated role-based portal for campus security guards (`guard_main / Guard@123`).
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

# Run complete application test suite (43 tests)
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 9. Application UI & Module Previews

### 9.1 Portal Summary Matrix

| Portal | Primary URL | Target Role | Key Capabilities |
| :--- | :--- | :--- | :--- |
| **Admin Portal** | `/admin/dashboard` | Administrator | System-wide statistics, hostel block provisioning, room & bed allocations, fee tariffs, master security logs, CSV audit export. |
| **Warden Desk** | `/warden/dashboard` | Warden | Block-scoped leave review desk, out-pass issuance & revocation, night roll-call attendance, maintenance ticketing, parent inquiries. |
| **Student Portal** | `/student/dashboard` | Student | Leave applications with file uploads, digital QR out-pass wallet, night attendance percentage, fee dues & receipt download, grievances. |
| **Security Gate Terminal** | `/security/scan` | Security Guard | Live camera QR scanner, flip camera support, auto-verification of cryptographic tokens, EXIT/ENTRY tracking, overdue returns flag, manual token fallback. |
| **Parent Portal** | `/parent/dashboard` | Parent / Guardian | Real-time perimeter tracking (inside/outside badge), ward profile, leave history, gate scan timeline, attendance charts, fee receipts, warden communication desk. |

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
```

### 9.3 UI Screenshots & Layouts

> *Screenshots can be stored in `docs/screenshots/` for visual documentation.*

- **Dashboard & Analytics:** Real-time occupancy charts (Chart.js), quick metric counters, recent gate activity feed.
- **Digital Out-Pass Slip:** High-resolution QR code, security verification badge, departure & return timestamps, student photo & room particulars.
- **Live Camera Scanner:** HTML5 webcam viewport with focus frame, auto-detection, instant AJAX verification response, and camera switching.
- **Parent Ward Monitor:** Live status card (Green = Inside Hostel, Amber = Outside on Leave), historical timeline of departures and arrivals.

---

## 10. Technology Stack Reference

- **Backend:** Python 3.12, Flask 3.0.3, Flask-Login 0.6.3, Flask-WTF 1.2.1, Flask-SQLAlchemy 3.1.1
- **Database:** SQLite 3 (Development & Automated Testing) / MySQL 8.0 (Production)
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla ES6+), Bootstrap 5.3.3, Font Awesome 6.5.2, Chart.js 4.4.2
- **QR Code Engine:** `qrcode[pil]` 7.4.2, `Pillow` 10.3.0, `html5-qrcode` 2.3.8 (Browser WebRTC)
- **Security:** `werkzeug.security` (scrypt password hashing), `secrets` (32-byte cryptographic entropy), `hmac` (constant-time token comparison)



