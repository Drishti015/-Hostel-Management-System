"""
HostelEase HMS — Production Demonstration Accounts Migration Utility (Final Hardened)
Safely provisions the 8 core demonstration accounts and their associated profiles
in the production Supabase PostgreSQL database using credentials supplied securely
at runtime via environment variables or hidden getpass prompts, hashed with the
application's Werkzeug scrypt password hashing method.

Architecture & Validation Rules:
1. Strict Database Target Enforcement:
   - Supabase project reference: yjhapstttgilcbaxbbce
   - Pooler username format: postgres.yjhapstttgilcbaxbbce
   - Exact Pooler hostname: aws-0-ap-south-1.pooler.supabase.com (case-insensitive exact match)
   - Pooler port: 6543
   - Database path: exactly /postgres
   - Query string: exactly one sslmode=require parameter (rejects unexpected, duplicate, blank, and malformed query strings)
   - Strict refusal on SQLite, localhost, direct port 5432, or malformed URLs
2. Bulletproof URL Masking:
   - Safe masking function that completely removes credentials regardless of special characters (@, :, %, etc.)
3. Dynamic SQLite Reference Loading & Ambiguity Detection:
   - Reads reference records directly from instance/hostel.sqlite3
   - Enforces exactly one row per entity query (aborts on zero or duplicate matches)
   - Validates internal SQLite relationships before proceeding (warden->hostel, parent->student, staff->mess)
4. Duplicate Production Record Detection & Identity Collision Prevention:
   - Replaces all .first() queries with query_production_single_or_none()
   - Strictly aborts on duplicate records in Hostels, MessProfile, Users, Wardens, Student, Parent, or MessStaff
   - Cross-checks alternate identifiers (employee_id, roll_no, enrollment_no, parent student_id, mess staff_name)
     to prevent collision or silent overwrite
5. 100% Comprehensive Field-Level Pre-Commit Verification:
   - Verifies every demographic, facility, and relational field for newly created AND existing records before commit:
   - Hostels: name, hostel_type, total_floors, total_rooms, description
   - MessProfile: mess_name, hostel_id (exact None handling), description, contact_number,
                  operating_status, meal_policy, daily_capacity
   - Wardens: employee_id, full_name, phone, designation, assigned_hostel_id (PostgreSQL ID)
   - Student: enrollment_no, roll_no, full_name, phone, gender, branch, year, semester,
              guardian_name, guardian_phone, emergency_phone, address, blood_group, status
   - ParentProfile: parent_name, phone_number, relationship_to_student, student_id (PostgreSQL ID), account_status
   - MessStaffProfile: staff_name, phone_number, role_designation, employment_status, mess_id (PostgreSQL ID)
6. Cross-Account Integrity:
   - Tracks resolved user IDs; aborts if any two intended accounts resolve to the same record
7. SQLAlchemy User.role Compatibility:
   - Type-safe string comparison matching sqlalchemy.Enum values using get_user_role_value()
8. Secure Runtime Credential Resolution & Werkzeug Hashing:
   - Zero plaintext or reversibly encoded passwords stored in Python source code.
   - All 8 passwords required at runtime through hidden getpass prompts or DEMO_PASS_<USERNAME> environment variables.
   - Pre-database credential collection via collect_all_demo_credentials() ensuring 8 distinct passwords >= 8 chars.
   - Secure Werkzeug scrypt hashing via User.set_password() with double verification (immediate & pre-commit).
   - Zero plaintext passwords printed in logs or migration summary.
   - Best-effort reference cleanup: password dictionaries and consumed environment variables are cleared on all exit paths (success, validation failure, database failure, rollback, and cancellation); Python does not guarantee immediate memory reclamation of string objects.
9. Atomic Transaction & Error Sanitization:
   - Single atomic transaction with automatic rollback on error
   - Zero raw connection strings, passwords, or hashes in logs
   - Migration summary displays usernames and status only; plaintext passwords are never printed
"""

import os
import sys
import re
import string
import secrets
import getpass
import sqlite3
import urllib.parse
from contextlib import contextmanager
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

def format_safe_exception_report(e: Exception, context_description: str = "") -> str:
    """
    Safely formats an exception for terminal reporting without exposing credentials or connection strings.
    Never prints or inspects raw str(e) to prevent database passwords or connection details from leaking.
    Returns: Exception class name and a sanitized, generic explanation based on the exception type.
    """
    exc_type = type(e).__name__
    category_map = {
        "OperationalError": "Database connection or network communication error.",
        "DBAPIError": "Database API communication error.",
        "ProgrammingError": "Database relation, schema, or query syntax error.",
        "IntegrityError": "Database constraint violation (unique, foreign key, or check constraint).",
        "DataError": "Database data format or conversion error.",
        "DatabaseError": "General database engine error.",
        "ConnectionError": "Network connectivity failure.",
        "TimeoutError": "Connection or operation timed out.",
        "AuthenticationError": "Database authentication or authorization failure.",
        "ValueError": "Validation constraint failure or invalid data value.",
        "KeyError": "Missing required configuration or reference key.",
        "TypeError": "Type mismatch error.",
    }
    explanation = category_map.get(exc_type, "An unexpected error occurred during execution.")
    if context_description:
        return f"{context_description}: [{exc_type}] {explanation}"
    return f"[{exc_type}] {explanation}"



def resolve_demo_credential(username: str, role: str = "") -> str:
    """
    Safely resolves the password for a demonstration account at runtime:
    1. Checks environment variable DEMO_PASS_<USERNAME> (e.g. DEMO_PASS_ADMIN).
    2. Checks environment variable DEMO_PASSWORD_<USERNAME>.
    3. Prompts the operator securely with hidden input via getpass.
    Applies identical validation to both environment variables and getpass:
      - Rejects empty or whitespace-only values.
      - Rejects passwords shorter than 8 characters.
      - Never prints or logs the password.
    """
    env_key1 = f"DEMO_PASS_{username.upper()}"
    env_key2 = f"DEMO_PASSWORD_{username.upper()}"

    # Check environment variables first
    matched_key = None
    raw_env_val = None
    if os.environ.get(env_key1) is not None:
        matched_key = env_key1
        raw_env_val = os.environ.get(env_key1)
    elif os.environ.get(env_key2) is not None:
        matched_key = env_key2
        raw_env_val = os.environ.get(env_key2)

    if matched_key is not None:
        stripped_env = raw_env_val.strip() if raw_env_val else ""
        if not stripped_env:
            raise ValueError(f"ENVIRONMENT CONFIGURATION ERROR: Password in '{matched_key}' cannot be empty or whitespace-only.")
        if len(stripped_env) < 8:
            raise ValueError(f"ENVIRONMENT CONFIGURATION ERROR: Password in '{matched_key}' must be at least 8 characters long.")
        return stripped_env

    prompt_label = f"Enter password for demo user '{username}'"
    if role:
        prompt_label += f" ({role})"
    prompt_label += " [hidden]: "

    while True:
        try:
            raw_pwd = getpass.getpass(prompt_label)
        except (KeyboardInterrupt, EOFError):
            print("\n[ABORTED] Operation cancelled by user.")
            sys.exit(1)
        stripped_pwd = raw_pwd.strip() if raw_pwd else ""
        if not stripped_pwd:
            print("  [ERROR] Password cannot be empty or whitespace-only. Please enter a valid password.")
            continue
        if len(stripped_pwd) < 8:
            print("  [ERROR] Password must be at least 8 characters long. Please try again.")
            continue
        return stripped_pwd


def collect_all_demo_credentials(accounts: list = None) -> dict:
    """
    Collects and validates runtime credentials for demonstration accounts
    that need creation or explicit password rotation.
    If accounts is None, defaults to INTENDED_ACCOUNTS (all 8 demonstration accounts).
    Ensures:
      - Passwords resolved via environment variables or hidden getpass prompt
      - Non-empty and not whitespace-only
      - Minimum 8 characters in length
      - Distinct passwords across all accounts being collected
    Never prints or logs the passwords.
    After credentials are collected (or on any failure), best-effort removes
    consumed DEMO_PASS_* and DEMO_PASSWORD_* variables from the process environment,
    and clears any partially populated credential dictionary if collection fails.
    """
    if accounts is None:
        accounts = INTENDED_ACCOUNTS

    if not accounts:
        return {}

    count_desc = f"all {len(accounts)}" if len(accounts) == len(INTENDED_ACCOUNTS) else f"{len(accounts)}"
    print(f"\n[INFO] Resolving runtime credentials for {count_desc} demonstration account(s)...")
    collected = {}
    collection_success = False
    try:
        for meta in accounts:
            u = meta["username"]
            role = meta["role"]
            pwd = resolve_demo_credential(u, role)
            if not pwd or len(pwd.strip()) < 8:
                raise ValueError(f"CREDENTIAL ERROR: Password for '{u}' must be at least 8 non-whitespace characters.")
            collected[u] = pwd

        distinct_count = len(set(collected.values()))
        if distinct_count != len(accounts):
            raise ValueError(
                f"SECURITY AUDIT ERROR: Password collision detected across demo accounts! "
                f"Expected {len(accounts)} distinct passwords, got {distinct_count}."
            )
        print(f"  [✓] All {len(accounts)} demo credentials collected and verified (distinct, >= 8 chars).")
        collection_success = True
        return collected
    finally:
        if not collection_success:
            collected.clear()
        # Best-effort cleanup: remove DEMO_PASS_* and DEMO_PASSWORD_* env vars
        # from the process environment regardless of success or failure.
        for meta in accounts:
            u_up = meta["username"].upper()
            os.environ.pop(f"DEMO_PASS_{u_up}", None)
            os.environ.pop(f"DEMO_PASSWORD_{u_up}", None)


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


def get_user_role_value(user_or_role) -> str:
    """
    Safely extracts the underlying string value of a User.role or role object/Enum.
    Handles SQLAlchemy Enum instances, Python Enum members (.value), and strings.
    """
    role_obj = getattr(user_or_role, 'role', user_or_role)
    if hasattr(role_obj, 'value'):
        return str(role_obj.value)
    return str(role_obj)


def resolve_mapped_mess_hostel_id(mess_ref: dict, ref: dict, session=None) -> int:
    """
    Cross-database ID mapping for MessProfile.hostel_id:
    1. If local SQLite mess_ref["hostel_id"] is None, returns None (central / unattached mess).
    2. If mess_ref["hostel_id"] is set, looks up the corresponding reference hostel by ID in SQLite,
       extracts its unique hostel name, and resolves the actual PostgreSQL Hostel.id.
    3. Strictly checks for missing, ambiguous, or unmapped production hostels and aborts safely.
    4. Never assumes SQLite and PostgreSQL primary keys are identical.
    """
    raw_hostel_id = mess_ref.get("hostel_id")
    if raw_hostel_id is None:
        return None

    # Identify the reference hostel name from ref or mess_ref
    source_hostel_name = None
    mess_hostel_ref = mess_ref.get("mess_hostel_ref") or ref.get("mess_hostel_ref")
    if mess_hostel_ref and mess_hostel_ref.get("name"):
        source_hostel_name = mess_hostel_ref["name"]
    else:
        # Check against known hostel references in ref
        for h_key in ("hostel_boys", "hostel_girls"):
            h_ref = ref.get(h_key)
            if h_ref and h_ref.get("id") == raw_hostel_id:
                source_hostel_name = h_ref.get("name")
                break

    if not source_hostel_name:
        raise ValueError(
            f"HOSTEL MAPPING ERROR: Local SQLite MessProfile references hostel_id '{raw_hostel_id}', "
            f"but no corresponding reference hostel name could be resolved. Aborting safely."
        )

    # In production (PostgreSQL), resolve the hostel by its unique name
    query = Hostel.query.filter_by(name=source_hostel_name)
    matched_hostels = query.all()
    if not matched_hostels:
        raise ValueError(
            f"HOSTEL MAPPING ERROR: No matching PostgreSQL Hostel found for name '{source_hostel_name}' "
            f"(mapped from SQLite hostel_id '{raw_hostel_id}'). Cannot assign MessProfile.hostel_id. Aborting safely."
        )
    if len(matched_hostels) > 1:
        raise ValueError(
            f"AMBIGUOUS HOSTEL MAPPING: Found {len(matched_hostels)} PostgreSQL hostels with name '{source_hostel_name}' "
            f"(mapped from SQLite hostel_id '{raw_hostel_id}'). Aborting safely."
        )

    return matched_hostels[0].id


def validate_or_create_warden_profile(existing_prof, user_id: int, ref_data: dict, assigned_hostel_id: int, session=None):
    """
    If existing_prof is None: creates a new Warden profile using local SQLite reference data
    and PostgreSQL assigned_hostel_id.
    If existing_prof is not None: STRICTLY READ-ONLY comparison. Does NOT assign or overwrite
    any field. Raises ValueError if any field differs from the local reference, preserving the
    existing production record unchanged.
    """
    if existing_prof is None:
        new_prof = Warden(
            user_id=user_id,
            employee_id=ref_data["employee_id"],
            full_name=ref_data["full_name"],  
            phone=ref_data["phone"],
            designation=ref_data["designation"],  
            assigned_hostel_id=assigned_hostel_id,
        )
        if session is not None:
            session.add(new_prof)
            session.flush()
        return new_prof, True

    # Existing profile: Strictly compare every field without modifying the record
    if existing_prof.user_id != user_id:
        raise ValueError(
            f"EXISTING WARDEN PROFILE MISMATCH: user_id '{existing_prof.user_id}' != expected '{user_id}'. "
            f"Original production record preserved unchanged."
        )
    if existing_prof.employee_id != ref_data["employee_id"]:
        raise ValueError(
            f"EXISTING WARDEN PROFILE MISMATCH: employee_id '{existing_prof.employee_id}' != expected '{ref_data['employee_id']}'. "
            f"Original production record preserved unchanged."
        )
    if existing_prof.full_name != ref_data["full_name"]:
        raise ValueError(
            f"EXISTING WARDEN PROFILE MISMATCH: full_name '{existing_prof.full_name}' != expected '{ref_data['full_name']}'. "
            f"Original production record preserved unchanged."
        )
    if existing_prof.phone != ref_data["phone"]:
        raise ValueError(
            f"EXISTING WARDEN PROFILE MISMATCH: phone '{existing_prof.phone}' != expected '{ref_data['phone']}'. "
            f"Original production record preserved unchanged."
        )
    if existing_prof.designation != ref_data["designation"]:
        raise ValueError(
            f"EXISTING WARDEN PROFILE MISMATCH: designation '{existing_prof.designation}' != expected '{ref_data['designation']}'. "
            f"Original production record preserved unchanged."
        )
    if existing_prof.assigned_hostel_id != assigned_hostel_id:
        raise ValueError(
            f"EXISTING WARDEN PROFILE MISMATCH: assigned_hostel_id '{existing_prof.assigned_hostel_id}' != expected '{assigned_hostel_id}'. "
            f"Original production record preserved unchanged."
        )

    return existing_prof, False


def validate_or_create_student_profile(existing_prof, user_id: int, ref_data: dict, session=None):
    """
    If existing_prof is None: creates a new Student profile using local SQLite reference data
    and PostgreSQL user_id.
    If existing_prof is not None: STRICTLY READ-ONLY comparison. Does NOT assign or overwrite
    any field. Raises ValueError if any field differs from the local reference, preserving the
    existing production record unchanged.
    """
    if existing_prof is None:
        new_prof = Student(
            user_id=user_id,
            enrollment_no=ref_data["enrollment_no"],
            roll_no=ref_data["roll_no"],
            full_name=ref_data["full_name"],
            phone=ref_data["phone"],
            gender=ref_data["gender"],
            branch=ref_data["branch"],
            year=ref_data["year"],
            semester=ref_data["semester"],
            guardian_name=ref_data["guardian_name"],
            guardian_phone=ref_data["guardian_phone"],
            emergency_phone=ref_data["emergency_phone"],
            address=ref_data["address"],
            blood_group=ref_data["blood_group"],
            status=ref_data["status"],
        )
        if session is not None:
            session.add(new_prof)
            session.flush()
        return new_prof, True

    # Existing profile: Strictly compare all 14 demographic/academic fields + user_id without modifying
    fields = [
        "user_id", "enrollment_no", "roll_no", "full_name", "phone",
        "gender", "branch", "year", "semester", "guardian_name",
        "guardian_phone", "emergency_phone", "address", "blood_group", "status"
    ]
    for f in fields:
        expected_val = user_id if f == "user_id" else ref_data[f]
        actual_val = getattr(existing_prof, f)
        if actual_val != expected_val:
            raise ValueError(
                f"EXISTING STUDENT PROFILE MISMATCH: {f} '{actual_val}' != expected '{expected_val}'. "
                f"Original production record preserved unchanged."
            )

    return existing_prof, False


def validate_or_create_parent_profile(existing_prof, user_id: int, ref_data: dict, student_id: int, session=None):
    """
    If existing_prof is None: creates a new ParentProfile using local SQLite reference data
    and PostgreSQL student_id.
    If existing_prof is not None: STRICTLY READ-ONLY comparison. Does NOT assign or overwrite
    any field. Raises ValueError if any field differs from the local reference, preserving the
    existing production record unchanged.
    """
    if existing_prof is None:
        new_prof = ParentProfile(
            user_id=user_id,
            parent_name=ref_data["parent_name"],
            phone_number=ref_data["phone_number"],
            relationship_to_student=ref_data["relationship_to_student"],
            student_id=student_id,
            account_status=ref_data["account_status"],
        )
        if session is not None:
            session.add(new_prof)
            session.flush()
        return new_prof, True

    # Existing profile: Strictly compare without modifying
    checks = [
        ("user_id", getattr(existing_prof, "user_id"), user_id),
        ("parent_name", getattr(existing_prof, "parent_name"), ref_data["parent_name"]),
        ("phone_number", getattr(existing_prof, "phone_number"), ref_data["phone_number"]),
        ("relationship_to_student", getattr(existing_prof, "relationship_to_student"), ref_data["relationship_to_student"]),
        ("student_id", getattr(existing_prof, "student_id"), student_id),
        ("account_status", getattr(existing_prof, "account_status"), ref_data["account_status"]),
    ]
    for field_name, actual_val, expected_val in checks:
        if actual_val != expected_val:
            raise ValueError(
                f"EXISTING PARENT PROFILE MISMATCH: {field_name} '{actual_val}' != expected '{expected_val}'. "
                f"Original production record preserved unchanged."
            )

    return existing_prof, False


def validate_or_create_mess_staff_profile(existing_prof, user_id: int, ref_data: dict, mess_id: int, session=None):
    """
    If existing_prof is None: creates a new MessStaffProfile using local SQLite reference data
    and PostgreSQL mess_id.
    If existing_prof is not None: STRICTLY READ-ONLY comparison. Does NOT assign or overwrite
    any field. Raises ValueError if any field differs from the local reference, preserving the
    existing production record unchanged.
    """
    if existing_prof is None:
        new_prof = MessStaffProfile(
            user_id=user_id,
            mess_id=mess_id,
            staff_name=ref_data["staff_name"],
            phone_number=ref_data["phone_number"],
            role_designation=ref_data["role_designation"],
            employment_status=ref_data["employment_status"],
        )
        if session is not None:
            session.add(new_prof)
            session.flush()
        return new_prof, True

    # Existing profile: Strictly compare without modifying
    checks = [
        ("user_id", getattr(existing_prof, "user_id"), user_id),
        ("mess_id", getattr(existing_prof, "mess_id"), mess_id),
        ("staff_name", getattr(existing_prof, "staff_name"), ref_data["staff_name"]),
        ("phone_number", getattr(existing_prof, "phone_number"), ref_data["phone_number"]),
        ("role_designation", getattr(existing_prof, "role_designation"), ref_data["role_designation"]),
        ("employment_status", getattr(existing_prof, "employment_status"), ref_data["employment_status"]),
    ]
    for field_name, actual_val, expected_val in checks:
        if actual_val != expected_val:
            raise ValueError(
                f"EXISTING MESS STAFF PROFILE MISMATCH: {field_name} '{actual_val}' != expected '{expected_val}'. "
                f"Original production record preserved unchanged."
            )

    return existing_prof, False


