"""
add_fresh_license_keys.py
One-time helper: adds the 25 new Yearly + 25 new Monthly license keys
(shipped in this update) into your EXISTING clinic.db, without touching
any of your existing data (patients, staff, bills, users, etc.).

Why you need this: license keys are only auto-seeded into a brand-new,
empty database. If you already have a clinic.db from before, it keeps
whatever keys it was first created with — this script tops it up with
the fresh batch from this release.

Run this once after replacing your app files with this update:
    python add_fresh_license_keys.py
(or double-click Add_Fresh_License_Keys.bat on Windows)
"""

import database as db
import licensing as lic


def main():
    print("=" * 60)
    print("SN Clinic - Add Fresh License Keys")
    print("=" * 60)

    db.init_db()  # safe to call again; only creates tables/columns that don't exist yet

    added_yearly = lic.add_specific_keys(db.PREISSUED_LICENSE_KEYS_YEARLY, duration_days=365)
    added_monthly = lic.add_specific_keys(db.PREISSUED_LICENSE_KEYS_MONTHLY, duration_days=30)

    print(f"\nAdded {len(added_yearly)} new Yearly key(s) and "
          f"{len(added_monthly)} new Monthly key(s) to clinic.db.")

    skipped_yearly = len(db.PREISSUED_LICENSE_KEYS_YEARLY) - len(added_yearly)
    skipped_monthly = len(db.PREISSUED_LICENSE_KEYS_MONTHLY) - len(added_monthly)
    if skipped_yearly or skipped_monthly:
        print(f"(Skipped {skipped_yearly + skipped_monthly} key(s) already present in your database.)")

    conn = db.get_db()
    total = conn.execute("SELECT COUNT(*) FROM license_key").fetchone()[0]
    unused = conn.execute("SELECT COUNT(*) FROM license_key WHERE status='Unused'").fetchone()[0]
    conn.close()
    print(f"\nYour database now has {total} license key(s) total, {unused} of them Unused.")
    print("\nAll done! You can now register a new clinic or activate a license using")
    print("any of the fresh keys from License_Keys.txt.")
    print("=" * 60)


if __name__ == "__main__":
    main()
