import hashlib
import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG & CUSTOM STYLING (MOBILE & CONTRAST FIX)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Clinic Management SaaS",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* Form Centering & Layout */
    div[data-testid="stForm"], div.stTextInput {
        max-width: 600px !important;
        margin: 0 auto;
    }
    
    /* FIX FOR METRIC CARDS TEXT VISIBILITY (MOBILE DARK MODE FIX) */
    div[data-testid="stMetric"] {
        background-color: #f8f9fa !important;
        padding: 14px !important;
        border-radius: 10px !important;
        border-left: 5px solid #0284c7 !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.08) !important;
    }
    
    /* Metric Title Label */
    div[data-testid="stMetricLabel"] label, div[data-testid="stMetricLabel"] p {
        color: #1e293b !important;
        font-weight: 600 !important;
        font-size: 15px !important;
    }
    
    /* Metric Numbers/Values */
    div[data-testid="stMetricValue"] div {
        color: #0f172a !important;
        font-weight: bold !important;
        font-size: 26px !important;
    }
    
    /* Metric Delta (Sub-text) */
    div[data-testid="stMetricDelta"] div {
        font-weight: 600 !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# -----------------------------------------------------------------------------
# 2. DATABASE INITIALIZATION
# -----------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect("clinic_saas.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def hash_pass(password):
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = get_db()
    c = conn.cursor()

    # Clinics Table (Tenants)
    c.execute("""CREATE TABLE IF NOT EXISTS clinics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        doctor_name TEXT,
        city TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Users Table
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL, -- 'super_admin' or 'clinic_user'
        clinic_code TEXT,
        FOREIGN KEY(clinic_code) REFERENCES clinics(clinic_code)
    )""")

    # Patients Table (Isolated by clinic_code)
    c.execute("""CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_code TEXT NOT NULL,
        patient_code TEXT,
        name TEXT NOT NULL,
        phone TEXT,
        age INTEGER,
        gender TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Appointments Table (Isolated by clinic_code)
    c.execute("""CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clinic_code TEXT NOT NULL,
        patient_id INTEGER,
        patient_name TEXT,
        doctor_name TEXT,
        appt_date TEXT NOT NULL,
        status TEXT DEFAULT 'Booked',
        fee REAL DEFAULT 0.0,
        FOREIGN KEY(patient_id) REFERENCES patients(id)
    )""")

    # Default Super Admin Account (For You)
    c.execute("SELECT * FROM users WHERE role='super_admin'")
    if not c.fetchone():
        hashed = hash_pass("admin123")  # Default password
        c.execute(
            "INSERT INTO users (username, password_hash, role) VALUES ('superadmin', ?, 'super_admin')",
            (hashed,),
        )

    conn.commit()
    conn.close()


init_db()


# -----------------------------------------------------------------------------
# 3. AUTHENTICATION & SESSION MANAGEMENT
# -----------------------------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.session_state["role"] = ""
    st.session_state["clinic_code"] = None
    st.session_state["clinic_name"] = ""

if not st.session_state["logged_in"]:
    st.title("🏥 Clinic Management Software Login")
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.subheader("🔐 Sign In")
        username_inp = st.text_input("Username", key="l_user").strip()
        pass_inp = st.text_input("Password", type="password", key="l_pass")

        if st.button("Login", use_container_width=True):
            conn = get_db()
            user = conn.execute(
                "SELECT * FROM users WHERE username=? AND password_hash=?",
                (username_inp, hash_pass(pass_inp)),
            ).fetchone()

            if user:
                st.session_state["logged_in"] = True
                st.session_state["username"] = user["username"]
                st.session_state["role"] = user["role"]
                st.session_state["clinic_code"] = user["clinic_code"]

                if user["role"] == "clinic_user":
                    clinic = conn.execute(
                        "SELECT name FROM clinics WHERE clinic_code=?",
                        (user["clinic_code"],),
                    ).fetchone()
                    st.session_state["clinic_name"] = clinic["name"] if clinic else "Clinic"
                else:
                    st.session_state["clinic_name"] = "Super Admin Portal"

                conn.close()
                st.success("Login Successful!")
                st.rerun()
            else:
                conn.close()
                st.error("Invalid Username or Password!")

    st.stop()


# -----------------------------------------------------------------------------
# 4. SIDEBAR LOGOUT & BRANDING
# -----------------------------------------------------------------------------
st.sidebar.title("🏥 SN Clinic SaaS")
if st.session_state["role"] == "super_admin":
    st.sidebar.write("Logged as: **Super Admin**")
else:
    st.sidebar.write(f"Clinic: **{st.session_state['clinic_name']}**")
    st.sidebar.caption(f"Code: `{st.session_state['clinic_code']}`")

st.sidebar.markdown("---")


# -----------------------------------------------------------------------------
# MODULE A: SUPER ADMIN DASHBOARD (FOR YOU TO SELL & MANAGE CLIENTS)
# -----------------------------------------------------------------------------
if st.session_state["role"] == "super_admin":
    menu = st.sidebar.radio("Navigation", ["Manage Clinics", "Add New Clinic Client"])

    conn = get_db()

    if st.sidebar.button("🔴 Logout", use_container_width=True):
        st.session_state["logged_in"] = False
        st.rerun()

    if menu == "Manage Clinics":
        st.title("👑 Super Admin - Client Clinics")
        
        clinics_df = pd.read_sql("""
            SELECT c.clinic_code, c.name as clinic_name, c.doctor_name, c.city, u.username, c.created_at 
            FROM clinics c LEFT JOIN users u ON c.clinic_code = u.clinic_code
        """, conn)
        
        st.dataframe(clinics_df, use_container_width=True)

    elif menu == "Add New Clinic Client":
        st.title("➕ Onboard New Clinic Client")
        with st.form("onboard_clinic"):
            c_code = st.text_input("Clinic Code (Unique, e.g. CLN001) *").strip().upper()
            c_name = st.text_input("Clinic Name *").strip()
            doc_name = st.text_input("Doctor/Owner Name").strip()
            city = st.text_input("City").strip()
            
            st.markdown("---")
            st.subheader("🔑 Assign Clinic Admin Login Credentials")
            u_name = st.text_input("Login Username *").strip()
            u_pass = st.text_input("Login Password *", type="password")

            if st.form_submit_button("Create Clinic Account"):
                if c_code and c_name and u_name and u_pass:
                    try:
                        conn.execute(
                            "INSERT INTO clinics (clinic_code, name, doctor_name, city) VALUES (?, ?, ?, ?)",
                            (c_code, c_name, doc_name, city),
                        )
                        conn.execute(
                            "INSERT INTO users (username, password_hash, role, clinic_code) VALUES (?, ?, 'clinic_user', ?)",
                            (u_name, hash_pass(u_pass), c_code),
                        )
                        conn.commit()
                        st.success(f"Clinic '{c_name}' onboarding successful! Username: {u_name}")
                    except sqlite3.IntegrityError:
                        st.error("Error: Clinic Code or Username already exists!")
                else:
                    st.error("Please fill all required fields (*)")

    conn.close()
    st.stop()


# -----------------------------------------------------------------------------
# MODULE B: CLIENT CLINIC DASHBOARD (STRICTLY ISOLATED PER CLINIC)
# -----------------------------------------------------------------------------
current_clinic = st.session_state["clinic_code"]

menu = st.sidebar.radio("Navigation", ["Dashboard", "Patients", "Appointments & Billing"])

if st.sidebar.button("🔴 Logout", use_container_width=True):
    st.session_state["logged_in"] = False
    st.rerun()

conn = get_db()
today_str = datetime.now().strftime("%Y-%m-%d")

# --- CLINIC DASHBOARD ---
if menu == "Dashboard":
    st.title(f"📊 Dashboard - {st.session_state['clinic_name']}")

    tot_patients = conn.execute(
        "SELECT COUNT(*) FROM patients WHERE clinic_code=?", (current_clinic,)
    ).fetchone()[0]
    
    appts_today = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE clinic_code=? AND appt_date=?", 
        (current_clinic, today_str)
    ).fetchone()[0]
    
    colln_today = conn.execute(
        "SELECT SUM(fee) FROM appointments WHERE clinic_code=? AND appt_date=?", 
        (current_clinic, today_str)
    ).fetchone()[0] or 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Registered Patients", tot_patients)
    c2.metric("Today's Appointments", appts_today)
    c3.metric("Today's Fee Collection", f"₹{colln_today:,.2f}")

    st.markdown("---")
    st.subheader("📋 Today's Appointment List")
    appts_df = pd.read_sql(
        "SELECT patient_name, doctor_name, status, fee FROM appointments WHERE clinic_code=? AND appt_date=? ORDER BY id DESC",
        conn,
        params=[current_clinic, today_str],
    )
    st.dataframe(appts_df, use_container_width=True)

# --- PATIENT MANAGEMENT ---
elif menu == "Patients":
    st.title("👨‍👩‍👧‍👦 Patient Records")

    t1, t2 = st.tabs(["📋 Patient Directory", "➕ Add New Patient"])

    with t1:
        p_df = pd.read_sql(
            "SELECT id, patient_code, name, phone, age, gender, created_at FROM patients WHERE clinic_code=? ORDER BY id DESC",
            conn,
            params=[current_clinic],
        )
        st.dataframe(p_df, use_container_width=True)

    with t2:
        with st.form("reg_p_form"):
            p_name = st.text_input("Patient Full Name *").strip()
            p_phone = st.text_input("Mobile Number")
            col_a, col_b = st.columns(2)
            p_age = col_a.number_input("Age", min_value=0, max_value=120, value=25)
            p_gender = col_b.selectbox("Gender", ["Male", "Female", "Other"])

            if st.form_submit_button("Register Patient"):
                if p_name:
                    p_cnt = conn.execute("SELECT COUNT(*) FROM patients WHERE clinic_code=?", (current_clinic,)).fetchone()[0] + 1
                    p_code = f"P-{p_cnt:04d}"
                    
                    conn.execute(
                        "INSERT INTO patients (clinic_code, patient_code, name, phone, age, gender) VALUES (?, ?, ?, ?, ?, ?)",
                        (current_clinic, p_code, p_name, p_phone, p_age, p_gender),
                    )
                    conn.commit()
                    st.success(f"Patient registered successfully! Code: {p_code}")
                    st.rerun()
                else:
                    st.error("Patient Name is required!")

# --- APPOINTMENTS & BILLING ---
elif menu == "Appointments & Billing":
    st.title("📅 Appointments & Fee Billing")

    patients_list = conn.execute(
        "SELECT id, name, patient_code FROM patients WHERE clinic_code=? ORDER BY name", (current_clinic,)
    ).fetchall()
    
    p_map = {p["id"]: f"{p['name']} ({p['patient_code'] or 'N/A'})" for p in patients_list}

    if not p_map:
        st.warning("Pehle ek Patient register karein.")
    else:
        with st.form("book_appt_form"):
            selected_pid = st.selectbox("Select Patient", options=list(p_map.keys()), format_func=lambda x: p_map[x])
            doc_name = st.text_input("Doctor Name")
            c1, c2 = st.columns(2)
            a_date = c1.date_input("Appointment Date", datetime.now())
            a_fee = c2.number_input("Consultation Fee (₹)", min_value=0.0, value=200.0)

            if st.form_submit_button("Book Appointment & Record Fee"):
                p_data = conn.execute("SELECT name FROM patients WHERE id=?", (selected_pid,)).fetchone()
                conn.execute(
                    "INSERT INTO appointments (clinic_code, patient_id, patient_name, doctor_name, appt_date, fee) VALUES (?, ?, ?, ?, ?, ?)",
                    (current_clinic, selected_pid, p_data["name"], doc_name, str(a_date), a_fee),
                )
                conn.commit()
                st.success("Appointment Booked & Collection Recorded!")
                st.rerun()

    st.markdown("---")
    st.subheader("📜 Recent Billings & Appointments")
    all_appts = pd.read_sql(
        "SELECT id, patient_name, doctor_name, appt_date, status, fee FROM appointments WHERE clinic_code=? ORDER BY id DESC",
        conn,
        params=[current_clinic],
    )
    st.dataframe(all_appts, use_container_width=True)

conn.close()
