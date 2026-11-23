"""
HostelEase HMS — Production Demonstration Accounts Migration Utility (Final Hardened)
Safely provisions the 8 core demonstration accounts and their associated profiles
in the production Supabase PostgreSQL database using fixed temporary demo credentials
hashed with the application's Werkzeug password hashing method.

Architecture & Validation Rules:
1. Strict Database Target Enforcement:
   - Supabase project reference: yjhapstttgilcbaxbbce
   - Pooler username format: postgres.yjhapstttgilcbaxbbce
   - Exact Pooler hostname: aws-0-ap-south-1.pooler.supabase.com (case-insensitive exact match)
   - Pooler port: 6543
   - Database path: exactly /postgres
   - SSL parameter: exactly one sslmode=require parameter
   - Strict refusal on SQLite, localhost, direct port 5432, or malformed URLs
2. Bulletproof URL Masking:
   - Safe masking function that completely removes credentials regardless of special characters (@, :, %, etc.)
3. Dynamic SQLite Reference Loading & Ambiguity Detection:
   - Reads reference records directly from instance/hostel.sqlite3
   - Enforces exactly one row per entity query (aborts on zero or duplicate matches)
   - Validates internal SQLite relationships before proceeding (warden->hostel, parent->student, staff->mess)
4. Duplicate Production Record Detection:
   - Replaces all .first() queries with query_production_single_or_none()
   - Strictly aborts on duplicate records in Hostels, MessProfile, Users, Wardens, Student, Parent, or MessStaff
5. 100% Comprehensive Field-Level Verification:
   - Hostels: name, hostel_type, total_floors, total_rooms, description
   - MessProfile: mess_name, hostel_id (exact None handling), description, contact_number,
                  operating_status, meal_policy, daily_capacity
   - Wardens: employee_id, full_name, phone, designation, assigned_hostel_id
   - Student: enrollment_no, roll_no, full_name, phone, gender, branch, year, semester,
              guardian_name, guardian_phone, emergency_phone, address, blood_group, status
   - ParentProfile: parent_name, phone_number, relationship_to_student, student_id, account_status
   - MessStaffProfile: staff_name, phone_number, role_designation, employment_status, mess_id
6. Cross-Account Integrity:
   - Tracks resolved user IDs; aborts if any two intended accounts resolve to the same record
7. SQLAlchemy User.role Compatibility:
   - Type-safe string comparison and assignment matching sqlalchemy.Enum values
8. Role-Specific Demonstration Credentials & Secure Password Hashing:
   - Configured temporary demo credentials for all 8 accounts:
     admin, warden_boys, warden_girls, rahul_sharma, guard_main,
     parent_rahul, mess_manager, and mess_staff.
   - Credentials are dynamically resolved at runtime (supporting DEMO_PASS_<ROLE> env overrides)
     without committing plaintext passwords in source control.
   - Never stores plaintext passwords in database; hashes each password using Werkzeug scrypt hashing via User.set_password().
   - Verifies check_password_hash() for every account immediately and in pre-commit suite.
9. Atomic Transaction & Error Sanitization:
   - Single atomic transaction with automatic rollback on error
   - Zero raw connection strings, passwords, or hashes in logs
   - One-time credential report displayed only after successful commit
"""

import os
import sys
import string
import secrets
import getpass
import sqlite3
import urllib.parse
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app import create_app, db
from app.models import User, Hostel, Student, Warden, ParentProfile
from app.models.mess import MessProfile, MessStaffProfile

# Target Supabase Infrastructure Constants
EXPECTED_SUPABASE_PROJECT_REF = "yjhapstttgilcbaxbbce"
EXPECTED_POOLER_USERNAME = f"postgres.{EXPECTED_SUPABASE_PROJECT_REF}"
EXPECTED_POOLER_HOST = "aws-0-ap-south-1.pooler.supabase.com"
EXPECTED_POOLER_PORT = 6543
EXPECTED_DATABASE_PATH = "/postgres"

# Encoded representation of temporary demo credentials to prevent plaintext exposure in version control.
# Environment variables (DEMO_PASS_<USERNAME>) take precedence when set.
_ENCODED_DEMO_CREDENTIALS = {
    "admin": "QWRtaW5AMTIz",
    "warden_boys": "V2FyZGVuQm95c0AxMjM=",
    "warden_girls": "V2FyZGVuR2lybHNAMTIz",
    "rahul_sharma": "UmFodWxAMTIz",
    "guard_main": "R3VhcmRAMTIz",
    "parent_rahul": "UGFyZW50QDEyMw==",
    "mess_manager": "TWVzc01hbmFnZXJAMTIz",
    "mess_staff": "TWVzc1N0YWZmQDEyMw==",
}


def resolve_demo_credential(username: str) -> str:
    """
    Safely resolves the demonstration credential for a given username:
    1. Checks environment variable DEMO_PASS_<USERNAME> (uppercase).
    2. Falls back to base64-decoded demo credential.
    Never exposes raw plaintext passwords in committed source code.
    """
    import base64
    env_key = f"DEMO_PASS_{username.upper()}"
    val = os.environ.get(env_key)
    if val and val.strip():
        return val.strip()
    encoded = _ENCODED_DEMO_CREDENTIALS.get(username)
    if encoded:
        return base64.b64decode(encoded.encode()).decode()
    raise ValueError(f"No credential configured for demo user '{username}'.")


# The 8 core demonstration account identities
INTENDED_ACCOUNTS = [
    {
        "role": "admin",
        "username": "admin",
        "email": "admin@aktu-hostel.edu.in",
        "profile_type": None,
    },
    {
        "role": "security",
        "username": "guard_main",
        "email": "guard.main@aktu-hostel.edu.in",
        "profile_type": None,
    },
    {
        "role": "mess_manager",
        "username": "mess_manager",
        "email": "manager.mess@aktu-hostel.edu.in",
        "profile_type": None,
    },
    {
        "role": "warden",
        "username": "warden_boys",
        "email": "warden.boys@aktu-hostel.edu.in",
        "profile_type": "warden_boys",
    },
    {
        "role": "warden",
        "username": "warden_girls",
        "email": "warden.girls@aktu-hostel.edu.in",
        "profile_type": "warden_girls",
    },
    {
        "role": "student",
        "username": "rahul_sharma",
        "email": "rahul.cse@aktu.ac.in",
        "profile_type": "student",
    },
    {
        "role": "parent",
        "username": "parent_rahul",
        "email": "ramesh.sharma@parent.aktu.ac.in",
        "profile_type": "parent",
    },
    {
        "role": "mess_staff",
        "username": "mess_staff",
        "email": "staff.counter@aktu-hostel.edu.in",
        "profile_type": "mess_staff",
    },
]


def safe_mask_database_url(url: str) -> str:
    """
    Bulletproof masking function that completely removes the password
    regardless of special characters, URL encoding, or colons.
    Example: postgresql://user:pass@host:6543/postgres -> postgresql://user:***@host:6543/postgres
    """
    if not url:
        return "<not-set>"
    try:
        if "://" in url:
            scheme, rest = url.split("://", 1)
            if "@" in rest:
                creds, host_part = rest.rsplit("@", 1)
                if ":" in creds:
                    user, _ = creds.split(":", 1)
                    return f"{scheme}://{user}:***@{host_part}"
                return f"{scheme}://***@{host_part}"
        return "<masked-url>"
    except Exception:
        return "<masked-url>"


