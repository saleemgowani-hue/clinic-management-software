import streamlit as st
import sqlite3
import hashlib

# 1. Page Config (Mobile Responsive Layout)
st.set_page_config(
    page_title="SN Clinic Management",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed" # Mobile me sidebar collapsible rahega
)

# 2. Database Setup (Simple SQLite)
def init_db():
    conn = sqlite3.connect("clinic.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')
    
    # Default Admin Creation
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        # Hash "admin123"
        hashed_pw = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute("INSERT INTO users VALUES ('admin', ?, 'admin')", (hashed_pw,))
        conn.commit()
    conn.close()

init_db()

# 3. Session State for Login
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""

# 4. Login Page
def login_page():
    st.title("🏥 SN Clinic Management System")
    st.subheader("Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        conn = sqlite3.connect("clinic.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, hashed_pw))
        user = c.fetchone()
        conn.close()

        if user:
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.success("Login Successful!")
            st.rerun()
        else:
            st.error("Invalid Username or Password")

# 5. Main Dashboard (Modules Navigation)
def main_dashboard():
    st.sidebar.title(f"Welcome, {st.session_state['username']}")
    
    # Navigation Options (Replacing Flask Blueprints)
    menu = [
        "Dashboard", 
        "Patients", 
        "Appointments", 
        "Fees", 
        "Medicines", 
        "Reports", 
        "Followups", 
        "Users", 
        "Staff"
    ]
    choice = st.sidebar.selectbox("Navigation", menu)

    if st.sidebar.button("Logout"):
        st.session_state["logged_in"] = False
        st.rerun()

    # Routing Logic
    if choice == "Dashboard":
        st.title("📊 Dashboard")
        st.write("Welcome to SN Clinic Dashboard")

    elif choice == "Patients":
        st.title("👨‍👩‍👧‍👦 Patient Management")
        # Yahan Patient Entry / Search Form aayega

    elif choice == "Appointments":
        st.title("📅 Appointments")
        # Appointment scheduling interface

    elif choice == "Fees":
        st.title("💳 Billing & Fees")

    elif choice == "Medicines":
        st.title("💊 Pharmacy & Inventory")

    elif choice == "Reports":
        st.title("📈 Reports & Analytics")

    elif choice == "Followups":
        st.title("🔄 Patient Follow-ups")

    elif choice == "Users":
        st.title("⚙️ User Management")

    elif choice == "Staff":
        st.title("👨‍⚕️ Staff Management")

# App Entry Point
if not st.session_state["logged_in"]:
    login_page()
else:
    main_dashboard()