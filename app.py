import hashlib
import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st

# 1. Page Config & CSS
st.set_page_config(
    page_title="SN Clinic Management System",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom Styling for Login Box & Layout
st.markdown(
    """
    <style>
    div[data-testid="stForm"], div.stTextInput {
        max-width: 420px !important;
        margin: 0 auto;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #007bff;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# 2. Database Setup (Full Schema for all original features)
def init_db():
    conn = sqlite3.connect("clinic.db")
    c = conn.cursor()

    # Users Table
    c.execute("""CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT)""")

    # Patients Table
    c.execute("""CREATE TABLE IF NOT EXISTS patients 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, age INT, gender TEXT, phone TEXT, address TEXT, created_at TEXT)""")

    # Appointments Table
    c.execute("""CREATE TABLE IF NOT EXISTS appointments 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_name TEXT, doctor TEXT, date TEXT, time TEXT, status TEXT)""")

    # Fees/Billing Table
    c.execute("""CREATE TABLE IF NOT EXISTS fees 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_name TEXT, amount REAL, payment_mode TEXT, date TEXT, status TEXT)""")

    # Medicines Table
    c.execute("""CREATE TABLE IF NOT EXISTS medicines 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, category TEXT, quantity INT, price REAL)""")

    # Follow-ups Table
    c.execute("""CREATE TABLE IF NOT EXISTS followups 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, patient_name TEXT, doctor TEXT, follow_date TEXT, notes TEXT)""")

    # Staff Directory Table
    c.execute("""CREATE TABLE IF NOT EXISTS staff 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, role TEXT, phone TEXT, email TEXT)""")

    # Default Admin Creation
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute(
            "INSERT INTO users VALUES ('admin', ?, 'admin')", (hashed_pw,)
        )

    conn.commit()
    conn.close()


init_db()

# 3. Session State Management
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""


# 4. Auth Page (Login & Registration)
def login_page():
    st.title("🏥 SN Clinic Management System")

    col1, col2, col3 = st.columns([1, 1.5, 1])

    with col2:
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Sign In / Register"])

        # LOGIN TAB
        with tab1:
            st.subheader("Login")
            username = st.text_input("Username", key="login_user")
            password = st.text_input(
                "Password", type="password", key="login_pass"
            )

            if st.button("Login", use_container_width=True):
                hashed_pw = hashlib.sha256(password.encode()).hexdigest()
                conn = sqlite3.connect("clinic.db")
                c = conn.cursor()
                c.execute(
                    "SELECT * FROM users WHERE username=? AND password=?",
                    (username, hashed_pw),
                )
                user = c.fetchone()
                conn.close()

                if user:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = username
                    st.success("Login Successful!")
                    st.rerun()
                else:
                    st.error("Invalid Username or Password")

        # REGISTER TAB
        with tab2:
            st.subheader("Create New Account")
            new_username = st.text_input("New Username", key="reg_user")
            new_password = st.text_input(
                "New Password", type="password", key="reg_pass"
            )
            confirm_password = st.text_input(
                "Confirm Password", type="password", key="reg_confirm"
            )
            role = st.selectbox(
                "Role", ["Staff", "Doctor", "Admin"], key="reg_role"
            )

            if st.button("Sign In / Register", use_container_width=True):
                if not new_username or not new_password:
                    st.warning("Please fill all fields")
                elif new_password != confirm_password:
                    st.error("Passwords do not match!")
                else:
                    hashed_pw = hashlib.sha256(
                        new_password.encode()
                    ).hexdigest()
                    conn = sqlite3.connect("clinic.db")
                    c = conn.cursor()

                    c.execute(
                        "SELECT * FROM users WHERE username=?", (new_username,)
                    )
                    if c.fetchone():
                        st.error("Username already exists!")
                    else:
                        c.execute(
                            "INSERT INTO users VALUES (?, ?, ?)",
                            (new_username, hashed_pw, role.lower()),
                        )
                        conn.commit()
                        st.success(
                            "Account created successfully! Please switch to Login tab."
                        )
                    conn.close()


# 5. Main Dashboard & All Modules
def main_dashboard():
    st.sidebar.title("🏥 SN Clinic")
    st.sidebar.caption(f"Logged in as: **{st.session_state['username']}**")

    # Original Routes converted to Navigation
    menu = [
        "Dashboard",
        "Patients Management",
        "Appointments",
        "Fees & Billing",
        "Medicines Inventory",
        "Reports & Analytics",
        "Followups Tracking",
        "User Management",
        "Staff Directory",
    ]
    choice = st.sidebar.selectbox("Navigation Menu", menu)

    st.sidebar.markdown("---")
    if st.sidebar.button("🔴 Logout", use_container_width=True):
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.rerun()

    conn = sqlite3.connect("clinic.db")

    # ================= 1. DASHBOARD =================
    if choice == "Dashboard":
        st.title("📊 Clinic Dashboard")

        # Fetch live stats from Database
        p_count = pd.read_sql("SELECT COUNT(*) FROM patients", conn).iloc[0, 0]
        a_count = pd.read_sql("SELECT COUNT(*) FROM appointments", conn).iloc[
            0, 0
        ]
        f_total = (
            pd.read_sql("SELECT SUM(amount) FROM fees", conn).iloc[0, 0] or 0
        )
        m_count = pd.read_sql("SELECT COUNT(*) FROM medicines", conn).iloc[0, 0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("👨‍👩‍👧‍👦 Total Patients", str(p_count))
        c2.metric("📅 Total Appointments", str(a_count))
        c3.metric("💳 Total Revenue", f"₹{f_total:,.2f}")
        c4.metric("💊 Medicine Types", str(m_count))

        st.markdown("---")
        st.subheader("📋 Recent Appointments")
        appointments_df = pd.read_sql(
            "SELECT * FROM appointments ORDER BY id DESC LIMIT 5", conn
        )
        st.dataframe(appointments_df, use_container_width=True)

    # ================= 2. PATIENTS MODULE =================
    elif choice == "Patients Management":
        st.title("👨‍👩‍👧‍👦 Patients Management")

        tab1, tab2 = st.tabs(["➕ Add New Patient", "📋 Patient Records"])

        with tab1:
            with st.form("patient_form", clear_on_submit=True):
                name = st.text_input("Full Name")
                col1, col2 = st.columns(2)
                age = col1.number_input("Age", min_value=0, max_value=120)
                gender = col2.selectbox("Gender", ["Male", "Female", "Other"])
                phone = st.text_input("Phone Number")
                address = st.text_area("Address")
                submit = st.form_submit_button("Save Patient Record")

                if submit:
                    if name and phone:
                        c = conn.cursor()
                        today = datetime.now().strftime("%Y-%m-%d")
                        c.execute(
                            "INSERT INTO patients (name, age, gender, phone, address, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                            (name, age, gender, phone, address, today),
                        )
                        conn.commit()
                        st.success(f"Patient '{name}' added successfully!")
                    else:
                        st.error("Please fill required fields (Name & Phone).")

        with tab2:
            df = pd.read_sql("SELECT * FROM patients", conn)
            st.dataframe(df, use_container_width=True)

    # ================= 3. APPOINTMENTS MODULE =================
    elif choice == "Appointments":
        st.title("📅 Appointments Management")

        tab1, tab2 = st.tabs(["➕ Schedule Appointment", "📋 Appointments List"])

        with tab1:
            patients = (
                pd.read_sql("SELECT name FROM patients", conn)["name"].tolist()
                or []
            )
            with st.form("appt_form", clear_on_submit=True):
                if patients:
                    p_name = st.selectbox("Select Patient", patients)
                else:
                    p_name = st.text_input("Patient Name")

                doctor = st.text_input("Doctor Name", "Dr. Sharma")
                col1, col2 = st.columns(2)
                a_date = col1.date_input("Appointment Date")
                a_time = col2.time_input("Appointment Time")
                status = st.selectbox(
                    "Status", ["Scheduled", "Completed", "Cancelled"]
                )

                if st.form_submit_button("Book Appointment"):
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO appointments (patient_name, doctor, date, time, status) VALUES (?, ?, ?, ?, ?)",
                        (
                            p_name,
                            doctor,
                            str(a_date),
                            str(a_time),
                            status,
                        ),
                    )
                    conn.commit()
                    st.success("Appointment Scheduled Successfully!")

        with tab2:
            df = pd.read_sql("SELECT * FROM appointments", conn)
            st.dataframe(df, use_container_width=True)

    # ================= 4. FEES & BILLING MODULE =================
    elif choice == "Fees & Billing":
        st.title("💳 Fees & Billing Management")

        tab1, tab2 = st.tabs(["🧾 Generate Bill", "📜 Payment Records"])

        with tab1:
            with st.form("fee_form", clear_on_submit=True):
                patient_name = st.text_input("Patient Name")
                amount = st.number_input("Amount (₹)", min_value=0.0)
                payment_mode = st.selectbox(
                    "Payment Mode", ["Cash", "UPI / Online", "Card"]
                )
                status = st.selectbox("Status", ["Paid", "Pending"])

                if st.form_submit_button("Record Payment"):
                    c = conn.cursor()
                    today = datetime.now().strftime("%Y-%m-%d")
                    c.execute(
                        "INSERT INTO fees (patient_name, amount, payment_mode, date, status) VALUES (?, ?, ?, ?, ?)",
                        (patient_name, amount, payment_mode, today, status),
                    )
                    conn.commit()
                    st.success("Billing Record Saved!")

        with tab2:
            df = pd.read_sql("SELECT * FROM fees", conn)
            st.dataframe(df, use_container_width=True)

    # ================= 5. MEDICINES INVENTORY =================
    elif choice == "Medicines Inventory":
        st.title("💊 Medicines Inventory")

        tab1, tab2 = st.tabs(["➕ Add Stock", "📦 Inventory List"])

        with tab1:
            with st.form("med_form", clear_on_submit=True):
                med_name = st.text_input("Medicine Name")
                category = st.text_input("Category / Type")
                col1, col2 = st.columns(2)
                quantity = col1.number_input("Quantity", min_value=1)
                price = col2.number_input("Price per Unit (₹)", min_value=0.0)

                if st.form_submit_button("Add to Stock"):
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO medicines (name, category, quantity, price) VALUES (?, ?, ?, ?)",
                        (med_name, category, quantity, price),
                    )
                    conn.commit()
                    st.success("Medicine added to inventory!")

        with tab2:
            df = pd.read_sql("SELECT * FROM medicines", conn)
            st.dataframe(df, use_container_width=True)

    # ================= 6. REPORTS & ANALYTICS =================
    elif choice == "Reports & Analytics":
        st.title("📈 Reports & Analytics")

        f_df = pd.read_sql("SELECT date, amount FROM fees", conn)
        if not f_df.empty:
            st.subheader("Revenue Trend")
            st.line_chart(f_df.groupby("date").sum())
        else:
            st.info("No transaction data available yet to generate reports.")

    # ================= 7. FOLLOWUPS TRACKING =================
    elif choice == "Followups Tracking":
        st.title("🔄 Follow-up Appointments")

        with st.form("followup_form", clear_on_submit=True):
            p_name = st.text_input("Patient Name")
            doctor = st.text_input("Doctor Name")
            f_date = st.date_input("Follow-up Date")
            notes = st.text_area("Doctor Notes / Recommendation")

            if st.form_submit_button("Add Follow-up"):
                c = conn.cursor()
                c.execute(
                    "INSERT INTO followups (patient_name, doctor, follow_date, notes) VALUES (?, ?, ?, ?)",
                    (p_name, doctor, str(f_date), notes),
                )
                conn.commit()
                st.success("Follow-up entry created!")

        st.subheader("📋 Scheduled Follow-ups")
        df = pd.read_sql("SELECT * FROM followups", conn)
        st.dataframe(df, use_container_width=True)

    # ================= 8. USER MANAGEMENT =================
    elif choice == "User Management":
        st.title("⚙️ User Access Control")
        df = pd.read_sql(
            "SELECT username, role FROM users", conn
        )  # Security: Password hash hidden
        st.dataframe(df, use_container_width=True)

    # ================= 9. STAFF DIRECTORY =================
    elif choice == "Staff Directory":
        st.title("👨‍⚕️ Staff & Doctor Directory")

        with st.form("staff_form", clear_on_submit=True):
            s_name = st.text_input("Staff Name")
            s_role = st.text_input("Role / Designation")
            col1, col2 = st.columns(2)
            phone = col1.text_input("Phone Number")
            email = col2.text_input("Email")

            if st.form_submit_button("Add Staff Member"):
                c = conn.cursor()
                c.execute(
                    "INSERT INTO staff (name, role, phone, email) VALUES (?, ?, ?, ?)",
                    (s_name, s_role, phone, email),
                )
                conn.commit()
                st.success("Staff member added!")

        st.subheader("👥 Current Staff List")
        df = pd.read_sql("SELECT * FROM staff", conn)
        st.dataframe(df, use_container_width=True)

    conn.close()


# Application Trigger
if not st.session_state["logged_in"]:
    login_page()
else:
    main_dashboard()