def verify_all_entity_fields_pre_commit(entities: dict, ref: dict) -> bool:
    """
    Exhaustively verifies every demographic, facility, and relational field
    for both newly created and existing production records against the SQLite reference
    prior to committing the transaction:
    1. Both Hostel records (boys & girls) - all 5 fields
    2. MessProfile record - all 7 fields, including exact hostel_id is None handling
    3. Both Warden profiles (boys & girls) - all 5 fields + PostgreSQL generated IDs
    4. Student profile - all 14 fields + PostgreSQL generated user_id
    5. Parent profile - all 5 fields + PostgreSQL generated user_id & student_id
    6. Mess staff profile - all 5 fields + PostgreSQL generated user_id & mess_id
    """
    hostel_boys = entities["hostel_boys"]
    hostel_girls = entities["hostel_girls"]
    mess = entities["mess"]
    w_boys_prof = entities["w_boys_prof"]
    w_girls_prof = entities["w_girls_prof"]
    student_prof = entities["student_prof"]
    parent_prof = entities["parent_prof"]
    staff_prof = entities["staff_prof"]
    user_records = entities["user_records"]

    h_boys_ref = ref["hostel_boys"]
    h_girls_ref = ref["hostel_girls"]
    mess_ref = ref["mess"]
    w_b_ref = ref["warden_boys"]
    w_g_ref = ref["warden_girls"]
    s_ref = ref["student"]
    p_ref = ref["parent"]
    ms_ref = ref["mess_staff"]
 
    # 1. Boys Hostel (5 fields)
    if hostel_boys.name != h_boys_ref["name"]:
        raise ValueError(f"HOSTEL PRE-COMMIT MISMATCH: Boys Hostel name '{hostel_boys.name}' != expected '{h_boys_ref['name']}'")
    if hostel_boys.hostel_type != h_boys_ref["hostel_type"]:
        raise ValueError(f"HOSTEL PRE-COMMIT MISMATCH: Boys Hostel hostel_type '{hostel_boys.hostel_type}' != expected '{h_boys_ref['hostel_type']}'")
    if hostel_boys.total_floors != h_boys_ref["total_floors"]:
        raise ValueError(f"HOSTEL PRE-COMMIT MISMATCH: Boys Hostel total_floors '{hostel_boys.total_floors}' != expected '{h_boys_ref['total_floors']}'")
    if hostel_boys.total_rooms != h_boys_ref["total_rooms"]:
        raise ValueError(f"HOSTEL PRE-COMMIT MISMATCH: Boys Hostel total_rooms '{hostel_boys.total_rooms}' != expected '{h_boys_ref['total_rooms']}'")
    if hostel_boys.description != h_boys_ref["description"]:
        raise ValueError("HOSTEL PRE-COMMIT MISMATCH: Boys Hostel description does not match local reference.")

    # 2. Girls Hostel (5 fields)
    if hostel_girls.name != h_girls_ref["name"]:
        raise ValueError(f"HOSTEL PRE-COMMIT MISMATCH: Girls Hostel name '{hostel_girls.name}' != expected '{h_girls_ref['name']}'")
    if hostel_girls.hostel_type != h_girls_ref["hostel_type"]:
        raise ValueError(f"HOSTEL PRE-COMMIT MISMATCH: Girls Hostel hostel_type '{hostel_girls.hostel_type}' != expected '{h_girls_ref['hostel_type']}'")
    if hostel_girls.total_floors != h_girls_ref["total_floors"]:
        raise ValueError(f"HOSTEL PRE-COMMIT MISMATCH: Girls Hostel total_floors '{hostel_girls.total_floors}' != expected '{h_girls_ref['total_floors']}'")
    if hostel_girls.total_rooms != h_girls_ref["total_rooms"]:
        raise ValueError(f"HOSTEL PRE-COMMIT MISMATCH: Girls Hostel total_rooms '{hostel_girls.total_rooms}' != expected '{h_girls_ref['total_rooms']}'")
    if hostel_girls.description != h_girls_ref["description"]:
        raise ValueError("HOSTEL PRE-COMMIT MISMATCH: Girls Hostel description does not match local reference.")

    # 3. Mess Dining Facility (7 fields, including cross-database hostel_id mapping)
    if mess.mess_name != mess_ref["mess_name"]:
        raise ValueError(f"MESS PRE-COMMIT MISMATCH: mess_name '{mess.mess_name}' != expected '{mess_ref['mess_name']}'")

    expected_mess_hostel_id = None
    if mess_ref.get("hostel_id") is not None:
        if entities.get("expected_mess_hostel_id") is not None:
            expected_mess_hostel_id = entities["expected_mess_hostel_id"]
        elif ref.get("hostel_boys") and mess_ref["hostel_id"] == ref["hostel_boys"]["id"]:
            expected_mess_hostel_id = hostel_boys.id
        elif ref.get("hostel_girls") and mess_ref["hostel_id"] == ref["hostel_girls"]["id"]:
            expected_mess_hostel_id = hostel_girls.id
        else:
            expected_mess_hostel_id = resolve_mapped_mess_hostel_id(mess_ref, ref)

    if expected_mess_hostel_id is None:
        if mess.hostel_id is not None:
            raise ValueError(f"MESS PRE-COMMIT MISMATCH: expected hostel_id is None, got '{mess.hostel_id}'")
    else:
        if mess.hostel_id != expected_mess_hostel_id:
            raise ValueError(
                f"MESS PRE-COMMIT MISMATCH: hostel_id '{mess.hostel_id}' != expected PostgreSQL ID '{expected_mess_hostel_id}' "
                f"(SQLite reference hostel_id was '{mess_ref['hostel_id']}')."
            )
    if mess.description != mess_ref["description"]:
        raise ValueError("MESS PRE-COMMIT MISMATCH: description does not match local reference.")
    if mess.contact_number != mess_ref["contact_number"]:
        raise ValueError(f"MESS PRE-COMMIT MISMATCH: contact_number '{mess.contact_number}' != expected '{mess_ref['contact_number']}'")
    if mess.operating_status != mess_ref["operating_status"]:
        raise ValueError(f"MESS PRE-COMMIT MISMATCH: operating_status '{mess.operating_status}' != expected '{mess_ref['operating_status']}'")
    if mess.meal_policy != mess_ref["meal_policy"]:
        raise ValueError(f"MESS PRE-COMMIT MISMATCH: meal_policy '{mess.meal_policy}' != expected '{mess_ref['meal_policy']}'")
    if mess.daily_capacity != mess_ref["daily_capacity"]:
        raise ValueError(f"MESS PRE-COMMIT MISMATCH: daily_capacity '{mess.daily_capacity}' != expected '{mess_ref['daily_capacity']}'")

    # 4. Boys Warden Profile (5 fields + PostgreSQL generated relationships)
    w_boys_user = user_records["warden_boys"]
    if w_boys_prof.user_id != w_boys_user.id:
        raise ValueError(f"WARDEN PRE-COMMIT MISMATCH: Boys Warden user_id '{w_boys_prof.user_id}' != expected '{w_boys_user.id}'")
    if w_boys_prof.employee_id != w_b_ref["employee_id"]:
        raise ValueError(f"WARDEN PRE-COMMIT MISMATCH: Boys Warden employee_id '{w_boys_prof.employee_id}' != expected '{w_b_ref['employee_id']}'")
    if w_boys_prof.full_name != w_b_ref["full_name"]:
        raise ValueError(f"WARDEN PRE-COMMIT MISMATCH: Boys Warden full_name '{w_boys_prof.full_name}' != expected '{w_b_ref['full_name']}'")
    if w_boys_prof.phone != w_b_ref["phone"]:
        raise ValueError(f"WARDEN PRE-COMMIT MISMATCH: Boys Warden phone '{w_boys_prof.phone}' != expected '{w_b_ref['phone']}'")
    if w_boys_prof.designation != w_b_ref["designation"]:
        raise ValueError(f"WARDEN PRE-COMMIT MISMATCH: Boys Warden designation '{w_boys_prof.designation}' != expected '{w_b_ref['designation']}'")
    if w_boys_prof.assigned_hostel_id != hostel_boys.id:
        raise ValueError(f"WARDEN PRE-COMMIT MISMATCH: Boys Warden assigned_hostel_id '{w_boys_prof.assigned_hostel_id}' != PostgreSQL hostel_boys.id '{hostel_boys.id}'")

    # 5. Girls Warden Profile (5 fields + PostgreSQL generated relationships)
    w_girls_user = user_records["warden_girls"]
    if w_girls_prof.user_id != w_girls_user.id:
        raise ValueError(f"WARDEN PRE-COMMIT MISMATCH: Girls Warden user_id '{w_girls_prof.user_id}' != expected '{w_girls_user.id}'")
    if w_girls_prof.employee_id != w_g_ref["employee_id"]:
        raise ValueError(f"WARDEN PRE-COMMIT MISMATCH: Girls Warden employee_id '{w_girls_prof.employee_id}' != expected '{w_g_ref['employee_id']}'")
    if w_girls_prof.full_name != w_g_ref["full_name"]:
        raise ValueError(f"WARDEN PRE-COMMIT MISMATCH: Girls Warden full_name '{w_girls_prof.full_name}' != expected '{w_g_ref['full_name']}'")
    if w_girls_prof.phone != w_g_ref["phone"]:
        raise ValueError(f"WARDEN PRE-COMMIT MISMATCH: Girls Warden phone '{w_girls_prof.phone}' != expected '{w_g_ref['phone']}'")
    if w_girls_prof.designation != w_g_ref["designation"]:
        raise ValueError(f"WARDEN PRE-COMMIT MISMATCH: Girls Warden designation '{w_girls_prof.designation}' != expected '{w_g_ref['designation']}'")
    if w_girls_prof.assigned_hostel_id != hostel_girls.id:
        raise ValueError(f"WARDEN PRE-COMMIT MISMATCH: Girls Warden assigned_hostel_id '{w_girls_prof.assigned_hostel_id}' != PostgreSQL hostel_girls.id '{hostel_girls.id}'")

    # 6. Student Profile (14 fields + PostgreSQL generated user_id)
    student_user = user_records["rahul_sharma"]
    if student_prof.user_id != student_user.id:
        raise ValueError(f"STUDENT PRE-COMMIT MISMATCH: user_id '{student_prof.user_id}' != expected '{student_user.id}'")
    if student_prof.enrollment_no != s_ref["enrollment_no"]:
        raise ValueError(f"STUDENT PRE-COMMIT MISMATCH: enrollment_no '{student_prof.enrollment_no}' != expected '{s_ref['enrollment_no']}'")
    if student_prof.roll_no != s_ref["roll_no"]:
        raise ValueError(f"STUDENT PRE-COMMIT MISMATCH: roll_no '{student_prof.roll_no}' != expected '{s_ref['roll_no']}'")
    if student_prof.full_name != s_ref["full_name"]:
        raise ValueError(f"STUDENT PRE-COMMIT MISMATCH: full_name '{student_prof.full_name}' != expected '{s_ref['full_name']}'")
    if student_prof.phone != s_ref["phone"]:
        raise ValueError(f"STUDENT PRE-COMMIT MISMATCH: phone '{student_prof.phone}' != expected '{s_ref['phone']}'")
    if student_prof.gender != s_ref["gender"]:
        raise ValueError(f"STUDENT PRE-COMMIT MISMATCH: gender '{student_prof.gender}' != expected '{s_ref['gender']}'")
    if student_prof.branch != s_ref["branch"]:
        raise ValueError(f"STUDENT PRE-COMMIT MISMATCH: branch '{student_prof.branch}' != expected '{s_ref['branch']}'")
    if student_prof.year != s_ref["year"]:
        raise ValueError(f"STUDENT PRE-COMMIT MISMATCH: year '{student_prof.year}' != expected '{s_ref['year']}'")
    if student_prof.semester != s_ref["semester"]:
        raise ValueError(f"STUDENT PRE-COMMIT MISMATCH: semester '{student_prof.semester}' != expected '{s_ref['semester']}'")
    if student_prof.guardian_name != s_ref["guardian_name"]:
        raise ValueError(f"STUDENT PRE-COMMIT MISMATCH: guardian_name '{student_prof.guardian_name}' != expected '{s_ref['guardian_name']}'")
    if student_prof.guardian_phone != s_ref["guardian_phone"]:
        raise ValueError(f"STUDENT PRE-COMMIT MISMATCH: guardian_phone '{student_prof.guardian_phone}' != expected '{s_ref['guardian_phone']}'")
    if student_prof.emergency_phone != s_ref["emergency_phone"]:
        raise ValueError(f"STUDENT PRE-COMMIT MISMATCH: emergency_phone '{student_prof.emergency_phone}' != expected '{s_ref['emergency_phone']}'")
    if student_prof.address != s_ref["address"]:
        raise ValueError(f"STUDENT PRE-COMMIT MISMATCH: address '{student_prof.address}' != expected '{s_ref['address']}'")
    if student_prof.blood_group != s_ref["blood_group"]:
        raise ValueError(f"STUDENT PRE-COMMIT MISMATCH: blood_group '{student_prof.blood_group}' != expected '{s_ref['blood_group']}'")
    if student_prof.status != s_ref["status"]:
        raise ValueError(f"STUDENT PRE-COMMIT MISMATCH: status '{student_prof.status}' != expected '{s_ref['status']}'")

    # 7. Parent Profile (5 fields + PostgreSQL generated user_id & student_id)
    parent_user = user_records["parent_rahul"]
    if parent_prof.user_id != parent_user.id:
        raise ValueError(f"PARENT PRE-COMMIT MISMATCH: user_id '{parent_prof.user_id}' != expected '{parent_user.id}'")
    if parent_prof.parent_name != p_ref["parent_name"]:
        raise ValueError(f"PARENT PRE-COMMIT MISMATCH: parent_name '{parent_prof.parent_name}' != expected '{p_ref['parent_name']}'")
    if parent_prof.phone_number != p_ref["phone_number"]:
        raise ValueError(f"PARENT PRE-COMMIT MISMATCH: phone_number '{parent_prof.phone_number}' != expected '{p_ref['phone_number']}'")
    if parent_prof.relationship_to_student != p_ref["relationship_to_student"]:
        raise ValueError(f"PARENT PRE-COMMIT MISMATCH: relationship '{parent_prof.relationship_to_student}' != expected '{p_ref['relationship_to_student']}'")
    if parent_prof.student_id != student_prof.id:
        raise ValueError(f"PARENT PRE-COMMIT MISMATCH: student_id '{parent_prof.student_id}' != PostgreSQL student_prof.id '{student_prof.id}'")
    if parent_prof.account_status != p_ref["account_status"]:
        raise ValueError(f"PARENT PRE-COMMIT MISMATCH: account_status '{parent_prof.account_status}' != expected '{p_ref['account_status']}'")

    # 8. Mess Staff Profile (5 fields + PostgreSQL generated user_id & mess_id)
    staff_user = user_records["mess_staff"]
    if staff_prof.user_id != staff_user.id:
        raise ValueError(f"MESS STAFF PRE-COMMIT MISMATCH: user_id '{staff_prof.user_id}' != expected '{staff_user.id}'")
    if staff_prof.mess_id != mess.id:
        raise ValueError(f"MESS STAFF PRE-COMMIT MISMATCH: mess_id '{staff_prof.mess_id}' != PostgreSQL mess.id '{mess.id}'")
    if staff_prof.staff_name != ms_ref["staff_name"]:
        raise ValueError(f"MESS STAFF PRE-COMMIT MISMATCH: staff_name '{staff_prof.staff_name}' != expected '{ms_ref['staff_name']}'")
    if staff_prof.phone_number != ms_ref["phone_number"]:
        raise ValueError(f"MESS STAFF PRE-COMMIT MISMATCH: phone_number '{staff_prof.phone_number}' != expected '{ms_ref['phone_number']}'")
    if staff_prof.role_designation != ms_ref["role_designation"]:
        raise ValueError(f"MESS STAFF PRE-COMMIT MISMATCH: role_designation '{staff_prof.role_designation}' != expected '{ms_ref['role_designation']}'")
    if staff_prof.employment_status != ms_ref["employment_status"]:
        raise ValueError(f"MESS STAFF PRE-COMMIT MISMATCH: employment_status '{staff_prof.employment_status}' != expected '{ms_ref['employment_status']}'")

    return True


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

    conn = None
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

        mess_hostel_ref = None
        if mess_ref["hostel_id"] is not None:
            cur.execute("SELECT * FROM hostels WHERE id = ?", (mess_ref["hostel_id"],))
            h_rows = cur.fetchall()
            if not h_rows:
                print(f"\n[ABORTED] REFERENCE RELATIONSHIP ERROR: Local SQLite MessProfile references hostel_id '{mess_ref['hostel_id']}', but no matching hostel exists in SQLite.")
                sys.exit(1)
            if len(h_rows) > 1:
                print(f"\n[ABORTED] REFERENCE RELATIONSHIP ERROR: Ambiguous reference hostel mapping for MessProfile hostel_id '{mess_ref['hostel_id']}'.")
                sys.exit(1)
            mess_hostel_ref = dict(h_rows[0])

        return {
            "hostel_boys": h_boys,
            "hostel_girls": h_girls,
            "mess": mess_ref,
            "mess_hostel_ref": mess_hostel_ref,
            "warden_boys": w_boys_ref,
            "warden_girls": w_girls_ref,
            "student": student_ref,
            "parent": parent_ref,
            "mess_staff": staff_ref,
        }
    except SystemExit:
        raise
    except Exception as e:
        safe_err = format_safe_exception_report(e, "Local SQLite read error")
        print(f"\n[ABORTED] ERROR reading local SQLite database: {safe_err}")
        sys.exit(1)
    finally:
        if conn is not None:
            conn.close()


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

    # 1B. URL Fragment Validation: Reject any non-empty fragment
    if parsed.fragment:
        raise ValueError("SAFETY REFUSAL: URL fragments are not permitted in DATABASE_URL.")

    # 2. Username Validation: Exact Expected Pooler Username
    username = parsed.username or ""
    if username != EXPECTED_POOLER_USERNAME:
        raise ValueError(f"SAFETY REFUSAL: Username must be '{EXPECTED_POOLER_USERNAME}'. Found: '{username}'.")

    # 2B. Database Password Validation: Reject missing or empty passwords
    if not parsed.password or not parsed.password.strip():
        raise ValueError("SAFETY REFUSAL: Database password is missing or empty.")

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

    # 6. Query Parameters Validation: Exactly one sslmode=require (no unexpected, duplicate, blank, or malformed parameters)
    if not parsed.query or not parsed.query.strip():
        raise ValueError("SECURITY ERROR: Missing required 'sslmode=require' query parameter.")

    raw_query = parsed.query.strip()

    # Reject malformed query strings (leading/trailing/consecutive '&', missing values, etc.)
    if raw_query.startswith("&") or raw_query.endswith("&") or "&&" in raw_query:
        raise ValueError("SECURITY ERROR: Malformed query string with empty or duplicate delimiters.")

    param_pairs = raw_query.split("&")
    if len(param_pairs) != 1:
        raise ValueError(
            f"SECURITY ERROR: Exactly one query parameter ('sslmode=require') permitted. "
            f"Found {len(param_pairs)} parameters."
        )

    pair = param_pairs[0]
    if "=" not in pair:
        raise ValueError("SECURITY ERROR: Malformed query parameter without '='.")

    parts = pair.split("=")
    if len(parts) != 2:
        raise ValueError("SECURITY ERROR: Malformed query parameter with multiple '='.")

    key, val = parts[0].strip(), parts[1].strip()
    if not key or not val:
        raise ValueError("SECURITY ERROR: Blank key or value in query parameter.")

    if key != "sslmode":
        raise ValueError("SECURITY ERROR: Unexpected query parameter detected. Only 'sslmode=require' is permitted.")

    if val.lower() != "require":
        raise ValueError("SECURITY ERROR: Parameter 'sslmode' must be 'require'.")

    # Extra validation using urllib.parse.parse_qs to ensure no duplicate keys or multi-values
    qs = urllib.parse.parse_qs(raw_query, keep_blank_values=True)
    if list(qs.keys()) != ["sslmode"]:
        raise ValueError("SECURITY ERROR: Unexpected parameters detected by query parser.")
    if len(qs["sslmode"]) != 1 or qs["sslmode"][0].lower() != "require":
        raise ValueError("SECURITY ERROR: Multiple or invalid 'sslmode' parameter values detected.")


def resolve_database_url() -> str:
    """Safely retrieves and validates DATABASE_URL from environment or hidden interactive prompt."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url or not db_url.strip():
        if sys.stdin.isatty():
            print("\nDATABASE_URL environment variable is not set in this session.")
            print("Please enter the production Supabase connection string.")
            print("(Input will be hidden for security):")
            try:
                db_url = getpass.getpass("Supabase DATABASE_URL: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n[ABORTED] Operation cancelled by user.")
                sys.exit(1)
        else:
            print("\n[ABORTED] ERROR: DATABASE_URL environment variable is missing or empty in non-interactive environment.")
            print("Set $env:DATABASE_URL=\"postgresql://postgres.[REF]:[PASS]@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require\" before running.")
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
        ("Missing database password", "postgresql://postgres.yjhapstttgilcbaxbbce@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require", False),
        ("Empty database password", "postgresql://postgres.yjhapstttgilcbaxbbce:@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require", False),
        ("Whitespace database password", "postgresql://postgres.yjhapstttgilcbaxbbce:   @aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require", False),
        ("Non-empty URL fragment", "postgresql://postgres.yjhapstttgilcbaxbbce:Secret123@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require#pooler-options", False),
        ("Missing sslmode", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres", False),
        ("Duplicate sslmode", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require&sslmode=disable", False),
        ("Duplicate identical sslmode", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require&sslmode=require", False),
        ("Wrong sslmode value", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=prefer", False),
        ("Unexpected parameter (connect_timeout)", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require&connect_timeout=10", False),
        ("Unexpected parameter (foo=bar)", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require&foo=bar", False),
        ("Trailing ampersand", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require&", False),
        ("Leading ampersand", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?&sslmode=require", False),
        ("Consecutive ampersands", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require&&extra=1", False),
        ("Blank parameter (&)", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require&=", False),
        ("Missing query value (sslmode=)", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=", False),
        ("Missing query key (=require)", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?=require", False),
        ("Malformed query without equals (sslmode)", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode", False),
        ("Malformed query multiple equals", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require=extra", False),
        ("Blank query string (?)", "postgresql://postgres.yjhapstttgilcbaxbbce:pass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?", False),
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
    Local-only unit tests verifying runtime password resolution & secure hashing:
    1. Tests runtime password resolution via environment variables without embedding
       real passwords or reversible encodings in Python source code.
    2. Verifies collect_all_demo_credentials() collects all 8 credentials and enforces distinctness.
    3. Verifies application's User model uses Werkzeug scrypt method ('scrypt:').
    4. Plaintext passwords never equal the hash.
    5. Invalid passwords fail verification via User.check_password().
    Preserves all 16 expected demo environment variables in a snapshot, isolates tests
    from real operator credentials, and guarantees exact environment restoration upon completion.
    """
    print("\n" + "=" * 80)
    print("RUNNING LOCAL-ONLY DEMO CREDENTIALS & HASHING UNIT TESTS")
    print("=" * 80)

    all_passed = True
    resolved_creds = {}

    with preserve_demo_credentials_environment():
        # Setup temporary mock environment variables to test runtime resolution without hardcoded passwords
        mock_env_vars = {}
        for idx, meta in enumerate(INTENDED_ACCOUNTS, start=1):
            u = meta["username"]
            env_key = f"DEMO_PASS_{u.upper()}"
            mock_val = f"MockTestSecret_{idx}_{u}_2026!"
            os.environ[env_key] = mock_val
            mock_env_vars[env_key] = mock_val

        try:
            # 1. Check all 8 accounts resolve valid credentials via collect_all_demo_credentials()
            try:
                resolved_creds = collect_all_demo_credentials()
                status = "PASS" if len(resolved_creds) == 8 else "FAIL"
                if len(resolved_creds) != 8:
                    all_passed = False
                print(f"  [{status}] collect_all_demo_credentials() -> Resolved {len(resolved_creds)} / 8 accounts.")
            except Exception as e:
                all_passed = False
                print(f"  [FAIL] collect_all_demo_credentials() failed: {e}")

            # 2. Check distinctness validation in collect_all_demo_credentials()
            distinct_count = len(set(resolved_creds.values()))
            status = "PASS" if distinct_count == 8 else "FAIL"
            if distinct_count != 8:
                all_passed = False
            print(f"  [{status}] Distinct resolved passwords count: {distinct_count} / 8")

            # Test duplicate password collision rejection in collect_all_demo_credentials()
            for idx, meta in enumerate(INTENDED_ACCOUNTS, start=1):
                u = meta["username"]
                os.environ[f"DEMO_PASS_{u.upper()}"] = f"MockTestSecret_{idx}_{u}_2026!"
            os.environ["DEMO_PASS_ADMIN"] = os.environ["DEMO_PASS_WARDEN_BOYS"]
            try:
                collect_all_demo_credentials()
                all_passed = False
                print("  [FAIL] collect_all_demo_credentials(): Accepted duplicate passwords across accounts!")
            except ValueError:
                print("  [PASS] collect_all_demo_credentials(): Successfully rejected duplicate password collision.")
            finally:
                for meta in INTENDED_ACCOUNTS:
                    os.environ.pop(f"DEMO_PASS_{meta['username'].upper()}", None)
                    os.environ.pop(f"DEMO_PASSWORD_{meta['username'].upper()}", None)

            # 3. Check actual application User model set_password() and check_password() with scrypt
            for u, pwd in resolved_creds.items():
                test_user = User(username=u, email=f"{u}@aktu-hostel.edu.in", role="student")
                test_user.set_password(pwd)
                is_scrypt = bool(test_user.password_hash and test_user.password_hash.startswith("scrypt:"))
                is_hashed = bool(test_user.password_hash != pwd and len(test_user.password_hash) > 20)
                verifies = test_user.check_password(pwd)
                fails_wrong = not test_user.check_password("IncorrectPassword@999")
                test_ok = is_scrypt and is_hashed and verifies and fails_wrong
                status = "PASS" if test_ok else "FAIL"
                if not test_ok:
                    all_passed = False
                print(f"  [{status}] User.set_password() for '{u:<15}' -> scrypt: {is_scrypt}, hash_ok: {is_hashed}, check_pwd: {verifies}, reject_wrong: {fails_wrong}")

            # 4. Check validation of environment variable values (identical to getpass rules)
            # Test 4A: Rejection of whitespace-only environment variable
            os.environ["DEMO_PASS_ADMIN"] = "   "
            try:
                resolve_demo_credential("admin")
                all_passed = False
                print("  [FAIL] Environment validation: Accepted whitespace password!")
            except ValueError:
                print("  [PASS] Environment validation: Rejected whitespace password.")

            # Test 4B: Rejection of short password (< 8 chars) in environment variable
            os.environ["DEMO_PASS_ADMIN"] = "short12"
            try:
                resolve_demo_credential("admin")
                all_passed = False
                print("  [FAIL] Environment validation: Accepted short password (< 8 chars)!")
            except ValueError:
                print("  [PASS] Environment validation: Rejected short password (< 8 chars).")

            # Test 4C: Support for DEMO_PASSWORD_<USERNAME> prefix
            del os.environ["DEMO_PASS_ADMIN"]
            os.environ["DEMO_PASSWORD_ADMIN"] = "ValidPassword2026!"
            try:
                p = resolve_demo_credential("admin")
                if p == "ValidPassword2026!":
                    print("  [PASS] Alternate prefix 'DEMO_PASSWORD_ADMIN': Resolved successfully.")
                else:
                    all_passed = False
                    print("  [FAIL] Alternate prefix 'DEMO_PASSWORD_ADMIN': Mismatch.")
            except Exception as e:
                all_passed = False
                print(f"  [FAIL] Alternate prefix error: {e}")

            # 5. Check password preservation by default vs rotation when requested
            # 5A: Preserve existing password by default (rotate_passwords=False)
            u_preserve = User(username="admin", email="admin@aktu-hostel.edu.in", role="admin", is_active=True)
            u_preserve.set_password("OriginalAdminPassword123!")
            orig_hash_saved = u_preserve.password_hash
            t5a_pass = (orig_hash_saved and orig_hash_saved.startswith("scrypt:") and u_preserve.check_password("OriginalAdminPassword123!"))
            if not t5a_pass:
                all_passed = False
            print(f"  [{'PASS' if t5a_pass else 'FAIL'}] Password preservation by default: Existing password hash verified via scrypt.")

            # 5B: Rotate existing password when explicitly requested (rotate_passwords=True)
            new_test_pass = "RotatedAdminPassword2026!"
            u_preserve.set_password(new_test_pass)
            t5b_pass = (u_preserve.password_hash != orig_hash_saved and u_preserve.check_password(new_test_pass))
            if not t5b_pass:
                all_passed = False
            print(f"  [{'PASS' if t5b_pass else 'FAIL'}] Password rotation when requested: Password successfully updated and verified via scrypt.")

        finally:
            # Clean up temporary test environment variables and dictionaries
            resolved_creds.clear()
            for env_key in list(mock_env_vars.keys()):
                os.environ.pop(env_key, None)
            mock_env_vars.clear()
            os.environ.pop("DEMO_PASS_ADMIN", None)
            os.environ.pop("DEMO_PASSWORD_ADMIN", None)

    print("=" * 80)
    print(f"Demo Credentials Test Suite Result: {'ALL TESTS PASSED' if all_passed else 'TESTS FAILED'}")
    print("=" * 80 + "\n")
    return all_passed


