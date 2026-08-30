"""
demo_data.py
Adds or removes a set of realistic sample records (patients, staff,
appointments, consultations, bills, medicines, attendance, expenses) for
one clinic, so an Admin can explore or demo the software without typing
in real data first.

Every row this module creates is tagged is_demo=1, which is how
remove_demo_data() finds exactly what to delete — nothing else in the
clinic is ever touched.
"""

from datetime import date, timedelta
import secrets

import database as db

DEMO_PATIENTS = [
    ("Sunita Sharma", "Ramesh Sharma", 34, "Female", "9000000001"),
    ("Ravi Kumar", "Suresh Kumar", 45, "Male", "9000000002"),
    ("Anjali Verma", "Manoj Verma", 28, "Female", "9000000003"),
    ("Amit Patel", "Kishore Patel", 52, "Male", "9000000004"),
    ("Pooja Singh", "Rajesh Singh", 22, "Female", "9000000005"),
    ("Vikram Rao", "Srinivas Rao", 61, "Male", "9000000006"),
    ("Neha Gupta", "Ashok Gupta", 39, "Female", "9000000007"),
    ("Rahul Mehta", "Dinesh Mehta", 30, "Male", "9000000008"),
    ("Kavya Reddy", "Venkat Reddy", 26, "Female", "9000000009"),
    ("Arjun Nair", "Mohan Nair", 41, "Male", "9000000010"),
    ("Priyanka Joshi", "Anil Joshi", 33, "Female", "9000000011"),
    ("Rohit Malhotra", "Sanjay Malhotra", 48, "Male", "9000000012"),
    ("Divya Iyer", "Krishnan Iyer", 29, "Female", "9000000013"),
    ("Karan Chopra", "Vijay Chopra", 55, "Male", "9000000014"),
    ("Meera Pillai", "Ravindran Pillai", 24, "Female", "9000000015"),
    ("Sandeep Yadav", "Ramesh Yadav", 37, "Male", "9000000016"),
    ("Aarti Deshmukh", "Prakash Deshmukh", 43, "Female", "9000000017"),
    ("Manoj Tiwari", "Ram Tiwari", 58, "Male", "9000000018"),
    ("Shreya Bhatt", "Nitin Bhatt", 27, "Female", "9000000019"),
    ("Deepak Kulkarni", "Ganesh Kulkarni", 46, "Male", "9000000020"),
    ("Ritu Saxena", "Vinod Saxena", 31, "Female", "9000000021"),
    ("Vivek Menon", "Suresh Menon", 50, "Male", "9000000022"),
    ("Swati Agarwal", "Rakesh Agarwal", 36, "Female", "9000000023"),
    ("Nikhil Bose", "Amit Bose", 44, "Male", "9000000024"),
]

DEMO_STAFF = [
    ("Dr. Kavita Joshi", "Doctor", "9000001001", 45000),
    ("Dr. Sanjay Nair", "Doctor", "9000001002", 42000),
    ("Priya Nurse", "Nurse", "9000001003", 18000),
    ("Rakesh Reception", "Receptionist", "9000001004", 15000),
]

DEMO_MEDICINES = [
    ("Paracetamol 500mg", 200, 30, 2.5),
    ("Amoxicillin 250mg", 120, 20, 6.0),
    ("Cetirizine 10mg", 8, 20, 1.5),   # intentionally low stock, to demo the alert
    ("ORS Sachets", 150, 25, 8.0),
    ("Vitamin C Tablets", 5, 15, 3.0),  # intentionally low stock
]

DEMO_EXPENSES = [
    ("Rent", "Monthly clinic rent", 15000),
    ("Electricity", "Electricity bill", 3200),
    ("Medicine Purchase", "Stock replenishment", 8500),
    ("Maintenance", "AC servicing", 1500),
]


def has_demo_data(center_id: int) -> bool:
    conn = db.get_db()
    try:
        count = conn.execute("SELECT COUNT(*) FROM patient WHERE center_id=? AND is_demo=1", (center_id,)).fetchone()[0]
        return count > 0
    finally:
        conn.close()


def _unique_code(conn, table, column, base_code):
    """Returns base_code if it's free in `table.column`, otherwise appends
    a short random suffix until it finds one that is. Guards against
    leftover data from an older version of this script (before demo codes
    were made per-clinic) or any other unexpected collision, since
    patient_code/employee_code are unique across the whole database, not
    just within one clinic."""
    code = base_code
    attempt = 0
    while conn.execute(f"SELECT 1 FROM {table} WHERE {column}=?", (code,)).fetchone():
        attempt += 1
        code = f"{base_code}-{secrets.token_hex(2).upper()}"
        if attempt > 20:  # practically unreachable, just a hard stop
            break
    return code


