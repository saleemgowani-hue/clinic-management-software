"""
db_postgres.py
PostgreSQL backend for the Online (multi-tenant SaaS) deployment of SN
Clinic Management System.

Design goal: let the ~165 existing `conn.execute("... ? ...", params)` /
`row["col"]` / `cur.lastrowid` call sites throughout app.py, database.py,
demo_data.py, and licensing.py keep working completely unchanged, whether
the app is running against SQLite (offline) or PostgreSQL (online). This
module provides that compatibility layer so the SAME application code
runs on both backends — only get_db() decides which one to use.

Requires: psycopg2-binary (see requirements-online.txt)
"""

import os
import re
from datetime import datetime

import psycopg2
import psycopg2.extensions


# =============================================================================
# ROW WRAPPER — supports both row["col"] and row[0], like sqlite3.Row
# =============================================================================
class PGRow:
    """A single result row supporting both named (row["col"]) and positional
    (row[0]) access, and safe dict(row) conversion — matching every access
    pattern already used throughout the app for sqlite3.Row objects."""
    __slots__ = ("_cols", "_data")

    def __init__(self, cols, data):
        self._cols = cols
        self._data = data

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._data[key]
        return self._data[self._cols.index(key)]

    def __contains__(self, key):
        return key in self._cols

    def keys(self):
        return list(self._cols)

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __repr__(self):
        return f"PGRow({dict(zip(self._cols, self._data))!r})"


# =============================================================================
# CURSOR / CONNECTION WRAPPERS
# =============================================================================
class _PGCursorResult:
    """Mimics the subset of sqlite3.Cursor behaviour this app relies on:
    fetchone(), fetchall(), lastrowid, and iteration."""

    def __init__(self, raw_cursor, lastrowid=None):
        self._cur = raw_cursor
        self.lastrowid = lastrowid
        self._cols = [d[0] for d in raw_cursor.description] if raw_cursor.description else []

    def fetchone(self):
        row = self._cur.fetchone()
        return PGRow(self._cols, row) if row is not None else None

    def fetchall(self):
        return [PGRow(self._cols, row) for row in self._cur.fetchall()]

    def __iter__(self):
        for row in self._cur:
            yield PGRow(self._cols, row)

    @property
    def rowcount(self):
        return self._cur.rowcount


_INSERT_RE = re.compile(r"^\s*INSERT\s+INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE)


class PGConnWrapper:
    """Wraps a raw psycopg2 connection so the rest of the app can keep using
    sqlite3-style calls unchanged:
        conn.execute("SELECT ... WHERE x=?", (val,))
        cur = conn.execute("INSERT INTO t (...) VALUES (?, ?)", (a, b))
        new_id = cur.lastrowid
        conn.commit() / conn.rollback() / conn.close()
    """

    def __init__(self, raw_conn):
        self._conn = raw_conn

    def execute(self, query, params=()):
        # psycopg2 uses printf-style %s substitution internally, so any
        # OTHER literal "%" in the query (e.g. LIKE '%Doctor%') must be
        # escaped to "%%" first — otherwise it's misread as a missing
        # placeholder. Escape everything, then introduce the real ?-derived
        # placeholders, so only those become plain %s.
        translated = query.replace("%", "%%").replace("?", "%s")
        # "user" is a reserved word in PostgreSQL; app.py's existing SQL
        # strings reference it unquoted (as SQLite allows), so transparently
        # quote it here rather than touching every call site.
        translated = re.sub(r'\buser\b', '"user"', translated, flags=re.IGNORECASE)
        is_insert = bool(_INSERT_RE.match(translated))
        stripped = translated.rstrip().rstrip(";")
        if is_insert and "RETURNING" not in translated.upper():
            translated = stripped + " RETURNING id"
        else:
            translated = stripped

        cursor = self._conn.cursor()
        cursor.execute(translated, tuple(params) if params else None)

        lastrowid = None
        if is_insert:
            try:
                fetched = cursor.fetchone()
                if fetched is not None:
                    lastrowid = fetched[0]
            except psycopg2.ProgrammingError:
                lastrowid = None

        return _PGCursorResult(cursor, lastrowid=lastrowid)

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def is_postgres_configured() -> bool:
    """True if a DATABASE_URL is set (via env var or Streamlit secrets) —
    that's the single switch between Offline (SQLite) and Online (Postgres)
    modes. See database.py::get_db()."""
    if os.environ.get("DATABASE_URL"):
        return True
    try:
        import streamlit as st
        return bool(st.secrets.get("DATABASE_URL"))
    except Exception:
        return False


def _get_database_url():
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    try:
        import streamlit as st
        return st.secrets.get("DATABASE_URL")
    except Exception:
        return None


def get_pg_connection():
    """Opens a new PostgreSQL connection wrapped for sqlite3-style usage."""
    url = _get_database_url()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Set it as an environment variable or in "
            ".streamlit/secrets.toml to run in Online (PostgreSQL) mode."
        )
    raw_conn = psycopg2.connect(url)
    raw_conn.autocommit = False
    return PGConnWrapper(raw_conn)