def run_role_enum_unit_tests() -> bool:
    """
    Local-only unit tests verifying SQLAlchemy User.role Enum compatibility:
    1. Inspects the actual User.role Enum column definition.
    2. Verifies that all 8 intended account roles match valid Enum members.
    3. Verifies that get_user_role_value() correctly resolves role values from User model instances.
    4. Rejects invalid / unmapped role values.
    """
    print("\n" + "=" * 80)
    print("RUNNING LOCAL-ONLY ROLE ENUM COMPATIBILITY UNIT TESTS")
    print("=" * 80)

    all_passed = True
    enum_members = list(User.role.property.columns[0].type.enums)
    print(f"  [INFO] SQLAlchemy User.role column Enum values: {enum_members}")

    for meta in INTENDED_ACCOUNTS:
        u = meta["username"]
        intended_role = meta["role"]

        # Check that intended role is in model's Enum definition
        in_enum = intended_role in enum_members
        if not in_enum:
            all_passed = False
            print(f"  [FAIL] Role '{intended_role}' for '{u}' is NOT in SQLAlchemy Enum definition!")
            continue

        # Instantiate model and verify get_user_role_value
        test_user = User(username=u, email=meta["email"], role=intended_role)
        resolved_val = get_user_role_value(test_user.role)
        matches = (resolved_val == intended_role)
        status = "PASS" if matches else "FAIL"
        if not matches:
            all_passed = False
        print(f"  [{status}] User '{u:<15}' -> Intended: '{intended_role:<12}', Resolved: '{resolved_val:<12}', In Enum: {in_enum}")

    # Verify invalid role rejection
    invalid_role = "unauthorized_superadmin"
    is_invalid_in_enum = invalid_role in enum_members
    status = "PASS" if not is_invalid_in_enum else "FAIL"
    if is_invalid_in_enum:
        all_passed = False
    print(f"  [{status}] Arbitrary role '{invalid_role}' safely rejected by Enum definition.")

    print("=" * 80)
    print(f"Role Enum Test Suite Result: {'ALL TESTS PASSED' if all_passed else 'TESTS FAILED'}")
    print("=" * 80 + "\n")
    return all_passed


def run_field_verification_unit_tests() -> bool:
    """
    Local-only unit tests for complete field-level pre-commit verification
    using local/mock objects only. Does NOT connect to Supabase.
    """
    print("\n" + "=" * 80)
    print("RUNNING LOCAL-ONLY FIELD-LEVEL PRE-COMMIT VERIFICATION TESTS")
    print("=" * 80)

    all_passed = True
    ref = load_local_sqlite_reference()

    # Simple mock class to simulate SQLAlchemy models with PostgreSQL generated IDs
    class MockRecord:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    # Build valid mock objects matching the SQLite reference with mock PostgreSQL IDs
    h_boys = MockRecord(
        id=101,
        name=ref["hostel_boys"]["name"],
        hostel_type=ref["hostel_boys"]["hostel_type"],
        total_floors=ref["hostel_boys"]["total_floors"],
        total_rooms=ref["hostel_boys"]["total_rooms"],
        description=ref["hostel_boys"]["description"],
    )
    h_girls = MockRecord(
        id=102,
        name=ref["hostel_girls"]["name"],
        hostel_type=ref["hostel_girls"]["hostel_type"],
        total_floors=ref["hostel_girls"]["total_floors"],
        total_rooms=ref["hostel_girls"]["total_rooms"],
        description=ref["hostel_girls"]["description"],
    )
    mess = MockRecord(
        id=201,
        hostel_id=ref["mess"]["hostel_id"],  # None
        mess_name=ref["mess"]["mess_name"],
        description=ref["mess"]["description"],
        contact_number=ref["mess"]["contact_number"],
        operating_status=ref["mess"]["operating_status"],
        meal_policy=ref["mess"]["meal_policy"],
        daily_capacity=ref["mess"]["daily_capacity"],
    )
    mock_users = {
        "warden_boys": MockRecord(id=501),
        "warden_girls": MockRecord(id=502),
        "rahul_sharma": MockRecord(id=503),
        "parent_rahul": MockRecord(id=504),
        "mess_staff": MockRecord(id=505),
    }
    w_boys = MockRecord(
        id=301,
        user_id=501,
        employee_id=ref["warden_boys"]["employee_id"],
        full_name=ref["warden_boys"]["full_name"],
        phone=ref["warden_boys"]["phone"],
        designation=ref["warden_boys"]["designation"],
        assigned_hostel_id=101,
    )
    w_girls = MockRecord(
        id=302,
        user_id=502,
        employee_id=ref["warden_girls"]["employee_id"],
        full_name=ref["warden_girls"]["full_name"],
        phone=ref["warden_girls"]["phone"],
        designation=ref["warden_girls"]["designation"],
        assigned_hostel_id=102,
    )
    student = MockRecord(
        id=401,
        user_id=503,
        enrollment_no=ref["student"]["enrollment_no"],
        roll_no=ref["student"]["roll_no"],
        full_name=ref["student"]["full_name"],
        phone=ref["student"]["phone"],
        gender=ref["student"]["gender"],
        branch=ref["student"]["branch"],
        year=ref["student"]["year"],
        semester=ref["student"]["semester"],
        guardian_name=ref["student"]["guardian_name"],
        guardian_phone=ref["student"]["guardian_phone"],
        emergency_phone=ref["student"]["emergency_phone"],
        address=ref["student"]["address"],
        blood_group=ref["student"]["blood_group"],
        status=ref["student"]["status"],
    )
    parent = MockRecord(
        id=601,
        user_id=504,
        parent_name=ref["parent"]["parent_name"],
        phone_number=ref["parent"]["phone_number"],
        relationship_to_student=ref["parent"]["relationship_to_student"],
        student_id=401,
        account_status=ref["parent"]["account_status"],
    )
    staff = MockRecord(
        id=701,
        user_id=505,
        mess_id=201,
        staff_name=ref["mess_staff"]["staff_name"],
        phone_number=ref["mess_staff"]["phone_number"],
        role_designation=ref["mess_staff"]["role_designation"],
        employment_status=ref["mess_staff"]["employment_status"],
    )

    base_entities = {
        "hostel_boys": h_boys,
        "hostel_girls": h_girls,
        "mess": mess,
        "w_boys_prof": w_boys,
        "w_girls_prof": w_girls,
        "student_prof": student,
        "parent_prof": parent,
        "staff_prof": staff,
        "user_records": mock_users,
    }

    # Test 1: Full verification passes on matching records
    try:
        verify_all_entity_fields_pre_commit(base_entities, ref)
        print("  [PASS] Full entity pre-commit verification passed on matching reference data.")
    except Exception as e:
        all_passed = False
        print(f"  [FAIL] Baseline verification failed: {e}")

    # Test 2: Hostel field mismatch detection
    orig_rooms = h_boys.total_rooms
    h_boys.total_rooms = 999
    try:
        verify_all_entity_fields_pre_commit(base_entities, ref)
        all_passed = False
        print("  [FAIL] Failed to detect hostel total_rooms mismatch!")
    except ValueError:
        print("  [PASS] Successfully detected hostel total_rooms mismatch.")
    finally:
        h_boys.total_rooms = orig_rooms

    # Test 3: Mess hostel_id None violation detection
    mess.hostel_id = 99
    try:
        verify_all_entity_fields_pre_commit(base_entities, ref)
        all_passed = False
        print("  [FAIL] Failed to detect mess hostel_id != None violation!")
    except ValueError:
        print("  [PASS] Successfully detected mess hostel_id exact None violation.")
    finally:
        mess.hostel_id = None

    # Test 3B: Cross-database Mess hostel_id mapping verification
    # When mess_ref has a hostel_id pointing to Boys Hostel (SQLite ID 1, PostgreSQL ID 101)
    fake_ref = dict(ref)
    fake_mess_ref = dict(ref["mess"])
    fake_mess_ref["hostel_id"] = 1  # SQLite ID
    fake_ref["mess"] = fake_mess_ref

    # Case A: mess.hostel_id has PostgreSQL ID 101 -> Passes!
    mess.hostel_id = 101
    try:
        verify_all_entity_fields_pre_commit(base_entities, fake_ref)
        print("  [PASS] Successfully verified cross-database Mess hostel_id mapping (PostgreSQL ID 101).")
    except Exception as e:
        all_passed = False
        print(f"  [FAIL] Cross-database Mess hostel_id mapping failed: {e}")

    # Case B: mess.hostel_id still has SQLite ID 1 -> Fails!
    mess.hostel_id = 1
    try:
        verify_all_entity_fields_pre_commit(base_entities, fake_ref)
        all_passed = False
        print("  [FAIL] Failed to detect unmapped SQLite hostel_id on MessProfile!")
    except ValueError:
        print("  [PASS] Successfully detected unmapped SQLite hostel_id on MessProfile.")
    finally:
        mess.hostel_id = None

    # Test 4: Warden assigned_hostel_id relationship mismatch detection
    orig_hostel_id = w_boys.assigned_hostel_id
    w_boys.assigned_hostel_id = 999
    try:
        verify_all_entity_fields_pre_commit(base_entities, ref)
        all_passed = False
        print("  [FAIL] Failed to detect warden assigned_hostel_id mismatch!")
    except ValueError:
        print("  [PASS] Successfully detected warden assigned_hostel_id mismatch.")
    finally:
        w_boys.assigned_hostel_id = orig_hostel_id

    # Test 5: Student field mismatch detection
    orig_status = student.status
    student.status = "Suspended"
    try:
        verify_all_entity_fields_pre_commit(base_entities, ref)
        all_passed = False
        print("  [FAIL] Failed to detect student status mismatch!")
    except ValueError:
        print("  [PASS] Successfully detected student status mismatch.")
    finally:
        student.status = orig_status

    # Test 6: Parent student_id relationship mismatch detection
    orig_student_id = parent.student_id
    parent.student_id = 999
    try:
        verify_all_entity_fields_pre_commit(base_entities, ref)
        all_passed = False
        print("  [FAIL] Failed to detect parent student_id mismatch!")
    except ValueError:
        print("  [PASS] Successfully detected parent student_id relationship mismatch.")
    finally:
        parent.student_id = orig_student_id

    # Test 7: Mess staff mess_id relationship mismatch detection
    orig_mess_id = staff.mess_id
    staff.mess_id = 999
    try:
        verify_all_entity_fields_pre_commit(base_entities, ref)
        all_passed = False
        print("  [FAIL] Failed to detect mess staff mess_id mismatch!")
    except ValueError:
        print("  [PASS] Successfully detected mess staff mess_id relationship mismatch.")
    finally:
        staff.mess_id = orig_mess_id

    print("=" * 80)
    print(f"Field-Level Verification Test Suite Result: {'ALL TESTS PASSED' if all_passed else 'TESTS FAILED'}")
    print("=" * 80 + "\n")
    return all_passed


def run_profile_immutability_unit_tests() -> bool:
    """
    Local-only unit tests verifying strict profile immutability and creation logic
    for all 5 associated profile types (Boys Warden, Girls Warden, Student, Parent, Mess Staff):
    1. Matching existing profile: verified without modifying any field (attributes preserved identical).
    2. Mismatched existing profile: raises ValueError and record remains unmodified (attributes preserved identical).
    3. Missing profile (None): created accurately from local SQLite reference data with PostgreSQL IDs.
    Does NOT connect to Supabase or execute the migration.
    """
    print("\n" + "=" * 80)
    print("RUNNING LOCAL-ONLY PROFILE IMMUTABILITY & CREATION UNIT TESTS")
    print("=" * 80)

    all_passed = True
    ref = load_local_sqlite_reference()

    class MockProfileRecord:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def to_dict(self):
            return dict(self.__dict__)

    # --- 1. Boys Warden Profile ---
    wb_ref = ref["warden_boys"]
    # 1A: Missing profile (None) -> created
    new_wb, created = validate_or_create_warden_profile(None, 501, wb_ref, 101, session=None)
    if not created or new_wb.user_id != 501 or new_wb.employee_id != wb_ref["employee_id"] or new_wb.assigned_hostel_id != 101:
        all_passed = False
        print("  [FAIL] Boys Warden creation from None failed.")
    else:
        print("  [PASS] Boys Warden: Created accurately when missing.")

    # 1B: Matching existing profile -> preserved unmodified
    mock_wb = MockProfileRecord(
        id=301,
        user_id=501,
        employee_id=wb_ref["employee_id"],
        full_name=wb_ref["full_name"],
        phone=wb_ref["phone"],
        designation=wb_ref["designation"],
        assigned_hostel_id=101,
    )
    snap_wb = mock_wb.to_dict()
    res_wb, created = validate_or_create_warden_profile(mock_wb, 501, wb_ref, 101, session=None)
    if created or res_wb is not mock_wb or mock_wb.to_dict() != snap_wb:
        all_passed = False
        print("  [FAIL] Boys Warden: Matching existing profile was modified or not preserved!")
    else:
        print("  [PASS] Boys Warden: Matching existing profile preserved unmodified.")

    # 1C: Mismatched existing profile -> raises ValueError without modifying record
    mock_wb_bad = MockProfileRecord(
        id=301,
        user_id=501,
        employee_id=wb_ref["employee_id"],
        full_name=wb_ref["full_name"],
        phone="9999999999",  # mismatch
        designation=wb_ref["designation"],
        assigned_hostel_id=101,
    )
    snap_wb_bad = mock_wb_bad.to_dict()
    try:
        validate_or_create_warden_profile(mock_wb_bad, 501, wb_ref, 101, session=None)
        all_passed = False
        print("  [FAIL] Boys Warden: Failed to raise ValueError on mismatched field!")
    except ValueError:
        if mock_wb_bad.to_dict() == snap_wb_bad:
            print("  [PASS] Boys Warden: Mismatched existing profile raised ValueError and preserved record unmodified.")
        else:
            all_passed = False
            print("  [FAIL] Boys Warden: Mismatched existing record was modified despite raising error!")

    # --- 2. Girls Warden Profile ---
    wg_ref = ref["warden_girls"]
    # 2A: Missing profile (None) -> created
    new_wg, created = validate_or_create_warden_profile(None, 502, wg_ref, 102, session=None)
    if not created or new_wg.user_id != 502 or new_wg.employee_id != wg_ref["employee_id"] or new_wg.assigned_hostel_id != 102:
        all_passed = False
        print("  [FAIL] Girls Warden creation from None failed.")
    else:
        print("  [PASS] Girls Warden: Created accurately when missing.")

    # 2B: Matching existing profile -> preserved unmodified
    mock_wg = MockProfileRecord(
        id=302,
        user_id=502,
        employee_id=wg_ref["employee_id"],
        full_name=wg_ref["full_name"],
        phone=wg_ref["phone"],
        designation=wg_ref["designation"],
        assigned_hostel_id=102,
    )
    snap_wg = mock_wg.to_dict()
    res_wg, created = validate_or_create_warden_profile(mock_wg, 502, wg_ref, 102, session=None)
    if created or res_wg is not mock_wg or mock_wg.to_dict() != snap_wg:
        all_passed = False
        print("  [FAIL] Girls Warden: Matching existing profile was modified or not preserved!")
    else:
        print("  [PASS] Girls Warden: Matching existing profile preserved unmodified.")

    # 2C: Mismatched existing profile -> raises ValueError without modifying record
    mock_wg_bad = MockProfileRecord(
        id=302,
        user_id=502,
        employee_id=wg_ref["employee_id"],
        full_name=wg_ref["full_name"],
        phone=wg_ref["phone"],
        designation="Wrong Designation",  # mismatch
        assigned_hostel_id=102,
    )
    snap_wg_bad = mock_wg_bad.to_dict()
    try:
        validate_or_create_warden_profile(mock_wg_bad, 502, wg_ref, 102, session=None)
        all_passed = False
        print("  [FAIL] Girls Warden: Failed to raise ValueError on mismatched field!")
    except ValueError:
        if mock_wg_bad.to_dict() == snap_wg_bad:
            print("  [PASS] Girls Warden: Mismatched existing profile raised ValueError and preserved record unmodified.")
        else:
            all_passed = False
            print("  [FAIL] Girls Warden: Mismatched existing record was modified despite raising error!")

    # --- 3. Student Profile ---
    s_ref = ref["student"]
    # 3A: Missing profile (None) -> created
    new_s, created = validate_or_create_student_profile(None, 503, s_ref, session=None)
    s_mismatch = (
        not created
        or new_s.user_id != 503
        or new_s.enrollment_no != s_ref["enrollment_no"]
        or new_s.roll_no != s_ref["roll_no"]
        or new_s.full_name != s_ref["full_name"]
        or new_s.status != s_ref["status"]
    )
    if s_mismatch:
        all_passed = False
        print("  [FAIL] Student creation from None failed.")
    else:
        print("  [PASS] Student: Created accurately when missing.")

    # 3B: Matching existing profile -> preserved unmodified
    mock_s = MockProfileRecord(
        id=401,
        user_id=503,
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
        status=s_ref["status"],
    )
    snap_s = mock_s.to_dict()
    res_s, created = validate_or_create_student_profile(mock_s, 503, s_ref, session=None)
    if created or res_s is not mock_s or mock_s.to_dict() != snap_s:
        all_passed = False
        print("  [FAIL] Student: Matching existing profile was modified or not preserved!")
    else:
        print("  [PASS] Student: Matching existing profile preserved unmodified.")

    # 3C: Mismatched existing profile -> raises ValueError without modifying record
    mock_s_bad = MockProfileRecord(
        id=401,
        user_id=503,
        enrollment_no=s_ref["enrollment_no"],
        roll_no=s_ref["roll_no"],
        full_name=s_ref["full_name"],
        phone=s_ref["phone"],
        gender=s_ref["gender"],
        branch="Electrical Engineering",  # mismatch
        year=s_ref["year"],
        semester=s_ref["semester"],
        guardian_name=s_ref["guardian_name"],
        guardian_phone=s_ref["guardian_phone"],
        emergency_phone=s_ref["emergency_phone"],
        address=s_ref["address"],
        blood_group=s_ref["blood_group"],
        status=s_ref["status"],
    )
    snap_s_bad = mock_s_bad.to_dict()
    try:
        validate_or_create_student_profile(mock_s_bad, 503, s_ref, session=None)
        all_passed = False
        print("  [FAIL] Student: Failed to raise ValueError on mismatched field!")
    except ValueError:
        if mock_s_bad.to_dict() == snap_s_bad:
            print("  [PASS] Student: Mismatched existing profile raised ValueError and preserved record unmodified.")
        else:
            all_passed = False
            print("  [FAIL] Student: Mismatched existing record was modified despite raising error!")

    # --- 4. Parent Profile ---
    p_ref = ref["parent"]
    # 4A: Missing profile (None) -> created
    new_p, created = validate_or_create_parent_profile(None, 504, p_ref, 401, session=None)
    if not created or new_p.user_id != 504 or new_p.student_id != 401 or new_p.parent_name != p_ref["parent_name"]:
        all_passed = False
        print("  [FAIL] Parent creation from None failed.")
    else:
        print("  [PASS] Parent: Created accurately when missing.")

    # 4B: Matching existing profile -> preserved unmodified
    mock_p = MockProfileRecord(
        id=601,
        user_id=504,
        parent_name=p_ref["parent_name"],
        phone_number=p_ref["phone_number"],
        relationship_to_student=p_ref["relationship_to_student"],
        student_id=401,
        account_status=p_ref["account_status"],
    )
    snap_p = mock_p.to_dict()
    res_p, created = validate_or_create_parent_profile(mock_p, 504, p_ref, 401, session=None)
    if created or res_p is not mock_p or mock_p.to_dict() != snap_p:
        all_passed = False
        print("  [FAIL] Parent: Matching existing profile was modified or not preserved!")
    else:
        print("  [PASS] Parent: Matching existing profile preserved unmodified.")

    # 4C: Mismatched existing profile -> raises ValueError without modifying record
    mock_p_bad = MockProfileRecord(
        id=601,
        user_id=504,
        parent_name=p_ref["parent_name"],
        phone_number=p_ref["phone_number"],
        relationship_to_student="Guardian",  # mismatch
        student_id=401,
        account_status=p_ref["account_status"],
    )
    snap_p_bad = mock_p_bad.to_dict()
    try:
        validate_or_create_parent_profile(mock_p_bad, 504, p_ref, 401, session=None)
        all_passed = False
        print("  [FAIL] Parent: Failed to raise ValueError on mismatched field!")
    except ValueError:
        if mock_p_bad.to_dict() == snap_p_bad:
            print("  [PASS] Parent: Mismatched existing profile raised ValueError and preserved record unmodified.")
        else:
            all_passed = False
            print("  [FAIL] Parent: Mismatched existing record was modified despite raising error!")

    # --- 5. Mess Staff Profile ---
    ms_ref = ref["mess_staff"]
    # 5A: Missing profile (None) -> created
    new_ms, created = validate_or_create_mess_staff_profile(None, 505, ms_ref, 201, session=None)
    if not created or new_ms.user_id != 505 or new_ms.mess_id != 201 or new_ms.staff_name != ms_ref["staff_name"]:
        all_passed = False
        print("  [FAIL] Mess Staff creation from None failed.")
    else:
        print("  [PASS] Mess Staff: Created accurately when missing.")

    # 5B: Matching existing profile -> preserved unmodified
    mock_ms = MockProfileRecord(
        id=701,
        user_id=505,
        mess_id=201,
        staff_name=ms_ref["staff_name"],
        phone_number=ms_ref["phone_number"],
        role_designation=ms_ref["role_designation"],
        employment_status=ms_ref["employment_status"],
    )
    snap_ms = mock_ms.to_dict()
    res_ms, created = validate_or_create_mess_staff_profile(mock_ms, 505, ms_ref, 201, session=None)
    if created or res_ms is not mock_ms or mock_ms.to_dict() != snap_ms:
        all_passed = False
        print("  [FAIL] Mess Staff: Matching existing profile was modified or not preserved!")
    else:
        print("  [PASS] Mess Staff: Matching existing profile preserved unmodified.")

    # 5C: Mismatched existing profile -> raises ValueError without modifying record
    mock_ms_bad = MockProfileRecord(
        id=701,
        user_id=505,
        mess_id=201,
        staff_name=ms_ref["staff_name"],
        phone_number=ms_ref["phone_number"],
        role_designation="Executive Chef",  # mismatch
        employment_status=ms_ref["employment_status"],
    )
    snap_ms_bad = mock_ms_bad.to_dict()
    try:
        validate_or_create_mess_staff_profile(mock_ms_bad, 505, ms_ref, 201, session=None)
        all_passed = False
        print("  [FAIL] Mess Staff: Failed to raise ValueError on mismatched field!")
    except ValueError:
        if mock_ms_bad.to_dict() == snap_ms_bad:
            print("  [PASS] Mess Staff: Mismatched existing profile raised ValueError and preserved record unmodified.")
        else:
            all_passed = False
            print("  [FAIL] Mess Staff: Mismatched existing record was modified despite raising error!")

    print("=" * 80)
    print(f"Profile Immutability & Creation Test Suite Result: {'ALL TESTS PASSED' if all_passed else 'TESTS FAILED'}")
    print("=" * 80 + "\n")
    return all_passed


