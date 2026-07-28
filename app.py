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

# Custom CSS for compact & centered forms (Fixed Parameter Here)
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


# 5. Main Dashboard (After Login Navigation)
def main_dashboard():
    st.sidebar.title(f"Welcome, {st.session_state['username']}")

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
    choice = st.sidebar.selectbox("Navigation", menu)

    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.rerun()

    # Module Sections
    if choice == "Dashboard":
        st.title("📊 Clinic Dashboard")
        st.write("Welcome to SN Clinic Management System!")

    elif choice == "Patients":
        st.title("👨‍👩‍👧‍👦 Patient Management")

    elif choice == "Appointments":
        st.title("📅 Appointments Management")

    elif choice == "Fees":
        st.title("💳 Billing & Fee Management")

    elif choice == "Medicines":
        st.title("💊 Medicine Inventory")

    elif choice == "Reports":
        st.title("📈 Reports & Analytics")

    elif choice == "Followups":
        st.title("🔄 Follow-up Tracking")

    elif choice == "Users":
        st.title("⚙️ User Access Management")

    elif choice == "Staff":
        st.title("👨‍⚕️ Staff Directory")


# Main Application Control
if not st.session_state["logged_in"]:
    login_page()
else:
    main_dashboard()