# =============================================================================
# SCHEMA — full table set, Postgres-native types, with UUID/version triggers
# =============================================================================
# Every table matches database.py's SQLite schema (including all columns
# added by SQLite's incremental migrations) so the same app.py code works
# unmodified against either backend. Unlike SQLite (which grows a table's
# columns over time via ALTER TABLE), Postgres tables are created once,
# already complete.

_TABLES_SQL = [
    """CREATE TABLE IF NOT EXISTS center (
        id SERIAL PRIMARY KEY,
        center_code TEXT,
        name TEXT,
        city TEXT,
        address TEXT,
        phone TEXT,
        plan TEXT DEFAULT 'Trial',
        plan_expiry TEXT,
        is_active INTEGER DEFAULT 1,
        is_demo_center INTEGER DEFAULT 0,
        demo_reset_at TEXT,
        created_at TEXT,
        pending_plan TEXT,
        razorpay_link_id TEXT,
        razorpay_link_url TEXT,
        razorpay_link_status TEXT,
        timing TEXT,
        closed_day TEXT,
        uuid TEXT UNIQUE,
        updated_at TEXT,
        deleted_at TEXT,
        version_number INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS "user" (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password_hash TEXT,
        password_salt TEXT,
        full_name TEXT,
        role TEXT,
        center_id INTEGER,
        is_active INTEGER DEFAULT 1,
        is_demo_account INTEGER DEFAULT 0,
        created_at TEXT,
        uuid TEXT UNIQUE,
        updated_at TEXT,
        deleted_at TEXT,
        version_number INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS patient (
        id SERIAL PRIMARY KEY,
        patient_code TEXT,
        name TEXT,
        guardian_name TEXT,
        age INTEGER,
        gender TEXT,
        mobile TEXT,
        address TEXT,
        center_id INTEGER,
        created_at TEXT,
        is_demo INTEGER DEFAULT 0,
        uuid TEXT UNIQUE,
        updated_at TEXT,
        deleted_at TEXT,
        version_number INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS appointment (
        id SERIAL PRIMARY KEY,
        patient_id INTEGER REFERENCES patient(id),
        doctor_name TEXT,
        appt_date TEXT,
        appt_time TEXT,
        reason TEXT,
        status TEXT,
        center_id INTEGER,
        created_at TEXT,
        is_demo INTEGER DEFAULT 0,
        uuid TEXT UNIQUE,
        updated_at TEXT,
        deleted_at TEXT,
        version_number INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS consultation (
        id SERIAL PRIMARY KEY,
        patient_id INTEGER REFERENCES patient(id),
        visit_date TEXT,
        symptoms TEXT,
        diagnosis TEXT,
        prescription TEXT,
        next_visit TEXT,
        doctor_name TEXT,
        center_id INTEGER,
        is_demo INTEGER DEFAULT 0,
        chief_complaints TEXT,
        clinical_findings TEXT,
        weight REAL,
        height REAL,
        bp TEXT,
        advice TEXT,
        uuid TEXT UNIQUE,
        updated_at TEXT,
        deleted_at TEXT,
        version_number INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS prescription_item (
        id SERIAL PRIMARY KEY,
        consultation_id INTEGER REFERENCES consultation(id),
        medicine_name TEXT,
        composition TEXT,
        dosage TEXT,
        duration TEXT,
        total_qty TEXT,
        center_id INTEGER,
        uuid TEXT UNIQUE,
        updated_at TEXT,
        deleted_at TEXT,
        version_number INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS fee (
        id SERIAL PRIMARY KEY,
        patient_id INTEGER REFERENCES patient(id),
        consultation_fee REAL,
        medicine_fee REAL,
        other_charges REAL DEFAULT 0,
        discount REAL,
        total REAL,
        payment_mode TEXT,
        paid_on TEXT,
        center_id INTEGER,
        is_demo INTEGER DEFAULT 0,
        uuid TEXT UNIQUE,
        updated_at TEXT,
        deleted_at TEXT,
        version_number INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS medicine (
        id SERIAL PRIMARY KEY,
        name TEXT,
        batch_no TEXT,
        expiry_date TEXT,
        stock INTEGER,
        low_stock_alert INTEGER,
        unit_price REAL,
        center_id INTEGER,
        is_demo INTEGER DEFAULT 0,
        uuid TEXT UNIQUE,
        updated_at TEXT,
        deleted_at TEXT,
        version_number INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS medicine_sale (
        id SERIAL PRIMARY KEY,
        patient_id INTEGER,
        customer_name TEXT,
        mobile TEXT,
        subtotal REAL DEFAULT 0,
        discount REAL DEFAULT 0,
        total REAL DEFAULT 0,
        payment_mode TEXT,
        sold_on TEXT,
        center_id INTEGER,
        is_demo INTEGER DEFAULT 0,
        uuid TEXT UNIQUE,
        updated_at TEXT,
        deleted_at TEXT,
        version_number INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS medicine_sale_item (
        id SERIAL PRIMARY KEY,
        sale_id INTEGER REFERENCES medicine_sale(id),
        medicine_id INTEGER,
        medicine_name TEXT,
        quantity INTEGER,
        unit_price REAL,
        subtotal REAL,
        uuid TEXT UNIQUE,
        updated_at TEXT,
        deleted_at TEXT,
        version_number INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS lab_test_catalog (
        id SERIAL PRIMARY KEY,
        test_name TEXT,
        price REAL DEFAULT 0,
        normal_range TEXT,
        unit TEXT,
        center_id INTEGER,
        uuid TEXT UNIQUE,
        updated_at TEXT,
        deleted_at TEXT,
        version_number INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS lab_order (
        id SERIAL PRIMARY KEY,
        patient_id INTEGER REFERENCES patient(id),
        doctor_name TEXT,
        order_date TEXT,
        status TEXT DEFAULT 'Ordered',
        payment_mode TEXT,
        center_id INTEGER,
        is_demo INTEGER DEFAULT 0,
        consultation_id INTEGER,
        uuid TEXT UNIQUE,
        updated_at TEXT,
        deleted_at TEXT,
        version_number INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS lab_order_item (
        id SERIAL PRIMARY KEY,
        order_id INTEGER REFERENCES lab_order(id),
        test_name TEXT,
        price REAL DEFAULT 0,
        normal_range TEXT,
        unit TEXT,
        result_value TEXT,
        status TEXT DEFAULT 'Pending',
        uuid TEXT UNIQUE,
        updated_at TEXT,
        deleted_at TEXT,
        version_number INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS staff (
        id SERIAL PRIMARY KEY,
        employee_code TEXT,
        name TEXT,
        designation TEXT,
        mobile TEXT,
        city TEXT,
        address TEXT,
        joining_date TEXT,
        salary REAL,
        status TEXT DEFAULT 'Active',
        center_id INTEGER,
        created_at TEXT,
        is_demo INTEGER DEFAULT 0,
        qualification TEXT,
        registration_no TEXT,
        uuid TEXT UNIQUE,
        updated_at TEXT,
        deleted_at TEXT,
        version_number INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS attendance (
        id SERIAL PRIMARY KEY,
        staff_id INTEGER REFERENCES staff(id),
        att_date TEXT,
        status TEXT,
        center_id INTEGER,
        is_demo INTEGER DEFAULT 0,
        uuid TEXT UNIQUE,
        updated_at TEXT,
        deleted_at TEXT,
        version_number INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS license_key (
        id SERIAL PRIMARY KEY,
        license_key TEXT UNIQUE,
        duration_days INTEGER,
        status TEXT,
        used_by_center_id INTEGER,
        activated_on TEXT,
        expires_on TEXT,
        created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS expense (
        id SERIAL PRIMARY KEY,
        category TEXT,
        description TEXT,
        amount REAL DEFAULT 0,
        expense_date TEXT,
        center_id INTEGER,
        created_at TEXT,
        is_demo INTEGER DEFAULT 0,
        uuid TEXT UNIQUE,
        updated_at TEXT,
        deleted_at TEXT,
        version_number INTEGER DEFAULT 1
    )""",
]