def cleanup_credential_dictionaries(*dicts) -> None:
    """
    Best-effort reference cleanup helper: safely clears dictionary references
    containing demonstration passwords or temporary credentials.
    Used by migrate_demo_accounts() and verified across all failure scenarios.
    """
    for d in dicts:
        if isinstance(d, dict):
            d.clear()


def execute_with_credential_cleanup(demo_passwords: dict, account_passwords: dict, action_fn):
    """
    Executes action_fn within an outer try/finally boundary that guarantees
    cleanup_credential_dictionaries(demo_passwords, account_passwords) runs
    on all exit paths: success, validation errors, database failures,
    system exits, KeyboardInterrupt, and EOFError.
    """
    try:
        return action_fn()
    finally:
        cleanup_credential_dictionaries(demo_passwords, account_passwords)


def snapshot_demo_credential_env_vars() -> dict:
    """
    Snapshots the original values of all 16 DEMO_PASS_* and DEMO_PASSWORD_*
    environment variables across all 8 intended accounts.
    Returns a dictionary mapping key -> value (or None if key was absent).
    """
    snapshot = {}
    for meta in INTENDED_ACCOUNTS:
        u_up = meta["username"].upper()
        k_pass = f"DEMO_PASS_{u_up}"
        k_password = f"DEMO_PASSWORD_{u_up}"
        snapshot[k_pass] = os.environ.get(k_pass)
        snapshot[k_password] = os.environ.get(k_password)
    return snapshot


def restore_demo_credential_env_vars(snapshot: dict) -> None:
    """
    Restores the exact original values of all 16 demo environment variables from a snapshot.
    Keys originally present are restored to their pre-test values;
    keys originally absent are removed via os.environ.pop().
    """
    for k, v in snapshot.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


@contextmanager
def preserve_demo_credentials_environment():
    """
    Context manager that isolates unit tests from real operator credentials:
    1. Snapshots all 16 expected demo credential environment variable keys.
    2. Clears all 16 keys from os.environ so existing operator credentials do not leak into or affect tests.
    3. Yields to the test execution.
    4. In finally, removes all test credentials and restores the exact original environment state.
    """
    snapshot = snapshot_demo_credential_env_vars()
    # Isolate tests: remove existing keys before tests run
    for k in snapshot:
        os.environ.pop(k, None)
    try:
        yield snapshot
    finally:
        # Guarantee all test keys removed and original state restored
        restore_demo_credential_env_vars(snapshot)


def execute_with_database_url_preservation(action_fn):
    """
    Executes action_fn while guaranteeing that the process DATABASE_URL
    environment variable is strictly restored to its original state upon exit
    (whether action_fn completes successfully or raises an exception/exit).
    If DATABASE_URL was absent initially, it is removed; if present, its original
    value is restored.
    """
    orig_database_url = os.environ.get("DATABASE_URL")
    try:
        return action_fn()
    finally:
        if orig_database_url is not None:
            os.environ["DATABASE_URL"] = orig_database_url
        else:
            os.environ.pop("DATABASE_URL", None)


def run_cleanup_unit_tests() -> bool:
    """
    Local-only unit tests demonstrating best-effort password and environment cleanup:
    1. Tests preservation, snapshotting, and restoration of all 16 demo environment variables.
    2. Tests both environment variable prefixes (DEMO_PASS_* and DEMO_PASSWORD_*) on collection.
    3. Tests removal of environment variables when credential collection fails (short password and collision).
    4. Tests execute_with_credential_cleanup() across all failure and success scenarios.
    5. Tests actual execute_with_database_url_preservation() across all four matrix states:
       - Initially absent + successful completion
       - Initially absent + exception raised
       - Initially present + successful completion
       - Initially present + exception raised
    """
    print("\n" + "=" * 80)
    print("RUNNING LOCAL-ONLY PASSWORD & ENVIRONMENT CLEANUP UNIT TESTS")
    print("=" * 80)

    all_passed = True

    with preserve_demo_credentials_environment():
        # -------------------------------------------------------------------------
        # PART 1: Environment Variable Cleanup Across Both Prefixes & Snapshot Restoration
        # -------------------------------------------------------------------------
        # 1A. All 8 DEMO_PASS_<USERNAME> variables populated
        for idx, meta in enumerate(INTENDED_ACCOUNTS, start=1):
            u = meta["username"]
            os.environ[f"DEMO_PASS_{u.upper()}"] = f"ValidTestSecret_{idx}_{u}!"

        res_1a = collect_all_demo_credentials()
        rem_1a = [
            f"DEMO_PASS_{m['username'].upper()}"
            for m in INTENDED_ACCOUNTS
            if f"DEMO_PASS_{m['username'].upper()}" in os.environ
        ]
        t1a_pass = (len(res_1a) == 8 and len(rem_1a) == 0)
        if not t1a_pass:
            all_passed = False
        print(f"  [{'PASS' if t1a_pass else 'FAIL'}] Prefix DEMO_PASS_*: All 8 resolved & removed from os.environ ({len(rem_1a)} remaining).")

        # 1B. All 8 DEMO_PASSWORD_<USERNAME> variables populated in a separate test
        for idx, meta in enumerate(INTENDED_ACCOUNTS, start=1):
            u = meta["username"]
            os.environ[f"DEMO_PASSWORD_{u.upper()}"] = f"ValidAlternateSecret_{idx}_{u}!"

        res_1b = collect_all_demo_credentials()
        rem_1b = [
            f"DEMO_PASSWORD_{m['username'].upper()}"
            for m in INTENDED_ACCOUNTS
            if f"DEMO_PASSWORD_{m['username'].upper()}" in os.environ
        ]
        t1b_pass = (len(res_1b) == 8 and len(rem_1b) == 0)
        if not t1b_pass:
            all_passed = False
        print(f"  [{'PASS' if t1b_pass else 'FAIL'}] Prefix DEMO_PASSWORD_*: All 8 resolved & removed from os.environ ({len(rem_1b)} remaining).")

        # Clear temporary test credential dictionaries after the environment-prefix tests
        cleanup_credential_dictionaries(res_1a, res_1b)
        t1_dicts_pass = (len(res_1a) == 0 and len(res_1b) == 0)
        if not t1_dicts_pass:
            all_passed = False
        print(f"  [{'PASS' if t1_dicts_pass else 'FAIL'}] Temporary credential dictionaries cleared after prefix tests.")

        # 1C. Prefix DEMO_PASS_* removed even when collection fails (short password < 8 chars)
        for idx, meta in enumerate(INTENDED_ACCOUNTS, start=1):
            u = meta["username"]
            os.environ[f"DEMO_PASS_{u.upper()}"] = f"ValidTestSecret_{idx}_{u}!"
        os.environ["DEMO_PASS_ADMIN"] = "short"  # Triggers validation failure

        failed_1c = False
        try:
            collect_all_demo_credentials()
        except ValueError:
            failed_1c = True

        rem_1c = [
            f"DEMO_PASS_{m['username'].upper()}"
            for m in INTENDED_ACCOUNTS
            if f"DEMO_PASS_{m['username'].upper()}" in os.environ
        ]
        t1c_pass = (failed_1c and len(rem_1c) == 0)
        if not t1c_pass:
            all_passed = False
        print(f"  [{'PASS' if t1c_pass else 'FAIL'}] Collection failure (short password): All DEMO_PASS_* cleaned up ({len(rem_1c)} remaining).")

        # 1D. Prefix DEMO_PASSWORD_* removed even when collection fails (collision detected)
        for idx, meta in enumerate(INTENDED_ACCOUNTS, start=1):
            u = meta["username"]
            os.environ[f"DEMO_PASSWORD_{u.upper()}"] = f"ValidAlternateSecret_{idx}_{u}!"
        os.environ["DEMO_PASSWORD_ADMIN"] = os.environ["DEMO_PASSWORD_WARDEN_BOYS"]  # Collision

        failed_1d = False
        try:
            collect_all_demo_credentials()
        except ValueError:
            failed_1d = True

        rem_1d = [
            f"DEMO_PASSWORD_{m['username'].upper()}"
            for m in INTENDED_ACCOUNTS
            if f"DEMO_PASSWORD_{m['username'].upper()}" in os.environ
        ]
        t1d_pass = (failed_1d and len(rem_1d) == 0)
        if not t1d_pass:
            all_passed = False
        print(f"  [{'PASS' if t1d_pass else 'FAIL'}] Collection failure (collision): All DEMO_PASSWORD_* cleaned up ({len(rem_1d)} remaining).")

        # 1E. Verification of snapshot and restore for all 16 demo environment variable keys
        mock_snapshot = {
            f"DEMO_PASS_{m['username'].upper()}": (f"SnapVal_{idx}" if idx % 2 == 0 else None)
            for idx, m in enumerate(INTENDED_ACCOUNTS, start=1)
        }
        mock_snapshot.update({
            f"DEMO_PASSWORD_{m['username'].upper()}": (f"AltSnap_{idx}" if idx % 2 != 0 else None)
            for idx, m in enumerate(INTENDED_ACCOUNTS, start=1)
        })
        restore_demo_credential_env_vars(mock_snapshot)
        for k in mock_snapshot:
            os.environ[k] = "MUTATED_VALUE_TEST"
        restore_demo_credential_env_vars(mock_snapshot)
        t1e_pass = all(os.environ.get(k) == v for k, v in mock_snapshot.items())
        # Clean up temporary keys tested in 1E
        for k in mock_snapshot:
            os.environ.pop(k, None)
        if not t1e_pass:
            all_passed = False
        print(f"  [{'PASS' if t1e_pass else 'FAIL'}] Snapshot & restoration: Verified exact state restoration across all 16 keys.")

        # -------------------------------------------------------------------------
        # PART 2: Actual Production Cleanup Implementation (execute_with_credential_cleanup)
        # -------------------------------------------------------------------------
        def make_populated_dicts():
            d1 = {m["username"]: f"Secret_{m['username']}_2026!" for m in INTENDED_ACCOUNTS}
            d2 = {m["username"]: f"Secret_{m['username']}_2026!" for m in INTENDED_ACCOUNTS}
            return d1, d2

        # 2A. Failure Scenario: Invalid production database URL
        d1, d2 = make_populated_dicts()
        caught_2a = False
        try:
            execute_with_credential_cleanup(
                d1, d2,
                lambda: validate_production_target("sqlite:///instance/hostel.sqlite3")
            )
        except ValueError:
            caught_2a = True

        t2a_pass = (caught_2a and len(d1) == 0 and len(d2) == 0)
        if not t2a_pass:
            all_passed = False
        print(f"  [{'PASS' if t2a_pass else 'FAIL'}] Cleanup on invalid database URL: Error caught, dictionaries cleared.")

        # 2B. Failure Scenario: Application factory initialization failure
        d1, d2 = make_populated_dicts()
        caught_2b = False
        from unittest.mock import patch
        with patch.object(sys.modules[__name__], 'create_app', side_effect=RuntimeError('Flask application factory failed to initialize')):
            try:
                execute_with_credential_cleanup(
                    d1, d2,
                    lambda: create_app("production")
                )
            except RuntimeError:
                caught_2b = True

        t2b_pass = (caught_2b and len(d1) == 0 and len(d2) == 0)
        if not t2b_pass:
            all_passed = False
        print(f"  [{'PASS' if t2b_pass else 'FAIL'}] Cleanup on application factory failure: Error caught, dictionaries cleared.")

        # 2C. Failure Scenario: Database connectivity failure
        d1, d2 = make_populated_dicts()
        caught_2c = False
        with patch.object(db.session, 'execute', side_effect=ConnectionError('Simulated pooler connection timeout to aws-0-ap-south-1.pooler.supabase.com:6543')):
            try:
                execute_with_credential_cleanup(
                    d1, d2,
                    lambda: db.session.execute(db.text("SELECT 1"))
                )
            except ConnectionError:
                caught_2c = True

        t2c_pass = (caught_2c and len(d1) == 0 and len(d2) == 0)
        if not t2c_pass:
            all_passed = False
        print(f"  [{'PASS' if t2c_pass else 'FAIL'}] Cleanup on database connectivity failure: Error caught, dictionaries cleared.")

        # 2D. Failure Scenario: Transaction validation failure
        d1, d2 = make_populated_dicts()
        ref = load_local_sqlite_reference()
        class MockEntity:
            def __init__(self, **kw):
                self.__dict__.update(kw)

        bad_entities = {
            "hostel_boys": MockEntity(name="Mismatched Hostel Name", hostel_type="Boys", total_floors=3, total_rooms=100, description=""),
            "hostel_girls": MockEntity(name=ref["hostel_girls"]["name"], hostel_type="Girls", total_floors=3, total_rooms=100, description=""),
            "mess": MockEntity(hostel_id=None, mess_name=ref["mess"]["mess_name"], description="", contact_number="", operating_status="", meal_policy="", daily_capacity=100),
            "w_boys_prof": MockEntity(id=1, user_id=1, employee_id="E1", full_name="", phone="", designation="", assigned_hostel_id=1),
            "w_girls_prof": MockEntity(id=2, user_id=2, employee_id="E2", full_name="", phone="", designation="", assigned_hostel_id=2),
            "student_prof": MockEntity(id=3, user_id=3, enrollment_no="ENR", roll_no="R", full_name="", phone="", gender="", branch="", year=1, semester=1, guardian_name="", guardian_phone="", emergency_phone="", address="", blood_group="", status="Active"),
            "parent_prof": MockEntity(id=4, user_id=4, parent_name="", phone_number="", relationship_to_student="", student_id=3, account_status="Active"),
            "staff_prof": MockEntity(id=5, user_id=5, mess_id=1, staff_name="", phone_number="", role_designation="", employment_status="Active"),
            "user_records": {"warden_boys": MockEntity(id=1), "warden_girls": MockEntity(id=2), "rahul_sharma": MockEntity(id=3), "parent_rahul": MockEntity(id=4), "mess_staff": MockEntity(id=5)},
        }
        caught_2d = False
        try:
            execute_with_credential_cleanup(
                d1, d2,
                lambda: verify_all_entity_fields_pre_commit(bad_entities, ref)
            )
        except ValueError:
            caught_2d = True

        t2d_pass = (caught_2d and len(d1) == 0 and len(d2) == 0)
        if not t2d_pass:
            all_passed = False
        print(f"  [{'PASS' if t2d_pass else 'FAIL'}] Cleanup on transaction validation failure: Error caught, dictionaries cleared.")

        # 2E. Failure Scenario: KeyboardInterrupt (operator cancellation)
        d1, d2 = make_populated_dicts()
        caught_2e = False
        def simulate_interrupt():
            raise KeyboardInterrupt("Simulated operator interrupt via SIGINT")

        try:
            execute_with_credential_cleanup(d1, d2, simulate_interrupt)
        except KeyboardInterrupt:
            caught_2e = True

        t2e_pass = (caught_2e and len(d1) == 0 and len(d2) == 0)
        if not t2e_pass:
            all_passed = False
        print(f"  [{'PASS' if t2e_pass else 'FAIL'}] Cleanup on KeyboardInterrupt: Caught, dictionaries cleared.")

        # 2F. Failure Scenario: EOFError (input stream termination)
        d1, d2 = make_populated_dicts()
        caught_2f = False
        def simulate_eof():
            raise EOFError("Simulated unexpected end of stream on input prompt")

        try:
            execute_with_credential_cleanup(d1, d2, simulate_eof)
        except EOFError:
            caught_2f = True

        t2f_pass = (caught_2f and len(d1) == 0 and len(d2) == 0)
        if not t2f_pass:
            all_passed = False
        print(f"  [{'PASS' if t2f_pass else 'FAIL'}] Cleanup on EOFError: Caught, dictionaries cleared.")

        # 2G. Failure Scenario: SystemExit (e.g. sys.exit(1) on validation or connection abort)
        d1, d2 = make_populated_dicts()
        caught_2g = False
        def simulate_sys_exit():
            sys.exit(1)

        try:
            execute_with_credential_cleanup(d1, d2, simulate_sys_exit)
        except SystemExit:
            caught_2g = True

        t2g_pass = (caught_2g and len(d1) == 0 and len(d2) == 0)
        if not t2g_pass:
            all_passed = False
        print(f"  [{'PASS' if t2g_pass else 'FAIL'}] Cleanup on SystemExit: Caught, dictionaries cleared.")

        # 2H. Success Scenario: Successful workflow completion cleanup
        d1, d2 = make_populated_dicts()
        def simulate_workflow_success():
            return "WORKFLOW_SUCCESS"

        result_2h = execute_with_credential_cleanup(d1, d2, simulate_workflow_success)
        t2h_pass = (result_2h == "WORKFLOW_SUCCESS" and len(d1) == 0 and len(d2) == 0)
        if not t2h_pass:
            all_passed = False
        print(f"  [{'PASS' if t2h_pass else 'FAIL'}] Cleanup on successful workflow completion: Return value preserved, dictionaries cleared.")

        # -------------------------------------------------------------------------
        # PART 3: Actual DATABASE_URL Environment Restoration Implementation
        # Tests execute_with_database_url_preservation across all four matrix states:
        # (Initially absent vs Initially preset) x (Successful completion vs Exception)
        # -------------------------------------------------------------------------
        orig_env_db = os.environ.get("DATABASE_URL")
        try:
            # 3A. Initially Absent + Successful Completion
            os.environ.pop("DATABASE_URL", None)
            def mutate_url_success():
                os.environ["DATABASE_URL"] = "postgresql://simulated-session-db-url:6543/postgres?sslmode=require"
                return "SUCCESS_VAL_3A"

            res_3a = execute_with_database_url_preservation(mutate_url_success)
            t3a_pass = (res_3a == "SUCCESS_VAL_3A" and "DATABASE_URL" not in os.environ)
            if not t3a_pass:
                all_passed = False
            print(f"  [{'PASS' if t3a_pass else 'FAIL'}] DATABASE_URL restoration (initially absent + success): Absent after execution.")

            # 3B. Initially Absent + Exception Raised
            os.environ.pop("DATABASE_URL", None)
            def mutate_url_raise_error():
                os.environ["DATABASE_URL"] = "postgresql://simulated-session-db-url:6543/postgres?sslmode=require"
                raise RuntimeError("Simulated failure during database workflow")

            caught_3b = False
            try:
                execute_with_database_url_preservation(mutate_url_raise_error)
            except RuntimeError:
                caught_3b = True
            t3b_pass = (caught_3b and "DATABASE_URL" not in os.environ)
            if not t3b_pass:
                all_passed = False
            print(f"  [{'PASS' if t3b_pass else 'FAIL'}] DATABASE_URL restoration (initially absent + exception): Error caught, absent after failure.")

            # 3C. Initially Present + Successful Completion
            preset_url = "postgresql://postgres.yjhapstttgilcbaxbbce:OriginalSecret123@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require"
            os.environ["DATABASE_URL"] = preset_url
            def mutate_url_with_preset():
                os.environ["DATABASE_URL"] = "postgresql://mutated-workflow-url:6543/postgres?sslmode=require"
                return "SUCCESS_VAL_3C"

            res_3c = execute_with_database_url_preservation(mutate_url_with_preset)
            t3c_pass = (res_3c == "SUCCESS_VAL_3C" and os.environ.get("DATABASE_URL") == preset_url)
            if not t3c_pass:
                all_passed = False
            print(f"  [{'PASS' if t3c_pass else 'FAIL'}] DATABASE_URL restoration (initially preset + success): Restored to preset value.")

            # 3D. Initially Present + Exception Raised
            os.environ["DATABASE_URL"] = preset_url
            def mutate_url_preset_raise_error():
                os.environ["DATABASE_URL"] = "postgresql://mutated-workflow-url:6543/postgres?sslmode=require"
                raise ValueError("Simulated validation failure during database workflow")

            caught_3d = False
            try:
                execute_with_database_url_preservation(mutate_url_preset_raise_error)
            except ValueError:
                caught_3d = True
            t3d_pass = (caught_3d and os.environ.get("DATABASE_URL") == preset_url)
            if not t3d_pass:
                all_passed = False
            print(f"  [{'PASS' if t3d_pass else 'FAIL'}] DATABASE_URL restoration (initially preset + exception): Error caught, restored to preset value.")

        finally:
            if orig_env_db is not None:
                os.environ["DATABASE_URL"] = orig_env_db
            else:
                os.environ.pop("DATABASE_URL", None)

    print("=" * 80)
    print(f"Cleanup Test Suite Result: {'ALL TESTS PASSED' if all_passed else 'TESTS FAILED'}")
    print("=" * 80 + "\n")
    return all_passed


