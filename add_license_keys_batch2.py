"""
add_license_keys_batch2.py
One-time helper: adds a second batch of 25 new Yearly + 50 new Monthly
license keys into your EXISTING database, without touching any existing
data (patients, staff, bills, users, license keys already issued, etc.).

Works against whichever database is active wherever you run it, exactly
like add_fresh_license_keys.py:
  - Offline: your local clinic.db (SQLite) — just run it as-is.
  - Online: your PostgreSQL database — set the DATABASE_URL environment
    variable to your production connection string first, then run it:
        export DATABASE_URL="postgresql://username:password@host:5432/dbname"
        python add_license_keys_batch2.py
    Run it once against each database (offline machine, online host) so
    these exact keys are valid to activate in both places.

Run this once per database:
    python add_license_keys_batch2.py
"""

import database as db
import licensing as lic


def main():
    print("=" * 60)
    print("SN Clinic - Add License Keys (Batch 2)")
    print("=" * 60)

    db.init_db()  # safe to call again; only creates tables/columns that don't exist yet

    added_yearly = lic.add_specific_keys(db.PREISSUED_LICENSE_KEYS_YEARLY_BATCH2, duration_days=365)
    added_monthly = lic.add_specific_keys(db.PREISSUED_LICENSE_KEYS_MONTHLY_BATCH2, duration_days=30)

    print(f"\nAdded {len(added_yearly)} new Yearly key(s) and "
          f"{len(added_monthly)} new Monthly key(s).")

    skipped_yearly = len(db.PREISSUED_LICENSE_KEYS_YEARLY_BATCH2) - len(added_yearly)
    skipped_monthly = len(db.PREISSUED_LICENSE_KEYS_MONTHLY_BATCH2) - len(added_monthly)
    if skipped_yearly or skipped_monthly:
        print(f"(Skipped {skipped_yearly + skipped_monthly} key(s) already present in this database.)")

    conn = db.get_db()
    total = conn.execute("SELECT COUNT(*) FROM license_key").fetchone()[0]
    unused = conn.execute("SELECT COUNT(*) FROM license_key WHERE status='Unused'").fetchone()[0]
    conn.close()
    print(f"\nThis database now has {total} license key(s) total, {unused} of them Unused.")
    print("=" * 60)


if __name__ == "__main__":
    main()