# Tables that get the auto UUID/updated_at/version_number triggers (every
# syncable business table — same set as SQLite's SYNC_TABLES).
_SYNC_TABLES = [
    "center", '"user"', "patient", "appointment", "consultation", "prescription_item",
    "fee", "medicine", "medicine_sale", "medicine_sale_item", "lab_test_catalog",
    "lab_order", "lab_order_item", "staff", "attendance", "expense",
]

_TRIGGER_FUNCTIONS_SQL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION trg_set_uuid_and_meta() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.uuid IS NULL THEN
        NEW.uuid := gen_random_uuid()::text;
    END IF;
    NEW.updated_at := to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS');
    NEW.version_number := 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trg_bump_version() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.uuid IS NOT NULL THEN
        NEW.updated_at := to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS');
        NEW.version_number := COALESCE(OLD.version_number, 1) + 1;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- SQLite's STRFTIME() has no native PostgreSQL equivalent. app.py's Reports
-- module calls STRFTIME('%Y-%m-%d', ...) / STRFTIME('%Y-%m', ...) directly
-- in raw SQL (the only two patterns used anywhere in this app), so rather
-- than touch those call sites, we define a same-named function here that
-- covers exactly those two patterns transparently.
CREATE OR REPLACE FUNCTION STRFTIME(fmt TEXT, value TEXT) RETURNS TEXT AS $$
DECLARE
    ts TIMESTAMP;