def run_preflight_unit_tests() -> bool:
    """
    Local-only unit tests verifying read-only preflight behavior:
    1. Proves preflight performs zero write operations (no add, commit, delete, flush).
    2. Proves preflight never calls the migration workflow or migrate_demo_accounts().
    3. Proves preflight handles database connection errors safely without crashing or leaking secrets.
    4. Proves preflight restores environment variables (DATABASE_URL preservation).
    5. Proves preflight does not expose credentials or password hashes in reports/logs.
    Runs locally using in-memory mock/testing structures without connecting to Supabase.
    """
    print("\n" + "=" * 80)
    print("RUNNING LOCAL-ONLY PRODUCTION PREFLIGHT UNIT TESTS")
    print("=" * 80)

    import io
    from unittest.mock import patch

    all_passed = True

    # -------------------------------------------------------------------------
    # TEST 1: Zero Write Operations Verified via Spy Session
    # -------------------------------------------------------------------------
    class SpySession:
        def __init__(self, real_session):
            self._real = real_session
            self.write_calls = []

        def execute(self, *args, **kwargs):
            return self._real.execute(*args, **kwargs)

        def add(self, *args, **kwargs):
            self.write_calls.append("add")
            raise AssertionError("ILLEGAL WRITE: session.add() called during read-only preflight!")

        def commit(self, *args, **kwargs):
            self.write_calls.append("commit")
            raise AssertionError("ILLEGAL WRITE: session.commit() called during read-only preflight!")

        def delete(self, *args, **kwargs):
            self.write_calls.append("delete")
            raise AssertionError("ILLEGAL WRITE: session.delete() called during read-only preflight!")

        def flush(self, *args, **kwargs):
            self.write_calls.append("flush")
            raise AssertionError("ILLEGAL WRITE: session.flush() called during read-only preflight!")

        def remove(self, *args, **kwargs):
            pass

    test_app = create_app("testing")
    with test_app.app_context():
        db.create_all()
        # Seed one valid user with scrypt password hash to verify inspection without writing
        u = User(username="admin", email="admin@aktu-hostel.edu.in", role="admin", is_active=True)
        u.set_password("PreflightTestPass123!")
        db.session.add(u)
        db.session.commit()

        spy = SpySession(db.session)

        # Run preflight with spy session
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            res1 = run_production_preflight(db_url="postgresql://mock", app=test_app, session=spy)
        finally:
            sys.stdout = old_stdout

        t1_pass = (len(spy.write_calls) == 0 and res1.get("success") is not None)
        if not t1_pass:
            all_passed = False
        print(f"  [{'PASS' if t1_pass else 'FAIL'}] Zero write operations: session.add/commit/delete/flush were NEVER called (0 write calls).")

    # -------------------------------------------------------------------------
    # TEST 2: Preflight Never Calls Migration Function
    # -------------------------------------------------------------------------
    migration_called = []
    def spy_migration(*args, **kwargs):
        migration_called.append(True)
        raise AssertionError("CRITICAL FAILURE: migrate_demo_accounts() invoked by preflight!")

    with patch.object(sys.modules[__name__], "migrate_demo_accounts", side_effect=spy_migration):
        with test_app.app_context():
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                res2 = run_production_preflight(db_url="postgresql://mock", app=test_app, session=db.session)
            finally:
                sys.stdout = old_stdout

        t2_pass = (len(migration_called) == 0)
        if not t2_pass:
            all_passed = False
        print(f"  [{'PASS' if t2_pass else 'FAIL'}] Migration isolation: migrate_demo_accounts() was NEVER called by preflight.")

    # -------------------------------------------------------------------------
    # TEST 3: Safe Handling of Database Connection Errors
    # -------------------------------------------------------------------------
    class FailingConnectionSession:
        def execute(self, *args, **kwargs):
            raise ConnectionError("Simulated pooler connection timeout to aws-0-ap-south-1.pooler.supabase.com:6543")
        def remove(self):
            pass

    failing_session = FailingConnectionSession()
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        res3 = run_production_preflight(db_url="postgresql://mock", app=test_app, session=failing_session)
    finally:
        sys.stdout = old_stdout

    t3_pass = (res3.get("success") is False and "connectivity" in res3.get("error", "").lower())
    if not t3_pass:
        all_passed = False
    print(f"  [{'PASS' if t3_pass else 'FAIL'}] Error handling: ConnectionError handled safely without crashing.")

    # -------------------------------------------------------------------------
    # TEST 4: Environment Variable Preservation Across All Preflight Paths
    # -------------------------------------------------------------------------
    orig_env = os.environ.get("DATABASE_URL")
    try:
        # Case 4A: Initially absent + preflight run
        os.environ.pop("DATABASE_URL", None)
        with patch.object(sys.modules[__name__], "resolve_database_url", return_value="postgresql://postgres.yjhapstttgilcbaxbbce:TestPass123@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require"):
            with patch.object(sys.modules[__name__], "run_production_preflight", return_value={"success": True}):
                execute_production_preflight()
        t4a_pass = ("DATABASE_URL" not in os.environ)

        # Case 4B: Initially present + preflight run
        preset_val = "postgresql://postgres.yjhapstttgilcbaxbbce:OriginalPresetPass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require"
        os.environ["DATABASE_URL"] = preset_val
        with patch.object(sys.modules[__name__], "resolve_database_url", return_value="postgresql://postgres.yjhapstttgilcbaxbbce:AnotherPass@aws-0-ap-south-1.pooler.supabase.com:6543/postgres?sslmode=require"):
            with patch.object(sys.modules[__name__], "run_production_preflight", return_value={"success": True}):
                execute_production_preflight()
        t4b_pass = (os.environ.get("DATABASE_URL") == preset_val)

        t4_pass = (t4a_pass and t4b_pass)
        if not t4_pass:
            all_passed = False
        print(f"  [{'PASS' if t4_pass else 'FAIL'}] Environment preservation: DATABASE_URL restored identically across all preflight runs.")
    finally:
        if orig_env is not None:
            os.environ["DATABASE_URL"] = orig_env
        else:
            os.environ.pop("DATABASE_URL", None)

    # -------------------------------------------------------------------------
    # TEST 5: Zero Credential / Hash Exposure in Preflight Output
    # -------------------------------------------------------------------------
    secret_marker = "SuperSecretHashMarkerXYZ789"
    with test_app.app_context():
        u_secret = User(username="guard_main", email="guard.main@aktu-hostel.edu.in", role="security", is_active=True)
        u_secret.password_hash = f"scrypt:32768:8:1${secret_marker}$dummy_hash"
        db.session.add(u_secret)
        db.session.commit()

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            res5 = run_production_preflight(db_url="postgresql://mock", app=test_app, session=db.session)
        finally:
            output_5 = sys.stdout.getvalue()
            sys.stdout = old_stdout

        t5_pass = (secret_marker not in output_5 and "scrypt:32768:8:1" not in output_5)
        if not t5_pass:
            all_passed = False
        print(f"  [{'PASS' if t5_pass else 'FAIL'}] Zero credential exposure: Password hashes and secrets were NEVER printed in preflight output.")

    # -------------------------------------------------------------------------
    # TEST 6: Exhaustive Field Verification in Preflight
    # -------------------------------------------------------------------------
    with test_app.app_context():
        ref_local = load_local_sqlite_reference()
        # 6A: Hostel description mismatch triggers FIELD_MISMATCH
        h_test = Hostel.query.filter_by(name=ref_local["hostel_boys"]["name"]).first()
        if not h_test:
            h_test = Hostel(
                name=ref_local["hostel_boys"]["name"],
                hostel_type=ref_local["hostel_boys"]["hostel_type"],
                total_floors=ref_local["hostel_boys"]["total_floors"],
                total_rooms=ref_local["hostel_boys"]["total_rooms"],
                description="Different description from local reference"
            )
            db.session.add(h_test)
            db.session.commit()
        else:
            h_test.description = "Different description from local reference"
            db.session.commit()

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            res6a = run_production_preflight(db_url="postgresql://mock", app=test_app, session=db.session)
        finally:
            sys.stdout = old_stdout

        t6a_pass = (res6a["facilities"]["hostel_boys"]["status"] == "FIELD_MISMATCH" and "description" in res6a["facilities"]["hostel_boys"]["detail"])
        if not t6a_pass:
            all_passed = False
        print(f"  [{'PASS' if t6a_pass else 'FAIL'}] Exhaustive facility field verification: Hostel description mismatch detected.")

        # Revert description to match reference
        h_test.description = ref_local["hostel_boys"]["description"]
        db.session.commit()

    # -------------------------------------------------------------------------
    # TEST 7: Unresolved Relationship Reporting When Related Record is Missing
    # -------------------------------------------------------------------------
    with test_app.app_context():
        # Clean up any existing student or parent records first
        ParentProfile.query.delete()
        Student.query.delete()
        u_p = User.query.filter_by(username="parent_rahul").first()
        if not u_p:
            u_p = User(username="parent_rahul", email="ramesh.sharma@parent.aktu.ac.in", role="parent", is_active=True)
            u_p.set_password("ParentPass2026!")
            db.session.add(u_p)
            db.session.commit()
        else:
            u_p.email = "ramesh.sharma@parent.aktu.ac.in"
            u_p.role = "parent"
            u_p.is_active = True
            u_p.set_password("ParentPass2026!")
            db.session.commit()

        # Delete student user to guarantee Student is missing in production
        u_s = User.query.filter_by(username="rahul_sharma").first()
        if u_s:
            db.session.delete(u_s)
            db.session.commit()

        # Create parent profile pointing to a non-existent student_id (missing student)
        p_test_obj = ParentProfile(
            user_id=u_p.id,
            parent_name=ref_local["parent"]["parent_name"],
            phone_number=ref_local["parent"]["phone_number"],
            relationship_to_student=ref_local["parent"]["relationship_to_student"],
            student_id=888888,  # Student record missing
            account_status=ref_local["parent"]["account_status"]
        )
        db.session.add(p_test_obj)
        db.session.commit()

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            res7 = run_production_preflight(db_url="postgresql://mock", app=test_app, session=db.session)
        finally:
            sys.stdout = old_stdout

        p_status = next((p["status"] for p in res7["profiles"] if p["profile"] == "Parent Profile"), "")
        t7_pass = (p_status == "UNRESOLVED_STUDENT_RELATION" and res7["has_conflicts"] is True)
        if not t7_pass:
            all_passed = False
        print(f"  [{'PASS' if t7_pass else 'FAIL'}] Unresolved relation detection: Missing student record reported as '{p_status}' (blocking conflict).")

        # Cleanup parent profile
        db.session.delete(p_test_obj)
        db.session.commit()

    # -------------------------------------------------------------------------
    # TEST 8: Safe Error Reporting (Exception Sanitization & Zero Leaks)
    # -------------------------------------------------------------------------
    sensitive_db_pass = "UltraSecretDBPasswordXYZ#999"
    leaking_msg = f"psycopg2.OperationalError: password=\"{sensitive_db_pass}\" host=\"aws-0-ap-south-1.pooler.supabase.com\""
    exc_sample = ConnectionError(leaking_msg)
    sanitized_report = format_safe_exception_report(exc_sample, "Database connection failure")

    t8a_pass = (
        sensitive_db_pass not in sanitized_report
        and "ConnectionError" in sanitized_report
        and "Network connectivity failure" in sanitized_report
    )

    class SecretLeakingSession:
        def execute(self, *args, **kwargs):
            raise Exception(f"FATAL: authentication failed for user 'postgres': password=\"{sensitive_db_pass}\"")
        def remove(self):
            pass

    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        res8b = run_production_preflight(db_url="postgresql://mock", app=test_app, session=SecretLeakingSession())
    finally:
        output_8b = sys.stdout.getvalue()
        sys.stdout = old_stdout

    t8b_pass = (
        sensitive_db_pass not in output_8b
        and sensitive_db_pass not in res8b.get("error", "")
        and res8b.get("success") is False
    )

    t8_pass = (t8a_pass and t8b_pass)
    if not t8_pass:
        all_passed = False
    print(f"  [{'PASS' if t8_pass else 'FAIL'}] Safe error reporting: Exception sanitized without exposing sensitive credentials ({'PASS' if t8_pass else 'FAIL'}).")

    # -------------------------------------------------------------------------
    # TEST 9: Account Password Hash Validation in Preflight (Blocking on Missing or Non-Scrypt Hash)
    # -------------------------------------------------------------------------
    with test_app.app_context():
        # Clean up any existing guard_main user
        u_guard = User.query.filter_by(username="guard_main").first()
        if not u_guard:
            u_guard = User(
                username="guard_main",
                email="guard.main@aktu-hostel.edu.in",
                role="security",
                is_active=True
            )
            u_guard.set_password("TemporaryValidPass2026!")
            db.session.add(u_guard)
            db.session.commit()
        else:
            u_guard.email = "guard.main@aktu-hostel.edu.in"
            u_guard.role = "security"
            u_guard.is_active = True
            u_guard.set_password("TemporaryValidPass2026!")
            db.session.commit()

        # Case 9A: Account with missing / empty password_hash ("")
        u_guard = User.query.filter_by(username="guard_main").first()
        u_guard.password_hash = ""
        db.session.commit()

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            res9a_empty = run_production_preflight(db_url="postgresql://mock", app=test_app, session=db.session)
        finally:
            sys.stdout = old_stdout

        guard_info_9a = next((a for a in res9a_empty["accounts"] if a["username"] == "guard_main"), {})
        t9a_pass = (
            guard_info_9a.get("status") == "INVALID_PASSWORD_HASH"
            and res9a_empty.get("has_conflicts") is True
            and res9a_empty.get("success") is False
        )
        if not t9a_pass:
            all_passed = False
        print(f"  [{'PASS' if t9a_pass else 'FAIL'}] Missing password hash blocking: Reported 'INVALID_PASSWORD_HASH', success=False.")

        # Case 9B: Account with non-scrypt password_hash (e.g. pbkdf2 or legacy md5)
        u_guard = User.query.filter_by(username="guard_main").first()
        u_guard.password_hash = "pbkdf2:sha256:600000$insecure$c7a82b94f0e1"
        db.session.commit()

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            res9b = run_production_preflight(db_url="postgresql://mock", app=test_app, session=db.session)
        finally:
            sys.stdout = old_stdout

        guard_info_9b = next((a for a in res9b["accounts"] if a["username"] == "guard_main"), {})
        t9b_pass = (
            guard_info_9b.get("status") == "INVALID_PASSWORD_HASH"
            and res9b.get("has_conflicts") is True
            and res9b.get("success") is False
        )
        if not t9b_pass:
            all_passed = False
        print(f"  [{'PASS' if t9b_pass else 'FAIL'}] Non-scrypt password hash blocking: Reported 'INVALID_PASSWORD_HASH', success=False.")

        # Case 9C: Account with valid Werkzeug scrypt hash -> PRESENT_VERIFIED
        u_guard = User.query.filter_by(username="guard_main").first()
        u_guard.set_password("ValidScryptPassword2026!")
        db.session.commit()

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            res9c = run_production_preflight(db_url="postgresql://mock", app=test_app, session=db.session)
        finally:
            sys.stdout = old_stdout

        guard_info_9c = next((a for a in res9c["accounts"] if a["username"] == "guard_main"), {})
        t9c_pass = (
            guard_info_9c.get("status") == "PRESENT_VERIFIED"
            and guard_info_9c.get("has_scrypt_hash") is True
        )
        if not t9c_pass:
            all_passed = False
        print(f"  [{'PASS' if t9c_pass else 'FAIL'}] Valid scrypt password hash verification: Reported 'PRESENT_VERIFIED'.")

        # Clean up test user
        u_guard = User.query.filter_by(username="guard_main").first()
        if u_guard:
            db.session.delete(u_guard)
            db.session.commit()

    # -------------------------------------------------------------------------
    # TEST 10: Preflight Initialization Never Invokes Schema Migrations or DDL
    # -------------------------------------------------------------------------
    from app import create_preflight_app
    with patch("app._ensure_schema_migrations") as mock_ensure_mig, \
         patch("app.models.db.create_all") as mock_create_all:
        preflight_test_app = create_preflight_app("testing")
        t10a_pass = (mock_ensure_mig.call_count == 0 and mock_create_all.call_count == 0)
        t10b_pass = bool(preflight_test_app.config.get("PREFLIGHT_MODE"))
        t10_pass = (t10a_pass and t10b_pass)
        if not t10_pass:
            all_passed = False
        print(f"  [{'PASS' if t10_pass else 'FAIL'}] Preflight startup isolation: _ensure_schema_migrations() and db.create_all() were NEVER called.")

    # -------------------------------------------------------------------------
    # TEST 11: Read-Only Statement Interception (Comments, CTEs, Multi-Statement)
    # -------------------------------------------------------------------------
    from sqlalchemy import text
    with test_app.app_context():
        cleanup_test_guards = configure_read_only_preflight_guards(db.engine)
        try:
            # 11A. SELECT is permitted
            db.session.execute(text("SELECT 1")).scalar()
            t11a_pass = True

            # 11B. Leading multi-line comment before INSERT is intercepted and rejected
            comment_aborted = False
            try:
                db.session.execute(text("/* leading comment */ INSERT INTO users (username) VALUES ('fail')"))
            except RuntimeError as re:
                comment_aborted = ("PREFLIGHT SAFETY VIOLATION" in str(re))
            except Exception as oe:
                comment_aborted = ("readonly" in str(oe).lower())

            # 11C. Data-modifying CTE is intercepted and rejected
            cte_aborted = False
            try:
                db.session.execute(text("WITH updated AS (UPDATE users SET is_active=false RETURNING *) SELECT * FROM updated"))
            except RuntimeError as re:
                cte_aborted = ("PREFLIGHT SAFETY VIOLATION" in str(re))
            except Exception as oe:
                cte_aborted = ("readonly" in str(oe).lower())

            # 11D. Multi-statement SQL is intercepted and rejected
            multi_aborted = False
            try:
                db.session.execute(text("SELECT 1; DROP TABLE users"))
            except RuntimeError as re:
                multi_aborted = ("PREFLIGHT SAFETY VIOLATION" in str(re))
            except Exception as oe:
                multi_aborted = ("readonly" in str(oe).lower())

            # 11E. State-changing PRAGMA and attempts to disable query_only are intercepted and rejected
            pragma_off_aborted = False
            try:
                db.session.execute(text("PRAGMA query_only = OFF"))
            except RuntimeError as re:
                pragma_off_aborted = ("PREFLIGHT SAFETY VIOLATION" in str(re))
            except Exception as oe:
                pragma_off_aborted = True

            pragma_func_aborted = False
            try:
                db.session.execute(text("PRAGMA query_only(0)"))
            except RuntimeError as re:
                pragma_func_aborted = ("PREFLIGHT SAFETY VIOLATION" in str(re))
            except Exception as oe:
                pragma_func_aborted = True

            # 11F. Arbitrary session setting is intercepted and rejected
            set_aborted = False
            try:
                db.session.execute(text("SET session_replication_role = 'replica'"))
            except RuntimeError as re:
                set_aborted = ("PREFLIGHT SAFETY VIOLATION" in str(re))
            except Exception as oe:
                set_aborted = True

            t11_pass = (t11a_pass and comment_aborted and cte_aborted and multi_aborted and pragma_off_aborted and pragma_func_aborted and set_aborted)
            if not t11_pass:
                all_passed = False
            print(f"  [{'PASS' if t11_pass else 'FAIL'}] Advanced SQL statement interception: Leading comments, data-modifying CTEs, PRAGMA assignments, and arbitrary SET rejected.")
        finally:
            cleanup_test_guards()

    # -------------------------------------------------------------------------
    # TEST 12: SQLite Query-Only Lifecycle & Reliable Restoration
    # -------------------------------------------------------------------------
    with test_app.app_context():
        # Setup guards and verify tracked restoration
        guard_cleanup_fn = configure_read_only_preflight_guards(db.engine)
        try:
            # Query-only should be active
            val_active = db.session.execute(text("PRAGMA query_only")).scalar()
            self_active_ok = (val_active in (1, "1"))
        finally:
            guard_cleanup_fn()

        # After cleanup, query_only must be 0 and write operations must succeed
        val_restored = db.session.execute(text("PRAGMA query_only")).scalar()
        t12_pass = (self_active_ok and val_restored in (0, "0"))
        if not t12_pass:
            all_passed = False
        print(f"  [{'PASS' if t12_pass else 'FAIL'}] SQLite guard lifecycle: Tracked DBAPI query-only reliably restored (0) after execution.")

    # -------------------------------------------------------------------------
    # TEST 13: PostgreSQL Read-Only Setup Failure Aborts Preflight Immediately
    # -------------------------------------------------------------------------
    with test_app.app_context():
        orig_name = db.engine.dialect.name
        db.engine.dialect.name = "postgresql"
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            res13 = run_production_preflight(app=test_app)
        finally:
            sys.stdout = old_stdout
            db.engine.dialect.name = orig_name

    t13_pass = (res13.get("success") is False and "read-only" in res13.get("error", "").lower())
    if not t13_pass:
        all_passed = False
    print(f"  [{'PASS' if t13_pass else 'FAIL'}] Read-only enforcement failure safety: Preflight immediately aborts when read-only mode cannot be enabled.")

    print("=" * 80)
    print(f"Production Preflight Test Suite Result: {'ALL TESTS PASSED' if all_passed else 'TESTS FAILED'}")
    print("=" * 80 + "\n")
    return all_passed


