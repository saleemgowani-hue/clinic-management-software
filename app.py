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
# 2. DATABASE INITIALIZATION & MIGRATIONS
# -----------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect("clinic.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS center (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        center_code TEXT UNIQUE,
        name TEXT NOT NULL,
        city TEXT,
        address TEXT,
        created_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL,
        center_id INTEGER
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
        center_id INTEGER,
        created_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS appointment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER,
        doctor_name TEXT,
        appt_date TEXT NOT NULL,
        appt_time TEXT,
        status TEXT DEFAULT 'Booked',
        center_id INTEGER,
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
        center_id INTEGER,
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
        center_id INTEGER,
        created_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER,
        att_date TEXT NOT NULL,
        status TEXT DEFAULT 'Present',
        FOREIGN KEY(staff_id) REFERENCES staff(id)
    )""")

    # SAFE MIGRATIONS FOR EXISTING DATABASES
    migrations = [
        "ALTER TABLE patient ADD COLUMN center_id INTEGER",
        "ALTER TABLE staff ADD COLUMN status TEXT DEFAULT 'Active'",
        "ALTER TABLE staff ADD COLUMN center_id INTEGER",
        "ALTER TABLE user ADD COLUMN center_id INTEGER",
        "ALTER TABLE fee ADD COLUMN center_id INTEGER",
        "ALTER TABLE appointment ADD COLUMN center_id INTEGER"
    ]

    for mig in migrations:
        try:
            c.execute(mig)
        except sqlite3.OperationalError:
            pass

    # Default Main Center
    c.execute("SELECT * FROM center WHERE center_code='CTR001'")
    if not c.fetchone():
        c.execute(
            "INSERT INTO center (center_code, name, city, address, created_at) VALUES ('CTR001', 'Main Branch', 'Raipur', 'Central Office', ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),)
        )

    # Default Admin User
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


def next_center_code():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM center").fetchone()[0] + 1
    conn.close()
    return f"CTR{count:03d}"


def get_patients_dropdown():
    conn = get_db()
    try:
        df = pd.read_sql("SELECT id, patient_code, name FROM patient ORDER BY name", conn)
        conn.close()
        return {row["id"]: f"{row['name']} ({row['patient_code']})" for _, row in df.iterrows()}
    except Exception:
        conn.close()
        return {}


def get_centers_dropdown():
    conn = get_db()
    try:
        df = pd.read_sql("SELECT id, center_code, name, city FROM center ORDER BY city, name", conn)
        conn.close()
        return {row["id"]: f"{row['name']} - {row['city']} ({row['center_code']})" for _, row in df.iterrows()}
    except Exception:
        conn.close()
        return {}


def get_unique_cities():
    conn = get_db()
    try:
        cities = [r[0] for r in conn.execute("SELECT DISTINCT city FROM center WHERE city IS NOT NULL AND city != '' ORDER BY city").fetchall()]
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


# -----------------------------------------------------------------------------
# 4. AUTHENTICATION (LOGIN & SIGN UP)
# -----------------------------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = None
    st.session_state["username"] = ""
    st.session_state["role"] = ""
    st.session_state["center_id"] = None

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
                    st.session_state["center_id"] = user["center_id"] if "center_id" in user.keys() else None
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
            signup_role = st.selectbox("Role", ["receptionist", "doctor", "admin"], key="su_role")
            centers_map = get_centers_dropdown()
            signup_center = st.selectbox("Select Center/Branch", options=list(centers_map.keys()), format_func=lambda x: centers_map[x], key="su_center") if centers_map else None

            if st.button("Sign Up", use_container_width=True, key="signup_btn"):
                if not signup_user or not signup_pass:
                    st.error("Username and password are required!")
                elif signup_pass != signup_conf:
                    st.error("Passwords do not match!")
                else:
                    conn = get_db()
                    try:
                        conn.execute(
                            "INSERT INTO user (username, password_hash, role, center_id) VALUES (?, ?, ?, ?)",
                            (signup_user, hash_pass(signup_pass), signup_role, signup_center),
                        )
                        conn.commit()
                        st.success(f"Account for '{signup_user}' created successfully! You can now login.")
                    except sqlite3.IntegrityError:
                        st.error("That username is already taken. Please choose another.")
                    finally:
                        conn.close()

    st.stop()


# -----------------------------------------------------------------------------
# 5. SIDEBAR NAVIGATION & CITY FILTER
# -----------------------------------------------------------------------------
st.sidebar.title("🏥 SN Clinic")
st.sidebar.write(f"Logged in: **{st.session_state['username']}** (`{st.session_state['role']}`)")

# GLOBAL CITY FILTER ONLY FOR ADMIN
selected_city = "All Cities"
if st.session_state["role"] == "admin":
    all_cities = get_unique_cities()
    selected_city = st.sidebar.selectbox("🌆 Filter by City / Branch", options=all_cities)
    st.sidebar.markdown("---")
else:
    selected_city = get_user_city(st.session_state["center_id"])

menu = [
    "Dashboard",
    "Patients",
    "Appointments",
    "Follow-ups",
    "Fees & Billing",
    "Medicines Inventory",
    "Staff Directory",
    "Daily Attendance",
    "Center Management",
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
    st.title(f"📊 Clinic Overview Dashboard {f'({selected_city})' if selected_city != 'All Cities' else ''}")

    try:
        if selected_city == "All Cities":
            total_patients = conn.execute("SELECT COUNT(*) FROM patient").fetchone()[0]
            new_today = conn.execute("SELECT COUNT(*) FROM patient WHERE DATE(created_at) = ?", (today_str,)).fetchone()[0]
            appts_today = conn.execute("SELECT COUNT(*) FROM appointment WHERE appt_date = ?", (today_str,)).fetchone()[0]
            fees_today = conn.execute("SELECT SUM(total) FROM fee WHERE DATE(paid_on) = ?", (today_str,)).fetchone()[0] or 0
        else:
            total_patients = conn.execute("SELECT COUNT(*) FROM patient p JOIN center c ON p.center_id=c.id WHERE c.city=?", (selected_city,)).fetchone()[0]
            new_today = conn.execute("SELECT COUNT(*) FROM patient p JOIN center c ON p.center_id=c.id WHERE DATE(p.created_at) = ? AND c.city=?", (today_str, selected_city)).fetchone()[0]
            appts_today = conn.execute("SELECT COUNT(*) FROM appointment a JOIN patient p ON a.patient_id=p.id JOIN center c ON p.center_id=c.id WHERE a.appt_date = ? AND c.city=?", (today_str, selected_city)).fetchone()[0]
            fees_today = conn.execute("SELECT SUM(f.total) FROM fee f JOIN patient p ON f.patient_id=p.id JOIN center c ON p.center_id=c.id WHERE DATE(f.paid_on) = ? AND c.city=?", (today_str, selected_city)).fetchone()[0] or 0
    except Exception:
        total_patients, new_today, appts_today, fees_today = 0, 0, 0, 0.0

    low_stock = conn.execute("SELECT COUNT(*) FROM medicine WHERE stock <= low_stock_alert").fetchone()[0]
    followups_due = conn.execute("SELECT COUNT(*) FROM consultation WHERE next_visit IS NOT NULL AND next_visit <= ?", (today_str,)).fetchone()[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Patients", total_patients, f"+{new_today} Today")
    c2.metric("Today's Appointments", appts_today)
    c3.metric("Today's Collection", f"₹{fees_today:,.2f}")

    c4, c5, c6 = st.columns(3)
    c4.metric("Low Stock Alert", low_stock)
    c5.metric("Follow-ups Due", followups_due)

    st.markdown("---")
    st.subheader("📋 Today's Appointments")
    
    try:
        appt_query = """SELECT a.id, p.patient_code, p.name as patient_name, c.city, c.name as center_name, a.doctor_name, a.appt_time, a.status 
                       FROM appointment a 
                       LEFT JOIN patient p ON a.patient_id = p.id 
                       LEFT JOIN center c ON p.center_id = c.id 
                       WHERE a.appt_date = ?"""
        params = [today_str]
        if selected_city != "All Cities":
            appt_query += " AND c.city = ?"
            params.append(selected_city)
        appt_query += " ORDER BY a.id DESC"

        appts_df = pd.read_sql(appt_query, conn, params=params)
        if not appts_df.empty:
            st.dataframe(appts_df, use_container_width=True)
        else:
            st.info("No appointments scheduled for today.")
    except Exception:
        st.info("No appointments found.")

# -----------------------------------------------------------------------------
# MODULE 2: PATIENTS
# -----------------------------------------------------------------------------
elif choice == "Patients":
    st.title("👨‍👩‍👧‍👦 Patient Management")

    t1, t2 = st.tabs(["📋 Patients List", "➕ Register New Patient"])

    with t1:
        q = st.text_input("🔍 Search Patient by Name, Mobile or Code", "")
        try:
            query = """SELECT p.id, p.patient_code, p.name, p.guardian_name, p.age, p.gender, p.mobile, p.address, c.name as center_name, c.city 
                       FROM patient p LEFT JOIN center c ON p.center_id=c.id WHERE 1=1"""
            params = []

            if selected_city != "All Cities":
                query += " AND c.city = ?"
                params.append(selected_city)

            if q:
                query += " AND (p.name LIKE ? OR p.mobile LIKE ? OR p.patient_code LIKE ?)"
                params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

            query += " ORDER BY p.id DESC"

            df = pd.read_sql(query, conn, params=params)
            st.dataframe(df, use_container_width=True)
        except Exception:
            st.error("Error reading patient records.")

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
        centers_map = get_centers_dropdown()
        with st.form("add_p_form"):
            st.write(f"**New Patient Code:** `{next_patient_code()}`")
            name = st.text_input("Full Name *")
            g_name = st.text_input("Guardian Name")
            col1, col2 = st.columns(2)
            age = col1.number_input("Age", min_value=0, max_value=120, value=0)
            gender = col2.selectbox("Gender", ["Male", "Female", "Other"])
            mobile = st.text_input("Mobile Number")
            address = st.text_area("Address")
            selected_ctr = st.selectbox("Assign Center / Branch", options=list(centers_map.keys()), format_func=lambda x: centers_map[x]) if centers_map else None

            if st.form_submit_button("Register Patient"):
                if name.strip():
                    pcode = next_patient_code()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    conn.execute(
                        "INSERT INTO patient (patient_code, name, guardian_name, age, gender, mobile, address, center_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (pcode, name, g_name, age if age > 0 else None, gender, mobile, address, selected_ctr, now),
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
        try:
            query = """SELECT a.id, p.patient_code, p.name as patient_name, c.name as center_name, c.city, a.doctor_name, a.appt_date, a.appt_time, a.status 
                       FROM appointment a 
                       LEFT JOIN patient p ON a.patient_id = p.id 
                       LEFT JOIN center c ON p.center_id = c.id WHERE 1=1"""
            params = []
            if selected_city != "All Cities":
                query += " AND c.city = ?"
                params.append(selected_city)
            query += " ORDER BY a.appt_date DESC, a.id DESC"

            appts_df = pd.read_sql(query, conn, params=params)
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
        except Exception:
            st.info("No appointments recorded yet.")

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

    try:
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
    except Exception:
        st.info("No follow-up records found.")

# -----------------------------------------------------------------------------
# MODULE 5: FEES & BILLING
# -----------------------------------------------------------------------------
elif choice == "Fees & Billing":
    st.title("💳 Fees & Billing Collection")

    t1, t2 = st.tabs(["📜 Collection Records", "🧾 Add Fee / Invoice"])

    with t1:
        try:
            query = """SELECT f.id, f.paid_on, p.patient_code, p.name as patient_name, c.name as center_name, c.city, f.consultation_fee, f.medicine_fee, f.discount, f.total, f.payment_mode 
                       FROM fee f 
                       LEFT JOIN patient p ON f.patient_id = p.id 
                       LEFT JOIN center c ON p.center_id = c.id WHERE 1=1"""
            params = []
            if selected_city != "All Cities":
                query += " AND c.city = ?"
                params.append(selected_city)
            query += " ORDER BY f.id DESC"

            fees_df = pd.read_sql(query, conn, params=params)
            st.dataframe(fees_df, use_container_width=True)
        except Exception:
            st.info("No billing records found.")

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
        try:
            query = """SELECT s.id, s.employee_code, s.name, s.designation, s.mobile, s.city as staff_city, c.name as center_name, c.city as center_city, s.joining_date, s.salary, s.status 
                       FROM staff s LEFT JOIN center c ON s.center_id=c.id WHERE 1=1"""
            params = []
            if selected_city != "All Cities":
                query += " AND (c.city = ? OR s.city = ?)"
                params.extend([selected_city, selected_city])
            query += " ORDER BY s.id DESC"

            staff_df = pd.read_sql(query, conn, params=params)
            st.dataframe(staff_df, use_container_width=True)
        except Exception:
            st.info("No staff records found.")

    with t2:
        centers_map = get_centers_dropdown()
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
            selected_ctr = st.selectbox("Assign Center / Branch", options=list(centers_map.keys()), format_func=lambda x: centers_map[x]) if centers_map else None

            if st.form_submit_button("Register Staff"):
                if sname.strip():
                    ecode = next_employee_code()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    conn.execute(
                        "INSERT INTO staff (employee_code, name, designation, mobile, city, address, joining_date, salary, status, center_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (ecode, sname, desig, mobile, city, address, str(jdate), salary, status, selected_ctr, now),
                    )
                    conn.commit()
                    st.success(f"Staff '{sname}' added with ID {ecode}")
                    st.rerun()

# -----------------------------------------------------------------------------
# MODULE 8: DAILY ATTENDANCE
# -----------------------------------------------------------------------------
elif choice == "Daily Attendance":
    st.title("📅 Daily Staff Attendance & Monthly Summary")

    t1, t2 = st.tabs(["✍️ Mark Daily Attendance", "📊 Attendance Report"])

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
        else:
            st.info("No active staff members found.")

    with t2:
        col1, col2 = st.columns(2)
        year = col1.number_input("Year", min_value=2020, max_value=2030, value=date.today().year)
        month = col2.number_input("Month (1-12)", min_value=1, max_value=12, value=date.today().month)

        start = f"{year}-{month:02d}-01"
        last_day = calendar.monthrange(year, month)[1]
        end = f"{year}-{month:02d}-{last_day:02d}"

        try:
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
        except Exception:
            st.info("No attendance records found.")

# -----------------------------------------------------------------------------
# MODULE 9: CENTER MANAGEMENT
# -----------------------------------------------------------------------------
elif choice == "Center Management":
    st.title("🏢 Center / Branch Management")

    if st.session_state["role"] != "admin":
        st.error("🔒 Only Admin can access Center Management.")
    else:
        t1, t2 = st.tabs(["📋 Center List", "➕ Add New Center"])

        with t1:
            centers_df = pd.read_sql("SELECT * FROM center ORDER BY id DESC", conn)
            st.dataframe(centers_df, use_container_width=True)

            if not centers_df.empty:
                st.markdown("---")
                st.subheader("🗑️ Delete Center")
                c_options = {row["id"]: f"{row['name']} ({row['center_code']}) - {row['city']}" for _, row in centers_df.iterrows()}
                cid_del = st.selectbox("Select Center to Delete", options=list(c_options.keys()), format_func=lambda x: c_options[x])

                if st.button("Delete Selected Center"):
                    conn.execute("DELETE FROM center WHERE id=?", (cid_del,))
                    conn.commit()
                    st.success("Center deleted successfully!")
                    st.rerun()

        with t2:
            with st.form("add_center_form"):
                st.write(f"**New Center Code:** `{next_center_code()}`")
                cname = st.text_input("Center Name *").strip()
                city = st.text_input("City *").strip()
                address = st.text_area("Address")

                if st.form_submit_button("Add Center"):
                    if cname and city:
                        ccode = next_center_code()
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        try:
                            conn.execute(
                                "INSERT INTO center (center_code, name, city, address, created_at) VALUES (?, ?, ?, ?, ?)",
                                (ccode, cname, city, address, now),
                            )
                            conn.commit()
                            st.success(f"Center '{cname}' in '{city}' added successfully!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Center Code already exists.")
                    else:
                        st.error("Center Name and City are required!")

# -----------------------------------------------------------------------------
# MODULE 10: REPORTS & ANALYTICS (CITY FILTER ONLY FOR ADMIN)
# -----------------------------------------------------------------------------
elif choice == "Reports & Analytics":
    st.title("📈 Reports & Analytics Center")

    all_cities_list = get_unique_cities()
    is_admin = st.session_state["role"] == "admin"

    rep_tab1, rep_tab2, rep_tab3, rep_tab4 = st.tabs([
        "👨‍👩‍👧‍👦 Day-wise Patient Report", 
        "💳 Day-wise Fee Report", 
        "📅 Daily Staff Attendance Report",
        "📊 Monthly Staff Attendance Summary"
    ])

    # 1. Day-wise Patient Report
    with rep_tab1:
        st.subheader("👨‍👩‍👧‍👦 Day-wise Patient Registration Report")
        
        if is_admin:
            c_filter_1, c_col1, c_col2 = st.columns([1.5, 1, 1])
            r1_city = c_filter_1.selectbox("🌆 Select City / Branch", options=all_cities_list, key="r1_city_select")
        else:
            c_col1, c_col2 = st.columns(2)
            r1_city = selected_city

        p_start = c_col1.date_input("Start Date", value=date.today(), key="p_start")
        p_end = c_col2.date_input("End Date", value=date.today(), key="p_end")

        try:
            p_query = """SELECT p.patient_code, p.name, p.guardian_name, p.age, p.gender, p.mobile, c.name as center_name, c.city, p.created_at 
                       FROM patient p LEFT JOIN center c ON p.center_id=c.id 
                       WHERE DATE(p.created_at) >= ? AND DATE(p.created_at) <= ?"""
            params = [str(p_start), str(p_end)]
            if r1_city != "All Cities":
                p_query += " AND c.city = ?"
                params.append(r1_city)
            p_query += " ORDER BY p.id DESC"

            p_df = pd.read_sql(p_query, conn, params=params)

            st.dataframe(p_df, use_container_width=True)
            if not p_df.empty:
                st.download_button("📥 Download Patient Report (CSV)", p_df.to_csv(index=False).encode('utf-8'), f"patient_report_{r1_city}.csv", "text/csv")
            else:
                st.info("No records found for selected criteria.")
        except Exception:
            st.info("No records found for selected period.")

    # 2. Day-wise Fee Report
    with rep_tab2:
        st.subheader("💳 Day-wise Fee Collection Report")
        
        if is_admin:
            c_filter_2, c_col1, c_col2 = st.columns([1.5, 1, 1])
            r2_city = c_filter_2.selectbox("🌆 Select City / Branch", options=all_cities_list, key="r2_city_select")
        else:
            c_col1, c_col2 = st.columns(2)
            r2_city = selected_city

        f_start = c_col1.date_input("Start Date", value=date.today(), key="f_start")
        f_end = c_col2.date_input("End Date", value=date.today(), key="f_end")

        try:
            fee_query = """SELECT f.paid_on, p.patient_code, p.name as patient_name, c.name as center_name, c.city, f.consultation_fee, f.medicine_fee, f.discount, f.total, f.payment_mode 
                           FROM fee f 
                           LEFT JOIN patient p ON f.patient_id=p.id 
                           LEFT JOIN center c ON p.center_id=c.id 
                           WHERE DATE(f.paid_on) >= ? AND DATE(f.paid_on) <= ?"""
            params = [str(f_start), str(f_end)]
            if r2_city != "All Cities":
                fee_query += " AND c.city = ?"
                params.append(r2_city)
            fee_query += " ORDER BY f.id DESC"

            fees_data = pd.read_sql(fee_query, conn, params=params)

            st.dataframe(fees_data, use_container_width=True)
            if not fees_data.empty:
                st.metric("Total Collection (Period)", f"₹{fees_data['total'].sum():,.2f}")
                st.download_button("📥 Download Fee Report (CSV)", fees_data.to_csv(index=False).encode('utf-8'), f"fee_report_{r2_city}.csv", "text/csv")
            else:
                st.info("No fee collection records found for selected criteria.")
        except Exception:
            st.info("No fee collection records found.")

    # 3. Daily Attendance Report
    with rep_tab3:
        st.subheader("📅 Daily Staff Attendance Report")
        
        if is_admin:
            c_filter_3, c_col1 = st.columns([1.5, 1])
            r3_city = c_filter_3.selectbox("🌆 Select City / Branch", options=all_cities_list, key="r3_city_select")
        else:
            c_col1 = st.container()
            r3_city = selected_city

        att_sel_date = c_col1.date_input("Select Date", value=date.today(), key="att_daily_date")

        try:
            daily_att_query = """SELECT s.employee_code, s.name, s.designation, c.name as center_name, c.city, a.status, a.att_date 
                                 FROM attendance a 
                                 JOIN staff s ON a.staff_id=s.id 
                                 LEFT JOIN center c ON s.center_id=c.id 
                                 WHERE a.att_date = ?"""
            params = [str(att_sel_date)]
            if r3_city != "All Cities":
                daily_att_query += " AND (c.city = ? OR s.city = ?)"
                params.extend([r3_city, r3_city])
            daily_att_query += " ORDER BY s.name"

            d_att_df = pd.read_sql(daily_att_query, conn, params=params)

            if not d_att_df.empty:
                st.dataframe(d_att_df, use_container_width=True)
                st.download_button("📥 Download Daily Attendance (CSV)", d_att_df.to_csv(index=False).encode('utf-8'), f"daily_attendance_{r3_city}_{att_sel_date}.csv", "text/csv")
            else:
                st.info("No attendance recorded for this date and city selection.")
        except Exception:
            st.info("No attendance recorded for this date.")

    # 4. Monthly Attendance Summary
    with rep_tab4:
        st.subheader("📊 Monthly Staff Attendance Summary")
        
        if is_admin:
            c_filter_4, col1, col2 = st.columns([1.5, 1, 1])
            r4_city = c_filter_4.selectbox("🌆 Select City / Branch", options=all_cities_list, key="r4_city_select")
        else:
            col1, col2 = st.columns(2)
            r4_city = selected_city

        m_year = col1.number_input("Select Year", min_value=2020, max_value=2030, value=date.today().year, key="m_yr")
        m_month = col2.number_input("Select Month (1-12)", min_value=1, max_value=12, value=date.today().month, key="m_mn")

        start_m = f"{m_year}-{m_month:02d}-01"
        last_d = calendar.monthrange(m_year, m_month)[1]
        end_m = f"{m_year}-{m_month:02d}-{last_d:02d}"

        try:
            m_att_query = """SELECT s.employee_code, s.name, a.status, COUNT(*) as count 
                             FROM attendance a 
                             JOIN staff s ON a.staff_id=s.id 
                             LEFT JOIN center c ON s.center_id=c.id
                             WHERE a.att_date >= ? AND a.att_date <= ?"""
            params = [start_m, end_m]
            if r4_city != "All Cities":
                m_att_query += " AND (c.city = ? OR s.city = ?)"
                params.extend([r4_city, r4_city])

            m_att_query += " GROUP BY s.id, a.status"

            m_att_records = pd.read_sql(m_att_query, conn, params=params)

            if not m_att_records.empty:
                pivot_m = m_att_records.pivot(index=["employee_code", "name"], columns="status", values="count").fillna(0)
                st.dataframe(pivot_m, use_container_width=True)
                st.download_button("📥 Download Monthly Attendance (CSV)", pivot_m.to_csv().encode('utf-8'), f"monthly_attendance_{r4_city}_{m_year}_{m_month}.csv", "text/csv")
            else:
                st.info("No monthly attendance records found for this selection.")
        except Exception:
            st.info("No monthly attendance records found.")

# -----------------------------------------------------------------------------
# MODULE 11: USERS MANAGEMENT
# -----------------------------------------------------------------------------
elif choice == "Users Management":
    st.title("⚙️ User Access Control")

    if st.session_state["role"] != "admin":
        st.error("🔒 Only Admin can access User Management.")
    else:
        t1, t2 = st.tabs(["👥 System Users", "➕ Add System User"])

        with t1:
            try:
                users_df = pd.read_sql("SELECT u.id, u.username, u.role, c.name as center_name, c.city FROM user u LEFT JOIN center c ON u.center_id=c.id", conn)
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
            except Exception:
                st.info("No user records found.")

        with t2:
            centers_map = get_centers_dropdown()
            with st.form("add_user_form"):
                new_u = st.text_input("Username *").strip()
                new_p = st.text_input("Password *", type="password")
                conf_p = st.text_input("Confirm Password *", type="password")
                role = st.selectbox("Role", ["receptionist", "doctor", "admin"])
                u_center = st.selectbox("Assign Center / Branch", options=list(centers_map.keys()), format_func=lambda x: centers_map[x]) if centers_map else None

                if st.form_submit_button("Create User"):
                    if not new_u or not new_p:
                        st.error("Username and password are required!")
                    elif new_p != conf_p:
                        st.error("Passwords do not match!")
                    else:
                        try:
                            conn.execute(
                                "INSERT INTO user (username, password_hash, role, center_id) VALUES (?, ?, ?, ?)",
                                (new_u, hash_pass(new_p), role, u_center),
                            )
                            conn.commit()
                            st.success(f"User '{new_u}' ({role}) created successfully!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Username already taken.")

conn.close()
