"""
database.py
Database layer for SN Clinic Management System (SaaS Edition)
Handles schema, migrations, and all data access functions.
Multi-tenant: every clinic/branch is a "center" - all data is scoped by center_id
so this single database can safely serve many paying clinics at once.
"""

import sqlite3
import hashlib
import secrets
import uuid as uuid_lib
from datetime import datetime

DB_NAME = "clinic.db"

# 25 pre-issued 1-year (Yearly) + 25 pre-issued 1-month (Monthly) license keys,
# ready to hand out to paying clinics. Each key can be used once (see licensing.py).
# Yearly keys are valid for 365 days from activation; Monthly keys for 30 days.
PREISSUED_LICENSE_KEYS_YEARLY = [
    "SNCLY-3KMS9-4ZJDB-E6RYM", "SNCLY-5GYMN-52UPT-UV9UA", "SNCLY-5N8RJ-5ZVSV-ABC3W",
    "SNCLY-6R7C9-P7PYA-8J5MU", "SNCLY-8FQ8C-2PZ5D-NYXG7", "SNCLY-8FRS4-5VT3M-3GDYR",
    "SNCLY-B7UNH-XHDNT-X8479", "SNCLY-DGUCK-GJ92T-7DKRP", "SNCLY-GV4F4-NGTED-A2KYY",
    "SNCLY-JKRR4-6A6AV-HBJEQ", "SNCLY-K2R8Q-DTB4K-UJNTA", "SNCLY-KFB3K-5NWTG-AZAMU",
    "SNCLY-KKB6D-HWZHM-A2FJ9", "SNCLY-NXHUV-9NDBA-8EADX", "SNCLY-P9V7X-JSCVY-7TKF5",
    "SNCLY-PYVKX-UVDSH-C66YX", "SNCLY-Q4NYU-CKSY3-X6DHE", "SNCLY-Q6E7G-FZ5VC-GFHUD",
    "SNCLY-QRPMX-8SXNC-G29FH", "SNCLY-TBE8A-3WA28-HPVVY", "SNCLY-TC2ZP-XPB46-EKJ2N",
    "SNCLY-U4NTD-5UC7Z-E2JCV", "SNCLY-VKQVC-SKDJT-FWYV8", "SNCLY-WZ5QM-QPM2F-CTJQH",
    "SNCLY-XPV79-EUUFC-ZQ3U7",
]

PREISSUED_LICENSE_KEYS_MONTHLY = [
    "SNCLM-2W8WD-Y9SUR-8F8JU", "SNCLM-32J8D-TY73F-TMGNN", "SNCLM-498AV-SZT6X-A63FP",
    "SNCLM-4QY94-J8C5U-G5D2D", "SNCLM-5QG5P-4HVFR-6H24E", "SNCLM-9DHAF-FPU5M-KGK9Q",
    "SNCLM-9QYWM-Z993T-2X8D9", "SNCLM-A345S-MG6MZ-DRCST", "SNCLM-B3P9N-CMN36-58S56",
    "SNCLM-BFQR2-PJERK-3KJGN", "SNCLM-C57TV-7WW9Y-CR7Y2", "SNCLM-C9M69-YM24B-HFKZZ",
    "SNCLM-EHTW5-K7QAN-AMP29", "SNCLM-EKQ72-4QUTX-8N2GV", "SNCLM-FMFMB-RVUD4-FKD3R",
    "SNCLM-JHWZ8-H5TM4-BJ4JS", "SNCLM-PJ4M6-PFVX5-FMXZA", "SNCLM-RFWN3-MMRR5-W3N6C",
    "SNCLM-SAQA9-K2UJQ-VMEV9", "SNCLM-SNVA8-WWNQG-QH62Q", "SNCLM-UTW3J-629AZ-W2KNB",
    "SNCLM-X7ZJM-QNAD6-YX5PY", "SNCLM-XMTJS-Q5FBX-PT233", "SNCLM-Y673X-WBRMZ-AV6A7",
    "SNCLM-YR29S-WYPU4-9E2MC",
]