def add_demo_data(center_id: int) -> dict:
    """Inserts a full set of sample records for the given clinic. Safe to
    call even if some demo data already exists (won't duplicate patients,
    since it checks first)."""
    if has_demo_data(center_id):
        return {"added": False, "reason": "Demo data already exists for this clinic."}

    conn = db.get_db()
    counts = {"patients": 0, "staff": 0, "appointments": 0, "consultations": 0,
              "bills": 0, "medicines": 0, "attendance": 0, "expenses": 0}
    try:
        today = date.today()
        now = db.now()

        # ---- Patients ----
        patient_ids = []
        for i, (name, guardian, age, gender, mobile) in enumerate(DEMO_PATIENTS, start=1):
            code = _unique_code(conn, "patient", "patient_code", f"DEMO-C{center_id}-P{i:03d}")
            cur = conn.execute(
                """INSERT INTO patient (patient_code, name, guardian_name, age, gender, mobile,
                                         address, center_id, created_at, is_demo)
                   VALUES (?, ?, ?, ?, ?, ?, 'Demo Address', ?, ?, 1)""",
                (code, name, guardian, age, gender, mobile, center_id, now),
            )
            patient_ids.append(cur.lastrowid)
            counts["patients"] += 1

        # ---- Staff ----
        staff_ids = []
        for i, (name, designation, mobile, salary) in enumerate(DEMO_STAFF, start=1):
            code = _unique_code(conn, "staff", "employee_code", f"DEMO-C{center_id}-E{i:03d}")
            joining = (today - timedelta(days=180)).isoformat()
            cur = conn.execute(
                """INSERT INTO staff (employee_code, name, designation, mobile, city, address,
                                       joining_date, salary, status, center_id, created_at, is_demo)
                   VALUES (?, ?, ?, ?, 'Demo City', 'Demo Address', ?, ?, 'Active', ?, ?, 1)""",
                (code, name, designation, mobile, joining, salary, center_id, now),
            )
            staff_ids.append(cur.lastrowid)
            counts["staff"] += 1

        doctor_names = [n for n, d, *_ in DEMO_STAFF if d == "Doctor"]

        # ---- Appointments (mix of past/today/upcoming, varied statuses) ----
        appt_plan = [
            (0, "Completed", "Fever and cold"),
            (0, "Booked", "Routine checkup"),
            (-1, "Completed", "Follow-up visit"),
            (-2, "No-Show", "Skin allergy"),
            (1, "Booked", "Vaccination"),
            (2, "Booked", "Dental consultation"),
        ]
        for idx, (day_offset, status, reason) in enumerate(appt_plan):
            pid = patient_ids[idx % len(patient_ids)]
            doctor = doctor_names[idx % len(doctor_names)] if doctor_names else "Dr. Kavita Joshi"
            appt_date = (today + timedelta(days=day_offset)).isoformat()
            conn.execute(
                """INSERT INTO appointment (patient_id, doctor_name, appt_date, appt_time, reason,
                                             status, center_id, created_at, is_demo)
                   VALUES (?, ?, ?, '10:30:00', ?, ?, ?, ?, 1)""",
                (pid, doctor, appt_date, reason, status, center_id, now),
            )
            counts["appointments"] += 1

        # ---- Consultations for a few patients ----
        consult_plan = [
            (patient_ids[0], "Fever, cold", "Viral fever", "Paracetamol 500mg twice daily", doctor_names[0] if doctor_names else "Dr. Kavita Joshi", (today + timedelta(days=5)).isoformat()),
            (patient_ids[2], "Skin rash", "Allergic dermatitis", "Cetirizine 10mg once daily", doctor_names[0] if doctor_names else "Dr. Kavita Joshi", (today + timedelta(days=3)).isoformat()),
            (patient_ids[4], "Cough", "Upper respiratory infection", "Amoxicillin 250mg thrice daily", doctor_names[-1] if doctor_names else "Dr. Sanjay Nair", None),
        ]
        for pid, symptoms, diagnosis, prescription, doctor, next_visit in consult_plan:
            conn.execute(
                """INSERT INTO consultation (patient_id, visit_date, symptoms, diagnosis, prescription,
                                              next_visit, doctor_name, center_id, is_demo)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (pid, now, symptoms, diagnosis, prescription, next_visit, doctor, center_id),
            )
            counts["consultations"] += 1

        # ---- Bills ----
        bill_plan = [
            (patient_ids[0], 300, 150, 0, "Cash"),
            (patient_ids[1], 400, 0, 50, "UPI"),
            (patient_ids[2], 250, 200, 0, "Card"),
            (patient_ids[3], 500, 100, 0, "Cash"),
            (patient_ids[4], 300, 80, 20, "UPI"),
        ]
        for pid, cfee, mfee, disc, mode in bill_plan:
            total = cfee + mfee - disc
            paid_on = (today - timedelta(days=1)).isoformat() + " 12:00:00"
            conn.execute(
                """INSERT INTO fee (patient_id, consultation_fee, medicine_fee, other_charges, discount,
                                    total, payment_mode, paid_on, center_id, is_demo)
                   VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, 1)""",
                (pid, cfee, mfee, disc, total, mode, paid_on, center_id),
            )
            counts["bills"] += 1

        # ---- Medicines ----
        for name, stock, low_alert, price in DEMO_MEDICINES:
            conn.execute(
                """INSERT INTO medicine (name, batch_no, expiry_date, stock, low_stock_alert,
                                          unit_price, center_id, is_demo)
                   VALUES (?, 'DEMO-BATCH', ?, ?, ?, ?, ?, 1)""",
                (name, (today + timedelta(days=365)).isoformat(), stock, low_alert, price, center_id),
            )
            counts["medicines"] += 1

        # ---- Attendance (last 5 days for each staff member) ----
        for sid in staff_ids:
            for d in range(5):
                att_date = (today - timedelta(days=d)).isoformat()
                status = "Present" if d != 2 else "Leave"
                conn.execute(
                    """INSERT INTO attendance (staff_id, att_date, status, center_id, is_demo)
                       VALUES (?, ?, ?, ?, 1)""",
                    (sid, att_date, status, center_id),
                )
                counts["attendance"] += 1

        # ---- Expenses ----
        for category, desc, amount in DEMO_EXPENSES:
            exp_date = (today - timedelta(days=3)).isoformat()
            conn.execute(
                """INSERT INTO expense (category, description, amount, expense_date, center_id,
                                         created_at, is_demo)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (category, desc, amount, exp_date, center_id, now),
            )
            counts["expenses"] += 1

        conn.commit()
        return {"added": True, "counts": counts}
    except Exception as e:
        conn.rollback()
        return {"added": False, "reason": str(e)}
    finally:
        conn.close()


