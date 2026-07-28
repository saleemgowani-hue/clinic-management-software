import calendar
import csv
import hashlib
import sqlite3
from datetime import date, datetime, timedelta
from io import StringIO

import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG & CUSTOM STYLING (Dark/Light Mode Compatible)
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
    /* Responsive Text Color for Dark/Light Mode Compatibility */
    div[data-testid="stMetricLabel"], 
    div[data-testid="stMetricValue"], 
    div[data-testid="stMetricDelta"],
    .stMetric label,
    p, span, h1, h2, h3, h4, h5, h6 {
        color: inherit !important;
    }

    /* Force high contrast for headers */
    h1, h2, h3, h4, h5, h6 {
        font-weight: 700 !important;
    }

    /* Metric Cards Styling */
    div[data-testid="stMetric"] {
        padding: 12px 16px !important;
        border-radius: 10px !important;
        border: 1px solid #d1d5db !important;
        border-left: 6px solid #0284c7 !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.08) !important;
    }

    div[data-testid="stForm"], div.stTextInput {
        max-width: 600px !important;
        margin: 0 auto;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# 2. DATABASE INITIALIZATION & AUTO-MIGRATIONS
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

    c.execute("PRAGMA table_info(staff)")
    staff_cols = [col[1] for col in c.fetchall()]
    if "status" not in staff_cols:
        c.execute("ALTER TABLE staff ADD COLUMN status TEXT DEFAULT 'Active'")
    if "center_id" not in staff_cols:
        c.execute("ALTER TABLE staff ADD COLUMN center_id INTEGER")
    if "created_at" not in staff_cols:
        c.execute("ALTER TABLE staff ADD COLUMN created_at TEXT")

    c.execute("PRAGMA table_info(patient)")
    patient_cols = [col[1] for col in c.fetchall()]
    if "center_id" not in patient_cols:
        c.execute("ALTER TABLE patient ADD COLUMN center_id INTEGER")
    if "created_at" not in patient_cols:
        c.execute("ALTER TABLE patient ADD COLUMN created_at TEXT")

    c.execute("PRAGMA table_info(user)")
    user_cols = [col[1] for col in c.fetchall()]
    if "center_id" not in user_cols:
        c.execute("ALTER TABLE user ADD COLUMN center_id INTEGER")

    c.execute("SELECT * FROM center WHERE center_code='CTR001'")
    if not c.fetchone():
        c.execute(
            "INSERT INTO center (center_code, name, city, address, created_at) VALUES ('CTR001', 'Main Branch', 'Raipur', 'Central Office', ?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),)
        )

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
# 4. AUTHENTICATION
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
                    st.session_state["role"] = user["role"].lower()
                    st.session_state["center_id"] = user["center_id"] if "center_id" in user.keys() else None
                    st.success("Login Successful!")
                    st.rerun()
                else:
                    st.error("Invalid Username or Password")

        with auth_tab2:
            st.subheader("Create New Account")
            signup_user = st.text_input("Choose Username *", key="su_user").strip()
            signup_pass = st.text_input("Choose Password *", type="password", key="su_pass")
            signup_conf = st.text_input("Confirm Password *", type="password", key="su_conf")
            signup_role = st.selectbox("Role", ["receptionist", "doctor", "hr", "admin"], key="su_role")
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
# 5. SIDEBAR NAVIGATION
# -----------------------------------------------------------------------------
st.sidebar.title("🏥 SN Clinic")
st.sidebar.write(f"Logged in: **{st.session_state['username']}** (`{st.session_state['role']}`)")

selected_city = "All Cities"
if st.session_state["role"] in ["admin", "hr"]:
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
    st.markdown(
        f"<h1>📊 Clinic Overview Dashboard {f'({selected_city})' if selected_city != 'All Cities' else ''}</h1>",
        unsafe_allow_html=True,
    )

    try:
        if selected_city == "All Cities":
            total_patients = conn.execute("SELECT COUNT(*) FROM patient").fetchone()[0]
            new_today = conn.execute("SELECT COUNT(*) FROM patient WHERE DATE(created_at) = ?", (today_str,)).fetchone()[0]
            appts_today = conn.execute("SELECT COUNT(*) FROM appointment WHERE appt_date = ?", (today_str,)).fetchone()[0]
            fees_today = conn.execute("SELECT SUM(total) FROM fee WHERE DATE(paid_on) = ?", (today_str,)).fetchone()[0] or 0
            followups_due = conn.execute("SELECT COUNT(*) FROM consultation WHERE next_visit IS NOT NULL AND next_visit >= ?", (today_str,)).fetchone()[0]
        else:
            total_patients = conn.execute("SELECT COUNT(*) FROM patient p JOIN center c ON p.center_id=c.id WHERE c.city=?", (selected_city,)).fetchone()[0]
            new_today = conn.execute("SELECT COUNT(*) FROM patient p JOIN center c ON p.center_id=c.id WHERE DATE(p.created_at) = ? AND c.city=?", (today_str, selected_city)).fetchone()[0]
            appts_today = conn.execute("SELECT COUNT(*) FROM appointment a JOIN patient p ON a.patient_id=p.id JOIN center c ON p.center_id=c.id WHERE a.appt_date = ? AND c.city=?", (today_str, selected_city)).fetchone()[0]
            fees_today = conn.execute("SELECT SUM(f.total) FROM fee f JOIN patient p ON f.patient_id=p.id JOIN center c ON p.center_id=c.id WHERE DATE(f.paid_on) = ? AND c.city=?", (today_str, selected_city)).fetchone()[0] or 0
            followups_due = conn.execute("SELECT COUNT(*) FROM consultation con JOIN patient p ON con.patient_id=p.id JOIN center c ON p.center_id=c.id WHERE con.next_visit IS NOT NULL AND con.next_visit >= ? AND c.city=?", (today_str, selected_city)).fetchone()[0]
    except Exception:
        total_patients, new_today, appts_today, fees_today, followups_due = 0, 0, 0, 0.0, 0

    low_stock = conn.execute("SELECT COUNT(*) FROM medicine WHERE stock <= low_stock_alert").fetchone()[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Patients", total_patients, f"+{new_today} Today")
    c2.metric("Today's Appointments", appts_today)
    c3.metric("Today's Collection", f"₹{fees_today:,.2f}")

    c4, c5, c6 = st.columns(3)
    c4.metric("Low Stock Alert", low_stock)
    c5.metric("Follow-ups Scheduled", followups_due)

    st.markdown("---")
    st.markdown("<h3>📋 Today's Appointments</h3>", unsafe_allow_html=True)
    
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

    t1, t2, t3 = st.tabs(["📋 Patients List", "➕ Register New Patient", "✏️ Edit Patient Details"])

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
            selected_pid = st.selectbox("Select Patient to view history", options=list(patient_map.keys()), format_func=lambda x: patient_map[x], key="pt_hist_sel")
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

    with t3:
        st.subheader("✏️ Edit Patient Details")
        patient_map = get_patients_dropdown()
        if patient_map:
            edit_pid = st.selectbox("Select Patient to Edit", options=list(patient_map.keys()), format_func=lambda x: patient_map[x], key="edit_pt_sel")
            p_data = conn.execute("SELECT * FROM patient WHERE id=?", (edit_pid,)).fetchone()
            centers_map = get_centers_dropdown()

            if p_data:
                with st.form("edit_p_form"):
                    e_name = st.text_input("Full Name *", value=p_data["name"])
                    e_gname = st.text_input("Guardian Name", value=p_data["guardian_name"] or "")
                    ec1, ec2 = st.columns(2)
                    e_age = ec1.number_input("Age", min_value=0, max_value=120, value=p_data["age"] or 0)
                    gender_opts = ["Male", "Female", "Other"]
                    e_gender = ec2.selectbox("Gender", gender_opts, index=gender_opts.index(p_data["gender"]) if p_data["gender"] in gender_opts else 0)
                    e_mobile = st.text_input("Mobile Number", value=p_data["mobile"] or "")
                    e_address = st.text_area("Address", value=p_data["address"] or "")
                    
                    ctr_keys = list(centers_map.keys())
                    c_idx = ctr_keys.index(p_data["center_id"]) if p_data["center_id"] in ctr_keys else 0
                    e_ctr = st.selectbox("Assign Center / Branch", options=ctr_keys, format_func=lambda x: centers_map[x], index=c_idx) if centers_map else None

                    if st.form_submit_button("Update Patient Info"):
                        conn.execute(
                            "UPDATE patient SET name=?, guardian_name=?, age=?, gender=?, mobile=?, address=?, center_id=? WHERE id=?",
                            (e_name, e_gname, e_age if e_age > 0 else None, e_gender, e_mobile, e_address, e_ctr, edit_pid),
                        )
                        conn.commit()
                        st.success("Patient details updated successfully!")
                        st.rerun()

# -----------------------------------------------------------------------------
# MODULE 3: APPOINTMENTS
# -----------------------------------------------------------------------------
elif choice == "Appointments":
    st.title("📅 Appointments Management")

    t1, t2, t3 = st.tabs(["📋 All Appointments", "➕ Book Appointment", "✏️ Edit Appointment"])

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
                st.subheader("⚡ Quick Status Update")
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
                doc = st.text_input("Doctor Name", "")
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

    with t3:
        st.subheader("✏️ Edit Appointment Details")
        all_appts = conn.execute("""SELECT a.id, a.doctor_name, a.appt_date, a.appt_time, a.status, p.name 
                                    FROM appointment a JOIN patient p ON a.patient_id=p.id ORDER BY a.id DESC""").fetchall()
        if all_appts:
            appt_dict = {a["id"]: f"ID #{a['id']} - {a['name']} ({a['appt_date']})" for a in all_appts}
            sel_aid = st.selectbox("Select Appointment to Edit", options=list(appt_dict.keys()), format_func=lambda x: appt_dict[x])
            a_data = conn.execute("SELECT * FROM appointment WHERE id=?", (sel_aid,)).fetchone()

            if a_data:
                with st.form("edit_appt_form"):
                    e_doc = st.text_input("Doctor Name", value=a_data["doctor_name"] or "")
                    ec1, ec2 = st.columns(2)
                    
                    try:
                        curr_d = datetime.strptime(a_data["appt_date"], "%Y-%m-%d").date()
                    except Exception:
                        curr_d = date.today()

                    e_date = ec1.date_input("Appointment Date", curr_d)
                    e_status = ec2.selectbox("Status", ["Booked", "Completed", "Cancelled"], index=["Booked", "Completed", "Cancelled"].index(a_data["status"]) if a_data["status"] in ["Booked", "Completed", "Cancelled"] else 0)

                    if st.form_submit_button("Update Appointment"):
                        conn.execute("UPDATE appointment SET doctor_name=?, appt_date=?, status=? WHERE id=?", (e_doc, str(e_date), e_status, sel_aid))
                        conn.commit()
                        st.success("Appointment updated successfully!")
                        st.rerun()

# -----------------------------------------------------------------------------
# MODULE 4: FOLLOW-UPS
# -----------------------------------------------------------------------------
elif choice == "Follow-ups":
    st.title("🔄 Upcoming & Due Follow-ups Tracking")

    today_date = date.today().isoformat()

    try:
        query = """SELECT c.id, c.next_visit, c.visit_date, c.symptoms, c.diagnosis, c.prescription,
                          p.patient_code, p.name as patient_name, p.mobile, ctr.name as center_name, ctr.city
                   FROM consultation c
                   JOIN patient p ON c.patient_id = p.id
                   LEFT JOIN center ctr ON p.center_id = ctr.id
                   WHERE c.next_visit IS NOT NULL AND c.next_visit >= ?"""
        
        params = [today_date]
        if selected_city != "All Cities":
            query += " AND ctr.city = ?"
            params.append(selected_city)

        query += " ORDER BY c.next_visit ASC"

        followups_df = pd.read_sql(query, conn, params=params)

        st.subheader("📅 Scheduled Follow-up Visits (Today & Future)")
        
        if not followups_df.empty:
            followups_df = followups_df[[
                "next_visit", "patient_code", "patient_name", "mobile", 
                "center_name", "city", "diagnosis", "symptoms", "prescription"
            ]]
            followups_df.rename(columns={
                "next_visit": "Scheduled Follow-up Date",
                "patient_code": "Patient Code",
                "patient_name": "Patient Name",
                "mobile": "Mobile Number",
                "center_name": "Center",
                "city": "City",
                "diagnosis": "Diagnosis",
                "symptoms": "Symptoms",
                "prescription": "Prescription"
            }, inplace=True)

            st.dataframe(followups_df, use_container_width=True)
            st.download_button(
                "📥 Download Follow-ups List (CSV)", 
                followups_df.to_csv(index=False).encode('utf-8'), 
                f"upcoming_followups_{today_date}.csv", 
                "text/csv"
            )
        else:
            st.info("No upcoming follow-ups scheduled after today.")

        st.markdown("---")
        st.subheader("⏳ Overdue Follow-ups (Past Dates)")
        
        past_query = """SELECT c.next_visit as "Scheduled Date", p.patient_code as "Patient Code", 
                               p.name as "Patient Name", p.mobile as "Mobile", c.diagnosis as "Diagnosis"
                        FROM consultation c
                        JOIN patient p ON c.patient_id = p.id
                        LEFT JOIN center ctr ON p.center_id = ctr.id
                        WHERE c.next_visit IS NOT NULL AND c.next_visit < ?"""
        past_params = [today_date]
        if selected_city != "All Cities":
            past_query += " AND ctr.city = ?"
            past_params.append(selected_city)
        past_query += " ORDER BY c.next_visit DESC"

        past_df = pd.read_sql(past_query, conn, params=past_params)
        if not past_df.empty:
            st.dataframe(past_df, use_container_width=True)
        else:
            st.success("No pending past overdue follow-ups!")

    except Exception as e:
        st.info("No follow-up records found.")

# -----------------------------------------------------------------------------
# MODULE 5: FEES & BILLING
# -----------------------------------------------------------------------------
elif choice == "Fees & Billing":
    st.title("💳 Fees & Billing Collection")

    t1, t2, t3 = st.tabs(["📜 Collection Records", "🧾 Add Fee / Invoice", "✏️ Edit / Delete Fee Record"])

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

            fee_df = pd.read_sql(query, conn, params=params)
            st.dataframe(fee_df, use_container_width=True)

            if not fee_df.empty:
                st.subheader("💰 Collection Summary")
                st.metric("Total Collection In View", f"₹{fee_df['total'].sum():,.2f}")
        except Exception:
            st.info("No billing records found.")

    with t2:
        patients_map = get_patients_dropdown()
        if patients_map:
            with st.form("add_fee_form"):
                pid = st.selectbox("Select Patient", options=list(patients_map.keys()), format_func=lambda x: patients_map[x])
                col1, col2 = st.columns(2)
                c_fee = col1.number_input("Consultation Fee (₹)", min_value=0.0, value=200.0, step=50.0)
                m_fee = col2.number_input("Medicine Fee (₹)", min_value=0.0, value=0.0, step=50.0)

                col3, col4 = st.columns(2)
                disc = col3.number_input("Discount (₹)", min_value=0.0, value=0.0, step=10.0)
                pay_mode = col4.selectbox("Payment Mode", ["Cash", "UPI / GPay", "Card", "Net Banking"])

                calc_total = max(0.0, (c_fee + m_fee) - disc)
                st.info(f"**Calculated Total:** ₹{calc_total:,.2f}")

                if st.form_submit_button("Generate Invoice & Save"):
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    conn.execute(
                        "INSERT INTO fee (patient_id, consultation_fee, medicine_fee, discount, total, payment_mode, paid_on) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (pid, c_fee, m_fee, disc, calc_total, pay_mode, now),
                    )
                    conn.commit()
                    st.success(f"Billing recorded successfully! Total: ₹{calc_total:,.2f}")
                    st.rerun()
        else:
            st.warning("Please register a patient first.")

    with t3:
        all_fees = conn.execute("""SELECT f.id, f.total, f.paid_on, p.name 
                                  FROM fee f JOIN patient p ON f.patient_id=p.id ORDER BY f.id DESC""").fetchall()
        if all_fees:
            fee_dict = {f["id"]: f"Invoice #{f['id']} - {f['name']} (₹{f['total']:.2f} on {f['paid_on']})" for f in all_fees}
            sel_fid = st.selectbox("Select Invoice Record", options=list(fee_dict.keys()), format_func=lambda x: fee_dict[x])
            f_data = conn.execute("SELECT * FROM fee WHERE id=?", (sel_fid,)).fetchone()

            if f_data:
                with st.form("edit_fee_form"):
                    ec_fee = st.number_input("Consultation Fee (₹)", min_value=0.0, value=float(f_data["consultation_fee"] or 0))
                    em_fee = st.number_input("Medicine Fee (₹)", min_value=0.0, value=float(f_data["medicine_fee"] or 0))
                    edisc = st.number_input("Discount (₹)", min_value=0.0, value=float(f_data["discount"] or 0))
                    
                    modes = ["Cash", "UPI / GPay", "Card", "Net Banking"]
                    epay_mode = st.selectbox("Payment Mode", modes, index=modes.index(f_data["payment_mode"]) if f_data["payment_mode"] in modes else 0)

                    e_total = max(0.0, (ec_fee + em_fee) - edisc)
                    st.info(f"**Updated Total:** ₹{e_total:,.2f}")

                    if st.form_submit_button("Update Fee Record"):
                        conn.execute(
                            "UPDATE fee SET consultation_fee=?, medicine_fee=?, discount=?, total=?, payment_mode=? WHERE id=?",
                            (ec_fee, em_fee, edisc, e_total, epay_mode, sel_fid),
                        )
                        conn.commit()
                        st.success("Fee record updated!")
                        st.rerun()

                if st.button("🗑️ Delete Fee Record", type="primary"):
                    conn.execute("DELETE FROM fee WHERE id=?", (sel_fid,))
                    conn.commit()
                    st.success("Record deleted.")
                    st.rerun()

# -----------------------------------------------------------------------------
# MODULE 6: MEDICINES INVENTORY
# -----------------------------------------------------------------------------
elif choice == "Medicines Inventory":
    st.title("💊 Medicines & Pharmacy Inventory")

    t1, t2, t3 = st.tabs(["📦 Stock List", "➕ Add New Medicine", "✏️ Update Stock / Price"])

    with t1:
        med_df = pd.read_sql("SELECT * FROM medicine ORDER BY name ASC", conn)
        if not med_df.empty:
            st.dataframe(med_df, use_container_width=True)

            low_stock_items = med_df[med_df["stock"] <= med_df["low_stock_alert"]]
            if not low_stock_items.empty:
                st.warning("⚠️ Low Stock Alert for the following items:")
                st.dataframe(low_stock_items[["name", "stock", "low_stock_alert"]], use_container_width=True)
        else:
            st.info("No medicines added to inventory.")

    with t2:
        with st.form("add_med_form"):
            m_name = st.text_input("Medicine Name *")
            m_stock = st.number_input("Initial Stock Quantity", min_value=0, value=50)
            m_alert = st.number_input("Low Stock Threshold Alert", min_value=1, value=10)
            m_price = st.number_input("Unit Price (₹)", min_value=0.0, value=10.0, step=1.0)

            if st.form_submit_button("Save Medicine"):
                if m_name.strip():
                    conn.execute(
                        "INSERT INTO medicine (name, stock, low_stock_alert, unit_price) VALUES (?, ?, ?, ?)",
                        (m_name.strip(), m_stock, m_alert, m_price),
                    )
                    conn.commit()
                    st.success(f"Medicine '{m_name}' added to inventory!")
                    st.rerun()
                else:
                    st.error("Medicine Name is required!")

    with t3:
        all_meds = conn.execute("SELECT * FROM medicine ORDER BY name ASC").fetchall()
        if all_meds:
            med_dict = {m["id"]: f"{m['name']} (Stock: {m['stock']})" for m in all_meds}
            sel_mid = st.selectbox("Select Medicine to Update", options=list(med_dict.keys()), format_func=lambda x: med_dict[x])
            m_data = conn.execute("SELECT * FROM medicine WHERE id=?", (sel_mid,)).fetchone()

            if m_data:
                with st.form("edit_med_form"):
                    e_mname = st.text_input("Medicine Name", value=m_data["name"])
                    e_mstock = st.number_input("Current Stock Quantity", min_value=0, value=m_data["stock"])
                    e_malert = st.number_input("Low Stock Alert Limit", min_value=1, value=m_data["low_stock_alert"])
                    e_mprice = st.number_input("Unit Price (₹)", min_value=0.0, value=float(m_data["unit_price"]))

                    if st.form_submit_button("Update Medicine Info"):
                        conn.execute(
                            "UPDATE medicine SET name=?, stock=?, low_stock_alert=?, unit_price=? WHERE id=?",
                            (e_mname, e_mstock, e_malert, e_mprice, sel_mid),
                        )
                        conn.commit()
                        st.success("Medicine updated!")
                        st.rerun()

# -----------------------------------------------------------------------------
# MODULE 7: STAFF DIRECTORY
# -----------------------------------------------------------------------------
elif choice == "Staff Directory":
    st.title("👨‍⚕️ Staff & Employee Management")

    t1, t2, t3 = st.tabs(["📋 Staff Directory", "➕ Add Staff Member", "✏️ Edit Staff Info"])

    with t1:
        query = """SELECT s.id, s.employee_code, s.name, s.designation, s.mobile, s.city, s.joining_date, s.salary, s.status, c.name as center_name 
                   FROM staff s LEFT JOIN center c ON s.center_id=c.id WHERE 1=1"""
        params = []
        if selected_city != "All Cities":
            query += " AND (c.city = ? OR s.city = ?)"
            params.extend([selected_city, selected_city])
        query += " ORDER BY s.id DESC"

        staff_df = pd.read_sql(query, conn, params=params)
        st.dataframe(staff_df, use_container_width=True)

    with t2:
        centers_map = get_centers_dropdown()
        with st.form("add_staff_form"):
            st.write(f"**New Employee Code:** `{next_employee_code()}`")
            s_name = st.text_input("Staff Full Name *")
            s_desig = st.selectbox("Designation", ["Doctor", "Nurse", "Receptionist", "Lab Technician", "Accountant", "Helper", "Other"])
            sc1, sc2 = st.columns(2)
            s_mobile = sc1.text_input("Mobile Number")
            s_city = sc2.text_input("City", value="Raipur")
            s_address = st.text_area("Address")
            
            sc3, sc4 = st.columns(2)
            s_jdate = sc3.date_input("Joining Date", date.today())
            s_salary = sc4.number_input("Monthly Salary (₹)", min_value=0.0, value=15000.0, step=1000.0)
            
            s_ctr = st.selectbox("Assigned Center / Branch", options=list(centers_map.keys()), format_func=lambda x: centers_map[x]) if centers_map else None

            if st.form_submit_button("Register Staff Member"):
                if s_name.strip():
                    ecode = next_employee_code()
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    conn.execute(
                        "INSERT INTO staff (employee_code, name, designation, mobile, city, address, joining_date, salary, status, center_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?)",
                        (ecode, s_name.strip(), s_desig, s_mobile, s_city, s_address, str(s_jdate), s_salary, s_ctr, now),
                    )
                    conn.commit()
                    st.success(f"Staff member registered with ID {ecode}")
                    st.rerun()
                else:
                    st.error("Name is required!")

    with t3:
        all_staff = conn.execute("SELECT * FROM staff ORDER BY name ASC").fetchall()
        if all_staff:
            s_dict = {s["id"]: f"{s['name']} ({s['employee_code']}) - {s['designation']}" for s in all_staff}
            sel_sid = st.selectbox("Select Staff Member to Edit", options=list(s_dict.keys()), format_func=lambda x: s_dict[x])
            s_data = conn.execute("SELECT * FROM staff WHERE id=?", (sel_sid,)).fetchone()
            centers_map = get_centers_dropdown()

            if s_data:
                with st.form("edit_staff_form"):
                    es_name = st.text_input("Full Name", value=s_data["name"])
                    desig_opts = ["Doctor", "Nurse", "Receptionist", "Lab Technician", "Accountant", "Helper", "Other"]
                    es_desig = st.selectbox("Designation", desig_opts, index=desig_opts.index(s_data["designation"]) if s_data["designation"] in desig_opts else 0)
                    
                    esc1, esc2 = st.columns(2)
                    es_mobile = esc1.text_input("Mobile Number", value=s_data["mobile"] or "")
                    es_city = esc2.text_input("City", value=s_data["city"] or "")
                    es_salary = st.number_input("Monthly Salary (₹)", min_value=0.0, value=float(s_data["salary"] or 0))
                    
                    status_opts = ["Active", "Inactive", "Resigned", "Terminated"]
                    es_status = st.selectbox("Employment Status", status_opts, index=status_opts.index(s_data["status"]) if s_data["status"] in status_opts else 0)

                    ctr_keys = list(centers_map.keys())
                    c_idx = ctr_keys.index(s_data["center_id"]) if s_data["center_id"] in ctr_keys else 0
                    es_ctr = st.selectbox("Assign Center / Branch", options=ctr_keys, format_func=lambda x: centers_map[x], index=c_idx) if centers_map else None

                    if st.form_submit_button("Update Staff Details"):
                        conn.execute(
                            "UPDATE staff SET name=?, designation=?, mobile=?, city=?, salary=?, status=?, center_id=? WHERE id=?",
                            (es_name, es_desig, es_mobile, es_city, es_salary, es_status, es_ctr, sel_sid),
                        )
                        conn.commit()
                        st.success("Staff profile updated!")
                        st.rerun()

# -----------------------------------------------------------------------------
# MODULE 8: DAILY ATTENDANCE
# -----------------------------------------------------------------------------
elif choice == "Daily Attendance":
    st.title("📅 Daily Staff Attendance Tracking")

    att_date = st.date_input("Select Attendance Date", date.today())
    att_date_str = str(att_date)

    active_staff = conn.execute("""SELECT s.id, s.employee_code, s.name, s.designation, c.name as center_name 
                                  FROM staff s LEFT JOIN center c ON s.center_id=c.id 
                                  WHERE s.status='Active' ORDER BY s.name ASC""").fetchall()

    if active_staff:
        st.subheader(f"Mark Attendance for {att_date_str}")
        
        with st.form("attendance_form"):
            attendance_records = {}
            for s in active_staff:
                existing = conn.execute("SELECT status FROM attendance WHERE staff_id=? AND att_date=?", (s["id"], att_date_str)).fetchone()
                default_status = existing["status"] if existing else "Present"
                
                c1, c2, c3 = st.columns([2, 2, 2])
                c1.write(f"**{s['name']}** ({s['employee_code']})")
                c2.write(f"{s['designation']} - {s['center_name'] or 'Main'}")
                status_val = c3.selectbox(f"Status for {s['id']}", ["Present", "Absent", "Half Day", "Leave"], index=["Present", "Absent", "Half Day", "Leave"].index(default_status), label_visibility="collapsed")
                attendance_records[s["id"]] = status_val

            if st.form_submit_button("💾 Save All Attendance Records"):
                for staff_id, status in attendance_records.items():
                    conn.execute("DELETE FROM attendance WHERE staff_id=? AND att_date=?", (staff_id, att_date_str))
                    conn.execute("INSERT INTO attendance (staff_id, att_date, status) VALUES (?, ?, ?)", (staff_id, att_date_str, status))
                conn.commit()
                st.success("Attendance updated successfully!")
                st.rerun()

        st.markdown("---")
        st.subheader("📊 Monthly Attendance Summary View")
        m_col1, m_col2 = st.columns(2)
        sel_year = m_col1.number_input("Year", min_value=2020, max_value=2030, value=date.today().year)
        sel_month = m_col2.number_input("Month", min_value=1, max_value=12, value=date.today().month)

        att_df = pd.read_sql("""SELECT a.att_date, s.employee_code, s.name, a.status 
                               FROM attendance a JOIN staff s ON a.staff_id=s.id 
                               WHERE strftime('%Y', a.att_date) = ? AND strftime('%m', a.att_date) = ?""",
                            conn, params=[str(sel_year), f"{sel_month:02d}"])
        if not att_df.empty:
            pivot_df = att_df.pivot(index=["employee_code", "name"], columns="att_date", values="status").fillna("-")
            st.dataframe(pivot_df, use_container_width=True)
        else:
            st.info("No attendance data found for the selected month.")
    else:
        st.warning("No active staff found. Please add staff members first.")

# -----------------------------------------------------------------------------
# MODULE 9: CENTER MANAGEMENT
# -----------------------------------------------------------------------------
elif choice == "Center Management":
    st.title("🏢 Clinic Center & Branch Management")

    if st.session_state["role"] not in ["admin", "hr"]:
        st.error("Access Restricted: Only Admin and HR personnel can manage centers.")
    else:
        t1, t2 = st.tabs(["📋 Centers List", "➕ Add New Branch"])

        with t1:
            centers_df = pd.read_sql("SELECT * FROM center ORDER BY city, name", conn)
            st.dataframe(centers_df, use_container_width=True)

        with t2:
            with st.form("add_ctr_form"):
                st.write(f"**New Center Code:** `{next_center_code()}`")
                c_name = st.text_input("Branch Name * (e.g., Central Clinic)")
                c_city = st.text_input("City * (e.g., Raipur)")
                c_address = st.text_area("Full Address")

                if st.form_submit_button("Register Branch"):
                    if c_name.strip() and c_city.strip():
                        code = next_center_code()
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        conn.execute(
                            "INSERT INTO center (center_code, name, city, address, created_at) VALUES (?, ?, ?, ?, ?)",
                            (code, c_name.strip(), c_city.strip(), c_address, now),
                        )
                        conn.commit()
                        st.success(f"Branch '{c_name}' created in {c_city} with code {code}!")
                        st.rerun()
                    else:
                        st.error("Branch Name and City are required!")

# -----------------------------------------------------------------------------
# MODULE 10: REPORTS & ANALYTICS
# -----------------------------------------------------------------------------
elif choice == "Reports & Analytics":
    st.title("📈 Reports & Business Analytics")

    r1, r2, r3 = st.tabs(["💰 Financial Collection Report", "👥 Patient Growth", "📊 Export Data"])

    with r1:
        st.subheader("Collection Breakdown")
        fin_query = """SELECT DATE(f.paid_on) as date, SUM(f.consultation_fee) as consult_fees, 
                             SUM(f.medicine_fee) as med_fees, SUM(f.discount) as total_discount, SUM(f.total) as grand_total 
                      FROM fee f LEFT JOIN patient p ON f.patient_id=p.id LEFT JOIN center c ON p.center_id=c.id WHERE 1=1"""
        params = []
        if selected_city != "All Cities":
            fin_query += " AND c.city = ?"
            params.append(selected_city)
        fin_query += " GROUP BY DATE(f.paid_on) ORDER BY date DESC"

        fin_df = pd.read_sql(fin_query, conn, params=params)
        if not fin_df.empty:
            st.dataframe(fin_df, use_container_width=True)
            st.line_chart(fin_df.set_index("date")["grand_total"])
        else:
            st.info("No financial records to display.")

    with r2:
        st.subheader("New Patient Registration Trend")
        p_query = """SELECT DATE(p.created_at) as date, COUNT(*) as new_patients 
                     FROM patient p LEFT JOIN center c ON p.center_id=c.id WHERE 1=1"""
        params = []
        if selected_city != "All Cities":
            p_query += " AND c.city = ?"
            params.append(selected_city)
        p_query += " GROUP BY DATE(p.created_at) ORDER BY date DESC"

        p_df = pd.read_sql(p_query, conn, params=params)
        if not p_df.empty:
            st.dataframe(p_df, use_container_width=True)
            st.bar_chart(p_df.set_index("date")["new_patients"])
        else:
            st.info("No registration data available.")

    with r3:
        st.subheader("📥 Export Tables to CSV")
        table_opt = st.selectbox("Select Table to Export", ["patient", "appointment", "consultation", "fee", "medicine", "staff", "attendance", "center"])
        if st.button("Generate Download Link"):
            exp_df = pd.read_sql(f"SELECT * FROM {table_opt}", conn)
            st.download_button(f"Download {table_opt}.csv", exp_df.to_csv(index=False).encode('utf-8'), f"{table_opt}_export.csv", "text/csv")

# -----------------------------------------------------------------------------
# MODULE 11: USERS MANAGEMENT
# -----------------------------------------------------------------------------
elif choice == "Users Management":
    st.title("👤 System Users & Access Control")

    if st.session_state["role"] != "admin":
        st.error("Access Denied: Only Administrator account can access User Management.")
    else:
        users_df = pd.read_sql("""SELECT u.id, u.username, u.role, c.name as center_name, c.city 
                                  FROM user u LEFT JOIN center c ON u.center_id=c.id ORDER BY u.id ASC""", conn)
        st.dataframe(users_df, use_container_width=True)

        st.markdown("---")
        st.subheader("🔑 Reset User Password")
        user_list = {u["id"]: u["username"] for u in conn.execute("SELECT id, username FROM user").fetchall()}
        sel_u = st.selectbox("Select User", options=list(user_list.keys()), format_func=lambda x: user_list[x])
        new_pass = st.text_input("New Password", type="password")

        if st.button("Change Password"):
            if new_pass.strip():
                conn.execute("UPDATE user SET password_hash=? WHERE id=?", (hash_pass(new_pass.strip()), sel_u))
                conn.commit()
                st.success(f"Password for {user_list[sel_u]} updated successfully!")
            else:
                st.error("Password cannot be empty.")

conn.close()
