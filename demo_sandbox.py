"""
demo_sandbox.py
A permanently available, self-resetting Demo clinic for sales demos.

How it works
------------
* One dedicated tenant (center code DEMO01, is_demo_center=1) holds all
  demo activity. It is isolated from every real clinic exactly like any
  other tenant, so a prospect poking around the demo can never see or
  touch paying customers' data.
* One login — demo / demo123 — role "admin", flagged is_demo_account=1
  so the password can never be changed from inside the app (see app.py).
* Anything the prospect adds during their visit lives at most one hour.
  On the first page load after DEMO_TTL_MINUTES have elapsed, every row
  belonging to the demo center is deleted and the standard sample set is
  re-seeded, so the next visitor always starts from the same clean state.

The reset is lazy (checked on page load), not scheduled — there is no
cron job or background thread to deploy, which keeps this working
identically on Streamlit Cloud, Render, Railway, or a plain VPS.
"""

from datetime import datetime, timedelta

import database as db
import demo_data as dd

DEMO_TTL_MINUTES = 60

DEMO_CENTER_CODE = "DEMO01"
DEMO_CENTER_NAME = "Demo Clinic (Sample Data)"
DEMO_CENTER_CITY = "Demo City"
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123"
DEMO_FULL_NAME = "Demo User"

# Child tables are cleared before their parents so foreign keys stay happy.
# medicine_sale_item / lab_order_item / prescription_item have no center_id
# of their own, so they are cleared via their parent's id.
_CHILD_VIA_PARENT = [
    ("medicine_sale_item", "sale_id", "medicine_sale"),
    ("lab_order_item", "order_id", "lab_order"),
    ("prescription_item", "consultation_id", "consultation"),
]

# Everything with a direct center_id, in delete-safe order.
_CENTER_SCOPED = [
    "attendance",
    "lab_order",
    "medicine_sale",
    "fee",
    "consultation",
    "appointment",
    "expense",
    "medicine",
    "lab_test_catalog",
    "staff",
    "patient",
]


def _far_future_expiry() -> str:
    """The demo tenant should never hit the license-expired screen."""
    return (datetime.now() + timedelta(days=3650)).strftime("%Y-%m-%d")


def get_demo_center_id():
    """Returns the demo center's id, or None if it hasn't been created yet."""
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT id FROM center WHERE center_code=?", (DEMO_CENTER_CODE,)
        ).fetchone()
        return row["id"] if row else None
    except Exception:
        return None
    finally:
        conn.close()


def is_demo_center(center_id) -> bool:
    if not center_id:
        return False
    return center_id == get_demo_center_id()


def ensure_demo_account():
    """Creates the demo tenant + demo login if missing. Idempotent — safe to
    call on every app start."""
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT id FROM center WHERE center_code=?", (DEMO_CENTER_CODE,)
        ).fetchone()

        if not row:
            conn.execute(
                """INSERT INTO center (center_code, name, city, address, phone,
                                       plan, plan_expiry, is_active, created_at)
                   VALUES (?, ?, ?, 'Sample data only', '', 'Active', ?, 1, ?)""",
                (DEMO_CENTER_CODE, DEMO_CENTER_NAME, DEMO_CENTER_CITY,
                 _far_future_expiry(), db.now()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT id FROM center WHERE center_code=?", (DEMO_CENTER_CODE,)
            ).fetchone()

        center_id = row["id"]

        # Flag it so Center Management can show it as a sandbox, and so the
        # tenant is easy to exclude from revenue reports later if wanted.
        conn.execute("UPDATE center SET is_demo_center=1 WHERE id=?", (center_id,))

        user_row = conn.execute(
            "SELECT id FROM user WHERE username=?", (DEMO_USERNAME,)
        ).fetchone()
        if not user_row:
            salt, pw_hash = db.make_password(DEMO_PASSWORD)
            conn.execute(
                """INSERT INTO user (username, password_hash, password_salt, full_name,
                                     role, center_id, is_active, created_at, is_demo_account)
                   VALUES (?, ?, ?, ?, 'admin', ?, 1, ?, 1)""",
                (DEMO_USERNAME, pw_hash, salt, DEMO_FULL_NAME, center_id, db.now()),
            )
        else:
            # Re-assert the lock in case an older build left it unset.
            conn.execute(
                "UPDATE user SET is_demo_account=1, center_id=? WHERE username=?",
                (center_id, DEMO_USERNAME),
            )
        conn.commit()
        return center_id
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()


def _wipe(conn, center_id):
    """Deletes EVERY record in the demo tenant — not just is_demo=1 rows, so
    anything a visitor typed in during their session goes too."""
    for child, fk, parent in _CHILD_VIA_PARENT:
        conn.execute(
            f"DELETE FROM {child} WHERE {fk} IN "
            f"(SELECT id FROM {parent} WHERE center_id=?)",
            (center_id,),
        )
    for table in _CENTER_SCOPED:
        conn.execute(f"DELETE FROM {table} WHERE center_id=?", (center_id,))
    # Staff/user logins other than the demo account itself are cleared too,
    # so a visitor can't leave behind a login for the next visitor.
    conn.execute(
        "DELETE FROM user WHERE center_id=? AND username<>?",
        (center_id, DEMO_USERNAME),
    )


def _minutes_since(stamp) -> float:
    if not stamp:
        return float("inf")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return (datetime.now() - datetime.strptime(str(stamp), fmt)).total_seconds() / 60.0
        except ValueError:
            continue
    return float("inf")


def minutes_left(center_id) -> int:
    """How long until the next auto-wipe — shown to the visitor as a banner."""
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT demo_reset_at FROM center WHERE id=?", (center_id,)
        ).fetchone()
    except Exception:
        return DEMO_TTL_MINUTES
    finally:
        conn.close()
    elapsed = _minutes_since(row["demo_reset_at"] if row else None)
    if elapsed == float("inf"):
        return DEMO_TTL_MINUTES
    return max(0, int(DEMO_TTL_MINUTES - elapsed))


def refresh_if_expired(center_id, force=False) -> bool:
    """Wipes and re-seeds the demo tenant if its data is older than
    DEMO_TTL_MINUTES. Returns True if a reset actually happened."""
    if not center_id:
        return False

    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT demo_reset_at FROM center WHERE id=?", (center_id,)
        ).fetchone()
        if not row:
            return False

        if not force and _minutes_since(row["demo_reset_at"]) < DEMO_TTL_MINUTES:
            return False

        _wipe(conn, center_id)
        # Stamp the reset BEFORE seeding: if seeding fails halfway, the next
        # page load won't loop into wiping again every single time.
        conn.execute(
            "UPDATE center SET demo_reset_at=? WHERE id=?", (db.now(), center_id)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()

    try:
        dd.add_demo_data(center_id)
    except Exception:
        pass
    return True