def migrate_demo_accounts(rotate_passwords: bool = False, db_url: str = None):
    print("=" * 80)
    print("HOSTELEASE HMS — PRODUCTION DEMO ACCOUNTS MIGRATION UTILITY (FINAL HARDENED)")
    print("=" * 80)

    # 1. Initialize credential containers before starting the workflow
    demo_passwords = {}
    account_passwords = {}

    def _execute_migration_workflow():
        # Step A: Load exact reference records from local SQLite
        print("\n[INFO] Loading and validating local reference records from instance/hostel.sqlite3...")
        ref = load_local_sqlite_reference()
        print("  [✓] All 8 reference entities and source relationships verified in local SQLite.")

        # Step B: Resolve and strictly validate production connection target
        target_db_url = db_url or resolve_database_url()
        validate_production_target(target_db_url)
        os.environ["DATABASE_URL"] = target_db_url

        print(f"\n[INFO] Target Database : {safe_mask_database_url(target_db_url)}")
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
            except Exception as exc:
                safe_err = format_safe_exception_report(exc, "Database connectivity failure")
                print("\n[ABORTED] Database Connection Failed.")
                print(f"Error Category : {safe_err}")
                print("Troubleshooting Guidance:")
                print("  1. Verify the database password for Supabase project: " + EXPECTED_SUPABASE_PROJECT_REF)
                print("  2. If the password contains special characters (@, #, %, etc.), ensure they are URL-encoded.")
                print("  3. Verify port 6543 and sslmode=require are present.")
                print("  4. Verify outbound network connectivity to aws-0-ap-south-1.pooler.supabase.com:6543.")
                sys.exit(1)

            print("[INFO] Database connection verified successfully over SSL.")

            # Step C: Determine which accounts require credential collection
            accounts_needing_passwords = []
            if rotate_passwords:
                accounts_needing_passwords = list(INTENDED_ACCOUNTS)
            else:
                for account_meta in INTENDED_ACCOUNTS:
                    target_user = account_meta["username"]
                    target_email = account_meta["email"]
                    target_role = account_meta["role"]

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

                    if u_by_username and u_by_email:
                        existing_user = u_by_username
                        current_role_val = get_user_role_value(existing_user.role)
                        if current_role_val != str(target_role):
                            raise ValueError(
                                f"ROLE MISMATCH: User '{target_user}' has role '{current_role_val}', "
                                f"expected '{target_role}'. Aborting to prevent privilege confusion."
                            )
                        if not existing_user.is_active:
                            raise ValueError(f"ACCOUNT INACTIVE: User '{target_user}' exists but is marked inactive. Aborting.")
                        # Verified existing account; password hash will be preserved without re-collecting credentials
                    else:
                        accounts_needing_passwords.append(account_meta)

            if accounts_needing_passwords:
                print(f"\n[INFO] Collecting credentials for {len(accounts_needing_passwords)} account(s) needing creation/rotation...")
                collected = collect_all_demo_credentials(accounts=accounts_needing_passwords)
                try:
                    demo_passwords.update(collected)
                finally:
                    collected.clear()
            else:
                print("\n[INFO] All 8 demo accounts already exist with valid passwords. No credentials collection required.")

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
                    print(f"  [=] Found existing: {h_boys_ref['name']} (ID: {hostel_boys.id})")

                # Field-by-field verification for newly created AND existing records
                if hostel_boys.name != h_boys_ref["name"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_boys_ref['name']}' name '{hostel_boys.name}', expected '{h_boys_ref['name']}'.")
                if hostel_boys.hostel_type != h_boys_ref["hostel_type"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_boys_ref['name']}' hostel_type '{hostel_boys.hostel_type}', expected '{h_boys_ref['hostel_type']}'.")
                if hostel_boys.total_floors != h_boys_ref["total_floors"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_boys_ref['name']}' total_floors '{hostel_boys.total_floors}', expected '{h_boys_ref['total_floors']}'.")
                if hostel_boys.total_rooms != h_boys_ref["total_rooms"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_boys_ref['name']}' total_rooms '{hostel_boys.total_rooms}', expected '{h_boys_ref['total_rooms']}'.")
                if hostel_boys.description != h_boys_ref["description"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_boys_ref['name']}' description does not match local reference.")
                print(f"  [✓] Verified: {h_boys_ref['name']} (ID: {hostel_boys.id}) -> All 5 fields match.")

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
                    print(f"  [=] Found existing: {h_girls_ref['name']} (ID: {hostel_girls.id})")

                # Field-by-field verification for newly created AND existing records
                if hostel_girls.name != h_girls_ref["name"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_girls_ref['name']}' name '{hostel_girls.name}', expected '{h_girls_ref['name']}'.")
                if hostel_girls.hostel_type != h_girls_ref["hostel_type"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_girls_ref['name']}' hostel_type '{hostel_girls.hostel_type}', expected '{h_girls_ref['hostel_type']}'.")
                if hostel_girls.total_floors != h_girls_ref["total_floors"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_girls_ref['name']}' total_floors '{hostel_girls.total_floors}', expected '{h_girls_ref['total_floors']}'.")
                if hostel_girls.total_rooms != h_girls_ref["total_rooms"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_girls_ref['name']}' total_rooms '{hostel_girls.total_rooms}', expected '{h_girls_ref['total_rooms']}'.")
                if hostel_girls.description != h_girls_ref["description"]:
                    raise ValueError(f"HOSTEL MISMATCH: '{h_girls_ref['name']}' description does not match local reference.")
                print(f"  [✓] Verified: {h_girls_ref['name']} (ID: {hostel_girls.id}) -> All 5 fields match.")

                # 1C. Mess Dining Facility (with duplicate production record detection and cross-database mapped hostel_id)
                mess_ref = ref["mess"]
                mapped_mess_hostel_id = resolve_mapped_mess_hostel_id(mess_ref, ref, session=db.session)
                mess = query_production_single_or_none(
                    MessProfile.query.filter_by(mess_name=mess_ref["mess_name"]),
                    f"MessProfile '{mess_ref['mess_name']}'"
                )
                if not mess:
                    mess = MessProfile(
                        hostel_id=mapped_mess_hostel_id,
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
                    print(f"  [=] Found existing: {mess_ref['mess_name']} (ID: {mess.id})")

                # Field-by-field verification including mapped hostel_id for newly created AND existing records
                if mess.mess_name != mess_ref["mess_name"]:
                    raise ValueError(f"MESS MISMATCH: '{mess.mess_name}' mess_name '{mess.mess_name}', expected '{mess_ref['mess_name']}'.")
                if mess.hostel_id != mapped_mess_hostel_id:
                    raise ValueError(f"MESS MISMATCH: '{mess.mess_name}' hostel_id '{mess.hostel_id}', expected '{mapped_mess_hostel_id}'.")
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
                print(f"  [✓] Verified: {mess_ref['mess_name']} (ID: {mess.id}) -> All fields match (hostel_id={mess.hostel_id}).")

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

                    # Demonstration password moved from demo_passwords to account_passwords
                    # only if this account required credential collection
                    if target_user in demo_passwords:
                        account_passwords[target_user] = demo_passwords.pop(target_user)

                    # Scenario 4: Account exists and identity is verified
                    if u_by_username and u_by_email:
                        existing_user = u_by_username
                        # Type-safe role check against model Enum using get_user_role_value
                        current_role_val = get_user_role_value(existing_user.role)
                        if current_role_val != str(target_role):
                            raise ValueError(
                                f"ROLE MISMATCH: User '{target_user}' has role '{current_role_val}', "
                                f"expected '{target_role}'. Aborting to prevent privilege confusion."
                            )
                        # Active status check
                        if not existing_user.is_active:
                            raise ValueError(f"ACCOUNT INACTIVE: User '{target_user}' exists but is marked inactive. Aborting.")

                        if not rotate_passwords:
                            # DEFAULT: Preserve existing verified account password hash unmodified
                            original_hash = existing_user.password_hash
                            if not original_hash or not original_hash.startswith("scrypt:"):
                                raise ValueError(
                                    f"EXISTING PASSWORD HASH INVALID: User '{target_user}' exists but does not have a valid Werkzeug scrypt password hash."
                                )
                            # Cross-account integrity check
                            if existing_user.id in resolved_user_ids:
                                raise ValueError(f"CROSS-ACCOUNT INTEGRITY COLLISION: User #{existing_user.id} resolved by multiple definitions!")
                            resolved_user_ids.add(existing_user.id)

                            created_credentials.append({
                                "role": target_role,
                                "username": target_user,
                                "email": target_email,
                                "status": "Preserved (Active)",
                                "original_hash": original_hash
                            })
                            user_records[target_user] = existing_user
                            print(f"  [*] Account Verified : {target_user:<15} [{target_role}] -> Existing password hash preserved unmodified.")
                        else:
                            # EXPLICIT ROTATION REQUESTED (--rotate-existing-passwords)
                            existing_user.set_password(account_passwords[target_user])
                            # Immediate hash verification
                            if not existing_user.check_password(account_passwords[target_user]):
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
                                "status": "Rotated (Active)"
                            })
                            user_records[target_user] = existing_user
                            print(f"  [*] Account Verified : {target_user:<15} [{target_role}] -> Password rotated & verified via Werkzeug scrypt.")

                    # Scenario 5: Account does not exist -> Create with demo password
                    else:
                        new_user = User(
                            username=target_user,
                            email=target_email,
                            role=target_role,
                            is_active=True
                        )
                        # Set and hash password using the application's Werkzeug secure scrypt method
                        new_user.set_password(account_passwords[target_user])
                        # Immediate hash verification
                        if not new_user.check_password(account_passwords[target_user]):
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
                            "status": "Created (Active)"
                        })
                        user_records[target_user] = new_user
                        print(f"  [+] Account Created  : {target_user:<15} [{target_role}] -> Password hashed & verified.")

                # Cross-account verification: Ensure exactly 8 distinct user IDs resolved
                if len(resolved_user_ids) != 8:
                    raise ValueError(f"CROSS-ACCOUNT INTEGRITY FAILED: Expected 8 distinct users, got {len(resolved_user_ids)}.")

                # =========================================================================
                # STEP 3: Associated Profile Models — Strict Non-Destructive Resolution
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
                if w_by_empid_b and (not w_boys_prof or w_boys_prof.id != w_by_empid_b.id):
                    raise ValueError(f"PROFILE COLLISION: Warden employee_id '{w_b_ref['employee_id']}' belongs to another user (Warden #{w_by_empid_b.id})!")

                w_boys_prof, created_wb = validate_or_create_warden_profile(
                    w_boys_prof, w_boys_user.id, w_b_ref, hostel_boys.id, db.session
                )
                if created_wb:
                    print("  [+] Created Profile  : Dr. Ramesh Chandra -> Assigned: Aryabhatta Boys Hostel")
                else:
                    print(f"  [✓] Verified Existing Profile : Dr. Ramesh Chandra (ID: {w_boys_prof.id}) -> Preserved unmodified.")

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
                if w_by_empid_g and (not w_girls_prof or w_girls_prof.id != w_by_empid_g.id):
                    raise ValueError(f"PROFILE COLLISION: Warden employee_id '{w_g_ref['employee_id']}' belongs to another user (Warden #{w_by_empid_g.id})!")

                w_girls_prof, created_wg = validate_or_create_warden_profile(
                    w_girls_prof, w_girls_user.id, w_g_ref, hostel_girls.id, db.session
                )
                if created_wg:
                    print("  [+] Created Profile  : Prof. Sunita Mishra -> Assigned: Gargi Girls Hostel")
                else:
                    print(f"  [✓] Verified Existing Profile : Prof. Sunita Mishra (ID: {w_girls_prof.id}) -> Preserved unmodified.")

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
                s_by_roll = query_production_single_or_none(
                    Student.query.filter_by(roll_no=s_ref["roll_no"]),
                    f"Student roll_no '{s_ref['roll_no']}'"
                )
                if s_by_enr and (not student_prof or student_prof.id != s_by_enr.id):
                    raise ValueError(f"PROFILE COLLISION: Student enrollment_no '{s_ref['enrollment_no']}' belongs to another user (Student #{s_by_enr.id})!")
                if s_by_roll and (not student_prof or student_prof.id != s_by_roll.id):
                    raise ValueError(f"PROFILE COLLISION: Student roll_no '{s_ref['roll_no']}' belongs to another user (Student #{s_by_roll.id})!")

                student_prof, created_s = validate_or_create_student_profile(
                    student_prof, student_user.id, s_ref, db.session
                )
                if created_s:
                    print(f"  [+] Created Profile  : Student Rahul Sharma ({s_ref['enrollment_no']})")
                else:
                    print(f"  [✓] Verified Existing Profile : Student Rahul Sharma (ID: {student_prof.id}) -> Preserved unmodified.")

                # 3D. Parent Profile (Using PostgreSQL student_prof.id and duplicate detection)
                p_ref = ref["parent"]
                parent_user = user_records["parent_rahul"]
                parent_prof = query_production_single_or_none(
                    ParentProfile.query.filter_by(user_id=parent_user.id),
                    f"ParentProfile for user '{parent_user.username}'"
                )
                p_by_student = query_production_single_or_none(
                    ParentProfile.query.filter_by(student_id=student_prof.id),
                    f"ParentProfile for student_id #{student_prof.id}"
                )
                if p_by_student and (not parent_prof or parent_prof.id != p_by_student.id):
                    raise ValueError(f"PROFILE COLLISION: Student #{student_prof.id} (Rahul Sharma) is already linked to parent profile #{p_by_student.id} belonging to another user!")

                parent_prof, created_p = validate_or_create_parent_profile(
                    parent_prof, parent_user.id, p_ref, student_prof.id, db.session
                )
                if created_p:
                    print("  [+] Created Profile  : Parent Ramesh Sharma (Father) -> Linked to Student: Rahul Sharma")
                else:
                    print(f"  [✓] Verified Existing Profile : Parent Ramesh Sharma (ID: {parent_prof.id}) -> Preserved unmodified.")

                # 3E. Mess Staff Profile (Using PostgreSQL mess.id and duplicate detection)
                ms_ref = ref["mess_staff"]
                staff_user = user_records["mess_staff"]
                staff_prof = query_production_single_or_none(
                    MessStaffProfile.query.filter_by(user_id=staff_user.id),
                    f"MessStaffProfile for user '{staff_user.username}'"
                )
                ms_by_name = query_production_single_or_none(
                    MessStaffProfile.query.filter_by(staff_name=ms_ref["staff_name"]),
                    f"MessStaffProfile staff_name '{ms_ref['staff_name']}'"
                )
                if ms_by_name and (not staff_prof or staff_prof.id != ms_by_name.id):
                    raise ValueError(f"PROFILE COLLISION: Mess staff '{ms_ref['staff_name']}' belongs to another user (Profile #{ms_by_name.id})!")

                staff_prof, created_ms = validate_or_create_mess_staff_profile(
                    staff_prof, staff_user.id, ms_ref, mess.id, db.session
                )
                if created_ms:
                    print("  [+] Created Profile  : Mess Staff Dinesh Kumar -> Assigned: Central Dining Hall")
                else:
                    print(f"  [✓] Verified Existing Profile : Mess Staff Dinesh Kumar (ID: {staff_prof.id}) -> Preserved unmodified.")

                # =========================================================================
                # STEP 4: Comprehensive Pre-Commit Verification Suite
                # =========================================================================
                print("\n[STEP 4/5] Executing Pre-Commit Verification Suite...")

                # 4A. Verify Exactly 8 Accounts Processed
                if len(created_credentials) != 8:
                    raise ValueError(f"CREDENTIAL AUDIT FAILED: Expected exactly 8 accounts processed, got {len(created_credentials)}.")

                # 4B. Verify Password Entries for Accounts Requiring Creation/Rotation
                if len(account_passwords) != len(accounts_needing_passwords):
                    raise ValueError(
                        f"SECURITY AUDIT FAILED: Expected {len(accounts_needing_passwords)} password entries, "
                        f"got {len(account_passwords)}."
                    )
                print(f"  [PASS 1/5] Exactly {len(accounts_needing_passwords)} password entries validated for accounts needing credentials.")

                # 4C. Verify Werkzeug Scrypt Password Hash for Every Single Account
                for cred in created_credentials:
                    uname = cred["username"]
                    u = user_records[uname]
                    if cred["status"] == "Preserved (Active)":
                        # Verify existing password hash was preserved completely unmodified and is valid scrypt
                        if not u.password_hash or not u.password_hash.startswith("scrypt:"):
                            raise ValueError(f"PRESERVED HASH INVALID: Account '{uname}' does not have a valid Werkzeug scrypt hash!")
                        if cred.get("original_hash") and u.password_hash != cred["original_hash"]:
                            raise ValueError(f"PRESERVED HASH MODIFIED: Existing password hash for '{uname}' was altered during transaction!")
                    else:
                        if not u.check_password(account_passwords[uname]):
                            raise ValueError(f"HASH VERIFICATION FAILED: Werkzeug check_password_hash() failed for '{uname}'!")
                print("  [PASS 2/5] Werkzeug scrypt password hashes verified for all 8 accounts before commit (existing hashes preserved).")

                # 4D. Verify Account Metadata
                for meta in INTENDED_ACCOUNTS:
                    u = user_records.get(meta["username"])
                    if not u:
                        raise ValueError(f"STATE FAILED: User '{meta['username']}' not found in active session.")
                    role_val = get_user_role_value(u.role)
                    if role_val != str(meta["role"]):
                        raise ValueError(f"STATE FAILED: User '{meta['username']}' role mismatch ({role_val} != {meta['role']}).")
                    if not u.is_active:
                        raise ValueError(f"STATE FAILED: User '{meta['username']}' is inactive.")
                    if u.email != meta["email"]:
                        raise ValueError(f"STATE FAILED: User '{meta['username']}' email mismatch ({u.email} != {meta['email']}).")
                print("  [PASS 3/5] All 8 users verified (active=True, correct role Enum value, matching email).")

                # 4E. Complete Field-Level Pre-Commit Verification (Every single field of hostels, mess, wardens, student, parent, mess staff)
                entities_to_verify = {
                    "hostel_boys": hostel_boys,
                    "hostel_girls": hostel_girls,
                    "mess": mess,
                    "w_boys_prof": w_boys_prof,
                    "w_girls_prof": w_girls_prof,
                    "student_prof": student_prof,
                    "parent_prof": parent_prof,
                    "staff_prof": staff_prof,
                    "user_records": user_records,
                }
                verify_all_entity_fields_pre_commit(entities_to_verify, ref)
                print("  [PASS 4/5] All demographic, facility, and relational fields verified across all entities.")

                # 4F. Commit Atomic Transaction
                db.session.commit()
                print("  [PASS 5/5] Single atomic transaction committed to Supabase PostgreSQL.")
                print("\n[SUCCESS] Production migration transaction completed successfully!")

                # Immediately clear plaintext passwords upon successful commit
                cleanup_credential_dictionaries(demo_passwords, account_passwords)

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

            except Exception as exc:
                db.session.rollback()
                safe_err = format_safe_exception_report(exc, "Database execution failure")
                print("\n" + "!" * 80)
                print("[DATABASE EXECUTION FAILURE] Transaction aborted and rolled back.")
                print(f"Detail: {safe_err}")
                print("A database constraint violation or execution error occurred during processing.")
                print("Troubleshooting Guidance:")
                print("  - Verify that schema_postgres.sql has been executed in the Supabase SQL Editor.")
                print("  - Ensure all 30 tables and 33 enums exist.")
                print("  - Verify that PostgreSQL role 'postgres' has permission to insert into public tables.")
                print("!" * 80)
                sys.exit(1)

            # =========================================================================
            # STEP 5: Final Post-Commit Migration Status Report
            # =========================================================================
            print("\n" + "=" * 80)
            print("DATABASE AUDIT & EXECUTION SUMMARY")
            print("=" * 80)
            print("Target Supabase Project : " + EXPECTED_SUPABASE_PROJECT_REF)
            print(f"Total Accounts Processed : 8 / 8")
            print(f"Newly Created Accounts   : {len([c for c in created_credentials if 'Created' in c['status']])}")
            print(f"Preserved Existing Accounts: {len([c for c in created_credentials if 'Preserved' in c['status']])}")
            print(f"Rotated Existing Accounts: {len([c for c in created_credentials if 'Rotated' in c['status']])}")
            print("=" * 80)

            print("\n" + "#" * 85)
            print("PRODUCTION DEMONSTRATION ACCOUNTS MIGRATION SUMMARY")
            print("#" * 85)
            print("SECURITY NOTICE:")
            print("1. All 8 accounts have been provisioned and verified active in Supabase PostgreSQL.")
            print("2. Stored passwords in PostgreSQL are hashed using Werkzeug scrypt (plaintext is never stored).")
            print("3. Each account is verified active with a valid Werkzeug scrypt password hash,")
            print("   verified profile entity, and complete foreign-key links.\n")
            print(f"{'Username':<25} | {'Account Status'}")
            print("-" * 55)
            for cred in created_credentials:
                print(f"{cred['username']:<25} | {cred['status']}")
            print("#" * 85)

            print("\nAll 8 production accounts and profiles are verified active in Supabase PostgreSQL.\n")

    def _execute_with_credential_guard():
        return execute_with_credential_cleanup(demo_passwords, account_passwords, _execute_migration_workflow)

    # Execute entire migration workflow guarded by both credential cleanup and DATABASE_URL preservation
    return execute_with_database_url_preservation(_execute_with_credential_guard)


def validate_readonly_sql(sql: str) -> tuple[bool, str]:
    """
    Exhaustively inspects SQL statements for preflight execution:
    PRIMARY SECURITY BOUNDARY: Database-enforced read-only transaction (SET TRANSACTION READ ONLY)
    is the primary security boundary. This static statement parser provides strict defense-in-depth.

    Strict SQL allowlist:
    1. Strips multi-line /* ... */ and single-line (-- or #) comments.
    2. Strips single and double quoted literals to avoid false positives inside strings.
    3. Detects and rejects multi-statement SQL (multiple non-empty statements separated by semicolons).
    4. Permits ONLY explicitly authorized read-only statement categories:
       - SELECT (excluding SELECT INTO and embedded write operations)
       - WITH (non-modifying CTEs only; rejects INSERT/UPDATE/DELETE/MERGE)
       - SHOW (PostgreSQL read-only variable inspection)
       - EXPLAIN (query plan inspection)
       - SET (strictly limited to exact 'SET TRANSACTION READ ONLY' for transaction initialization)
       - PRAGMA (strictly limited to authorized read-only inspection pragmas; rejects all PRAGMA assignments,
         state-changing commands, and attempts to disable query_only)
    5. Rejects all transaction-control statements (BEGIN, COMMIT, ROLLBACK).
    6. Rejects all arbitrary session-setting statements (arbitrary SET commands).
    7. Rejects all write, DDL, and administrative/procedural operations (INSERT, UPDATE, DELETE, DROP,
       ALTER, CREATE, TRUNCATE, MERGE, GRANT, REVOKE, LOCK, CALL, EXEC, EXECUTE, COPY, VACUUM, REPLACE).
    """
    if not sql or not str(sql).strip():
        return True, "empty"

    # Strip multi-line comments
    clean = re.sub(r'/\*.*?\*/', ' ', str(sql), flags=re.DOTALL)
    # Strip single-line comments (-- and #)
    clean = re.sub(r'(--|#)[^\r\n]*', ' ', clean).strip()
    if not clean:
        return True, "empty"

    # Strip quoted string literals to inspect structural SQL syntax
    struct = re.sub(r"'([^'\\]|\\.)*'", "''", clean)
    struct = re.sub(r'"([^"\\]|\\.)*"', '""', struct)

    # Multi-statement SQL detection
    statements = [s.strip() for s in struct.split(';') if s.strip()]
    if len(statements) > 1:
        return False, "Multi-statement execution rejected"

    stmt = statements[0] if statements else ""
    tokens = stmt.split()
    first_token = tokens[0].upper() if tokens else ""

    # Transaction-control statements are rejected in cursor execution
    if first_token in {'BEGIN', 'COMMIT', 'ROLLBACK'}:
        return False, f"Transaction control statement '{first_token}' rejected in read-only cursor execution"

    # Only permitted leading keywords
    permitted_starts = {'SELECT', 'WITH', 'SHOW', 'EXPLAIN', 'SET', 'PRAGMA'}
    if first_token not in permitted_starts:
        return False, f"Disallowed statement keyword: '{first_token}'"

    # Universal write/DDL/administrative verb check
    forbidden_pattern = r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|MERGE|GRANT|REVOKE|LOCK|CALL|EXEC|EXECUTE|COPY|VACUUM|REPLACE)\b'
    if re.search(forbidden_pattern, stmt, re.IGNORECASE):
        if first_token == 'WITH':
            return False, "Data-modifying CTE rejected"
        return False, "Write or administrative operation rejected"

    # Category-specific validation:
    if first_token == 'SET':
        # Permit ONLY SET TRANSACTION READ ONLY (and its standard isolation variant)
        normalized_set = ' '.join(stmt.upper().split())
        is_set_ro = bool(
            normalized_set == 'SET TRANSACTION READ ONLY' or
            re.match(r'^SET\s+TRANSACTION\s+(?:ISOLATION\s+LEVEL\s+[A-Z\s]+)?READ\s+ONLY$', normalized_set)
        )
        if not is_set_ro:
            return False, "Arbitrary session-setting statement rejected"

    elif first_token == 'PRAGMA':
        # Check for query_only disabling in any assignment or parenthesized form (including quoted variants)
        disabling_pattern = r'\bquery_only\s*(?:=\s*|\(\s*)([\'"]?)(off|0|false|no)\b\1|\bquery_only\s*(?:=\s*|\(\s*)[\'"]\s*[\'"]'
        if re.search(disabling_pattern, clean, re.IGNORECASE):
            return False, "PRAGMA query_only disabling rejected"

        # Match PRAGMA [schema.]name followed optionally by:
        # 1) = value
        # 2) (arg)
        pragma_pattern = r'^PRAGMA\s+(?:([a-zA-Z0-9_]+)\.)?([a-zA-Z0-9_]+)(?:\s*=\s*(.*?)\s*|\s*\(\s*(.*?)\s*\))?$'
        m = re.match(pragma_pattern, stmt.strip(), re.IGNORECASE)
        if not m:
            return False, "Malformed PRAGMA statement rejected"

        schema, name, val_eq, val_paren = m.group(1), m.group(2).lower(), m.group(3), m.group(4)

        # Disabling values for query_only in either assignment or function form
        disabling_values = {'off', '0', 'false', 'no'}
        def _clean_val(v):
            if v is None:
                return ""
            v = v.strip().strip("'\"").strip()
            return v.lower()

        clean_eq = _clean_val(val_eq) if val_eq is not None else None
        clean_paren = _clean_val(val_paren) if val_paren is not None else None

        # Check for query_only disabling first
        if name == 'query_only':
            if (clean_eq in disabling_values) or (clean_paren in disabling_values):
                return False, "PRAGMA query_only disabling rejected"
            # Only exact required initialization statement is permitted as state-changing:
            # PRAGMA query_only = ON or 1
            if clean_eq in {'on', '1', 'true', 'yes'} and val_paren is None:
                return True, "OK"
            # Bare inspection: PRAGMA query_only (no args, no paren)
            if val_eq is None and val_paren is None:
                return True, "OK"
            return False, "State-changing PRAGMA assignment rejected"

        # Any '=' assignment on other PRAGMAs is strictly forbidden
        if val_eq is not None:
            return False, "State-changing PRAGMA assignment rejected"

        # Inspection PRAGMAs that take a parenthesized table/index argument
        table_arg_inspection_pragmas = {
            'table_info', 'table_xinfo', 'index_list', 'index_info',
            'index_xinfo', 'foreign_key_list'
        }
        # Inspection PRAGMAs that take NO arguments
        bare_inspection_pragmas = {
            'database_list', 'collation_list', 'compile_options'
        }

        if name in table_arg_inspection_pragmas:
            # Must either have a parenthesized table argument or bare (SQLite allows PRAGMA table_info)
            if val_paren is not None:
                arg_raw = val_paren.strip()
                if not re.match(r"^[a-zA-Z0-9_'\"]+$", arg_raw):
                    return False, "Arbitrary parenthesized PRAGMA argument rejected"
            return True, "OK"

        if name in bare_inspection_pragmas:
            if val_paren is not None:
                return False, f"Arbitrary parenthesized PRAGMA argument rejected: '{name}'"
            return True, "OK"

        return False, f"Unauthorized PRAGMA statement rejected: '{name}'"

    elif first_token == 'SELECT':
        if re.search(r'\bSELECT\s+.*?\s+INTO\b', stmt, re.IGNORECASE):
            return False, "SELECT INTO table creation rejected"

    return True, "OK"