def remove_demo_data(center_id: int) -> dict:
    """Deletes every is_demo=1 row for this clinic, across all tables."""
    conn = db.get_db()
    try:
        demo_patient_ids = [r[0] for r in conn.execute(
            "SELECT id FROM patient WHERE center_id=? AND is_demo=1", (center_id,)
        ).fetchall()]
        demo_staff_ids = [r[0] for r in conn.execute(
            "SELECT id FROM staff WHERE center_id=? AND is_demo=1", (center_id,)
        ).fetchall()]

        removed = {}

        if demo_patient_ids:
            placeholders = ",".join("?" * len(demo_patient_ids))
            removed["consultations"] = conn.execute(
                f"DELETE FROM consultation WHERE patient_id IN ({placeholders})", demo_patient_ids
            ).rowcount

        if demo_staff_ids:
            placeholders = ",".join("?" * len(demo_staff_ids))
            removed["attendance"] = conn.execute(
                f"DELETE FROM attendance WHERE staff_id IN ({placeholders})", demo_staff_ids
            ).rowcount

        removed["bills"] = conn.execute(
            "DELETE FROM fee WHERE center_id=? AND is_demo=1", (center_id,)
        ).rowcount
        removed["appointments"] = conn.execute(
            "DELETE FROM appointment WHERE center_id=? AND is_demo=1", (center_id,)
        ).rowcount
        removed["medicines"] = conn.execute(
            "DELETE FROM medicine WHERE center_id=? AND is_demo=1", (center_id,)
        ).rowcount
        removed["expenses"] = conn.execute(
            "DELETE FROM expense WHERE center_id=? AND is_demo=1", (center_id,)
        ).rowcount
        removed["staff"] = conn.execute(
            "DELETE FROM staff WHERE center_id=? AND is_demo=1", (center_id,)
        ).rowcount
        removed["patients"] = conn.execute(
            "DELETE FROM patient WHERE center_id=? AND is_demo=1", (center_id,)
        ).rowcount

        conn.commit()
        return {"removed": True, "counts": removed}
    except Exception as e:
        conn.rollback()
        return {"removed": False, "reason": str(e)}
    finally:
        conn.close()
