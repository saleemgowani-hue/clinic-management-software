"""
migrate_to_online.py
One-time migration: copies all data from your existing offline clinic.db
(SQLite) into the online PostgreSQL database (DATABASE_URL). Existing
UUIDs are preserved so records keep the same global identity after the
move. Safe to re-run — rows that already exist (matched by UUID) are
skipped rather than duplicated.

Foreign keys (patient_id, center_id, consultation_id, etc.) are correctly
remapped: SQLite's local auto-increment IDs are NOT reused as-is in
Postgres (Postgres assigns its own new IDs), so this script tracks an
old-ID -> new-ID mapping per table and rewrites every foreign-key column
accordingly as it goes, table by table in dependency order.

This is a ONE-TIME, ONE-DIRECTION copy (Offline -> Online), run manually
by you when you're ready to move a clinic online. It is NOT continuous
sync — the two databases are independent again the moment this finishes.
Run it once, verify the data looks right in the Online app, then have
the clinic switch to using the Online version going forward.

Usage:
    export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
    python migrate_to_online.py [path-to-clinic.db]

If no path is given, it looks for clinic.db in the current folder.
"""

import sys
import sqlite3

import db_postgres


# Tables in dependency order (parents before children) and, for each, which
# columns are foreign keys pointing at which parent table's "id" — these
# get remapped from the old SQLite id to the new Postgres id as we go.
TABLE_ORDER = [
    ("center", {}),
    ("user", {"center_id": "center"}),
    ("patient", {"center_id": "center"}),
    ("staff", {"center_id": "center"}),
    ("appointment", {"patient_id": "patient", "center_id": "center"}),
    ("consultation", {"patient_id": "patient", "center_id": "center"}),
    ("prescription_item", {"consultation_id": "consultation", "center_id": "center"}),
    ("fee", {"patient_id": "patient", "center_id": "center"}),
    ("medicine", {"center_id": "center"}),
    ("medicine_sale", {"patient_id": "patient", "center_id": "center"}),
    ("medicine_sale_item", {"sale_id": "medicine_sale", "medicine_id": "medicine"}),
    ("lab_test_catalog", {"center_id": "center"}),
    ("lab_order", {"patient_id": "patient", "center_id": "center", "consultation_id": "consultation"}),
    ("lab_order_item", {"order_id": "lab_order"}),
    ("attendance", {"staff_id": "staff", "center_id": "center"}),
    ("expense", {"center_id": "center"}),
    ("license_key", {"used_by_center_id": "center"}),
]


# For tables with their own natural unique constraint, check by that field
# too (not just uuid) — e.g. both the offline and online databases
# independently seed a default 'admin' superadmin account with different
# UUIDs, which would otherwise collide on the username UNIQUE constraint.
NATURAL_KEYS = {
    "user": "username",
    "center": "center_code",
    "license_key": "license_key",
}


def get_sqlite_columns(sqlite_conn, table):
    return [r[1] for r in sqlite_conn.execute(f"PRAGMA table_info({table})").fetchall()]


def migrate_table(sqlite_conn, pg_conn, table, fk_map, id_maps):
    cols = get_sqlite_columns(sqlite_conn, table)
    if not cols:
        print(f"  [skip] {table}: not found in source database")
        return 0, 0

    rows = sqlite_conn.execute(f"SELECT {', '.join(cols)} FROM {table}").fetchall()
    if not rows:
        print(f"  [skip] {table}: no rows")
        return 0, 0

    has_uuid = "uuid" in cols
    natural_key = NATURAL_KEYS.get(table)
    id_maps.setdefault(table, {})
    inserted, skipped = 0, 0

    for row in rows:
        row_dict = dict(zip(cols, row))
        old_id = row_dict.get("id")

        existing = None
        if has_uuid and row_dict.get("uuid"):
            existing = pg_conn.execute(
                f"SELECT id FROM {table} WHERE uuid=?", (row_dict["uuid"],)
            ).fetchone()
        if existing is None and natural_key and row_dict.get(natural_key) is not None:
            existing = pg_conn.execute(
                f"SELECT id FROM {table} WHERE {natural_key}=?", (row_dict[natural_key],)
            ).fetchone()

        if existing:
            id_maps[table][old_id] = existing["id"]
            skipped += 1
            continue

        insert_cols = [c for c in cols if c != "id"]
        values = []
        for c in insert_cols:
            val = row_dict[c]
            if c in fk_map and val is not None:
                parent_table = fk_map[c]
                val = id_maps.get(parent_table, {}).get(val, val)
            values.append(val)

        placeholders = ", ".join("?" for _ in insert_cols)
        cur = pg_conn.execute(
            f"INSERT INTO {table} ({', '.join(insert_cols)}) VALUES ({placeholders})",
            values,
        )
        if old_id is not None:
            id_maps[table][old_id] = cur.lastrowid
        inserted += 1

    pg_conn.commit()
    print(f"  [ok] {table}: {inserted} inserted, {skipped} already present (skipped)")
    return inserted, skipped


def main():
    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else "clinic.db"

    if not db_postgres.is_postgres_configured():
        print("[ERROR] DATABASE_URL is not set. Set it before running this script:")
        print('  export DATABASE_URL="postgresql://user:pass@host:5432/dbname"')
        sys.exit(1)

    print("=" * 60)
    print("SN Clinic — Offline to Online Migration")
    print("=" * 60)
    print(f"\nSource (offline):  {sqlite_path}")
    print("Destination (online): the PostgreSQL database in DATABASE_URL")
    print("\nThis is a one-time copy. Your offline clinic.db is not modified.")
    print()

    try:
        sqlite_conn = sqlite3.connect(sqlite_path)
    except Exception as e:
        print(f"[ERROR] Could not open {sqlite_path}: {e}")
        sys.exit(1)

    print("Preparing the online database (creating tables if needed)...")
    db_postgres.init_db_postgres()
    pg_conn = db_postgres.get_pg_connection()

    id_maps = {}
    total_inserted = 0
    total_skipped = 0
    for table, fk_map in TABLE_ORDER:
        ins, skip = migrate_table(sqlite_conn, pg_conn, table, fk_map, id_maps)
        total_inserted += ins
        total_skipped += skip

    sqlite_conn.close()
    pg_conn.close()

    print()
    print("=" * 60)
    print(f"Done. {total_inserted} row(s) migrated, {total_skipped} already present.")
    print("Log in to the Online app and confirm your data looks correct before")
    print("switching your clinic over to using it day-to-day.")
    print("=" * 60)


if __name__ == "__main__":
    main()