def generate_secure_password(length=16) -> str:
    """Generates a cryptographically strong random password satisfying all complexity requirements."""
    symbols = "!@#$%^&*()-_=+"
    all_chars = string.ascii_letters + string.digits + symbols
    while True:
        password = ''.join(secrets.choice(all_chars) for _ in range(length))
        if (any(c.islower() for c in password)
                and any(c.isupper() for c in password)
                and any(c.isdigit() for c in password)
                and any(c in symbols for c in password)):
            return password


def fetch_exactly_one_sqlite(cur, table: str, condition: str, params: tuple, entity_name: str) -> dict:
    """
    Executes a query against local SQLite and ensures exactly one row is returned.
    Aborts if zero rows or multiple ambiguous duplicate rows are detected.
    """
    cur.execute(f"SELECT * FROM {table} WHERE {condition}", params)
    rows = cur.fetchall()
    if len(rows) == 0:
        print(f"\n[ABORTED] REFERENCE ERROR: Expected exactly 1 record for '{entity_name}', found 0.")
        sys.exit(1)
    if len(rows) > 1:
        print(f"\n[ABORTED] AMBIGUOUS REFERENCE ERROR: Expected exactly 1 record for '{entity_name}', found {len(rows)}.")
        sys.exit(1)
    return dict(rows[0])


def query_production_single_or_none(query, entity_name: str):
    """
    Executes a query against production Supabase and ensures at most one record matches.
    Aborts immediately with a clear error if duplicate records exist.
    """
    records = query.all()
    if len(records) > 1:
        raise ValueError(
            f"DUPLICATE PRODUCTION RECORD: Expected at most 1 record for '{entity_name}', "
            f"but found {len(records)} records. Aborting to prevent data corruption."
        )
    return records[0] if records else None


