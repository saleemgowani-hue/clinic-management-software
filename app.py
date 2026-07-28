import calendar
import csv
import hashlib
import sqlite3
from datetime import date, datetime, timedelta
from io import StringIO

import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG & CUSTOM STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="SN Clinic Management System",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    div[data-testid="stForm"], div.stTextInput {
        max-width: 500px !important;
        margin: 0 auto;
    }
    .stMetric {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 8px;
        border-left: 4px solid #0284c7;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# 2. DATABASE INITIALIZATION
# -----------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect("clinic.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS patient (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_code TEXT UNIQUE,
        name TEXT NOT NULL,
        guardian_name TEXT,
        age INTEGER,
        gender TEXT,
        mobile TEXT,
        address TEXT,
        created_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS appointment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        doctor_name TEXT,
        appt_date TEXT NOT NULL,
        appt_time TEXT,
        status TEXT DEFAULT 'Booked',
        FOREIGN KEY(patient_id) REFERENCES patient(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS consultation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        visit_date TEXT,
        symptoms TEXT,
        diagnosis TEXT,
        prescription TEXT,
        next_visit TEXT,
        FOREIGN KEY(patient_id) REFERENCES patient(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS fee (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        consultation_fee REAL DEFAULT 0,
        medicine_fee REAL DEFAULT 0,
        discount REAL DEFAULT 0,
        total REAL DEFAULT 0,
        payment_mode TEXT,
        paid_on TEXT,
        FOREIGN KEY(patient_id) REFERENCES patient(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS medicine (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        stock INTEGER DEFAULT 0,
        low_stock_alert INTEGER DEFAULT 10,
        unit_price REAL DEFAULT 0
    )""")

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
        created_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER,
        att_date TEXT NOT NULL,
        status TEXT DEFAULT 'Present',
        FOREIGN KEY(staff_id) REFERENCES staff(id)
    )""")

    c.execute("SELECT * FROM user WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute(
            "INSERT INTO user (username, password_hash, role) VALUES ('admin', ?, 'admin')",
            (hashed_pw,),
        )

    conn.commit()
    conn.close()


init_db()


# -----------------------------------------------------------------------------
# 3. HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()


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


def get_patients_dropdown():
    conn = get_db()
    df = pd.read_sql("SELECT id, patient_code, name FROM patient ORDER BY name", conn)
    conn.close()
    return {row["id"]: f"{row['name']} ({row['patient_code']})" for _, row in df.iterrows()}


# -----------------------------------------------------------------------------
# 4. AUTHENTICATION (LOGIN & SIGN UP)
# -----------------------------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = None
    st.session_state["username"] = ""
    st.session_state["role"] = ""

if not st.session_state["logged_in"]:
    st.title("🏥 SN Clinic Management System")
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        auth_tab1, auth_tab2 = st.tabs(["🔐 Login", "📝 Sign Up"])

        # TAB 1: LOGIN
        with auth_tab1:
            st.subheader("Login to System")
            user_input = st.text_input("Username", key="login_user")
            pass_input = st.text_input("Password", type="password", key="login_pass")

            if st.button("Login", use_container_width=True, key="login_btn"):
                conn = get_db()
                user = conn.execute(
                    "SELECT * FROM user WHERE username=? AND password_hash=?",
                    (user_input.strip(), hash_pass(pass_input)),
                ).fetchone()
                conn.close()

                if user:
                    st.session_state["logged_in"] = True
                    st.session_state["user_id"] = user["id"]
                    st.session_state["username"] = user["username"]
                    st.session_state["role"] = user["role"]
                    st.success("Login Successful!")
                    st.rerun()
                else:
                    st.error("Invalid Username or Password")

        # TAB 2: SIGN UP
        with auth_tab2:
            st.subheader("Create New Account")
            signup_user = st.text_input("Choose Username *", key="su_user").strip()
            signup_pass = st.text_input("Choose Password *", type="password", key="su_pass")
            signup_conf = st.text_input("Confirm Password *", type="password", key="su_conf")
            signup_role = st.selectbox("Role", ["receptionist", "doctor"], key="su_role")

            if st.button("Sign Up", use_container_width=True, key="signup_btn"):
                if not signup_user or not signup_pass:
                    st.error("Username and password are required!")
                elif signup_pass != signup_conf:
                    st.error("Passwords do not match!")
                else:
                    conn = get_db()
                    try:
                        conn.execute(
                            "INSERT INTO user (username, password_hash, role) VALUES (?, ?, ?)",
                            (signup_user, hash_pass(signup_pass), signup_role),
                        )
                        conn.commit()
                        st.success(f"Account for '{signup_user}' created successfully! You can now login.")
                    except sqlite3.IntegrityError:
                        st.error("That username is already taken. Please choose another.")
                    finally:
                        conn.close()

    st.stop()


# -----------------------------------------------------------------------------
# 5. SIDEBAR NAVIGATION
# -----------------------------------------------------------------------------
st.sidebar.title("🏥 SN Clinic")
st.sidebar.write(f"Logged in: **{st.session_state['username']}** (`{st.session_state['role']}`)")

menu = [
    "Dashboard",
    "Patients",
    "Appointments",
    "Follow-ups",
    "Fees & Billing",
    "Medicines Inventory",
    "Staff Directory",
    "Daily Attendance",
    "Reports & Analytics",
    "Users Management",
]

choice = st.sidebar.radio("Navigation", menu)

st.sidebar.markdown("---")
if st.sidebar.button("🔴 Logout", use_container_width=True):
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.session_state["role"] = ""
    st.rerun()

conn = get_db()
today_str = date.today().isoformat()

# -----------------------------------------------------------------------------
# MODULE 1: DASHBOARD
# -----------------------------------------------------------------------------
if choice == "Dashboard":
    st.title("📊 Clinic Overview Dashboard")

    total_patients = conn.execute("SELECT COUNT(*) FROM patient").fetchone()[0]
    new_today = conn.execute(
        "SELECT COUNT(*) FROM patient WHERE DATE(created_at) = ?", (today_str,)
    ).fetchone()[0]
    appts_today = conn.execute(
        "SELECT COUNT(*) FROM appointment WHERE appt_date = ?", (today_str,)
    ).fetchone()[0]
    fees_today = (
        conn.execute(
            "SELECT SUM(total) FROM fee WHERE DATE(paid_on) = ?", (today_str,)
        ).fetchone()[0]
        or 0
    )
    low_stock = conn.execute(
        "SELECT COUNT(*) FROM medicine WHERE stock <= low_stock_alert"
    ).fetchone()[0]
    followups_due = conn.execute(
        "SELECT COUNT(*) FROM consultation WHERE next_visit IS NOT NULL AND next_visit <= ?",
        (today_str,),
    ).fetchone()[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Patients", total_patients, f"+{new_today} Today")
    c2.metric("Today's Appointments", appts_today)
    c3.metric("Today's Collection", f"₹{fees_today:,.2f}")

    c4, c5, c6 = st.columns(3)
    c4.metric("Low Stock Alert", low_stock)
    c5.metric("Follow-ups Due", followups_due)

    st.markdown("---")
    st.subheader("📋 Today's Appointments")
    appts_df = pd.read_sql(
        """SELECT a.id, p.patient_code, p.name as patient_name, a.doctor_name, a.appt_time, a.status 
           FROM appointment a LEFT JOIN patient p ON a.patient_id = p.id 
           WHERE a.appt_date = ? ORDER BY a.id DESC""",
        conn,
        params=[today_str],
    )
    if not appts_df.empty:
        st.dataframe(appts_df, use_container_width=True)
    else:
        st.info("No appointments scheduled for today.")

# -----------------------------------------------------------------------------
# MODULE 2: PATIENTS
# -----------------------------------------------------------------------------
elif choice == "Patients":
    st.title("👨‍👩‍👧‍👦 Patient Management")

    t1, t2 = st.tabs(["📋 Patients List", "➕ Register New Patient"])

    with t1:
        q = st.text_input("🔍 Search Patient by Name, Mobile or Code", "")
        query = "SELECT * FROM patient"
        params = []
        if q:
            query += " WHERE name LIKE ? OR mobile LIKE ? OR patient_code LIKE ?"
            params = [f"%{q}%", f"%{q}%", f"%{q}%"]
        query += " ORDER BY id DESC"

        df = pd.read_sql(query, conn, params=params)
        st.dataframe(df, use_container_width=True)

        st.markdown("---")
        st.subheader("📄 Patient Detail View")
        patient_map = get_patients_dropdown()
        if patient_map:
            selected_pid = st.selectbox("Select Patient to view history", options=list(patient_map.keys()), format_func=lambda x: patient_map[x])
            p = conn.execute("SELECT * FROM patient WHERE id=?", (selected_pid,)).fetchone()

            if p:
                st.write(f"**Code:** {p['patient_code']} | **Guardian:** {p['guardian_name'] or '-'} | **Age/Gender:** {p['age'] or '-'} / {p['gender']} | **Mobile:** {p['mobile']} | **Address:** {p['address']}")

                pt1, pt2, pt3 = st.tabs(["🩺 Consultations History", "💳 Fee History", "➕ Add Consultation"])
                with pt1:
                    c_df = pd.read_sql("SELECT visit_date, symptoms, diagnosis, prescription, next_visit FROM consultation WHERE patient_id=? ORDER BY id DESC", conn, params=[selected_pid])
                    st.dataframe(c_df, use_container_width=True)
                with pt2:
                    f_df = pd.read_sql("SELECT paid_on, consultation_fee, medicine_fee, discount, total, payment_mode FROM fee WHERE patient_id=? ORDER BY id DESC", conn, params=[selected_pid])
                    st.dataframe(f_df, use_container_width=True)
                with pt3:
                    with st.form("add_c_form"):
                        sym = st.text_area("Symptoms")
                        diag = st.text_area("Diagnosis")
                        pres = st.text_area("Prescription")
                        next_v = st.date_input("Next Visit Date", value=None)
                        if st.form_submit_button("Save Consultation"):
                            v_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            nv_str = str(next_v) if next_v else None
                            conn.execute(
                                "INSERT INTO consultation (patient_id, visit_date, symptoms, diagnosis, prescription, next_visit) VALUES (?, ?, ?, ?, ?, ?)",
                                (selected_pid, v_date, sym, diag, pres, nv_str),
                            )
                            conn.commit()
                            st.success("Consultation saved!")
                            st.rerun()

    with t2:
        with st.form("add_p_form"):
            st.write(f"**New Patient Code:** `{next_patient_code()}`")
            name = st.text_input("Full Name *")
            g_name = st.text_input("Guardian Name")
            col1, col2 = st.columns(2)
            age = col1.number_input("Age", min_value=0, max_value=120, value=0)
            gender = col2.selectbox("Gender", ["Male", "Female", "Other"])
            mobile = st.text_input("Mobile Number")
            address = st.text_area("Address")

            if st.form_submit_button("Register Patient"):
                if name.strip():
                    pcode = next_patient_code()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    conn.execute(
                        "INSERT INTO patient (patient_code, name, guardian_name, age, gender, mobile, address, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (pcode, name, g_name, age if age > 0 else None, gender, mobile, address, now),
                    )
                    conn.commit()
                    st.success(f"Patient registered with ID {pcode}")
                    st.rerun()
                else:
                    st.error("Patient Name is required!")

# -----------------------------------------------------------------------------
# MODULE 3: APPOINTMENTS
# -----------------------------------------------------------------------------
elif choice == "Appointments":
    st.title("📅 Appointments Management")

    t1, t2 = st.tabs(["📋 All Appointments", "➕ Book Appointment"])

    with t1:
        appts_df = pd.read_sql(
            """SELECT a.id, p.patient_code, p.name as patient_name, a.doctor_name, a.appt_date, a.appt_time, a.status 
               FROM appointment a LEFT JOIN patient p ON a.patient_id = p.id ORDER BY a.appt_date DESC, a.id DESC""",
            conn,
        )
        st.dataframe(appts_df, use_container_width=True)

        if not appts_df.empty:
            st.markdown("---")
            st.subheader("⚡ Quick Actions")
            col_a, col_b = st.columns(2)
            aid = col_a.selectbox("Select Appointment ID", options=appts_df["id"].tolist())
            new_status = col_b.selectbox("Change Status", ["Booked", "Completed", "Cancelled"])
            if st.button("Update Status"):
                conn.execute("UPDATE appointment SET status=? WHERE id=?", (new_status, aid))
                conn.commit()
                st.success(f"Appointment #{aid} status updated to {new_status}")
                st.rerun()

    with t2:
        patients_map = get_patients_dropdown()
        if patients_map:
            with st.form("book_appt"):
                pid = st.selectbox("Select Patient", options=list(patients_map.keys()), format_func=lambda x: patients_map[x])
                doc = st.text_input("Doctor Name", "Dr. Sharma")
                col1, col2 = st.columns(2)
                adate = col1.date_input("Appointment Date", date.today())
                atime = col2.time_input("Appointment Time")

                if st.form_submit_button("Book Appointment"):
                    conn.execute(
                        "INSERT INTO appointment (patient_id, doctor_name, appt_date, appt_time, status) VALUES (?, ?, ?, ?, 'Booked')",
                        (pid, doc, str(adate), str(atime)),
                    )
                    conn.commit()
                    st.success("Appointment booked successfully!")
                    st.rerun()
        else:
            st.warning("Please register a patient first.")

# -----------------------------------------------------------------------------
# MODULE 4: FOLLOW-UPS
# -----------------------------------------------------------------------------
elif choice == "Follow-ups":
    st.title("🔄 Patient Follow-ups Tracking")

    today = date.today()
    horizon = today + timedelta(days=7)

    consults = conn.execute(
        "SELECT c.*, p.name, p.mobile, p.patient_code FROM consultation c JOIN patient p ON c.patient_id=p.id WHERE c.next_visit IS NOT NULL ORDER BY c.visit_date DESC"
    ).fetchall()

    latest_per_patient = {}
    for c in consults:
        if c["patient_id"] not in latest_per_patient:
            latest_per_patient[c["patient_id"]] = c

    overdue = []
    due_soon = []
    for c in latest_per_patient.values():
        nv = datetime.strptime(c["next_visit"], "%Y-%m-%d").date()
        if nv < today:
            overdue.append(c)
        elif nv <= horizon:
            due_soon.append(c)

    st.subheader("⚠️ Overdue Follow-ups")
    if overdue:
        o_df = pd.DataFrame([{
            "Patient Code": x["patient_code"],
            "Name": x["name"],
            "Mobile": x["mobile"],
            "Next Visit": x["next_visit"],
            "Diagnosis": x["diagnosis"],
        } for x in overdue])
        st.dataframe(o_df, use_container_width=True)
    else:
        st.success("No overdue follow-ups!")

    st.subheader("📅 Due Soon (Next 7 Days)")
    if due_soon:
        s_df = pd.DataFrame([{
            "Patient Code": x["patient_code"],
            "Name": x["name"],
            "Mobile": x["mobile"],
            "Next Visit": x["next_visit"],
            "Diagnosis": x["diagnosis"],
        } for x in due_soon])
        st.dataframe(s_df, use_container_width=True)
    else:
        st.info("No follow-ups due in the next 7 days.")

# -----------------------------------------------------------------------------
# MODULE 5: FEES & BILLING
# -----------------------------------------------------------------------------
elif choice == "Fees & Billing":
    st.title("💳 Fees & Billing Collection")

    t1, t2 = st.tabs(["📜 Collection Records", "🧾 Add Fee / Invoice"])

    with t1:
        fees_df = pd.read_sql(
            """SELECT f.id, f.paid_on, p.patient_code, p.name as patient_name, f.consultation_fee, f.medicine_fee, f.discount, f.total, f.payment_mode 
               FROM fee f LEFT JOIN patient p ON f.patient_id = p.id ORDER BY f.id DESC""",
            conn,
        )
        st.dataframe(fees_df, use_container_width=True)

    with t2:
        patients_map = get_patients_dropdown()
        if patients_map:
            with st.form("add_fee_form"):
                pid = st.selectbox("Select Patient", options=list(patients_map.keys()), format_func=lambda x: patients_map[x])
                col1, col2, col3 = st.columns(3)
                cf = col1.number_input("Consultation Fee (₹)", min_value=0.0, value=0.0)
                mf = col2.number_input("Medicine Fee (₹)", min_value=0.0, value=0.0)
                disc = col3.number_input("Discount (₹)", min_value=0.0, value=0.0)
                pay_mode = st.selectbox("Payment Mode", ["Cash", "UPI", "Card", "Net Banking"])

                if st.form_submit_button("Record Payment"):
                    net_total = (cf + mf) - disc
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    conn.execute(
                        "INSERT INTO fee (patient_id, consultation_fee, medicine_fee, discount, total, payment_mode, paid_on) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (pid, cf, mf, disc, net_total, pay_mode, now),
                    )
                    conn.commit()
                    st.success(f"Fee of ₹{net_total} collected successfully!")
                    st.rerun()

# -----------------------------------------------------------------------------
# MODULE 6: MEDICINES INVENTORY
# -----------------------------------------------------------------------------
elif choice == "Medicines Inventory":
    st.title("💊 Medicines Inventory Management")

    t1, t2 = st.tabs(["📦 Stock List", "➕ Add New Medicine"])

    with t1:
        meds_df = pd.read_sql("SELECT * FROM medicine ORDER BY name", conn)
        st.dataframe(meds_df, use_container_width=True)

    with t2:
        with st.form("add_med"):
            name = st.text_input("Medicine Name *")
            col1, col2, col3 = st.columns(3)
            stock = col1.number_input("Initial Stock", min_value=0, value=0)
            low_alert = col2.number_input("Low Stock Alert", min_value=1, value=10)
            price = col3.number_input("Unit Price (₹)", min_value=0.0, value=0.0)

            if st.form_submit_button("Save Medicine"):
                if name.strip():
                    conn.execute(
                        "INSERT INTO medicine (name, stock, low_stock_alert, unit_price) VALUES (?, ?, ?, ?)",
                        (name, stock, low_alert, price),
                    )
                    conn.commit()
                    st.success(f"Medicine '{name}' added!")
                    st.rerun()

# -----------------------------------------------------------------------------
# MODULE 7: STAFF DIRECTORY
# -----------------------------------------------------------------------------
elif choice == "Staff Directory":
    st.title("👨‍⚕️ Staff & Employee Management")

    t1, t2 = st.tabs(["👥 Staff Directory", "➕ Add Staff Member"])

    with t1:
        staff_df = pd.read_sql("SELECT * FROM staff ORDER BY id DESC", conn)
        st.dataframe(staff_df, use_container_width=True)

    with t2:
        with st.form("add_staff_form"):
            st.write(f"**Employee Code:** `{next_employee_code()}`")
            sname = st.text_input("Full Name *")
            desig = st.text_input("Designation")
            col1, col2 = st.columns(2)
            mobile = col1.text_input("Mobile")
            city = col2.text_input("City")
            address = st.text_area("Address")
            col3, col4 = st.columns(2)
            jdate = col3.date_input("Joining Date", date.today())
            salary = col4.number_input("Salary (₹)", min_value=0.0, value=0.0)
            status = st.selectbox("Status", ["Active", "Inactive"])

            if st.form_submit_button("Register Staff"):
                if sname.strip():
                    ecode = next_employee_code()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    conn.execute(
                        "INSERT INTO staff (employee_code, name, designation, mobile, city, address, joining_date, salary, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (ecode, sname, desig, mobile, city, address, str(jdate), salary, status, now),
                    )
                    conn.commit()
                    st.success(f"Staff '{sname}' added with ID {ecode}")
                    st.rerun()

# -----------------------------------------------------------------------------
# MODULE 8: DAILY ATTENDANCE
# -----------------------------------------------------------------------------
elif choice == "Daily Attendance":
    st.title("📅 Daily Staff Attendance & Monthly Summary")

    t1, t2 = st.tabs(["✍️ Mark Daily Attendance", "📊 Monthly Attendance Report"])

    with t1:
        att_date = st.date_input("Select Attendance Date", date.today())
        active_staff = conn.execute("SELECT * FROM staff WHERE status='Active' ORDER BY name").fetchall()

        if active_staff:
            existing_marks = {
                a["staff_id"]: a["status"]
                for a in conn.execute("SELECT * FROM attendance WHERE att_date=?", (str(att_date),)).fetchall()
            }

            with st.form("mark_att"):
                st.write(f"Marking attendance for: **{att_date.strftime('%d-%b-%Y')}**")
                marks = {}
                for s in active_staff:
                    default_idx = ["Present", "Absent", "Half Day", "Leave"].index(existing_marks.get(s["id"], "Present"))
                    marks[s["id"]] = st.selectbox(
                        f"{s['employee_code']} - {s['name']} ({s['designation'] or '-'})",
                        ["Present", "Absent", "Half Day", "Leave"],
                        index=default_idx,
                        key=f"att_{s['id']}",
                    )

                if st.form_submit_button("Save Attendance"):
                    for sid, status in marks.items():
                        conn.execute("DELETE FROM attendance WHERE staff_id=? AND att_date=?", (sid, str(att_date)))
                        conn.execute("INSERT INTO attendance (staff_id, att_date, status) VALUES (?, ?, ?)", (sid, str(att_date), status))
                    conn.commit()
                    st.success("Attendance saved successfully!")
                    st.rerun()

    with t2:
        col1, col2 = st.columns(2)
        year = col1.number_input("Year", min_value=2020, max_value=2030, value=date.today().year)
        month = col2.number_input("Month (1-12)", min_value=1, max_value=12, value=date.today().month)

        start = f"{year}-{month:02d}-01"
        last_day = calendar.monthrange(year, month)[1]
        end = f"{year}-{month:02d}-{last_day:02d}"

        att_records = pd.read_sql(
            """SELECT s.employee_code, s.name, a.status, COUNT(*) as count 
               FROM attendance a JOIN staff s ON a.staff_id=s.id 
               WHERE a.att_date >= ? AND a.att_date <= ? 
               GROUP BY s.id, a.status""",
            conn,
            params=[start, end],
        )

        if not att_records.empty:
            pivot_df = att_records.pivot(index=["employee_code", "name"], columns="status", values="count").fillna(0)
            st.dataframe(pivot_df, use_container_width=True)
        else:
            st.info("No attendance records found for selected month.")

# -----------------------------------------------------------------------------
# MODULE 9: REPORTS & ANALYTICS
# -----------------------------------------------------------------------------
elif choice == "Reports & Analytics":
    st.title("📈 Reports & Export Center")

    st.subheader("🗓️ Date Filtered Fee Collection")
    col1, col2 = st.columns(2)
    start_d = col1.date_input("Start Date", value=None)
    end_d = col2.date_input("End Date", value=None)

    fee_query = "SELECT f.paid_on, p.name as patient_name, p.patient_code, f.consultation_fee, f.medicine_fee, f.discount, f.total, f.payment_mode FROM fee f LEFT JOIN patient p ON f.patient_id=p.id"
    params = []
    if start_d or end_d:
        fee_query += " WHERE 1=1"
        if start_d:
            fee_query += " AND DATE(f.paid_on) >= ?"
            params.append(str(start_d))
        if end_d:
            fee_query += " AND DATE(f.paid_on) <= ?"
            params.append(str(end_d))

    fees_data = pd.read_sql(fee_query, conn, params=params)
    st.dataframe(fees_data, use_container_width=True)

    col_e1, col_e2 = st.columns(2)

    # CSV Fee Export
    if not fees_data.empty:
        csv_buffer = fees_data.to_csv(index=False).encode('utf-8')
        col_e1.download_button("📥 Export Fees (CSV)", data=csv_buffer, file_name="fee_report.csv", mime="text/csv")

    # CSV Patients Export
    p_all = pd.read_sql("SELECT * FROM patient", conn)
    if not p_all.empty:
        p_csv_buffer = p_all.to_csv(index=False).encode('utf-8')
        col_e2.download_button("👥 Export All Patients (CSV)", data=p_csv_buffer, file_name="patient_list.csv", mime="text/csv")

# -----------------------------------------------------------------------------
# MODULE 10: USERS MANAGEMENT
# -----------------------------------------------------------------------------
elif choice == "Users Management":
    st.title("⚙️ User Access Control")

    if st.session_state["role"] != "admin":
        st.error("🔒 Only Admin can access User Management.")
    else:
        t1, t2 = st.tabs(["👥 System Users", "➕ Add System User"])

        with t1:
            users_df = pd.read_sql("SELECT id, username, role FROM user", conn)
            st.dataframe(users_df, use_container_width=True)

            st.markdown("---")
            st.subheader("🗑️ Delete User")
            uid_del = st.selectbox("Select User ID to Delete", options=[u for u in users_df["id"].tolist() if u != st.session_state["user_id"]])
            if st.button("Delete Selected User"):
                target = conn.execute("SELECT username FROM user WHERE id=?", (uid_del,)).fetchone()
                if target and target["username"] == "admin":
                    st.error("Default admin account cannot be deleted.")
                else:
                    conn.execute("DELETE FROM user WHERE id=?", (uid_del,))
                    conn.commit()
                    st.success("User deleted!")
                    st.rerun()

        with t2:
            with st.form("add_user_form"):
                new_u = st.text_input("Username *").strip()
                new_p = st.text_input("Password *", type="password")
                conf_p = st.text_input("Confirm Password *", type="password")
                role = st.selectbox("Role", ["receptionist", "doctor", "admin"])

                if st.form_submit_button("Create User"):
                    if not new_u or not new_p:
                        st.error("Username and password are required!")
                    elif new_p != conf_p:
                        st.error("Passwords do not match!")
                    else:
                        try:
                            conn.execute(
                                "INSERT INTO user (username, password_hash, role) VALUES (?, ?, ?)",
                                (new_u, hash_pass(new_p), role),
                            )
                            conn.commit()
                            st.success(f"User '{new_u}' ({role}) created successfully!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Username already taken.")

conn.close()