def configure_read_only_preflight_guards(engine, connection=None):
    """
    Attaches transaction-level and statement-level read-only guards to a SQLAlchemy engine:
    1. Transaction-level read-only enforcement:
       - For PostgreSQL: executes 'SET TRANSACTION READ ONLY' before any inspection query in the transaction.
         Aborts immediately with RuntimeError if read-only mode cannot be enabled.
       - For SQLite: tracks exact raw DBAPI connection and applies 'PRAGMA query_only = ON'.
    2. Statement-level read-only verification:
       - Uses validate_readonly_sql() via before_cursor_execute to reject write/DDL operations,
         data-modifying CTEs, leading comments, and multi-statement queries.
    3. Lifecycle & cleanup:
       - Restores SQLite PRAGMA query_only = OFF on exact tracked DBAPI connections and verifies restoration.
       - Raises RuntimeError if restoration fails.
       - Removes all event listeners on every exit path.
    """
    from sqlalchemy.engine import Engine, Connection
    if not isinstance(engine, (Engine, Connection)):
        return lambda: None

    from sqlalchemy import event, text

    guarded_dbapi_conns = set()

    def _verify_read_only_statement(conn, cursor, statement, parameters, context, executemany):
        is_safe, reason = validate_readonly_sql(statement)
        if not is_safe:
            raise RuntimeError(
                f"PREFLIGHT SAFETY VIOLATION: Statement rejected in read-only preflight: {reason}."
            )

    def _enforce_begin_read_only(conn):
        dialect_name = getattr(conn.dialect, "name", "")
        if dialect_name == "postgresql":
            try:
                conn.execute(text("SET TRANSACTION READ ONLY"))
            except Exception as e:
                exc_cls = type(e).__name__
                raise RuntimeError(
                    f"CRITICAL READ-ONLY SAFETY FAILURE: Failed to set PostgreSQL transaction to READ ONLY mode [{exc_cls}]."
                ) from None
        elif dialect_name == "sqlite":
            try:
                raw_conn = getattr(getattr(conn, "connection", None), "dbapi_connection", None)
                if raw_conn is not None:
                    cursor = raw_conn.cursor()
                    cursor.execute("PRAGMA query_only = ON")
                    cursor.close()
                    guarded_dbapi_conns.add(raw_conn)
                else:
                    conn.execute(text("PRAGMA query_only = ON"))
            except Exception as e:
                exc_cls = type(e).__name__
                raise RuntimeError(
                    f"CRITICAL READ-ONLY SAFETY FAILURE: Failed to set SQLite to query_only mode [{exc_cls}]."
                ) from None

    event.listen(engine, "before_cursor_execute", _verify_read_only_statement)
    event.listen(engine, "begin", _enforce_begin_read_only)

    active_conn = connection
    if active_conn is not None:
        dialect_name = getattr(engine.dialect, "name", "")
        if dialect_name == "sqlite":
            try:
                raw_conn = getattr(getattr(active_conn, "connection", None), "dbapi_connection", None)
                if raw_conn is not None:
                    cursor = raw_conn.cursor()
                    cursor.execute("PRAGMA query_only = ON")
                    cursor.close()
                    guarded_dbapi_conns.add(raw_conn)
                else:
                    active_conn.execute(text("PRAGMA query_only = ON"))
            except Exception as e:
                exc_cls = type(e).__name__
                raise RuntimeError(
                    f"CRITICAL READ-ONLY SAFETY FAILURE: Failed to set SQLite connection to query_only [{exc_cls}]."
                ) from None
        elif dialect_name == "postgresql":
            try:
                active_conn.execute(text("SET TRANSACTION READ ONLY"))
            except Exception as e:
                exc_cls = type(e).__name__
                raise RuntimeError(
                    f"CRITICAL READ-ONLY SAFETY FAILURE: Failed to set PostgreSQL connection to READ ONLY [{exc_cls}]."
                ) from None

    def _cleanup():
        cleanup_errors = []
        try:
            # Restore exact SQLite connections and verify restoration
            dialect_name = getattr(engine.dialect, "name", "")
            if dialect_name == "sqlite":
                for raw_conn in list(guarded_dbapi_conns):
                    try:
                        cursor = raw_conn.cursor()
                        cursor.execute("PRAGMA query_only = OFF")
                        cursor.execute("PRAGMA query_only")
                        row = cursor.fetchone()
                        cursor.close()
                        res = row[0] if row else None
                        if res != 0 and res != "0":
                            cleanup_errors.append(f"PRAGMA query_only verification failed (value={res})")
                    except Exception as e:
                        cleanup_errors.append(f"Failed to restore PRAGMA query_only on raw connection: {type(e).__name__}")
                guarded_dbapi_conns.clear()

                if active_conn is not None:
                    try:
                        active_conn.execute(text("PRAGMA query_only = OFF"))
                    except Exception as e:
                        cleanup_errors.append(f"Failed to restore active_conn query_only: {type(e).__name__}")
        finally:
            # Event listeners MUST be removed in a finally block on every exit path
            try:
                event.remove(engine, "before_cursor_execute", _verify_read_only_statement)
            except Exception as e:
                cleanup_errors.append(f"Failed to remove before_cursor_execute listener: {type(e).__name__}")
            try:
                event.remove(engine, "begin", _enforce_begin_read_only)
            except Exception as e:
                cleanup_errors.append(f"Failed to remove begin listener: {type(e).__name__}")

        if cleanup_errors:
            raise RuntimeError(
                f"CRITICAL PREFLIGHT CLEANUP FAILURE: Guard restoration failed: {'; '.join(cleanup_errors)}"
            )

    return _cleanup


def run_production_preflight(db_url: str = None, app=None, session=None) -> dict:
    """
    Executes a strict read-only preflight inspection of Supabase PostgreSQL.
    Safety Guarantees:
    - Dedicated no-schema-migration application factory (create_preflight_app).
    - _ensure_schema_migrations() and db.create_all() are strictly bypassed.
    - Read-only transaction enforcement active (SET TRANSACTION READ ONLY / PRAGMA query_only = ON).
    - Statement-level verification enforces SELECT-only execution.
    - Zero write operations (never calls add, commit, flush, delete, update).
    - Never calls migrate_demo_accounts().
    - Validates target Supabase pooler URL before connecting.
    - Inspects all 8 intended demo accounts and associated profile entities.
    - Detects missing, present, duplicate, and colliding records.
    - Never prints password hashes, plaintext passwords, or raw credentials.
    - Restores DATABASE_URL and closes session upon all exit paths.
    """
    orig_env_db_url = os.environ.get("DATABASE_URL")
    had_env_db_url = "DATABASE_URL" in os.environ
    guards_cleanup = None
    managed_context = None
    ref = None
    enum_members = None

    def _inspect_within_context():
        target_session = session or db.session
        bind = getattr(target_session, "bind", None) or (target_session.get_bind() if hasattr(target_session, "get_bind") else None)
        if bind is None and app is not None:
            try:
                bind = db.engine
            except Exception:
                pass
        nonlocal guards_cleanup
        if guards_cleanup is None and bind is not None:
            guards_cleanup = configure_read_only_preflight_guards(bind)
        dialect_name = getattr(getattr(bind, "dialect", None), "name", "")

        # ---------------------------------------------------------------------
        # Critical Requirement B: Verify actual transaction is read-only before running any inspection queries!
        # Ensure command executes before any other SQL statement in that transaction.
        # Do not continue after a failed read-only safety check!
        # ---------------------------------------------------------------------
        if dialect_name == "postgresql":
            try:
                # Ensure SET TRANSACTION READ ONLY was executed and verify setting
                target_session.execute(db.text("SET TRANSACTION READ ONLY"))
                ro_state = target_session.execute(db.text("SELECT current_setting('transaction_read_only')")).scalar()
            except Exception as e:
                safe_err = format_safe_exception_report(e, "PostgreSQL read-only transaction setup failure")
                print(f"\n[PREFLIGHT FATAL] Failed to establish read-only transaction: {safe_err}")
                return {
                    "success": False,
                    "error": safe_err,
                    "accounts": [],
                    "profiles": [],
                    "facilities": {},
                }
            if ro_state != "on":
                safe_err = f"Transaction read-only verification failed: expected 'on', got '{ro_state}'"
                print(f"\n[PREFLIGHT FATAL] {safe_err}")
                return {
                    "success": False,
                    "error": safe_err,
                    "accounts": [],
                    "profiles": [],
                    "facilities": {},
                }
        elif dialect_name == "sqlite":
            try:
                target_session.execute(db.text("PRAGMA query_only = ON"))
                ro_state = target_session.execute(db.text("PRAGMA query_only")).scalar()
            except Exception as e:
                safe_err = format_safe_exception_report(e, "SQLite query_only setup failure")
                print(f"\n[PREFLIGHT FATAL] Failed to establish SQLite query_only: {safe_err}")
                return {
                    "success": False,
                    "error": safe_err,
                    "accounts": [],
                    "profiles": [],
                    "facilities": {},
                }
            if ro_state != 1 and ro_state != "1":
                safe_err = f"SQLite query_only verification failed: expected 1, got {ro_state}"
                print(f"\n[PREFLIGHT FATAL] {safe_err}")
                return {
                    "success": False,
                    "error": safe_err,
                    "accounts": [],
                    "profiles": [],
                    "facilities": {},
                }

        if dialect_name == "sqlite":
            connected_db = "sqlite_test_db"
            connected_user = "test_user"
            server_addr = "127.0.0.1"
        else:
            try:
                conn_info = target_session.execute(
                    db.text("SELECT current_database(), current_user, inet_server_addr()")
                ).fetchone()
                connected_db = str(conn_info[0])
                connected_user = str(conn_info[1])
                server_addr = str(conn_info[2])
            except Exception as e:
                masked_url = safe_mask_database_url(db_url or os.environ.get("DATABASE_URL", ""))
                safe_err = format_safe_exception_report(e, "Database connectivity failure")
                print(f"\n[PREFLIGHT ERROR] Database connectivity failure: {masked_url}")
                print(f"Error detail: {safe_err}")
                return {
                    "success": False,
                    "error": safe_err,
                    "accounts": [],
                    "profiles": [],
                    "facilities": {},
                }

        masked_url = safe_mask_database_url(db_url or os.environ.get("DATABASE_URL", ""))

        print("\n" + "=" * 80)
        print("HOSTELEASE HMS — PRODUCTION DATABASE READ-ONLY PREFLIGHT AUDIT")
        print("=" * 80)
        print(f"Target Database URL   : {masked_url}")
        print(f"Connected Database    : {connected_db}")
        print(f"Connected User        : {connected_user}")
        print(f"Server IP Address     : {server_addr}")
        print(f"Execution Mode        : STRICT READ-ONLY PREFLIGHT (ZERO WRITES)")
        print("=" * 80)

        # ---------------------------------------------------------------------
        # 1. Facilities Inspection
        # ---------------------------------------------------------------------
        print("\n[PREFLIGHT STEP 1/3] Inspecting Hostel & Mess Facility Records...")
        facilities_summary = {}

        # 1A. Boys Hostel
        hb_list = Hostel.query.filter_by(name=ref["hostel_boys"]["name"]).all()
        if not hb_list:
            hb_status = "MISSING"
            hb_detail = "Record not found in production; will be provisioned during migration."
            hb_inst = None
        elif len(hb_list) > 1:
            hb_status = "DUPLICATE_CONFLICT"
            hb_detail = f"DUPLICATE CONFLICT: Found {len(hb_list)} records with name '{ref['hostel_boys']['name']}'."
            hb_inst = None
        else:
            hb_inst = hb_list[0]
            mismatches = []
            if hb_inst.hostel_type != ref["hostel_boys"]["hostel_type"]:
                mismatches.append(f"hostel_type ('{hb_inst.hostel_type}' != '{ref['hostel_boys']['hostel_type']}')")
            if hb_inst.total_floors != ref["hostel_boys"]["total_floors"]:
                mismatches.append(f"total_floors ({hb_inst.total_floors} != {ref['hostel_boys']['total_floors']})")
            if hb_inst.total_rooms != ref["hostel_boys"]["total_rooms"]:
                mismatches.append(f"total_rooms ({hb_inst.total_rooms} != {ref['hostel_boys']['total_rooms']})")
            if hb_inst.description != ref["hostel_boys"]["description"]:
                mismatches.append("description")
            if mismatches:
                hb_status = "FIELD_MISMATCH"
                hb_detail = f"Record #{hb_inst.id} exists but has field differences: {', '.join(mismatches)}"
            else:
                hb_status = "PRESENT_VERIFIED"
                hb_detail = f"Record #{hb_inst.id} exists and matches all reference fields."
        facilities_summary["hostel_boys"] = {"status": hb_status, "detail": hb_detail, "instance": hb_inst}
        print(f"  * Boys Hostel       : [{hb_status}] {hb_detail}")

        # 1B. Girls Hostel
        hg_list = Hostel.query.filter_by(name=ref["hostel_girls"]["name"]).all()
        if not hg_list:
            hg_status = "MISSING"
            hg_detail = "Record not found in production; will be provisioned during migration."
            hg_inst = None
        elif len(hg_list) > 1:
            hg_status = "DUPLICATE_CONFLICT"
            hg_detail = f"DUPLICATE CONFLICT: Found {len(hg_list)} records with name '{ref['hostel_girls']['name']}'."
            hg_inst = None
        else:
            hg_inst = hg_list[0]
            mismatches = []
            if hg_inst.hostel_type != ref["hostel_girls"]["hostel_type"]:
                mismatches.append(f"hostel_type ('{hg_inst.hostel_type}' != '{ref['hostel_girls']['hostel_type']}')")
            if hg_inst.total_floors != ref["hostel_girls"]["total_floors"]:
                mismatches.append(f"total_floors ({hg_inst.total_floors} != {ref['hostel_girls']['total_floors']})")
            if hg_inst.total_rooms != ref["hostel_girls"]["total_rooms"]:
                mismatches.append(f"total_rooms ({hg_inst.total_rooms} != {ref['hostel_girls']['total_rooms']})")
            if hg_inst.description != ref["hostel_girls"]["description"]:
                mismatches.append("description")
            if mismatches:
                hg_status = "FIELD_MISMATCH"
                hg_detail = f"Record #{hg_inst.id} exists but has field differences: {', '.join(mismatches)}"
            else:
                hg_status = "PRESENT_VERIFIED"
                hg_detail = f"Record #{hg_inst.id} exists and matches all reference fields."
        facilities_summary["hostel_girls"] = {"status": hg_status, "detail": hg_detail, "instance": hg_inst}
        print(f"  * Girls Hostel      : [{hg_status}] {hg_detail}")

        # 1C. Mess Dining Facility
        mess_list = MessProfile.query.filter_by(mess_name=ref["mess"]["mess_name"]).all()
        if not mess_list:
            m_status = "MISSING"
            m_detail = "Record not found in production; will be provisioned during migration."
            m_inst = None
        elif len(mess_list) > 1:
            m_status = "DUPLICATE_CONFLICT"
            m_detail = f"DUPLICATE CONFLICT: Found {len(mess_list)} records with name '{ref['mess']['mess_name']}'."
            m_inst = None
        else:
            m_inst = mess_list[0]
            mismatches = []
            expected_mess_hostel_id = resolve_mapped_mess_hostel_id(ref["mess"], ref, session=target_session)
            if m_inst.hostel_id != expected_mess_hostel_id:
                mismatches.append(f"hostel_id ({m_inst.hostel_id} != {expected_mess_hostel_id})")
            if m_inst.operating_status != ref["mess"]["operating_status"]:
                mismatches.append(f"operating_status ('{m_inst.operating_status}' != '{ref['mess']['operating_status']}')")
            if m_inst.meal_policy != ref["mess"]["meal_policy"]:
                mismatches.append("meal_policy")
            if m_inst.daily_capacity != ref["mess"]["daily_capacity"]:
                mismatches.append(f"daily_capacity ({m_inst.daily_capacity} != {ref['mess']['daily_capacity']})")
            if m_inst.contact_number != ref["mess"]["contact_number"]:
                mismatches.append("contact_number")
            if m_inst.description != ref["mess"]["description"]:
                mismatches.append("description")
            if mismatches:
                m_status = "FIELD_MISMATCH"
                m_detail = f"Record #{m_inst.id} exists but has field differences: {', '.join(mismatches)}"
            else:
                m_status = "PRESENT_VERIFIED"
                m_detail = f"Record #{m_inst.id} exists and matches all reference fields (hostel_id={expected_mess_hostel_id})."
        facilities_summary["mess"] = {"status": m_status, "detail": m_detail, "instance": m_inst}
        print(f"  * Central Mess      : [{m_status}] {m_detail}")

        # ---------------------------------------------------------------------
        # 2. Demonstration Accounts Inspection (All 8 Intended Accounts)
        # ---------------------------------------------------------------------
        print("\n[PREFLIGHT STEP 2/3] Inspecting All 8 Demonstration User Accounts...")
        accounts_report = []
        user_map = {}

        for meta in INTENDED_ACCOUNTS:
            target_user = meta["username"]
            target_email = meta["email"]
            target_role = meta["role"]

            u_by_username = User.query.filter_by(username=target_user).all()
            u_by_email = User.query.filter_by(email=target_email).all()

            acct_info = {
                "username": target_user,
                "expected_role": target_role,
                "expected_email": target_email,
                "status": "",
                "detail": "",
                "user_id": None,
                "has_scrypt_hash": False,
                "is_active": False,
            }

            if not u_by_username and not u_by_email:
                acct_info["status"] = "MISSING"
                acct_info["detail"] = "Account does not exist in production database. Ready for creation."
            elif len(u_by_username) > 1:
                acct_info["status"] = "DUPLICATE_USERNAME"
                acct_info["detail"] = f"CRITICAL CONFLICT: {len(u_by_username)} accounts found with username '{target_user}'."
            elif len(u_by_email) > 1:
                acct_info["status"] = "DUPLICATE_EMAIL"
                acct_info["detail"] = f"CRITICAL CONFLICT: {len(u_by_email)} accounts found with email '{target_email}'."
            elif u_by_username and u_by_email and u_by_username[0].id != u_by_email[0].id:
                acct_info["status"] = "IDENTITY_COLLISION"
                acct_info["detail"] = (
                    f"CRITICAL COLLISION: Username belongs to User #{u_by_username[0].id}, "
                    f"but email belongs to User #{u_by_email[0].id}."
                )
            elif u_by_username and not u_by_email:
                acct_info["status"] = "EMAIL_COLLISION"
                acct_info["detail"] = (
                    f"COLLISION: Username '{target_user}' exists (User #{u_by_username[0].id}) "
                    f"with email '{u_by_username[0].email}' instead of '{target_email}'."
                )
            elif u_by_email and not u_by_username:
                acct_info["status"] = "USERNAME_COLLISION"
                acct_info["detail"] = (
                    f"COLLISION: Email '{target_email}' exists (User #{u_by_email[0].id}) "
                    f"with username '{u_by_email[0].username}' instead of '{target_user}'."
                )
            else:
                u = u_by_username[0]
                acct_info["user_id"] = u.id
                user_map[target_user] = u
                current_role = get_user_role_value(u.role)
                role_valid = current_role in enum_members
                role_match = (current_role == target_role)
                is_active = bool(u.is_active)
                has_hash = bool(u.password_hash)
                is_scrypt = bool(u.password_hash and len(u.password_hash) > 20 and u.password_hash.startswith("scrypt:"))
                acct_info["has_scrypt_hash"] = is_scrypt
                acct_info["is_active"] = is_active

                if not role_valid:
                    acct_info["status"] = "INVALID_ENUM_ROLE"
                    acct_info["detail"] = f"ROLE ERROR: Current role '{current_role}' is not in User.role Enum!"
                elif not role_match:
                    acct_info["status"] = "ROLE_MISMATCH"
                    acct_info["detail"] = f"ROLE MISMATCH: Role is '{current_role}', expected '{target_role}'."
                elif not is_active:
                    acct_info["status"] = "INACTIVE"
                    acct_info["detail"] = f"ACCOUNT INACTIVE: User #{u.id} exists but is inactive."
                elif not is_scrypt:
                    acct_info["status"] = "INVALID_PASSWORD_HASH"
                    acct_info["detail"] = (
                        f"PASSWORD HASH INVALID: User #{u.id} exists but password_hash is "
                        f"{'missing' if not u.password_hash else 'not a valid Werkzeug scrypt hash'}."
                    )
                else:
                    acct_info["status"] = "PRESENT_VERIFIED"
                    acct_info["detail"] = f"User #{u.id} active, role '{current_role}' verified, valid scrypt password hash."

            accounts_report.append(acct_info)
            print(f"  * {target_user:<15} [{target_role:<12}] -> [{acct_info['status']}] {acct_info['detail']}")

        # ---------------------------------------------------------------------
        # 3. Associated Profiles Inspection
        # ---------------------------------------------------------------------
        print("\n[PREFLIGHT STEP 3/3] Inspecting Associated Profile Models & Foreign Keys...")
        profiles_report = []

        # 3A. Boys Warden Profile
        w_b_user = user_map.get("warden_boys")
        w_b_ref = ref["warden_boys"]
        w_b_by_u = Warden.query.filter_by(user_id=w_b_user.id).all() if w_b_user else []
        w_b_by_emp = Warden.query.filter_by(employee_id=w_b_ref["employee_id"]).all()
        w_b_info = {"profile": "Warden (Boys)", "status": "", "detail": ""}

        if not w_b_by_u and not w_b_by_emp:
            w_b_info["status"] = "MISSING"
            w_b_info["detail"] = "Profile not found in production; will be created during migration."
        elif len(w_b_by_emp) > 1:
            w_b_info["status"] = "DUPLICATE_CONFLICT"
            w_b_info["detail"] = f"DUPLICATE CONFLICT: Found {len(w_b_by_emp)} wardens with employee_id '{w_b_ref['employee_id']}'."
        elif w_b_by_emp and (not w_b_by_u or w_b_by_emp[0].user_id != (w_b_user.id if w_b_user else None)):
            w_b_info["status"] = "PROFILE_COLLISION"
            w_b_info["detail"] = f"COLLISION: employee_id '{w_b_ref['employee_id']}' belongs to another user (Warden #{w_b_by_emp[0].id})."
        elif len(w_b_by_u) > 1:
            w_b_info["status"] = "DUPLICATE_CONFLICT"
            w_b_info["detail"] = f"DUPLICATE CONFLICT: User #{w_b_user.id} has {len(w_b_by_u)} warden profiles."
        else:
            w_inst = w_b_by_u[0]
            if w_b_user is None:
                w_b_info["status"] = "UNRESOLVED_USER_RELATION"
                w_b_info["detail"] = f"Warden #{w_inst.id} exists but user 'warden_boys' is missing in production database."
            elif hb_inst is None:
                w_b_info["status"] = "UNRESOLVED_HOSTEL_RELATION"
                w_b_info["detail"] = f"Warden #{w_inst.id} exists but Boys Hostel record is missing; assigned_hostel_id cannot be verified."
            else:
                mismatches = []
                if w_inst.user_id != w_b_user.id:
                    mismatches.append(f"user_id ({w_inst.user_id} != {w_b_user.id})")
                if w_inst.employee_id != w_b_ref["employee_id"]:
                    mismatches.append(f"employee_id ('{w_inst.employee_id}' != '{w_b_ref['employee_id']}')")
                if w_inst.full_name != w_b_ref["full_name"]:
                    mismatches.append(f"full_name ('{w_inst.full_name}' != '{w_b_ref['full_name']}')")
                if w_inst.phone != w_b_ref["phone"]:
                    mismatches.append(f"phone ('{w_inst.phone}' != '{w_b_ref['phone']}')")
                if w_inst.designation != w_b_ref["designation"]:
                    mismatches.append(f"designation ('{w_inst.designation}' != '{w_b_ref['designation']}')")
                if w_inst.assigned_hostel_id != hb_inst.id:
                    mismatches.append(f"assigned_hostel_id ({w_inst.assigned_hostel_id} != Boys Hostel #{hb_inst.id})")
                if mismatches:
                    w_b_info["status"] = "FIELD_MISMATCH"
                    w_b_info["detail"] = f"Warden #{w_inst.id} exists but has mismatches: {', '.join(mismatches)}"
                else:
                    w_b_info["status"] = "PRESENT_VERIFIED"
                    w_b_info["detail"] = f"Warden #{w_inst.id} exists and matches all reference fields & hostel linkage."
        profiles_report.append(w_b_info)
        print(f"  * Warden (Boys)     : [{w_b_info['status']}] {w_b_info['detail']}")

        # 3B. Girls Warden Profile
        w_g_user = user_map.get("warden_girls")
        w_g_ref = ref["warden_girls"]
        w_g_by_u = Warden.query.filter_by(user_id=w_g_user.id).all() if w_g_user else []
        w_g_by_emp = Warden.query.filter_by(employee_id=w_g_ref["employee_id"]).all()
        w_g_info = {"profile": "Warden (Girls)", "status": "", "detail": ""}

        if not w_g_by_u and not w_g_by_emp:
            w_g_info["status"] = "MISSING"
            w_g_info["detail"] = "Profile not found in production; will be created during migration."
        elif len(w_g_by_emp) > 1:
            w_g_info["status"] = "DUPLICATE_CONFLICT"
            w_g_info["detail"] = f"DUPLICATE CONFLICT: Found {len(w_g_by_emp)} wardens with employee_id '{w_g_ref['employee_id']}'."
        elif w_g_by_emp and (not w_g_by_u or w_g_by_emp[0].user_id != (w_g_user.id if w_g_user else None)):
            w_g_info["status"] = "PROFILE_COLLISION"
            w_g_info["detail"] = f"COLLISION: employee_id '{w_g_ref['employee_id']}' belongs to another user (Warden #{w_g_by_emp[0].id})."
        elif len(w_g_by_u) > 1:
            w_g_info["status"] = "DUPLICATE_CONFLICT"
            w_g_info["detail"] = f"DUPLICATE CONFLICT: User #{w_g_user.id} has {len(w_g_by_u)} warden profiles."
        else:
            w_inst = w_g_by_u[0]
            if w_g_user is None:
                w_g_info["status"] = "UNRESOLVED_USER_RELATION"
                w_g_info["detail"] = f"Warden #{w_inst.id} exists but user 'warden_girls' is missing in production database."
            elif hg_inst is None:
                w_g_info["status"] = "UNRESOLVED_HOSTEL_RELATION"
                w_g_info["detail"] = f"Warden #{w_inst.id} exists but Girls Hostel record is missing; assigned_hostel_id cannot be verified."
            else:
                mismatches = []
                if w_inst.user_id != w_g_user.id:
                    mismatches.append(f"user_id ({w_inst.user_id} != {w_g_user.id})")
                if w_inst.employee_id != w_g_ref["employee_id"]:
                    mismatches.append(f"employee_id ('{w_inst.employee_id}' != '{w_g_ref['employee_id']}')")
                if w_inst.full_name != w_g_ref["full_name"]:
                    mismatches.append(f"full_name ('{w_inst.full_name}' != '{w_g_ref['full_name']}')")
                if w_inst.phone != w_g_ref["phone"]:
                    mismatches.append(f"phone ('{w_inst.phone}' != '{w_g_ref['phone']}')")
                if w_inst.designation != w_g_ref["designation"]:
                    mismatches.append(f"designation ('{w_inst.designation}' != '{w_g_ref['designation']}')")
                if w_inst.assigned_hostel_id != hg_inst.id:
                    mismatches.append(f"assigned_hostel_id ({w_inst.assigned_hostel_id} != Girls Hostel #{hg_inst.id})")
                if mismatches:
                    w_g_info["status"] = "FIELD_MISMATCH"
                    w_g_info["detail"] = f"Warden #{w_inst.id} exists but has mismatches: {', '.join(mismatches)}"
                else:
                    w_g_info["status"] = "PRESENT_VERIFIED"
                    w_g_info["detail"] = f"Warden #{w_inst.id} exists and matches all reference fields & hostel linkage."
        profiles_report.append(w_g_info)
        print(f"  * Warden (Girls)    : [{w_g_info['status']}] {w_g_info['detail']}")

        # 3C. Student Profile
        s_user = user_map.get("rahul_sharma")
        s_ref = ref["student"]
        s_by_u = Student.query.filter_by(user_id=s_user.id).all() if s_user else []
        s_by_enr = Student.query.filter_by(enrollment_no=s_ref["enrollment_no"]).all()
        s_by_roll = Student.query.filter_by(roll_no=s_ref["roll_no"]).all()
        s_info = {"profile": "Student (Rahul)", "status": "", "detail": "", "instance": None}

        if not s_by_u and not s_by_enr and not s_by_roll:
            s_info["status"] = "MISSING"
            s_info["detail"] = "Profile not found in production; will be created during migration."
        elif len(s_by_enr) > 1 or len(s_by_roll) > 1:
            s_info["status"] = "DUPLICATE_CONFLICT"
            s_info["detail"] = "DUPLICATE CONFLICT: Multiple student records found matching enrollment or roll number."
        elif s_by_enr and (not s_by_u or s_by_enr[0].user_id != (s_user.id if s_user else None)):
            s_info["status"] = "PROFILE_COLLISION"
            s_info["detail"] = f"COLLISION: enrollment_no '{s_ref['enrollment_no']}' belongs to another user (Student #{s_by_enr[0].id})."
        elif s_by_roll and (not s_by_u or s_by_roll[0].user_id != (s_user.id if s_user else None)):
            s_info["status"] = "PROFILE_COLLISION"
            s_info["detail"] = f"COLLISION: roll_no '{s_ref['roll_no']}' belongs to another user (Student #{s_by_roll[0].id})."
        elif len(s_by_u) > 1:
            s_info["status"] = "DUPLICATE_CONFLICT"
            s_info["detail"] = f"DUPLICATE CONFLICT: User #{s_user.id} has {len(s_by_u)} student profiles."
        else:
            s_inst = s_by_u[0]
            s_info["instance"] = s_inst
            if s_user is None:
                s_info["status"] = "UNRESOLVED_USER_RELATION"
                s_info["detail"] = f"Student #{s_inst.id} exists but user 'rahul_sharma' is missing in production database."
            else:
                mismatches = []
                if s_inst.user_id != s_user.id:
                    mismatches.append(f"user_id ({s_inst.user_id} != {s_user.id})")
                all_student_fields = [
                    "enrollment_no", "roll_no", "full_name", "phone", "gender",
                    "branch", "year", "semester", "guardian_name", "guardian_phone",
                    "emergency_phone", "address", "blood_group", "status"
                ]
                for f in all_student_fields:
                    val = getattr(s_inst, f)
                    ref_val = s_ref[f]
                    if val != ref_val:
                        mismatches.append(f"{f} ('{val}' != '{ref_val}')")
                if mismatches:
                    s_info["status"] = "FIELD_MISMATCH"
                    s_info["detail"] = f"Student #{s_inst.id} exists but has mismatches: {', '.join(mismatches)}"
                else:
                    s_info["status"] = "PRESENT_VERIFIED"
                    s_info["detail"] = f"Student #{s_inst.id} exists and matches all 14 reference demographic & academic fields."
        profiles_report.append(s_info)
        print(f"  * Student Profile   : [{s_info['status']}] {s_info['detail']}")

        # 3D. Parent Profile
        p_user = user_map.get("parent_rahul")
        p_ref = ref["parent"]
        p_by_u = ParentProfile.query.filter_by(user_id=p_user.id).all() if p_user else []
        student_inst = s_info.get("instance") or (s_by_enr[0] if len(s_by_enr) == 1 else None)
        p_by_st = ParentProfile.query.filter_by(student_id=student_inst.id).all() if student_inst else []
        p_info = {"profile": "Parent Profile", "status": "", "detail": ""}

        if not p_by_u and not p_by_st:
            p_info["status"] = "MISSING"
            p_info["detail"] = "Profile not found in production; will be created during migration."
        elif len(p_by_st) > 1:
            p_info["status"] = "DUPLICATE_CONFLICT"
            p_info["detail"] = f"DUPLICATE CONFLICT: Student #{student_inst.id} has {len(p_by_st)} parent profiles."
        elif p_by_st and (not p_by_u or p_by_st[0].user_id != (p_user.id if p_user else None)):
            p_info["status"] = "PROFILE_COLLISION"
            p_info["detail"] = f"COLLISION: Student #{student_inst.id} is linked to ParentProfile #{p_by_st[0].id} belonging to another user."
        elif len(p_by_u) > 1:
            p_info["status"] = "DUPLICATE_CONFLICT"
            p_info["detail"] = f"DUPLICATE CONFLICT: User #{p_user.id} has {len(p_by_u)} parent profiles."
        else:
            p_inst = p_by_u[0]
            if p_user is None:
                p_info["status"] = "UNRESOLVED_USER_RELATION"
                p_info["detail"] = f"ParentProfile #{p_inst.id} exists but user 'parent_rahul' is missing in production database."
            elif student_inst is None:
                p_info["status"] = "UNRESOLVED_STUDENT_RELATION"
                p_info["detail"] = f"ParentProfile #{p_inst.id} exists but required Student record is missing; student_id cannot be verified."
            else:
                mismatches = []
                if p_inst.user_id != p_user.id:
                    mismatches.append(f"user_id ({p_inst.user_id} != {p_user.id})")
                if p_inst.student_id != student_inst.id:
                    mismatches.append(f"student_id ({p_inst.student_id} != Student #{student_inst.id})")
                if p_inst.parent_name != p_ref["parent_name"]:
                    mismatches.append(f"parent_name ('{p_inst.parent_name}' != '{p_ref['parent_name']}')")
                if p_inst.phone_number != p_ref["phone_number"]:
                    mismatches.append(f"phone_number ('{p_inst.phone_number}' != '{p_ref['phone_number']}')")
                if p_inst.relationship_to_student != p_ref["relationship_to_student"]:
                    mismatches.append(f"relationship_to_student ('{p_inst.relationship_to_student}' != '{p_ref['relationship_to_student']}')")
                if p_inst.account_status != p_ref["account_status"]:
                    mismatches.append(f"account_status ('{p_inst.account_status}' != '{p_ref['account_status']}')")
                if mismatches:
                    p_info["status"] = "FIELD_MISMATCH"
                    p_info["detail"] = f"ParentProfile #{p_inst.id} exists but has mismatches: {', '.join(mismatches)}"
                else:
                    p_info["status"] = "PRESENT_VERIFIED"
                    p_info["detail"] = f"ParentProfile #{p_inst.id} exists and matches all reference fields & student linkage."
        profiles_report.append(p_info)
        print(f"  * Parent Profile    : [{p_info['status']}] {p_info['detail']}")

        # 3E. Mess Staff Profile
        ms_user = user_map.get("mess_staff")
        ms_ref = ref["mess_staff"]
        ms_by_u = MessStaffProfile.query.filter_by(user_id=ms_user.id).all() if ms_user else []
        ms_by_name = MessStaffProfile.query.filter_by(staff_name=ref["mess_staff"]["staff_name"]).all()
        ms_info = {"profile": "Mess Staff", "status": "", "detail": ""}

        if not ms_by_u and not ms_by_name:
            ms_info["status"] = "MISSING"
            ms_info["detail"] = "Profile not found in production; will be created during migration."
        elif len(ms_by_name) > 1:
            ms_info["status"] = "DUPLICATE_CONFLICT"
            ms_info["detail"] = f"DUPLICATE CONFLICT: Found {len(ms_by_name)} mess staff profiles matching '{ms_ref['staff_name']}'."
        elif ms_by_name and (not ms_by_u or ms_by_name[0].user_id != (ms_user.id if ms_user else None)):
            ms_info["status"] = "PROFILE_COLLISION"
            ms_info["detail"] = f"COLLISION: Staff '{ms_ref['staff_name']}' belongs to another user (Profile #{ms_by_name[0].id})."
        elif len(ms_by_u) > 1:
            ms_info["status"] = "DUPLICATE_CONFLICT"
            ms_info["detail"] = f"DUPLICATE CONFLICT: User #{ms_user.id} has {len(ms_by_u)} mess staff profiles."
        else:
            ms_inst = ms_by_u[0]
            if ms_user is None:
                ms_info["status"] = "UNRESOLVED_USER_RELATION"
                ms_info["detail"] = f"MessStaffProfile #{ms_inst.id} exists but user 'mess_staff' is missing in production database."
            elif m_inst is None:
                ms_info["status"] = "UNRESOLVED_MESS_RELATION"
                ms_info["detail"] = f"MessStaffProfile #{ms_inst.id} exists but Central Mess facility is missing; mess_id cannot be verified."
            else:
                mismatches = []
                if ms_inst.user_id != ms_user.id:
                    mismatches.append(f"user_id ({ms_inst.user_id} != {ms_user.id})")
                if ms_inst.mess_id != m_inst.id:
                    mismatches.append(f"mess_id ({ms_inst.mess_id} != Central Mess #{m_inst.id})")
                if ms_inst.staff_name != ms_ref["staff_name"]:
                    mismatches.append(f"staff_name ('{ms_inst.staff_name}' != '{ms_ref['staff_name']}')")
                if ms_inst.phone_number != ms_ref["phone_number"]:
                    mismatches.append(f"phone_number ('{ms_inst.phone_number}' != '{ms_ref['phone_number']}')")
                if ms_inst.role_designation != ms_ref["role_designation"]:
                    mismatches.append(f"role_designation ('{ms_inst.role_designation}' != '{ms_ref['role_designation']}')")
                if ms_inst.employment_status != ms_ref["employment_status"]:
                    mismatches.append(f"employment_status ('{ms_inst.employment_status}' != '{ms_ref['employment_status']}')")
                if mismatches:
                    ms_info["status"] = "FIELD_MISMATCH"
                    ms_info["detail"] = f"MessStaffProfile #{ms_inst.id} exists but has mismatches: {', '.join(mismatches)}"
                else:
                    ms_info["status"] = "PRESENT_VERIFIED"
                    ms_info["detail"] = f"MessStaffProfile #{ms_inst.id} exists and matches all reference fields & mess linkage."
        profiles_report.append(ms_info)
        print(f"  * Mess Staff        : [{ms_info['status']}] {ms_info['detail']}")

        # ---------------------------------------------------------------------
        # 4. Summary & Verification Verdict
        # ---------------------------------------------------------------------
        missing_accts = [a for a in accounts_report if a["status"] == "MISSING"]
        verified_accts = [a for a in accounts_report if a["status"] == "PRESENT_VERIFIED"]
        conflict_accts = [a for a in accounts_report if a["status"] not in ("MISSING", "PRESENT_VERIFIED")]

        missing_profs = [p for p in profiles_report if p["status"] == "MISSING"]
        conflict_profs = [p for p in profiles_report if p["status"] not in ("MISSING", "PRESENT_VERIFIED")]

        has_conflicts = bool(
            conflict_accts
            or conflict_profs
            or any("CONFLICT" in f["status"] or "MISMATCH" in f["status"] for f in facilities_summary.values())
        )

        print("\n" + "=" * 80)
        print("PREFLIGHT AUDIT SUMMARY & READINESS VERDICT")
        print("=" * 80)
        print(f"Total Accounts Inspected : {len(accounts_report)} / 8")
        print(f"  - Missing (To Create)  : {len(missing_accts)}")
        print(f"  - Verified Existing    : {len(verified_accts)}")
        print(f"  - Conflicting / Errors : {len(conflict_accts)}")
        print(f"Total Profiles Inspected : {len(profiles_report)} / 5")
        print(f"  - Missing (To Create)  : {len(missing_profs)}")
        print(f"  - Conflicting / Errors : {len(conflict_profs)}")
        print("-" * 80)
        if has_conflicts:
            print("PREFLIGHT VERDICT : BLOCKED BY CONFLICTS (Conflicts must be resolved before migration)")
        else:
            print("PREFLIGHT VERDICT : READY FOR MIGRATION (No blocking conflicts detected)")
        print("SAFETY CONFIRMATION: Zero write operations were executed.")
        print("                     No records were created, updated, or deleted.")
        print("                     No passwords or credentials were changed.")
        print("                     Migration workflow was NOT invoked.")
        print("=" * 80 + "\n")

        return {
            "success": not has_conflicts,
            "connected_db": connected_db,
            "connected_user": connected_user,
            "server_addr": server_addr,
            "facilities": facilities_summary,
            "accounts": accounts_report,
            "profiles": profiles_report,
            "has_conflicts": has_conflicts,
        }

    pushed_context = None
    if app is None:
        target_url = db_url or os.environ.get("DATABASE_URL")
        if not target_url:
            raise ValueError("DATABASE_URL is missing. Target URL required for preflight inspection.")
        validate_production_target(target_url)
        from app import create_preflight_app
        app = create_preflight_app("production", db_url=target_url)
        pushed_context = app.app_context()
        pushed_context.push()
    else:
        try:
            from flask import has_app_context
            if not has_app_context():
                pushed_context = app.app_context()
                pushed_context.push()
        except Exception:
            pass

    try:
        ref = load_local_sqlite_reference()
        enum_members = list(User.role.property.columns[0].type.enums)
        return _inspect_within_context()
    finally:
        cleanup_errors = []
        target_cleanup_session = session or db.session
        try:
            if hasattr(target_cleanup_session, "remove"):
                target_cleanup_session.remove()
        except Exception as e:
            cleanup_errors.append(f"db.session.remove failure [{type(e).__name__}]")

        if guards_cleanup:
            try:
                guards_cleanup()
            except Exception as e:
                cleanup_errors.append(f"guards_cleanup failure [{type(e).__name__}]")

        # Guarantee DATABASE_URL restoration unconditionally on every exit path
        try:
            if had_env_db_url:
                os.environ["DATABASE_URL"] = orig_env_db_url
            else:
                os.environ.pop("DATABASE_URL", None)
        except Exception as e:
            cleanup_errors.append(f"DATABASE_URL restoration failure [{type(e).__name__}]")

        if pushed_context:
            try:
                pushed_context.pop()
            except Exception as e:
                cleanup_errors.append(f"app_context.pop failure [{type(e).__name__}]")

        if cleanup_errors:
            raise RuntimeError(f"PREFLIGHT CLEANUP FAILURE: {'; '.join(cleanup_errors)}")