# -----------------------------------------------------------------------------
# CONNECTION
# -----------------------------------------------------------------------------
def get_db():
    """Returns a database connection. Offline mode (default): SQLite, local
    file. Online mode: PostgreSQL, if a DATABASE_URL is configured (env var
    or .streamlit/secrets.toml) — see db_postgres.py. The object returned
    either way supports the same .execute()/.commit()/.close() interface
    and row["col"] access, so the rest of the app never needs to know or
    care which backend is actually in use."""
    try:
        import db_postgres
        if db_postgres.is_postgres_configured():
            return db_postgres.get_pg_connection()
    except ImportError:
        pass  # db_postgres.py / psycopg2 not present — offline-only install, that's fine.

    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_sql(query, conn, params=None):
    """Backend-aware replacement for pd.read_sql(query, conn, params=...).
    On SQLite this is pd.read_sql unchanged (proven, works natively). On
    PostgreSQL, pandas' own DBAPI2 fallback bypasses our ?-to-%s query
    translation (it calls the raw cursor directly), so we run the query
    ourselves through the same conn.execute() used everywhere else in the
    app and build the DataFrame from the result — same call signature,
    same return type, for every existing call site."""
    import pandas as pd
    params = params or []
    if type(conn).__name__ == "PGConnWrapper":
        cur = conn.execute(query, params)
        rows = cur.fetchall()
        cols = cur._cols
        return pd.DataFrame([list(r) for r in rows], columns=cols)
    return pd.read_sql(query, conn, params=params)


def hash_pass(password):
    """Legacy unsalted hash — kept only so any external/old callers don't
    break. New code should use make_password() / verify_password() instead."""
    return hashlib.sha256(password.encode()).hexdigest()


def make_password(password: str):
    """Generates a fresh random salt and returns (salt, hash) for a NEW
    or CHANGED password. Always use this for new accounts going forward."""
    salt = secrets.token_hex(16)
    pw_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    return salt, pw_hash


def verify_password(password: str, stored_hash: str, stored_salt: str = None) -> bool:
    """Verifies a login password against what's stored for that user.
    Supports accounts created before salting was added (stored_salt empty)
    by transparently falling back to the old unsalted scheme — existing
    logins keep working without forcing a password reset."""
    if stored_salt:
        candidate = hashlib.sha256((stored_salt + password).encode()).hexdigest()
    else:
        candidate = hashlib.sha256(password.encode()).hexdigest()
    return candidate == stored_hash


def new_uuid() -> str:
    """Stable global identifier for a record — used for future offline/online
    sync and safe cross-database migration (not yet wired into every table)."""
    return str(uuid_lib.uuid4())


