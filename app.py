import hashlib
import sqlite3
import streamlit as st

# 1. Page Configuration (Mobile Responsive & Clean Title)
st.set_page_config(
    page_title="SN Clinic Management",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",  # Mobile me sidebar auto-collapse rahega
)

# Custom CSS for compact & centered login forms
st.markdown(
    """
    <style>
    div[data-testid="stForm"], div.stTextInput {
        max-width: 400px !important;
        margin: 0 auto;
    }
    </style>
""",
    unsafe_allow_html=True,
)


# 2. Database Initialization
def init_db():
    conn = sqlite3.connect("clinic.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT)""")

    # Default Admin User Creation
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


# 4. Auth Page (Compact Login & Sign In / Register Tabs)
def login_page():
    st.title("🏥 SN Clinic Management System")

    # Layout: Center column to keep form compact
    col1, col2, col3 = st.columns([1, 1.5, 1])

    with col2:
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Sign In / Register"])

        # TAB 1: LOGIN
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

        # TAB 2: SIGN IN / REGISTER
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
                        st.error(
                            "Username already exists! Choose another one."
                        )
                    else:
                        c.execute(
                            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                            (new_username, hashed_pw, role.lower()),
                        )
                        conn.commit()
                        st.success(
                            "Account created successfully! Please switch to Login tab."
                        )
                    conn.close()


# 5. Main Dashboard (Interactive Dashboard & Navigation)
def main_dashboard():
    # Sidebar Navigation & Mobile Collapse Setup
    st.sidebar.title("🏥 SN Clinic")
    st.sidebar.caption(f"Logged in as: **{st.session_state['username']}**")

    menu = [
        "Dashboard",
        "Patients",
        "Appointments",
        "Fees",
        "Medicines",
        "Reports",
        "Followups",
        "Users",
        "Staff",
    ]
    choice = st.sidebar.selectbox("Navigation Menu", menu)

    st.sidebar.markdown("---")
    if st.sidebar.button("🔴 Logout", use_container_width=True):
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.rerun()

    # ------------------ DASHBOARD MODULE ------------------
    if choice == "Dashboard":
        st.title("📊 Clinic Overview Dashboard")
        st.write(
            f"Welcome back, **{st.session_state['username']}**! Here is today's summary:"
        )

        st.markdown("---")

        # 1. Key Metrics Cards
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="👨‍👩‍👧‍👦 Total Patients", value="128", delta="+5 Today"
            )

        with col2:
            st.metric(
                label="📅 Today's Appointments", value="12", delta="3 Pending"
            )

        with col3:
            st.metric(
                label="💳 Today's Collection",
                value="₹14,500",
                delta="₹2,000 Unpaid",
            )

        with col4:
            st.metric(
                label="💊 Low Stock Medicines",
                value="4",
                delta="-2 Items",
                delta_color="inverse",
            )

        st.markdown("---")

        # 2. Quick Action Buttons
        st.subheader("⚡ Quick Actions")
        q_col1, q_col2, q_col3 = st.columns(3)

        with q_col1:
            if st.button("➕ Register New Patient", use_container_width=True):
                st.info(
                    "Navigate to 'Patients' tab from sidebar to add record."
                )

        with q_col2:
            if st.button("📅 Schedule Appointment", use_container_width=True):
                st.info(
                    "Navigate to 'Appointments' tab to book a time slot."
                )

        with q_col3:
            if st.button("🧾 Generate Fee Bill", use_container_width=True):
                st.info("Navigate to 'Fees' tab to create an invoice.")

        st.markdown("---")

        # 3. Recent Appointments Table Placeholder
        st.subheader("📋 Today's Appointment Schedule")

        sample_data = [
            {
                "Time": "10:00 AM",
                "Patient Name": "Ramesh Kumar",
                "Doctor": "Dr. Sharma",
                "Status": "Completed",
            },
            {
                "Time": "10:30 AM",
                "Patient Name": "Priya Singh",
                "Doctor": "Dr. Sharma",
                "Status": "In Consultation",
            },
            {
                "Time": "11:15 AM",
                "Patient Name": "Amit Verma",
                "Doctor": "Dr. Patel",
                "Status": "Waiting",
            },
            {
                "Time": "12:00 PM",
                "Patient Name": "Suresh Patel",
                "Doctor": "Dr. Sharma",
                "Status": "Scheduled",
            },
        ]
        st.dataframe(sample_data, use_container_width=True)

    # ------------------ OTHER MODULES ------------------
    elif choice == "Patients":
        st.title("👨‍👩‍👧‍👦 Patient Management")
        st.write("Patient Records and Registration form will go here.")

    elif choice == "Appointments":
        st.title("📅 Appointments Management")
        st.write("Schedule and manage patient slots here.")

    elif choice == "Fees":
        st.title("💳 Billing & Fee Management")
        st.write("Generate invoices and track payments here.")

    elif choice == "Medicines":
        st.title("💊 Medicine Inventory")
        st.write("Manage pharmacy stock and medicines here.")

    elif choice == "Reports":
        st.title("📈 Reports & Analytics")
        st.write("View clinic revenue and patient reports here.")

    elif choice == "Followups":
        st.title("🔄 Follow-up Tracking")
        st.write("Track upcoming follow-up appointments here.")

    elif choice == "Users":
        st.title("⚙️ User Access Management")
        st.write("Manage user roles and passwords here.")

    elif choice == "Staff":
        st.title("👨‍⚕️ Staff Directory")
        st.write("Manage doctors and clinic staff details here.")


# Main Application Control
if not st.session_state["logged_in"]:
    login_page()
else:
    main_dashboard()