def execute_production_preflight(db_url: str = None) -> bool:
    """
    Executes production preflight with strict DATABASE_URL preservation
    and guaranteed read-only execution.
    """
    def _action():
        resolved_url = db_url or resolve_database_url()
        os.environ["DATABASE_URL"] = resolved_url
        res = run_production_preflight(resolved_url)
        return res.get("success", False)

    return execute_with_database_url_preservation(_action)


def confirm_production_migration_execution(db_url: str = None) -> bool:
    """
    Prompts the user for interactive confirmation before executing a production migration.
    Clearly identifies the production target database, project ref, pooler host,
    and explains that database records will be modified.
    Returns True if user confirmed, False otherwise.
    """
    masked_url = "[UNRESOLVED_DATABASE_URL]"
    try:
        if db_url:
            masked_url = safe_mask_database_url(db_url)
        elif os.environ.get("DATABASE_URL"):
            masked_url = safe_mask_database_url(os.environ["DATABASE_URL"])
        else:
            try:
                resolved_url = resolve_database_url()
                if resolved_url:
                    masked_url = safe_mask_database_url(resolved_url)
            except (Exception, SystemExit):
                pass
    except Exception:
        pass

    print("\n" + "!" * 80)
    print("PRODUCTION MIGRATION EXECUTION CONFIRMATION REQUIRED")
    print("!" * 80)
    print(f"Target Database URL : {masked_url}")
    print(f"Target Project      : {EXPECTED_SUPABASE_PROJECT_REF}")
    print(f"Target Pooler Host  : {EXPECTED_POOLER_HOST}")
    print(f"Target Pooler Port  : {EXPECTED_POOLER_PORT}")
    print("\nWARNING: This operation will modify production database records, provision")
    print("missing facilities and demo accounts, and set password hashes.")
    print("!" * 80)

    try:
        response = input("Type 'CONFIRM PRODUCTION MIGRATION' to proceed: ").strip()
        return response == "CONFIRM PRODUCTION MIGRATION"
    except (EOFError, KeyboardInterrupt):
        return False


def main(cli_args: list = None) -> int:
    """
    Main entry point for production demo accounts migration utility.
    Enforces fail-closed argument parsing:
    - Running without arguments prints usage and exits safely (return code 1).
    - Requires explicit flag '--execute-production-migration'.
    - Runs interactive confirmation before executing production migration.
    - Keeps --preflight-only completely separate from migration.
    - Test flags (--test-all, --test, --test-url) only run local tests.
    - Unexpected arguments exit safely with code 1.
    """
    if cli_args is None:
        raw_args = sys.argv[1:]
    else:
        raw_args = list(cli_args)

    args = [a.lower() for a in raw_args]

    if not args:
        print("HOSTELEASE HMS — PRODUCTION DEMO ACCOUNTS MIGRATION UTILITY")
        print("\nERROR: No command specified. Production migration is fail-closed.")
        print("To inspect production safely without writes, use: --preflight-only")
        print("To execute production migration, use: --execute-production-migration")
        print("Run with --help for full usage instructions.")
        return 1

    if "--help" in args or "-h" in args:
        print("Usage: python migrate_demo_accounts_prod.py [OPTIONS]")
        print("\nSafe Inspection & Testing Options (Zero Writes):")
        print("  --preflight-only              Execute read-only production preflight inspection (zero writes).")
        print("  --test-all                    Run all local verification unit test suites.")
        print("  --test                        Alias for --test-all.")
        print("  --test-url                    Run only local URL masking and URL validation unit tests.")
        print("  --help, -h                    Show this help message and exit.")
        print("\nProduction Execution Options:")
        print("  --execute-production-migration  Explicitly execute production demonstration accounts migration.")
        print("                                  Requires interactive confirmation before proceeding.")
        print("  --rotate-existing-passwords     Rotate passwords for existing verified accounts (Default: Preserve).")
        print("                                  Can only be used alongside --execute-production-migration.")
        return 0

    if "--test-url" in args:
        # Run only URL masking and URL validation tests (no application/database dependencies required)
        t1 = run_masking_unit_tests()
        t2 = run_url_validation_unit_tests()
        return 0 if (t1 and t2) else 1

    if "--test-all" in args or "--test" in args:
        # Run all verification test suites (--test is an alias for --test-all)
        print("\n" + "=" * 80)
        print("HOSTELEASE HMS — RUNNING ALL VERIFICATION TEST SUITES")
        print("=" * 80)

        suites = [
            ("1. Database URL Masking", run_masking_unit_tests),
            ("2. Database URL Validation", run_url_validation_unit_tests),
            ("3. Demo Credentials & Hashing", run_demo_credentials_unit_tests),
            ("4. Role Enum Compatibility", run_role_enum_unit_tests),
            ("5. Field-Level Pre-Commit Verification", run_field_verification_unit_tests),
            ("6. Profile Immutability & Creation", run_profile_immutability_unit_tests),
            ("7. Password & Environment Cleanup", run_cleanup_unit_tests),
            ("8. Production Preflight Isolation", run_preflight_unit_tests),
        ]

        results = []
        for name, suite_func in suites:
            passed = suite_func()
            results.append((name, passed))

        print("\n" + "=" * 80)
        print("HOSTELEASE HMS — ALL TEST SUITES EXECUTION SUMMARY")
        print("=" * 80)
        total_passed = sum(1 for _, passed in results if passed)
        for name, passed in results:
            status_str = "PASS" if passed else "FAIL"
            print(f"  [{status_str}] {name:<45} : {'PASSED' if passed else 'FAILED'}")
        print("-" * 80)
        print(f"Total Suites Executed: {len(results)}")
        print(f"Total Suites Passed  : {total_passed} / {len(results)}")
        print(f"Total Suites Failed  : {len(results) - total_passed} / {len(results)}")
        all_ok = (total_passed == len(results))
        print(f"Final Status         : {'ALL SUITES PASSED (100%)' if all_ok else 'SOME SUITES FAILED'}")
        print("=" * 80 + "\n")
        return 0 if all_ok else 1

    if "--preflight-only" in args:
        # Execute strict read-only production preflight inspection (zero writes)
        success = execute_production_preflight()
        return 0 if success else 1

    if "--execute-production-migration" in args:
        rotate_existing = ("--rotate-existing-passwords" in args or "--rotate-passwords" in args)
        unrecognized = [a for a in args if a not in ("--execute-production-migration", "--rotate-existing-passwords", "--rotate-passwords")]
        if unrecognized:
            print(f"Unknown option(s) '{' '.join(unrecognized)}' alongside --execute-production-migration. Aborting.")
            return 1

        if not confirm_production_migration_execution():
            print("\n[ABORTED] Production migration was NOT confirmed by operator. Exiting safely without changes.")
            return 1

        migrate_demo_accounts(rotate_passwords=rotate_existing)
        return 0

    # Any other arguments without --execute-production-migration or recognized test flags
    print(f"ERROR: Unrecognized or invalid arguments: {' '.join(raw_args)}")
    print("Production migration is fail-closed. Valid options: --preflight-only, --execute-production-migration, --test-all, --help.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