# -----------------------------------------------------------------------------
# SCHEMA + MIGRATIONS
# -----------------------------------------------------------------------------
def init_db():
    try:
        import db_postgres
        if db_postgres.is_postgres_configured():
            db_postgres.init_db_postgres()
            return
    except ImportError:
        pass

    conn = get_db()
    c = conn.cursor()

    # ---- Center (tenant / branch) ----
    c.execute("""CREATE TABLE IF NOT EXISTS center (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        center_code TEXT UNIQUE,
        name TEXT NOT NULL,
        city TEXT,
        address TEXT,
        phone TEXT,
        plan TEXT DEFAULT 'Trial',
        plan_expiry TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT
    )""")

    # ---- User (login accounts) ----
    c.execute("""CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT,
        role TEXT NOT NULL,
        center_id INTEGER,
        is_active INTEGER DEFAULT 1,
        created_at TEXT
    )""")

    # ---- Patient ----
    c.execute("""CREATE TABLE IF NOT EXISTS patient (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_code TEXT UNIQUE,
        name TEXT NOT NULL,
        guardian_name TEXT,
        age INTEGER,
        gender TEXT,
        mobile TEXT,
        address TEXT,
        center_id INTEGER,
        created_at TEXT
    )""")

    # ---- Appointment ----
    c.execute("""CREATE TABLE IF NOT EXISTS appointment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        doctor_name TEXT,
        appt_date TEXT NOT NULL,
        appt_time TEXT,
        reason TEXT,
        status TEXT DEFAULT 'Booked',
        center_id INTEGER,
        created_at TEXT,
        FOREIGN KEY(patient_id) REFERENCES patient(id)
    )""")

    # ---- Consultation ----
    c.execute("""CREATE TABLE IF NOT EXISTS consultation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        visit_date TEXT,
        symptoms TEXT,
        diagnosis TEXT,
        prescription TEXT,
        next_visit TEXT,
        doctor_name TEXT,
        center_id INTEGER,
        FOREIGN KEY(patient_id) REFERENCES patient(id)
    )""")

    # ---- Fee / Billing ----
    c.execute("""CREATE TABLE IF NOT EXISTS fee (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        consultation_fee REAL DEFAULT 0,
        medicine_fee REAL DEFAULT 0,
        other_charges REAL DEFAULT 0,
        discount REAL DEFAULT 0,
        total REAL DEFAULT 0,
        payment_mode TEXT,
        paid_on TEXT,
        center_id INTEGER,
        FOREIGN KEY(patient_id) REFERENCES patient(id)
    )""")

    # ---- Medicine Inventory ----
    c.execute("""CREATE TABLE IF NOT EXISTS medicine (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        batch_no TEXT,
        expiry_date TEXT,
        stock INTEGER DEFAULT 0,
        low_stock_alert INTEGER DEFAULT 10,
        unit_price REAL DEFAULT 0,
        center_id INTEGER
    )""")

    # ---- Staff ----
    c.execute("""CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_code TEXT UNIQUE,
        name TEXT NOT NULL,
        designation TEXT,
        mobile TEXT,
        city TEXT,
        address TEXT,
        joining_date TEXT,
        salary REAL DEFAULT 0,
        status TEXT DEFAULT 'Active',
        center_id INTEGER,
        created_at TEXT
    )""")

    # ---- Attendance ----
    c.execute("""CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER,
        att_date TEXT NOT NULL,
        status TEXT DEFAULT 'Present',
        center_id INTEGER,
        FOREIGN KEY(staff_id) REFERENCES staff(id)
    )""")

    # ---- License Keys (1-year activation codes) ----
    c.execute("""CREATE TABLE IF NOT EXISTS license_key (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_key TEXT UNIQUE NOT NULL,
        duration_days INTEGER DEFAULT 365,
        status TEXT DEFAULT 'Unused',
        used_by_center_id INTEGER,
        activated_on TEXT,
        expires_on TEXT,
        created_at TEXT
    )""")

    # ---- Expenses ----
    c.execute("""CREATE TABLE IF NOT EXISTS expense (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        description TEXT,
        amount REAL DEFAULT 0,
        expense_date TEXT,
        center_id INTEGER,
        created_at TEXT
    )""")

    # ---- Prescription line items (structured Rx: medicine + dosage + duration) ----
    c.execute("""CREATE TABLE IF NOT EXISTS prescription_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        consultation_id INTEGER,
        medicine_name TEXT,
        composition TEXT,
        dosage TEXT,
        duration TEXT,
        total_qty TEXT,
        center_id INTEGER,
        FOREIGN KEY(consultation_id) REFERENCES consultation(id)
    )""")

    # ---- Medicine Sale (pharmacy counter, separate from OPD fee billing) ----
    c.execute("""CREATE TABLE IF NOT EXISTS medicine_sale (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        customer_name TEXT,
        mobile TEXT,
        subtotal REAL DEFAULT 0,
        discount REAL DEFAULT 0,
        total REAL DEFAULT 0,
        payment_mode TEXT,
        sold_on TEXT,
        center_id INTEGER,
        is_demo INTEGER DEFAULT 0
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS medicine_sale_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER,
        medicine_id INTEGER,
        medicine_name TEXT,
        quantity INTEGER,
        unit_price REAL,
        subtotal REAL,
        FOREIGN KEY(sale_id) REFERENCES medicine_sale(id)
    )""")

    # ---- Pathology Lab ----
    c.execute("""CREATE TABLE IF NOT EXISTS lab_test_catalog (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_name TEXT,
        price REAL DEFAULT 0,
        normal_range TEXT,
        unit TEXT,
        center_id INTEGER
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS lab_order (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        doctor_name TEXT,
        order_date TEXT,
        status TEXT DEFAULT 'Ordered',
        payment_mode TEXT,
        center_id INTEGER,
        is_demo INTEGER DEFAULT 0,
        FOREIGN KEY(patient_id) REFERENCES patient(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS lab_order_item (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        test_name TEXT,
        price REAL DEFAULT 0,
        normal_range TEXT,
        unit TEXT,
        result_value TEXT,
        status TEXT DEFAULT 'Pending',
        FOREIGN KEY(order_id) REFERENCES lab_order(id)
    )""")

    conn.commit()

    # ---- Lightweight auto-migrations (safe to re-run) ----
    _ensure_columns(c, "staff", {
        "status": "TEXT DEFAULT 'Active'",
        "center_id": "INTEGER",
        "created_at": "TEXT",
        "is_demo": "INTEGER DEFAULT 0",
        "qualification": "TEXT",
        "registration_no": "TEXT",
    })
    _ensure_columns(c, "patient", {
        "center_id": "INTEGER",
        "created_at": "TEXT",
        "is_demo": "INTEGER DEFAULT 0",
    })
    _ensure_columns(c, "user", {
        "center_id": "INTEGER",
        "full_name": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "created_at": "TEXT",
        "password_salt": "TEXT",
        "is_demo_account": "INTEGER DEFAULT 0",
    })
    _ensure_columns(c, "center", {
        "plan": "TEXT DEFAULT 'Trial'",
        "plan_expiry": "TEXT",
        "is_active": "INTEGER DEFAULT 1",
        "phone": "TEXT",
        "pending_plan": "TEXT",
        "razorpay_link_id": "TEXT",
        "razorpay_link_url": "TEXT",
        "razorpay_link_status": "TEXT",
        "timing": "TEXT",
        "closed_day": "TEXT",
    })
    _ensure_columns(c, "appointment", {
        "reason": "TEXT",
        "center_id": "INTEGER",
        "created_at": "TEXT",
        "is_demo": "INTEGER DEFAULT 0",
    })
    _ensure_columns(c, "consultation", {
        "doctor_name": "TEXT",
        "center_id": "INTEGER",
        "is_demo": "INTEGER DEFAULT 0",
        "chief_complaints": "TEXT",
        "clinical_findings": "TEXT",
        "weight": "REAL",
        "height": "REAL",
        "bp": "TEXT",
        "advice": "TEXT",
    })
    _ensure_columns(c, "fee", {
        "other_charges": "REAL DEFAULT 0",
        "center_id": "INTEGER",
        "is_demo": "INTEGER DEFAULT 0",
    })
    _ensure_columns(c, "medicine", {
        "batch_no": "TEXT",
        "expiry_date": "TEXT",
        "center_id": "INTEGER",
        "is_demo": "INTEGER DEFAULT 0",
    })
    _ensure_columns(c, "attendance", {
        "center_id": "INTEGER",
        "is_demo": "INTEGER DEFAULT 0",
    })
    _ensure_columns(c, "lab_order", {
        "consultation_id": "INTEGER",
    })
    _ensure_columns(c, "expense", {
        "is_demo": "INTEGER DEFAULT 0",
    })

    # ---- Sync-readiness columns (foundation for future offline<->online sync) ----
    # Added to every business/syncable table. Additive only — never removes or
    # renames anything, so existing installs upgrade in place with no data loss.
    SYNC_TABLES = [
        "center", "user", "patient", "appointment", "consultation", "prescription_item",
        "fee", "medicine", "medicine_sale", "medicine_sale_item", "lab_test_catalog",
        "lab_order", "lab_order_item", "staff", "attendance", "expense",
    ]
    for _t in SYNC_TABLES:
        _ensure_columns(c, _t, {
            "uuid": "TEXT",
            "updated_at": "TEXT",
            "deleted_at": "TEXT",
            "version_number": "INTEGER DEFAULT 1",
        })
    conn.commit()

    # Backfill a UUID for any existing row that doesn't have one yet (safe to
    # re-run — only touches rows where uuid IS NULL, so it's a no-op after the
    # first run on any given database).
    for _t in SYNC_TABLES:
        rows_missing_uuid = c.execute(f"SELECT id FROM {_t} WHERE uuid IS NULL").fetchall()
        for (row_id,) in rows_missing_uuid:
            c.execute(f"UPDATE {_t} SET uuid=? WHERE id=?", (new_uuid(), row_id))
    conn.commit()

    # Triggers: every table gets its rows auto-assigned a UUID on insert (if
    # not already provided) and updated_at/version_number auto-maintained on
    # update — this means existing INSERT/UPDATE statements throughout the
    # app don't each need to be touched individually, and nothing can
    # accidentally slip through without sync metadata.
    for _t in SYNC_TABLES:
        c.execute(f"""
            CREATE TRIGGER IF NOT EXISTS trg_{_t}_uuid
            AFTER INSERT ON {_t}
            FOR EACH ROW WHEN NEW.uuid IS NULL
            BEGIN
                UPDATE {_t} SET uuid = (
                    lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' ||
                    substr(lower(hex(randomblob(2))), 2) || '-' ||
                    substr('89ab', abs(random()) % 4 + 1, 1) || substr(lower(hex(randomblob(2))), 2) || '-' ||
                    lower(hex(randomblob(6)))
                ), updated_at = datetime('now'), version_number = 1
                WHERE rowid = NEW.rowid;
            END;
        """)
        # Guarded with "OLD.uuid IS NOT NULL" so this only fires for genuine
        # app-level updates to an already-existing row — not for the internal
        # UPDATE that trg_{_t}_uuid above issues to assign a fresh row's UUID
        # right after insert (which would otherwise cascade into here and
        # bump version_number to 2 before the row has even been used).
        c.execute(f"""
            CREATE TRIGGER IF NOT EXISTS trg_{_t}_updated_at
            AFTER UPDATE ON {_t}
            FOR EACH ROW WHEN OLD.uuid IS NOT NULL
            BEGIN
                UPDATE {_t} SET updated_at = datetime('now'),
                                 version_number = COALESCE(OLD.version_number, 1) + 1
                WHERE rowid = NEW.rowid;
            END;
        """)

    conn.commit()

    # ---- Seed default center ----
    c.execute("SELECT * FROM center WHERE center_code='CTR001'")
    if not c.fetchone():
        c.execute(
            """INSERT INTO center (center_code, name, city, address, phone, plan, is_active, created_at)
               VALUES ('CTR001', 'Main Branch', 'Raipur', 'Central Office', '', 'Active', 1, ?)""",
            (now(),),
        )
        conn.commit()

    main_center = c.execute("SELECT id FROM center WHERE center_code='CTR001'").fetchone()

    # ---- Seed default super-admin ----
    c.execute("SELECT * FROM user WHERE username='admin'")
    if not c.fetchone():
        c.execute(
            """INSERT INTO user (username, password_hash, full_name, role, center_id, is_active, created_at)
               VALUES ('admin', ?, 'Super Admin', 'superadmin', ?, 1, ?)""",
            (hash_pass("admin123"), main_center["id"] if main_center else None, now()),
        )
        conn.commit()

    # ---- Seed the 50 Yearly + 50 Monthly pre-issued license keys (only once) ----
    c.execute("SELECT COUNT(*) FROM license_key")
    if c.fetchone()[0] == 0:
        for key_str in PREISSUED_LICENSE_KEYS_YEARLY:
            c.execute(
                """INSERT OR IGNORE INTO license_key (license_key, duration_days, status, created_at)
                   VALUES (?, 365, 'Unused', ?)""",
                (key_str, now()),
            )
        for key_str in PREISSUED_LICENSE_KEYS_MONTHLY:
            c.execute(
                """INSERT OR IGNORE INTO license_key (license_key, duration_days, status, created_at)
                   VALUES (?, 30, 'Unused', ?)""",
                (key_str, now()),
            )
        conn.commit()

    conn.close()