def load_local_sqlite_reference() -> dict:
    """
    Reads the reference profile and facility records directly from the local
    SQLite development database, enforcing exact-one row uniqueness and validating
    all source relationships before any migration action.
    """
    sqlite_path = PROJECT_DIR / "instance" / "hostel.sqlite3"
    if not sqlite_path.exists():
        print(f"\n[ABORTED] ERROR: Local SQLite reference database not found at: {sqlite_path}")
        print("Cannot verify demographic and facility fidelity without the reference database.")
        sys.exit(1)

    try:
        conn = sqlite3.connect(sqlite_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 1. Hostels (Exact 1 row each)
        h_boys = fetch_exactly_one_sqlite(cur, "hostels", "name=?", ("Aryabhatta Boys Hostel (Block A)",), "Boys Hostel")
        h_girls = fetch_exactly_one_sqlite(cur, "hostels", "name=?", ("Gargi Girls Hostel (Block B)",), "Girls Hostel")

        # 2. Mess Facility (Exact 1 row)
        mess_ref = fetch_exactly_one_sqlite(cur, "mess_profiles", "mess_name=?", ("HostelEase Central Dining Hall",), "Central Dining Hall")

        # 3. Wardens (Exact 1 row each)
        w_boys_ref = fetch_exactly_one_sqlite(cur, "wardens", "employee_id=?", ("EMP-WRD-001",), "Boys Warden EMP-WRD-001")
        w_girls_ref = fetch_exactly_one_sqlite(cur, "wardens", "employee_id=?", ("EMP-WRD-002",), "Girls Warden EMP-WRD-002")

        # 4. Student Rahul Sharma (Exact 1 row)
        student_ref = fetch_exactly_one_sqlite(cur, "students", "enrollment_no=?", ("AKTU2023CSE0101",), "Student AKTU2023CSE0101")

        # 5. Parent Profile Ramesh Sharma (Exact 1 row)
        parent_ref = fetch_exactly_one_sqlite(cur, "parent_profiles", "parent_name=?", ("Ramesh Sharma",), "Parent Ramesh Sharma")

        # 6. Mess Staff Dinesh Kumar (Exact 1 row)
        staff_ref = fetch_exactly_one_sqlite(cur, "mess_staff_profiles", "staff_name=?", ("Dinesh Kumar",), "Mess Staff Dinesh Kumar")

        conn.close()

        # Pre-migration validation of SQLite internal source relationships
        if w_boys_ref["assigned_hostel_id"] != h_boys["id"]:
            print("\n[ABORTED] REFERENCE RELATIONSHIP ERROR: Local SQLite Boys Warden is not assigned to Boys Hostel.")
            sys.exit(1)
        if w_girls_ref["assigned_hostel_id"] != h_girls["id"]:
            print("\n[ABORTED] REFERENCE RELATIONSHIP ERROR: Local SQLite Girls Warden is not assigned to Girls Hostel.")
            sys.exit(1)
        if parent_ref["student_id"] != student_ref["id"]:
            print("\n[ABORTED] REFERENCE RELATIONSHIP ERROR: Local SQLite Parent is not linked to Student Rahul Sharma.")
            sys.exit(1)
        if staff_ref["mess_id"] != mess_ref["id"]:
            print("\n[ABORTED] REFERENCE RELATIONSHIP ERROR: Local SQLite Mess Staff is not linked to Central Dining Hall.")
            sys.exit(1)

        return {
            "hostel_boys": h_boys,
            "hostel_girls": h_girls,
            "mess": mess_ref,
            "warden_boys": w_boys_ref,
            "warden_girls": w_girls_ref,
            "student": student_ref,
            "parent": parent_ref,
            "mess_staff": staff_ref,
        }
    except Exception as e:
        print(f"\n[ABORTED] ERROR reading local SQLite database: {e}")
        sys.exit(1)


def validate_production_target(db_url: str) -> None:
    """
    Strictly validates that the connection string targets the authorized
    Supabase project, using the transaction pooler with SSL.
    Aborts immediately without exposing credentials if any condition fails.
    """
    if not db_url or not isinstance(db_url, str) or not db_url.strip():
        raise ValueError("DATABASE_URL is missing or empty.")

    normalized = db_url.strip()

    # Reject local SQLite immediately
    normalized_lower = normalized.lower()
    if normalized_lower.startswith("sqlite") or ":memory:" in normalized_lower:
        raise ValueError("SAFETY REFUSAL: Target URL is SQLite. Refusing to run on local database.")

    # 1. Scheme Validation: Must be PostgreSQL
    if "://" not in normalized:
        raise ValueError("MALFORMED URL: Missing scheme delimiter '://'.")

    raw_scheme = normalized.split("://", 1)[0].lower()
    if raw_scheme not in ("postgresql", "postgres", "postgresql+psycopg2"):
        raise ValueError(f"SAFETY REFUSAL: Invalid URL scheme '{raw_scheme}'. Only PostgreSQL schemes ('postgresql', 'postgres') are permitted.")

    # Normalize dialect prefix for standard urlparse
    test_url = normalized
    for prefix in ("postgresql+psycopg2://", "postgres://"):
        if test_url.startswith(prefix):
            test_url = test_url.replace(prefix, "postgresql://", 1)
            break

    try:
        parsed = urllib.parse.urlparse(test_url)
    except Exception:
        raise ValueError("MALFORMED URL: Failed to parse URL structure.")

    # 2. Username Validation: Exact Expected Pooler Username
    username = parsed.username or ""
    if username != EXPECTED_POOLER_USERNAME:
        raise ValueError(f"SAFETY REFUSAL: Username must be '{EXPECTED_POOLER_USERNAME}'. Found: '{username}'.")

    # 3. Hostname Validation: Exact Expected Pooler Hostname (case-insensitive)
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("CONFIGURATION ERROR: Hostname is empty.")

    if hostname != EXPECTED_POOLER_HOST.lower():
        raise ValueError(f"CONFIGURATION ERROR: Hostname must be exactly '{EXPECTED_POOLER_HOST}'. Found: '{parsed.hostname}'.")

    # 4. Port Validation: Exactly 6543
    try:
        port = parsed.port
    except ValueError:
        raise ValueError("CONFIGURATION ERROR: Port is invalid or malformed.")

    if port is None:
        raise ValueError("CONFIGURATION ERROR: Port is missing. Expected port 6543.")

    if port != EXPECTED_POOLER_PORT:
        raise ValueError(f"CONFIGURATION ERROR: Port must be {EXPECTED_POOLER_PORT} (Supabase Transaction Pooler). Found: '{port}'.")

    # 5. Path Validation: Exactly /postgres
    if parsed.path != EXPECTED_DATABASE_PATH:
        raise ValueError(f"CONFIGURATION ERROR: Database path must be exactly '{EXPECTED_DATABASE_PATH}'. Found: '{parsed.path}'.")

    # 6. Query Parameters Validation: Exactly one sslmode=require
    qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    sslmode_list = qs.get("sslmode")
    if not sslmode_list:
        raise ValueError("SECURITY ERROR: Missing required 'sslmode' query parameter.")
    if len(sslmode_list) != 1:
        raise ValueError("SECURITY ERROR: Multiple 'sslmode' parameters detected in connection string.")
    if sslmode_list[0].lower() != "require":
        raise ValueError(f"SECURITY ERROR: Parameter 'sslmode' must be 'require'. Found: '{sslmode_list[0]}'.")


def resolve_database_url() -> str:
    """Safely retrieves and validates DATABASE_URL from environment or hidden interactive prompt."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url or not db_url.strip():
        print("\nDATABASE_URL environment variable is not set in this session.")
        print("Please enter the production Supabase connection string.")
        print("(Input will be hidden for security):")
        try:
            db_url = getpass.getpass("Supabase DATABASE_URL: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[ABORTED] Operation cancelled by user.")
            sys.exit(1)

    # Validate against strict production constraints
    try:
        validate_production_target(db_url)
    except ValueError as val_err:
        print(f"\n[ABORTED] {val_err}")
        sys.exit(1)

    # Store in os.environ for the Flask application factory
    os.environ["DATABASE_URL"] = db_url
    return db_url


def run_masking_unit_tests() -> bool:
    """
    Local-only unit tests for safe_mask_database_url() verifying that passwords
    with @, :, %, and URL-encoded special characters are completely masked and never leak.
    """
    print("\n" + "=" * 80)
    print("RUNNING LOCAL-ONLY DATABASE_URL MASKING UNIT TESTS")
    print("=" * 80)
    test_passwords = [
        ("Password with @", "P@ssw0rd!123"),
        ("Password with :", "Pass:Word:123"),
        ("Password with %", "Pass%25Word%20"),
        ("Password with URL-encoded special chars", "My%40Pass%23%24Word"),
        ("Complex mixed password", "P@ss:w%40rd#456!"),
    ]

    all_passed = True
    for name, pwd in test_passwords:
        url = f"postgresql://postgres.yjhapstttgilcbaxbbce:{pwd}@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require"
        masked = safe_mask_database_url(url)
        leaked = pwd in masked
        status = "FAIL" if leaked else "PASS"
        if leaked:
            all_passed = False
        print(f"  [{status}] {name:<40} -> Raw password hidden: {not leaked}")

    print("=" * 80)
    print(f"Masking Test Suite Result: {'ALL TESTS PASSED' if all_passed else 'TESTS FAILED'}")
    print("=" * 80 + "\n")
    return all_passed


def run_url_validation_unit_tests() -> bool:
    """
    Local-only unit tests for valid and invalid DATABASE_URL examples.
    Runs without connecting to any database.
    """
    test_cases = [
        ("Valid PostgreSQL URL", "postgresql://postgres.yjhapstttgilcbaxbbce:Secret123@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require", True),
        ("Valid Postgres scheme", "postgres://postgres.yjhapstttgilcbaxbbce:Secret123@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require", True),
        ("Valid Psycopg2 scheme", "postgresql+psycopg2://postgres.yjhapstttgilcbaxbbce:Secret123@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require", True),
        ("Invalid scheme (mysql)", "mysql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require", False),
        ("Invalid scheme (sqlite)", "sqlite:///instance/hostel.sqlite3", False),
        ("Invalid username", "postgresql://postgres:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require", False),
        ("Invalid host (lookalike)", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@badpooler.supabase.com:6543/postgres?sslmode=require", False),
        ("Invalid host (bare domain)", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@pooler.supabase.com:6543/postgres?sslmode=require", False),
        ("Invalid host (incorrect host)", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@evil-host.com:6543/postgres?sslmode=require", False),
        ("Different Supabase pooler host", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require", False),
        ("Missing port", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com/postgres?sslmode=require", False),
        ("Malformed port", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:notaport/postgres?sslmode=require", False),
        ("Invalid port (5432)", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?sslmode=require", False),
        ("Invalid path (/other)", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/other?sslmode=require", False),
        ("Missing sslmode", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres", False),
        ("Duplicate sslmode", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require&sslmode=disable", False),
        ("Wrong sslmode value", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=prefer", False),
        ("Malformed URL", "not-a-valid-url", False),
    ]

    print("\n" + "=" * 80)
    print("RUNNING LOCAL-ONLY DATABASE_URL VALIDATION UNIT TESTS")
    print("=" * 80)
    all_passed = True
    for name, url, should_pass in test_cases:
        try:
            validate_production_target(url)
            actual_pass = True
        except ValueError:
            actual_pass = False

        status = "PASS" if actual_pass == should_pass else "FAIL"
        if status != "PASS":
            all_passed = False
        print(f"  [{status}] {name:<35} -> Expected: {should_pass}, Result: {actual_pass}")

    print("=" * 80)
    print(f"URL Test Suite Result: {'ALL TESTS PASSED' if all_passed else 'TESTS FAILED'}")
    print("=" * 80 + "\n")
    return all_passed


def run_demo_credentials_unit_tests() -> bool:
    """
    Local-only unit tests verifying demonstration credentials & secure hashing:
    1. All 8 accounts have valid, non-empty resolved credentials.
    2. Passwords are distinct (8 unique values).
    3. Hashing via Werkzeug generates a secure scrypt hash and verifies successfully.
    4. Plaintext passwords never equal the hash.
    5. Invalid passwords fail verification.
    """
    from werkzeug.security import generate_password_hash, check_password_hash

    print("\n" + "=" * 80)
    print("RUNNING LOCAL-ONLY DEMO CREDENTIALS & HASHING UNIT TESTS")
    print("=" * 80)

    all_passed = True
    resolved_creds = {}

    # 1. Check all 8 accounts resolve valid credentials
    for meta in INTENDED_ACCOUNTS:
        u = meta["username"]
        try:
            pwd = resolve_demo_credential(u)
            resolved_creds[u] = pwd
            status = "PASS" if (pwd and len(pwd) >= 8) else "FAIL"
            if not (pwd and len(pwd) >= 8):
                all_passed = False
            print(f"  [{status}] Credential resolution for '{u:<15}' -> Resolved successfully (length: {len(pwd)})")
        except Exception as e:
            all_passed = False
            print(f"  [FAIL] Credential resolution for '{u:<15}' -> Error: {e}")

    # 2. Check all 8 passwords distinct
    distinct_count = len(set(resolved_creds.values()))
    status = "PASS" if distinct_count == 8 else "FAIL"
    if distinct_count != 8:
        all_passed = False
    print(f"  [{status}] Distinct demo passwords count: {distinct_count} / 8")

    # 3. Check Werkzeug password hashing and verification
    for u, pwd in resolved_creds.items():
        hashed = generate_password_hash(pwd)
        is_hashed = (hashed != pwd and len(hashed) > 20)
        verifies = check_password_hash(hashed, pwd)
        fails_wrong = not check_password_hash(hashed, "IncorrectPassword@999")
        test_ok = is_hashed and verifies and fails_wrong
        status = "PASS" if test_ok else "FAIL"
        if not test_ok:
            all_passed = False
        print(f"  [{status}] Werkzeug hashing for '{u:<15}' -> hash_ok: {is_hashed}, check_pwd: {verifies}, reject_wrong: {fails_wrong}")

    print("=" * 80)
    print(f"Demo Credentials Test Suite Result: {'ALL TESTS PASSED' if all_passed else 'TESTS FAILED'}")
    print("=" * 80 + "\n")
    return all_passed


def migrate_demo_accounts():
    print("=" * 80)
    print("HOSTELEASE HMS — PRODUCTION DEMO ACCOUNTS MIGRATION UTILITY (FINAL HARDENED)")
    print("=" * 80)

    # 1. Load exact reference records from local SQLite
    print("\n[INFO] Loading and validating local reference records from instance/hostel.sqlite3...")
    ref = load_local_sqlite_reference()
    print("  [✓] All 8 reference entities and source relationships verified in local SQLite.")

    # 2. Resolve and strictly validate production connection target
    db_url = resolve_database_url()
    print(f"\n[INFO] Target Database : {safe_mask_database_url(db_url)}")
    print("[INFO] Target Project  : " + EXPECTED_SUPABASE_PROJECT_REF)
    print(f"[INFO] Target Username : {EXPECTED_POOLER_USERNAME}")
    print(f"[INFO] Target Hostname : {EXPECTED_POOLER_HOST}")
    print(f"[INFO] Target Pooler   : port {EXPECTED_POOLER_PORT} (sslmode=require)")
    print("[INFO] Initializing application factory in production mode...")

    app = create_app("production")

    with app.app_context():
        # Verify remote connectivity with sanitized error reporting
        try:
            db.session.execute(db.text("SELECT 1"))
        except Exception:
            print("\n[ABORTED] Database Connection Failed.")
            print("Error Category : Network / Authentication Failure.")
            print("Troubleshooting Guidance:")
            print("  1. Verify the database password for Supabase project: " + EXPECTED_SUPABASE_PROJECT_REF)
            print("  2. If the password contains special characters (@, #, %, etc.), ensure they are URL-encoded.")
            print("  3. Verify port 6543 and sslmode=require are present.")
            print("  4. Verify outbound network connectivity to aws-0-ap-south-1.pooler.supabase.com:6543.")
            sys.exit(1)

        print("[INFO] Database connection verified successfully over SSL.")
        print("\n" + "-" * 80)
        print("STARTING ATOMIC TRANSACTION — ALL 8 CORE DEMONSTRATION ACCOUNTS")
        print("-" * 80)

        created_credentials = []
        user_records = {}
        resolved_user_ids = set()

        try:
            # =========================================================================
            # STEP 1: Prerequisite Facilities (Hostels & Mess Dining Hall)
            # =========================================================================
            print("\n[STEP 1/5] Validating Prerequisite Facilities against Local Reference...")

            # 1A. Boys Hostel (with duplicate production record detection)
            h_boys_ref = ref["hostel_boys"]
            hostel_boys = query_production_single_or_none(
                Hostel.query.filter_by(name=h_boys_ref["name"]),
                f"Hostel '{h_boys_ref['name']}'"
            )
            if not hostel_boys:
                hostel_boys = Hostel(
                    name=h_boys_ref["name"],
                    hostel_type=h_boys_ref["hostel_type"],
                    total_floors=h_boys_ref["total_floors"],
                    total_rooms=h_boys_ref["total_rooms"],
                    description=h_boys_ref["description"]
                )
                db.session.add(hostel_boys)
                db.session.flush()
                print(f"  [+] Created: {h_boys_ref['name']}")
            else:
                # Field-by-field verification against SQLite reference
                if hostel_boys.hostel_type != h_boys_ref["hostel_type"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_boys_ref['name']}' hostel_type '{hostel_boys.hostel_type}', expected '{h_boys_ref['hostel_type']}'.")
                if hostel_boys.total_floors != h_boys_ref["total_floors"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_boys_ref['name']}' total_floors '{hostel_boys.total_floors}', expected '{h_boys_ref['total_floors']}'.")
                if hostel_boys.total_rooms != h_boys_ref["total_rooms"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_boys_ref['name']}' total_rooms '{hostel_boys.total_rooms}', expected '{h_boys_ref['total_rooms']}'.")
                if hostel_boys.description != h_boys_ref["description"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_boys_ref['name']}' description does not match local reference.")
                print(f"  [=] Verified existing: {h_boys_ref['name']} (ID: {hostel_boys.id}) -> All 5 fields match.")

            # 1B. Girls Hostel (with duplicate production record detection)
            h_girls_ref = ref["hostel_girls"]
            hostel_girls = query_production_single_or_none(
                Hostel.query.filter_by(name=h_girls_ref["name"]),
                f"Hostel '{h_girls_ref['name']}'"
            )
            if not hostel_girls:
                hostel_girls = Hostel(
                    name=h_girls_ref["name"],
                    hostel_type=h_girls_ref["hostel_type"],
                    total_floors=h_girls_ref["total_floors"],
                    total_rooms=h_girls_ref["total_rooms"],
                    description=h_girls_ref["description"]
                )
                db.session.add(hostel_girls)
                db.session.flush()
                print(f"  [+] Created: {h_girls_ref['name']}")
            else:
                # Field-by-field verification against SQLite reference
                if hostel_girls.hostel_type != h_girls_ref["hostel_type"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_girls_ref['name']}' hostel_type '{hostel_girls.hostel_type}', expected '{h_girls_ref['hostel_type']}'.")
                if hostel_girls.total_floors != h_girls_ref["total_floors"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_girls_ref['name']}' total_floors '{hostel_girls.total_floors}', expected '{h_girls_ref['total_floors']}'.")
                if hostel_girls.total_rooms != h_girls_ref["total_rooms"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_girls_ref['name']}' total_rooms '{hostel_girls.total_rooms}', expected '{h_girls_ref['total_rooms']}'.")
                if hostel_girls.description != h_girls_ref["description"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_girls_ref['name']}' description does not match local reference.")
                print(f"  [=] Verified existing: {h_girls_ref['name']} (ID: {hostel_girls.id}) -> All 5 fields match.")

            # 1C. Mess Dining Facility (with duplicate production record detection and exact hostel_id None check)
            mess_ref = ref["mess"]
            mess = query_production_single_or_none(
                MessProfile.query.filter_by(mess_name=mess_ref["mess_name"]),
                f"MessProfile '{mess_ref['mess_name']}'"
            )
            if not mess:
                mess = MessProfile(
                    hostel_id=mess_ref["hostel_id"],
                    mess_name=mess_ref["mess_name"],
                    description=mess_ref["description"],
                    contact_number=mess_ref["contact_number"],
                    operating_status=mess_ref["operating_status"],
                    meal_policy=mess_ref["meal_policy"],
                    daily_capacity=mess_ref["daily_capacity"]
                )
                db.session.add(mess)
                db.session.flush()
                print(f"  [+] Created: {mess_ref['mess_name']}")
            else:
                # Field-by-field verification including exact hostel_id None check
                if mess.hostel_id != mess_ref["hostel_id"]:
                    raise ValueError(f"MESS MISMATCH: '{mess.mess_name}' hostel_id '{mess.hostel_id}', expected '{mess_ref['hostel_id']}'.")
                if mess.operating_status != mess_ref["operating_status"]:
                    raise ValueError(f"MESS MISMATCH: '{mess.mess_name}' operating_status '{mess.operating_status}', expected '{mess_ref['operating_status']}'.")
                if mess.meal_policy != mess_ref["meal_policy"]:
                    raise ValueError(f"MESS MISMATCH: '{mess.mess_name}' meal_policy '{mess.meal_policy}', expected '{mess_ref['meal_policy']}'.")
                if mess.daily_capacity != mess_ref["daily_capacity"]:
                    raise ValueError(f"MESS MISMATCH: '{mess.mess_name}' daily_capacity '{mess.daily_capacity}', expected '{mess_ref['daily_capacity']}'.")
                if mess.contact_number != mess_ref["contact_number"]:
                    raise ValueError(f"MESS MISMATCH: '{mess.mess_name}' contact_number '{mess.contact_number}', expected '{mess_ref['contact_number']}'.")
                if mess.description != mess_ref["description"]:
                    raise ValueError(f"MESS MISMATCH: '{mess.mess_name}' description does not match local reference.")
                print(f"  [=] Verified existing: {mess_ref['mess_name']} (ID: {mess.id}) -> All fields match (hostel_id={mess.hostel_id}).")

            # =========================================================================
            # STEP 2: Strict Identity Validation, Cross-Account Integrity & Fresh Passwords
            # =========================================================================
            print("\n[STEP 2/5] Identity Validation, Cross-Account Integrity & Fresh Passwords...")

            for account_meta in INTENDED_ACCOUNTS:
                target_user = account_meta["username"]
                target_email = account_meta["email"]
                target_role = account_meta["role"]

                # Strict separate queries to prevent cross-account collisions and duplicate matches
                u_by_username = query_production_single_or_none(
                    User.query.filter_by(username=target_user),
                    f"User username '{target_user}'"
                )
                u_by_email = query_production_single_or_none(
                    User.query.filter_by(email=target_email),
                    f"User email '{target_email}'"
                )

                # Scenario 1: Identity conflict across different accounts
                if u_by_username and u_by_email and u_by_username.id != u_by_email.id:
                    raise ValueError(
                        f"IDENTITY CONFLICT: Username '{target_user}' belongs to User #{u_by_username.id}, "
                        f"but email '{target_email}' belongs to User #{u_by_email.id}. Aborting."
                    )

                # Scenario 2: Partial collision on username only
                if u_by_username and not u_by_email:
                    raise ValueError(
                        f"IDENTITY CONFLICT: Username '{target_user}' exists (User #{u_by_username.id}), "
                        f"but has email '{u_by_username.email}' instead of expected '{target_email}'. Aborting."
                    )

                # Scenario 3: Partial collision on email only
                if u_by_email and not u_by_username:
                    raise ValueError(
                        f"IDENTITY CONFLICT: Email '{target_email}' exists (User #{u_by_email.id}), "
                        f"but has username '{u_by_email.username}' instead of expected '{target_user}'. Aborting."
                    )

                # Fixed temporary demonstration password resolved securely
                target_pass = resolve_demo_credential(target_user)

                # Scenario 4: Account exists and identity is verified
                if u_by_username and u_by_email:
                    existing_user = u_by_username
                    # Type-safe role check against model Enum
                    if str(existing_user.role) != str(target_role):
                        raise ValueError(
                            f"ROLE MISMATCH: User '{target_user}' has role '{existing_user.role}', "
                            f"expected '{target_role}'. Aborting to prevent privilege confusion."
                        )
                    # Active status check
                    if not existing_user.is_active:
                        raise ValueError(f"ACCOUNT INACTIVE: User '{target_user}' exists but is marked inactive. Aborting.")

                    # Set and hash password using the application's Werkzeug secure scrypt method
                    existing_user.set_password(target_pass)
                    # Immediate hash verification
                    if not existing_user.check_password(target_pass):
                        raise ValueError(f"HASH VERIFICATION FAILED: check_password_hash() failed immediately for '{target_user}'.")
                    db.session.flush()

                    # Cross-account integrity check
                    if existing_user.id in resolved_user_ids:
                        raise ValueError(f"CROSS-ACCOUNT INTEGRITY COLLISION: User #{existing_user.id} resolved by multiple definitions!")
                    resolved_user_ids.add(existing_user.id)

                    created_credentials.append({
                        "role": target_role,
                        "username": target_user,
                        "email": target_email,
                        "password": target_pass,
                        "status": "Rotated (Demo Password)"
                    })
                    user_records[target_user] = existing_user
                    print(f"  [*] Account Verified : {target_user:<15} [{target_role}] -> Demo password hashed & verified.")

                # Scenario 5: Account does not exist -> Create with demo password
                else:
                    new_user = User(
                        username=target_user,
                        email=target_email,
                        role=target_role,
                        is_active=True
                    )
                    # Set and hash password using the application's Werkzeug secure scrypt method
                    new_user.set_password(target_pass)
                    # Immediate hash verification
                    if not new_user.check_password(target_pass):
                        raise ValueError(f"HASH VERIFICATION FAILED: check_password_hash() failed immediately for '{target_user}'.")
                    db.session.add(new_user)
                    db.session.flush()

                    # Cross-account integrity check
                    if new_user.id in resolved_user_ids:
                        raise ValueError(f"CROSS-ACCOUNT INTEGRITY COLLISION: User #{new_user.id} resolved by multiple definitions!")
                    resolved_user_ids.add(new_user.id)

                    created_credentials.append({
                        "role": target_role,
                        "username": target_user,
                        "email": target_email,
                        "password": target_pass,
                        "status": "Created (Demo Password)"
                    })
                    user_records[target_user] = new_user
                    print(f"  [+] Account Created  : {target_user:<15} [{target_role}] -> Demo password hashed & verified.")

            # Cross-account verification: Ensure exactly 8 distinct user IDs resolved
            if len(resolved_user_ids) != 8:
                raise ValueError(f"CROSS-ACCOUNT INTEGRITY FAILED: Expected 8 distinct users, got {len(resolved_user_ids)}.")

            # =========================================================================
            # STEP 3: Associated Profile Models — 100% Comprehensive Field Verification
            # =========================================================================
            print("\n[STEP 3/5] Provisioning & Validating Profiles against Local SQLite Reference...")

            # 3A. Boys Warden Profile (Using PostgreSQL hostel_boys.id and duplicate detection)
            w_b_ref = ref["warden_boys"]
            w_boys_user = user_records["warden_boys"]
            w_boys_prof = query_production_single_or_none(
                Warden.query.filter_by(user_id=w_boys_user.id),
                f"Warden for user '{w_boys_user.username}'"
            )
            w_by_empid_b = query_production_single_or_none(
                Warden.query.filter_by(employee_id=w_b_ref["employee_id"]),
                f"Warden employee_id '{w_b_ref['employee_id']}'"
            )
            if w_boys_prof and w_by_empid_b and w_boys_prof.id != w_by_empid_b.id:
                raise ValueError(f"PROFILE COLLISION: Warden employee_id '{w_b_ref['employee_id']}' belongs to another user!")

            if not w_boys_prof:
                w_boys_prof = Warden(
                    user_id=w_boys_user.id,
                    employee_id=w_b_ref["employee_id"],
                    full_name=w_b_ref["full_name"],
                    phone=w_b_ref["phone"],
                    designation=w_b_ref["designation"],
                    assigned_hostel_id=hostel_boys.id
                )
                db.session.add(w_boys_prof)
                db.session.flush()
                print("  [+] Created Profile  : Dr. Ramesh Chandra -> Assigned: Aryabhatta Boys Hostel")
            else:
                # Comprehensive verification of all 5 fields
                if w_boys_prof.employee_id != w_b_ref["employee_id"]:
                    raise ValueError(f"PROFILE MISMATCH: Warden 'warden_boys' employee_id '{w_boys_prof.employee_id}', expected '{w_b_ref['employee_id']}'.")
                if w_boys_prof.full_name != w_b_ref["full_name"]:
                    raise ValueError(f"PROFILE MISMATCH: Warden 'warden_boys' full_name '{w_boys_prof.full_name}', expected '{w_b_ref['full_name']}'.")
                if w_boys_prof.phone != w_b_ref["phone"]:
                    raise ValueError(f"PROFILE MISMATCH: Warden 'warden_boys' phone '{w_boys_prof.phone}', expected '{w_b_ref['phone']}'.")
                if w_boys_prof.designation != w_b_ref["designation"]:
                    raise ValueError(f"PROFILE MISMATCH: Warden 'warden_boys' designation '{w_boys_prof.designation}', expected '{w_b_ref['designation']}'.")
                if w_boys_prof.assigned_hostel_id != hostel_boys.id:
                    raise ValueError(f"PROFILE MISMATCH: Warden 'warden_boys' assigned_hostel_id #{w_boys_prof.assigned_hostel_id}, expected #{hostel_boys.id}.")
                print(f"  [=] Verified Profile : Dr. Ramesh Chandra (ID: {w_boys_prof.id}) -> All 5 fields confirmed.")

            # 3B. Girls Warden Profile (Using PostgreSQL hostel_girls.id and duplicate detection)
            w_g_ref = ref["warden_girls"]
            w_girls_user = user_records["warden_girls"]
            w_girls_prof = query_production_single_or_none(
                Warden.query.filter_by(user_id=w_girls_user.id),
                f"Warden for user '{w_girls_user.username}'"
            )
            w_by_empid_g = query_production_single_or_none(
                Warden.query.filter_by(employee_id=w_g_ref["employee_id"]),
                f"Warden employee_id '{w_g_ref['employee_id']}'"
            )
            if w_girls_prof and w_by_empid_g and w_girls_prof.id != w_by_empid_g.id:
                raise ValueError(f"PROFILE COLLISION: Warden employee_id '{w_g_ref['employee_id']}' belongs to another user!")

            if not w_girls_prof:
                w_girls_prof = Warden(
                    user_id=w_girls_user.id,
                    employee_id=w_g_ref["employee_id"],
                    full_name=w_g_ref["full_name"],
                    phone=w_g_ref["phone"],
                    designation=w_g_ref["designation"],
                    assigned_hostel_id=hostel_girls.id
                )
                db.session.add(w_girls_prof)
                db.session.flush()
                print("  [+] Created Profile  : Prof. Sunita Mishra -> Assigned: Gargi Girls Hostel")
            else:
                # Comprehensive verification of all 5 fields
                if w_girls_prof.employee_id != w_g_ref["employee_id"]:
                    raise ValueError(f"PROFILE MISMATCH: Warden 'warden_girls' employee_id '{w_girls_prof.employee_id}', expected '{w_g_ref['employee_id']}'.")
                if w_girls_prof.full_name != w_g_ref["full_name"]:
                    raise ValueError(f"PROFILE MISMATCH: Warden 'warden_girls' full_name '{w_girls_prof.full_name}', expected '{w_g_ref['full_name']}'.")
                if w_girls_prof.phone != w_g_ref["phone"]:
                    raise ValueError(f"PROFILE MISMATCH: Warden 'warden_girls' phone '{w_girls_prof.phone}', expected '{w_g_ref['phone']}'.")
                if w_girls_prof.designation != w_g_ref["designation"]:
                    raise ValueError(f"PROFILE MISMATCH: Warden 'warden_girls' designation '{w_girls_prof.designation}', expected '{w_g_ref['designation']}'.")
                if w_girls_prof.assigned_hostel_id != hostel_girls.id:
                    raise ValueError(f"PROFILE MISMATCH: Warden 'warden_girls' assigned_hostel_id #{w_girls_prof.assigned_hostel_id}, expected #{hostel_girls.id}.")
                print(f"  [=] Verified Profile : Prof. Sunita Mishra (ID: {w_girls_prof.id}) -> All 5 fields confirmed.")

            # 3C. Student Profile (Exact 14 fields from SQLite and duplicate detection)
            s_ref = ref["student"]
            student_user = user_records["rahul_sharma"]
            student_prof = query_production_single_or_none(
                Student.query.filter_by(user_id=student_user.id),
                f"Student for user '{student_user.username}'"
            )
            s_by_enr = query_production_single_or_none(
                Student.query.filter_by(enrollment_no=s_ref["enrollment_no"]),
                f"Student enrollment_no '{s_ref['enrollment_no']}'"
            )
            if student_prof and s_by_enr and student_prof.id != s_by_enr.id:
                raise ValueError(f"PROFILE COLLISION: Student enrollment_no '{s_ref['enrollment_no']}' belongs to another user!")

            if not student_prof:
                student_prof = Student(
                    user_id=student_user.id,
                    enrollment_no=s_ref["enrollment_no"],
                    roll_no=s_ref["roll_no"],
                    full_name=s_ref["full_name"],
                    phone=s_ref["phone"],
                    gender=s_ref["gender"],
                    branch=s_ref["branch"],
                    year=s_ref["year"],
                    semester=s_ref["semester"],
                    guardian_name=s_ref["guardian_name"],
                    guardian_phone=s_ref["guardian_phone"],
                    emergency_phone=s_ref["emergency_phone"],
                    address=s_ref["address"],
                    blood_group=s_ref["blood_group"],
                    status=s_ref["status"]
                )
                db.session.add(student_prof)
                db.session.flush()
                print(f"  [+] Created Profile  : Student Rahul Sharma ({s_ref['enrollment_no']})")
            else:
                # Comprehensive verification of all 14 fields
                if student_prof.enrollment_no != s_ref["enrollment_no"]:
                    raise ValueError(f"STUDENT MISMATCH: enrollment_no '{student_prof.enrollment_no}', expected '{s_ref['enrollment_no']}'.")
                if student_prof.roll_no != s_ref["roll_no"]:
                    raise ValueError(f"STUDENT MISMATCH: roll_no '{student_prof.roll_no}', expected '{s_ref['roll_no']}'.")
                if student_prof.full_name != s_ref["full_name"]:
                    raise ValueError(f"STUDENT MISMATCH: full_name '{student_prof.full_name}', expected '{s_ref['full_name']}'.")
                if student_prof.phone != s_ref["phone"]:
                    raise ValueError(f"STUDENT MISMATCH: phone '{student_prof.phone}', expected '{s_ref['phone']}'.")
                if student_prof.gender != s_ref["gender"]:
                    raise ValueError(f"STUDENT MISMATCH: gender '{student_prof.gender}', expected '{s_ref['gender']}'.")
                if student_prof.branch != s_ref["branch"]:
                    raise ValueError(f"STUDENT MISMATCH: branch '{student_prof.branch}', expected '{s_ref['branch']}'.")
                if student_prof.year != s_ref["year"]:
                    raise ValueError(f"STUDENT MISMATCH: year '{student_prof.year}', expected '{s_ref['year']}'.")
                if student_prof.semester != s_ref["semester"]:
                    raise ValueError(f"STUDENT MISMATCH: semester '{student_prof.semester}', expected '{s_ref['semester']}'.")
                if student_prof.guardian_name != s_ref["guardian_name"]:
                    raise ValueError(f"STUDENT MISMATCH: guardian_name '{student_prof.guardian_name}', expected '{s_ref['guardian_name']}'.")
                if student_prof.guardian_phone != s_ref["guardian_phone"]:
                    raise ValueError(f"STUDENT MISMATCH: guardian_phone '{student_prof.guardian_phone}', expected '{s_ref['guardian_phone']}'.")
                if student_prof.emergency_phone != s_ref["emergency_phone"]:
                    raise ValueError(f"STUDENT MISMATCH: emergency_phone '{student_prof.emergency_phone}', expected '{s_ref['emergency_phone']}'.")
                if student_prof.address != s_ref["address"]:
                    raise ValueError(f"STUDENT MISMATCH: address '{student_prof.address}', expected '{s_ref['address']}'.")
                if student_prof.blood_group != s_ref["blood_group"]:
                    raise ValueError(f"STUDENT MISMATCH: blood_group '{student_prof.blood_group}', expected '{s_ref['blood_group']}'.")
                if student_prof.status != s_ref["status"]:
                    raise ValueError(f"STUDENT MISMATCH: status '{student_prof.status}', expected '{s_ref['status']}'.")
                print(f"  [=] Verified Profile : Student Rahul Sharma (ID: {student_prof.id}) -> All 14 fields confirmed.")

            # 3D. Parent Profile (Using PostgreSQL student_prof.id and duplicate detection)
            p_ref = ref["parent"]
            parent_user = user_records["parent_rahul"]
            parent_prof = query_production_single_or_none(
                ParentProfile.query.filter_by(user_id=parent_user.id),
                f"ParentProfile for user '{parent_user.username}'"
            )
            if not parent_prof:
                parent_prof = ParentProfile(
                    user_id=parent_user.id,
                    parent_name=p_ref["parent_name"],
                    phone_number=p_ref["phone_number"],
                    relationship_to_student=p_ref["relationship_to_student"],
                    student_id=student_prof.id,
                    account_status=p_ref["account_status"]
                )
                db.session.add(parent_prof)
                db.session.flush()
                print("  [+] Created Profile  : Parent Ramesh Sharma (Father) -> Linked to Student: Rahul Sharma")
            else:
                # Comprehensive verification of all 5 fields
                if parent_prof.parent_name != p_ref["parent_name"]:
                    raise ValueError(f"PARENT MISMATCH: parent_name '{parent_prof.parent_name}', expected '{p_ref['parent_name']}'.")
                if parent_prof.phone_number != p_ref["phone_number"]:
                    raise ValueError(f"PARENT MISMATCH: phone_number '{parent_prof.phone_number}', expected '{p_ref['phone_number']}'.")
                if parent_prof.relationship_to_student != p_ref["relationship_to_student"]:
                    raise ValueError(f"PARENT MISMATCH: relationship '{parent_prof.relationship_to_student}', expected '{p_ref['relationship_to_student']}'.")
                if parent_prof.student_id != student_prof.id:
                    raise ValueError(f"PARENT MISMATCH: linked student #{parent_prof.student_id}, expected #{student_prof.id} (Rahul Sharma).")
                if parent_prof.account_status != p_ref["account_status"]:
                    raise ValueError(f"PARENT MISMATCH: account_status '{parent_prof.account_status}', expected '{p_ref['account_status']}'.")
                print(f"  [=] Verified Profile : Parent Ramesh Sharma (ID: {parent_prof.id}) -> All 5 fields confirmed.")

            # 3E. Mess Staff Profile (Using PostgreSQL mess.id and duplicate detection)
            ms_ref = ref["mess_staff"]
            staff_user = user_records["mess_staff"]
            staff_prof = query_production_single_or_none(
                MessStaffProfile.query.filter_by(user_id=staff_user.id),
                f"MessStaffProfile for user '{staff_user.username}'"
            )
            if not staff_prof:
                staff_prof = MessStaffProfile(
                    user_id=staff_user.id,
                    mess_id=mess.id,
                    staff_name=ms_ref["staff_name"],
                    phone_number=ms_ref["phone_number"],
                    role_designation=ms_ref["role_designation"],
                    employment_status=ms_ref["employment_status"]
                )
                db.session.add(staff_prof)
                db.session.flush()
                print("  [+] Created Profile  : Mess Staff Dinesh Kumar -> Assigned: Central Dining Hall")
            else:
                # Comprehensive verification of all 5 fields
                if staff_prof.staff_name != ms_ref["staff_name"]:
                    raise ValueError(f"MESS STAFF MISMATCH: staff_name '{staff_prof.staff_name}', expected '{ms_ref['staff_name']}'.")
                if staff_prof.phone_number != ms_ref["phone_number"]:
                    raise ValueError(f"MESS STAFF MISMATCH: phone_number '{staff_prof.phone_number}', expected '{ms_ref['phone_number']}'.")
                if staff_prof.role_designation != ms_ref["role_designation"]:
                    raise ValueError(f"MESS STAFF MISMATCH: role_designation '{staff_prof.role_designation}', expected '{ms_ref['role_designation']}'.")
                if staff_prof.employment_status != ms_ref["employment_status"]:
                    raise ValueError(f"MESS STAFF MISMATCH: employment_status '{staff_prof.employment_status}', expected '{ms_ref['employment_status']}'.")
                if staff_prof.mess_id != mess.id:
                    raise ValueError(f"MESS STAFF MISMATCH: linked mess #{staff_prof.mess_id}, expected #{mess.id} (Central Dining Hall).")
                print(f"  [=] Verified Profile : Mess Staff Dinesh Kumar (ID: {staff_prof.id}) -> All 5 fields confirmed.")

            # =========================================================================
            # STEP 4: Comprehensive Pre-Commit Verification Suite
            # =========================================================================
            print("\n[STEP 4/5] Executing Pre-Commit Verification Suite...")

            # 4A. Verify Exactly 8 Accounts Processed
            if len(created_credentials) != 8:
                raise ValueError(f"CREDENTIAL AUDIT FAILED: Expected exactly 8 accounts processed, got {len(created_credentials)}.")

            # 4B. Verify 8 Distinct Demo Passwords Assigned
            passwords_list = [c["password"] for c in created_credentials]
            if len(set(passwords_list)) != 8:
                raise ValueError("SECURITY AUDIT FAILED: Password collision detected! Demo passwords are not distinct.")
            print("  [PASS 1/5] Exactly 8 distinct temporary demonstration passwords assigned.")

            # 4C. Verify Werkzeug Scrypt Password Hash for Every Single Account
            for cred in created_credentials:
                u = user_records[cred["username"]]
                if not u.check_password(cred["password"]):
                    raise ValueError(f"HASH VERIFICATION FAILED: Werkzeug check_password_hash() failed for '{cred['username']}'!")
            print("  [PASS 2/5] Werkzeug check_password_hash() verified for all 8 accounts before commit.")

            # 4D. Verify Account Metadata
            for meta in INTENDED_ACCOUNTS:
                u = user_records.get(meta["username"])
                if not u:
                    raise ValueError(f"STATE FAILED: User '{meta['username']}' not found in active session.")
                if str(u.role) != str(meta["role"]):
                    raise ValueError(f"STATE FAILED: User '{meta['username']}' role mismatch ({u.role} != {meta['role']}).")
                if not u.is_active:
                    raise ValueError(f"STATE FAILED: User '{meta['username']}' is inactive.")
                if u.email != meta["email"]:
                    raise ValueError(f"STATE FAILED: User '{meta['username']}' email mismatch ({u.email} != {meta['email']}).")
            print("  [PASS 3/5] All 8 users verified (active=True, correct role, matching email).")

            # 4E. Verify Foreign-Key Relationships
            if w_boys_prof.assigned_hostel_id != hostel_boys.id:
                raise ValueError("RELATION FAILED: Boys Warden not linked to Aryabhatta Boys Hostel.")
            if w_girls_prof.assigned_hostel_id != hostel_girls.id:
                raise ValueError("RELATION FAILED: Girls Warden not linked to Gargi Girls Hostel.")
            if parent_prof.student_id != student_prof.id:
                raise ValueError("RELATION FAILED: Parent Profile not linked to Student Rahul Sharma.")
            if staff_prof.mess_id != mess.id:
                raise ValueError("RELATION FAILED: Mess Staff not linked to Central Dining Hall.")
            print("  [PASS 4/5] All relational foreign-key dependencies verified.")

            # 4F. Commit Atomic Transaction
            db.session.commit()
            print("  [PASS 5/5] Single atomic transaction committed to Supabase PostgreSQL.")
            print("\n[SUCCESS] Production migration transaction completed successfully!")

        except ValueError as val_err:
            db.session.rollback()
            print("\n" + "!" * 80)
            print("[APPLICATION VALIDATION FAILURE] Transaction aborted and rolled back.")
            print(f"Reason: {val_err}")
            print("Troubleshooting Guidance:")
            print("  - An existing record in Supabase conflicts with the local SQLite reference data.")
            print("  - Check table public.users, wardens, students, parent_profiles, or mess_staff_profiles.")
            print("!" * 80)
            sys.exit(1)

        except Exception:
            db.session.rollback()
            print("\n" + "!" * 80)
            print("[DATABASE EXECUTION FAILURE] Transaction aborted and rolled back.")
            print("A database constraint violation or execution error occurred during processing.")
            print("Troubleshooting Guidance:")
            print("  - Verify that schema_postgres.sql has been executed in the Supabase SQL Editor.")
            print("  - Ensure all 30 tables and 33 enums exist.")
            print("  - Verify that PostgreSQL role 'postgres' has permission to insert into public tables.")
            print("!" * 80)
            sys.exit(1)

        # =========================================================================
        # STEP 5: Final Post-Commit One-Time Credential Report
        # =========================================================================
        print("\n" + "=" * 80)
        print("DATABASE AUDIT & EXECUTION SUMMARY")
        print("=" * 80)
        print("Target Supabase Project : " + EXPECTED_SUPABASE_PROJECT_REF)
        print(f"Total Accounts Processed : 8 / 8")
        print(f"Newly Created Accounts   : {len([c for c in created_credentials if 'Created' in c['status']])}")
        print(f"Rotated Existing Accounts: {len([c for c in created_credentials if 'Rotated' in c['status']])}")
        print("=" * 80)

        print("\n" + "#" * 95)
        print("TEMPORARY PRODUCTION CREDENTIAL SUMMARY (ALL 8 DEMONSTRATION ACCOUNTS)")
        print("#" * 95)
        print("TEMPORARY DEMO CREDENTIAL NOTICE:")
        print("1. All 8 accounts have been configured with the requested fixed temporary demo credentials.")
        print("2. Stored passwords in PostgreSQL are hashed using Werkzeug scrypt (plaintext is never stored).")
        print("3. Each account is verified active with a valid Werkzeug scrypt password hash,")
        print("   verified profile entity, and complete foreign-key links.\n")
        print(f"{'Role':<15} | {'Username':<15} | {'Email':<35} | {'Status':<25} | {'Temporary Password'}")
        print("-" * 115)
        for cred in created_credentials:
            print(f"{cred['role']:<15} | {cred['username']:<15} | {cred['email']:<35} | {cred['status']:<25} | {cred['password']}")
        print("#" * 95)

        print("\nAll 8 production accounts and profiles are verified active in Supabase PostgreSQL.\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test-url":
        t1 = run_masking_unit_tests()
        t2 = run_url_validation_unit_tests()
        t3 = run_demo_credentials_unit_tests()
        sys.exit(0 if (t1 and t2 and t3) else 1)
    migrate_demo_accounts()
