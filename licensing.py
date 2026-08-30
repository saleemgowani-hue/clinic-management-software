"""
licensing.py
Handles license key activation for clinics. A license key is a single-use
code that, once entered by a clinic Admin, sets that clinic's plan
validity to `duration_days` (30 for Monthly, 365 for Yearly) from the day
it's activated.

Keys are stored in the `license_key` table (see database.py) and are
seeded with ready-to-sell keys on first run (see PREISSUED_LICENSE_KEYS_*
in database.py).
"""

import re
import secrets
from datetime import datetime, timedelta

import database as db

# Characters chosen to avoid visual ambiguity (no 0/O, 1/I/L).
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

# Matches a key like "SNCLY-2GRCH-3NATF-5ESE8" or "SNCLM-..." (or the older
# prefix-less "SNCL-..." format), anywhere inside a larger string — this
# lets us recover the real key even if the user accidentally copy-pasted
# extra text around it (a list number like "12.", surrounding spaces, a
# stray newline from a two-column text file, etc.).
KEY_PATTERN = re.compile(r"SNCL[YM]?-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}", re.IGNORECASE)


def _clean_key(raw: str) -> str:
    """Extracts and normalizes a license key from whatever the user typed/pasted."""
    if not raw:
        return ""
    match = KEY_PATTERN.search(raw.upper())
    if match:
        return match.group(0)
    # Fall back to a plain strip/uppercase in case of an unexpected format,
    # so we still give the DB lookup a fair chance instead of failing early.
    return raw.strip().upper()


def generate_license_key(prefix: str = "SNCL") -> str:
    """Generates one new, nicely formatted license key (not yet saved to DB)."""
    groups = ["".join(secrets.choice(ALPHABET) for _ in range(5)) for _ in range(3)]
    return f"{prefix}-" + "-".join(groups)


def create_new_keys(count: int = 10, duration_days: int = 365) -> list:
    """Generates `count` brand-new unique keys and inserts them as 'Unused'."""
    prefix = "SNCLM" if duration_days <= 31 else ("SNCLY" if duration_days >= 200 else "SNCL")
    conn = db.get_db()
    created = []
    try:
        while len(created) < count:
            key_str = generate_license_key(prefix)
            existing = conn.execute("SELECT id FROM license_key WHERE license_key=?", (key_str,)).fetchone()
            if existing:
                continue
            conn.execute(
                """INSERT INTO license_key (license_key, duration_days, status, created_at)
                   VALUES (?, ?, 'Unused', ?)""",
                (key_str, duration_days, db.now()),
            )
            created.append(key_str)
        conn.commit()
    finally:
        conn.close()
    return created


def validate_key(key_str: str):
    """
    Checks whether a license key is valid and unused, WITHOUT consuming it
    (doesn't mark it 'Used' or attach it to any center). Used at clinic
    registration time to verify the key before creating the clinic.
    Returns (valid: bool, message: str, duration_days: int|None).
    """
    cleaned = _clean_key(key_str)
    if not cleaned:
        return False, "Please enter a license key.", None

    conn = db.get_db()
    try:
        row = conn.execute("SELECT * FROM license_key WHERE license_key=?", (cleaned,)).fetchone()
        if not row:
            return False, "That license key was not recognized. Please check and try again.", None
        if row["status"] == "Used":
            return False, "This license key has already been used.", None
        if row["status"] == "Revoked":
            return False, "This license key has been revoked. Please contact support.", None
        return True, "Key is valid.", row["duration_days"] or 365
    finally:
        conn.close()


def activate_key(key_str: str, center_id: int):
    """
    Attempts to activate a license key for the given center.
    Returns (success: bool, message: str, new_expiry: str|None).
    On success, extends/sets the center's plan to 'Licensed - Monthly' or
    'Licensed - Yearly' (based on the key's duration) with a plan_expiry of
    today + the key's duration_days, and marks the key 'Used'.
    """
    cleaned = _clean_key(key_str)
    if not cleaned:
        return False, "Please enter a license key.", None

    conn = db.get_db()
    try:
        row = conn.execute("SELECT * FROM license_key WHERE license_key=?", (cleaned,)).fetchone()
        if not row:
            return False, "That license key was not recognized. Please check and try again.", None
        if row["status"] == "Used":
            return False, "This license key has already been used.", None
        if row["status"] == "Revoked":
            return False, "This license key has been revoked. Please contact support.", None

        duration = row["duration_days"] or 365
        expires_on = (datetime.now() + timedelta(days=duration)).strftime("%Y-%m-%d")
        plan_label = "Licensed - Monthly" if duration <= 31 else "Licensed - Yearly"

        conn.execute(
            """UPDATE license_key SET status='Used', used_by_center_id=?, activated_on=?, expires_on=?
               WHERE id=?""",
            (center_id, db.now(), expires_on, row["id"]),
        )
        conn.execute(
            "UPDATE center SET plan=?, plan_expiry=?, is_active=1 WHERE id=?",
            (plan_label, expires_on, center_id),
        )
        conn.commit()
        kind = "Monthly" if duration <= 31 else "Yearly"
        return True, f"{kind} license activated! Valid until {expires_on}.", expires_on
    finally:
        conn.close()


def list_keys():
    """Returns all license keys with their status, for the Super Admin view."""
    conn = db.get_db()
    try:
        rows = conn.execute(
            """SELECT lk.license_key, lk.status, lk.duration_days, lk.activated_on, lk.expires_on,
                      c.name as used_by_clinic
               FROM license_key lk LEFT JOIN center c ON lk.used_by_center_id = c.id
               ORDER BY lk.id"""
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_specific_keys(keys: list, duration_days: int) -> list:
    """
    Inserts a specific, pre-generated list of keys (not randomly generated
    here) as 'Unused', skipping any that already exist. Used to add a fresh
    batch of known keys (e.g. from License_Keys.txt) into an existing
    database without needing to wipe it. Returns the list actually added.
    """
    conn = db.get_db()
    added = []
    try:
        for key_str in keys:
            key_str = key_str.strip().upper()
            if not key_str:
                continue
            existing = conn.execute("SELECT id FROM license_key WHERE license_key=?", (key_str,)).fetchone()
            if existing:
                continue
            conn.execute(
                """INSERT INTO license_key (license_key, duration_days, status, created_at)
                   VALUES (?, ?, 'Unused', ?)""",
                (key_str, duration_days, db.now()),
            )
            added.append(key_str)
        conn.commit()
    finally:
        conn.close()
    return added