BEGIN
    IF value IS NULL THEN
        RETURN NULL;
    END IF;
    ts := value::timestamp;
    IF fmt = '%Y-%m' THEN
        RETURN TO_CHAR(ts, 'YYYY-MM');
    ELSE
        RETURN TO_CHAR(ts, 'YYYY-MM-DD');
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
"""


# Mirrors the ALTER TABLE migration map in database.py. Add an entry here
# whenever a column is added to a table that may already exist in the wild.
_COLUMN_MIGRATIONS = [
    ('"user"', "is_demo_account", "INTEGER DEFAULT 0"),
    ("center", "is_demo_center", "INTEGER DEFAULT 0"),
    ("center", "demo_reset_at", "TEXT"),
]


def init_db_postgres():
    """Creates the full schema (if not already present) on the PostgreSQL
    database pointed to by DATABASE_URL, including the same UUID/version
    auto-maintenance behaviour as the SQLite offline version. Safe to call
    on every app startup — every statement is idempotent."""
    conn = get_pg_connection()
    raw = conn._conn
    cur = raw.cursor()

    for stmt in _TABLES_SQL:
        cur.execute(stmt)

    # ---- Column migrations for databases created by an earlier version ----
    # CREATE TABLE IF NOT EXISTS above is a no-op on an existing table, so any
    # column added after that table was first created must be applied here.
    # ADD COLUMN IF NOT EXISTS is idempotent, so this is safe on every startup.
    for _tbl, _col, _decl in _COLUMN_MIGRATIONS:
        cur.execute(f'ALTER TABLE {_tbl} ADD COLUMN IF NOT EXISTS {_col} {_decl}')

    cur.execute(_TRIGGER_FUNCTIONS_SQL)

    for t in _SYNC_TABLES:
        cur.execute(f'DROP TRIGGER IF EXISTS trg_{t.strip(chr(34))}_insert_meta ON {t}')
        cur.execute(f"""
            CREATE TRIGGER trg_{t.strip(chr(34))}_insert_meta
            BEFORE INSERT ON {t}
            FOR EACH ROW EXECUTE FUNCTION trg_set_uuid_and_meta();
        """)
        cur.execute(f'DROP TRIGGER IF EXISTS trg_{t.strip(chr(34))}_update_meta ON {t}')
        cur.execute(f"""
            CREATE TRIGGER trg_{t.strip(chr(34))}_update_meta
            BEFORE UPDATE ON {t}
            FOR EACH ROW EXECUTE FUNCTION trg_bump_version();
        """)

    raw.commit()

    # ---- Seed default center + superadmin (only if empty, mirrors database.py) ----
    cur.execute("SELECT COUNT(*) FROM center")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO center (center_code, name, city, plan, is_active, created_at) "
            "VALUES ('CTR001', 'Main Branch', 'Central Office', 'Active', 1, %s) RETURNING id",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),),
        )
        raw.commit()

    cur.execute('SELECT COUNT(*) FROM "user" WHERE role=%s', ("superadmin",))
    if cur.fetchone()[0] == 0:
        import hashlib
        import secrets as _secrets
        salt = _secrets.token_hex(16)
        pw_hash = hashlib.sha256((salt + "admin123").encode()).hexdigest()
        cur.execute(
            'INSERT INTO "user" (username, password_hash, password_salt, full_name, role, is_active, created_at) '
            "VALUES ('admin', %s, %s, 'Platform Owner', 'superadmin', 1, %s)",
            (pw_hash, salt, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        raw.commit()

    # ---- Seed the 25 Yearly + 25 Monthly pre-issued license keys (only once) ----
    cur.execute("SELECT COUNT(*) FROM license_key")
    if cur.fetchone()[0] == 0:
        import database as _db
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for key_str in _db.PREISSUED_LICENSE_KEYS_YEARLY:
            cur.execute(
                "INSERT INTO license_key (license_key, duration_days, status, created_at) "
                "VALUES (%s, 365, 'Unused', %s) ON CONFLICT (license_key) DO NOTHING",
                (key_str, now_str),
            )
        for key_str in _db.PREISSUED_LICENSE_KEYS_MONTHLY:
            cur.execute(
                "INSERT INTO license_key (license_key, duration_days, status, created_at) "
                "VALUES (%s, 30, 'Unused', %s) ON CONFLICT (license_key) DO NOTHING",
                (key_str, now_str),
            )
        raw.commit()

    cur.close()
    conn.close()