def _ensure_columns(cursor, table, columns: dict):
    cursor.execute(f"PRAGMA table_info({table})")
    existing = [col[1] for col in cursor.fetchall()]
    for col_name, col_type in columns.items():
        if col_name not in existing:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")


# -----------------------------------------------------------------------------
# CODE GENERATORS
# -----------------------------------------------------------------------------
def next_patient_code():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM patient").fetchone()[0] + 1
    conn.close()
    return f"P{count:05d}"


def next_employee_code():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM staff").fetchone()[0] + 1
    conn.close()
    return f"E{count:05d}"


def next_center_code():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM center").fetchone()[0] + 1
    conn.close()
    return f"CTR{count:03d}"


# -----------------------------------------------------------------------------
# CENTER / TENANT HELPERS
# -----------------------------------------------------------------------------
def get_centers_dropdown(active_only=False):
    conn = get_db()
    q = "SELECT id, center_code, name, city FROM center"
    if active_only:
        q += " WHERE is_active=1"
    q += " ORDER BY city, name"
    try:
        rows = conn.execute(q).fetchall()
        conn.close()
        return {r["id"]: f"{r['name']} - {r['city']} ({r['center_code']})" for r in rows}
    except Exception:
        conn.close()
        return {}


def get_unique_cities():
    conn = get_db()
    try:
        cities = [r[0] for r in conn.execute(
            "SELECT DISTINCT city FROM center WHERE city IS NOT NULL AND city != '' ORDER BY city"
        ).fetchall()]
        conn.close()
        return ["All Cities"] + cities
    except Exception:
        conn.close()
        return ["All Cities"]


def get_user_city(center_id):
    if not center_id:
        return "All Cities"
    conn = get_db()
    res = conn.execute("SELECT city FROM center WHERE id=?", (center_id,)).fetchone()
    conn.close()
    return res["city"] if res else "All Cities"


def get_center_name(center_id):
    if not center_id:
        return "-"
    conn = get_db()
    res = conn.execute("SELECT name FROM center WHERE id=?", (center_id,)).fetchone()
    conn.close()
    return res["name"] if res else "-"


# -----------------------------------------------------------------------------
# PATIENT HELPERS
# -----------------------------------------------------------------------------
def get_patients_dropdown(center_id=None):
    conn = get_db()
    try:
        q = "SELECT id, patient_code, name FROM patient"
        params = []
        if center_id:
            q += " WHERE center_id=?"
            params.append(center_id)
        q += " ORDER BY name"
        rows = conn.execute(q, params).fetchall()
        conn.close()
        return {r["id"]: f"{r['name']} ({r['patient_code']})" for r in rows}
    except Exception:
        conn.close()
        return {}
