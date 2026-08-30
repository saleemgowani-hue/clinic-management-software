"""
app.py
SN Clinic Management System - SaaS Edition
A multi-tenant clinic/hospital management platform built with Streamlit.
Every clinic that signs up becomes its own "Center" (tenant) - all patient,
staff, billing and appointment data stays isolated to that center, so this
one app + database can be sold to many clinics at once.
"""

import hashlib
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

import database as db
import invoice as inv
import billing
import licensing as lic
import whatsapp as wa
import demo_data as dd

# -----------------------------------------------------------------------------
# 1. PAGE CONFIG & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="SN Clinic Management System",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown(
    """
    <style>
    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricValue"],
    div[data-testid="stMetricDelta"],
    .stMetric label,
    p, span, h1, h2, h3, h4, h5, h6 {
        color: inherit !important;
    }
    h1, h2, h3, h4, h5, h6 { font-weight: 700 !important; }

    div[data-testid="stMetric"] {
        padding: 12px 16px !important;
        border-radius: 10px !important;
        border: 1px solid #d1d5db !important;
        border-left: 6px solid #0284c7 !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.08) !important;
    }

    div[data-testid="stForm"], div.stTextInput { max-width: 640px !important; }

    .plan-badge {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        background: #0284c7;
        color: white !important;
    }

    .colored-metric-card {
        border-radius: 14px;
        padding: 16px 18px;
        color: white;
        box-shadow: 0 3px 8px rgba(0,0,0,0.15);
        min-height: 92px;
    }
    .colored-metric-card .cm-label { font-size: 0.8rem; opacity: 0.92; font-weight: 600; color: white !important; }
    .colored-metric-card .cm-value { font-size: 1.65rem; font-weight: 800; margin-top: 4px; color: white !important; }
    .colored-metric-card .cm-delta { font-size: 0.78rem; opacity: 0.9; margin-top: 2px; color: white !important; }

    /* ---- Mobile & tablet responsiveness ---- */
    @media (max-width: 640px) {
        /* The sidebar normally sits side-by-side with the main content and
           takes a fixed ~300px width — on a narrow phone that leaves almost
           nothing for the actual page, squeezing every card/table into an
           unusable sliver. Make it float over the content instead, like a
           standard mobile navigation drawer, so the page underneath keeps
           its full width whether the drawer is open or closed. */
        [data-testid="stSidebar"] {
            position: fixed !important;
            top: 0;
            left: 0;
            height: 100vh !important;
            z-index: 999999 !important;
            box-shadow: 4px 0 18px rgba(0,0,0,0.25);
        }
    }
    @media (max-width: 768px) {
        div[data-testid="stMetric"] {
            padding: 8px 10px !important;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.3rem !important;
        }
        h1 { font-size: 1.5rem !important; }
        h2 { font-size: 1.25rem !important; }
        h3 { font-size: 1.1rem !important; }
        div[data-testid="stForm"], div.stTextInput { max-width: 100% !important; }
        .stButton > button, .stDownloadButton > button, .stLinkButton > a {
            font-size: 0.9rem !important;
            padding: 0.5rem 0.75rem !important;
            min-height: 44px !important;
        }
        div[data-testid="stDataFrame"] { font-size: 0.85rem !important; }
        .colored-metric-card { padding: 10px 12px; min-height: 72px; }
        .colored-metric-card .cm-value { font-size: 1.3rem; }
        /* Shrink tab labels/padding so more tabs fit before needing to
           scroll — most module pages have 2-4 tabs that otherwise overflow
           a narrow screen and get hidden behind a ">" scroll arrow. */
        div[data-baseweb="tab-list"] { gap: 2px !important; }
        .stTabs [data-testid="stTab"] {
            font-size: 0.78rem !important;
            padding: 6px 8px !important;
            white-space: nowrap;
        }
    }
    @media (max-width: 480px) {
        div[data-testid="stMetricValue"] {
            font-size: 1.1rem !important;
        }
        h1 { font-size: 1.3rem !important; }
        .colored-metric-card .cm-value { font-size: 1.1rem; }
    }
    /* Let wide tables scroll sideways instead of squeezing unreadably */
    div[data-testid="stDataFrame"] { overflow-x: auto !important; }
    </style>
""",
    unsafe_allow_html=True,
)

db.init_db()


def colored_metric(container, label, value, color, delta=None, icon=""):
    """Renders a professional colorful metric card (used on the Dashboard)."""
    delta_html = f'<div class="cm-delta">{delta}</div>' if delta else ""
    container.markdown(
        f"""
        <div class="colored-metric-card" style="background:linear-gradient(135deg, {color} 0%, {color}cc 100%);">
            <div class="cm-label">{icon} {label}</div>
            <div class="cm-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

ROLE_MENU = {
    "superadmin": ["Dashboard", "Patients", "Appointments", "Follow-ups", "Fees & Billing",
                    "Medicines Inventory", "Pathology Lab", "Staff Directory", "Daily Attendance",
                    "Center Management", "Reports & Analytics", "Users Management"],
    "admin": ["Dashboard", "Patients", "Appointments", "Follow-ups", "Fees & Billing",
              "Medicines Inventory", "Pathology Lab", "Staff Directory", "Daily Attendance",
              "Reports & Analytics", "Users Management", "Billing & Upgrade"],
    "doctor": ["Dashboard", "Patients", "Appointments", "Follow-ups", "Pathology Lab", "Reports & Analytics"],
    "receptionist": ["Dashboard", "Patients", "Appointments", "Fees & Billing", "Medicines Inventory", "Pathology Lab"],
    "hr": ["Dashboard", "Staff Directory", "Daily Attendance", "Reports & Analytics"],
}

# Icon + color per menu item, used to render the sidebar as colorful buttons (no dropdown).
MENU_ICONS = {
    "Dashboard": "📊", "Patients": "🧑‍🤝‍🧑", "Appointments": "📅", "Follow-ups": "🔁",
    "Fees & Billing": "💳", "Medicines Inventory": "💊", "Pathology Lab": "🧪", "Staff Directory": "🧑‍⚕️",
    "Daily Attendance": "🗓️", "Center Management": "🏢", "Reports & Analytics": "📈",
    "Users Management": "👤", "Billing & Upgrade": "💰",
}
MENU_COLORS = {
    "Dashboard": "#0284c7", "Patients": "#059669", "Appointments": "#7c3aed", "Follow-ups": "#db2777",
    "Fees & Billing": "#d97706", "Medicines Inventory": "#0891b2", "Pathology Lab": "#be185d", "Staff Directory": "#65a30d",
    "Daily Attendance": "#4f46e5", "Center Management": "#dc2626", "Reports & Analytics": "#0d9488",
    "Users Management": "#9333ea", "Billing & Upgrade": "#ea580c",
}


# -----------------------------------------------------------------------------
# 2. AUTHENTICATION / SAAS ONBOARDING
# -----------------------------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = None
    st.session_state["username"] = ""
    st.session_state["full_name"] = ""
    st.session_state["role"] = ""
    st.session_state["center_id"] = None
    st.session_state["license_expired"] = False

if not st.session_state["logged_in"]:
    st.title("🏥 SN Clinic Management System")
    st.caption("Cloud-based practice management, billing & patient records for clinics — SaaS Edition")
    col1, col2, col3 = st.columns([1, 1.6, 1])

    with col2:
        auth_tab1, auth_tab2 = st.tabs(
            ["🔐 Login", "🏥 Register New Clinic"]
        )

        # ---- LOGIN ----
        with auth_tab1:
            st.subheader("Login to System")
            user_input = st.text_input("Username", key="login_user")
            pass_input = st.text_input("Password", type="password", key="login_pass")

            if st.button("Login", use_container_width=True, key="login_btn"):
                conn = db.get_db()
                user = conn.execute(
                    "SELECT * FROM user WHERE username=?",
                    (user_input.strip(),),
                ).fetchone()
                if user and db.verify_password(pass_input, user["password_hash"], user["password_salt"]):
                    if not user["password_salt"]:
                        # Legacy unsalted account, verified successfully — quietly
                        # upgrade it to a salted hash so it's protected going forward.
                        new_salt, new_hash = db.make_password(pass_input)
                        conn.execute(
                            "UPDATE user SET password_hash=?, password_salt=? WHERE id=?",
                            (new_hash, new_salt, user["id"]),
                        )
                        conn.commit()
                else:
                    user = None
                conn.close()

                if user and (user["is_active"] if "is_active" in user.keys() else 1):
                    role_lower = user["role"].lower()
                    center_row = None
                    if user["center_id"]:
                        center_row = conn2 = None
                        conn2 = db.get_db()
                        center_row = conn2.execute("SELECT * FROM center WHERE id=?", (user["center_id"],)).fetchone()
                        conn2.close()

                    # Enforce clinic plan/license status (skip for platform superadmin)
                    license_expired = False
                    if role_lower != "superadmin" and center_row is not None:
                        if not center_row["is_active"]:
                            st.error("🚫 This clinic's account has been suspended. Please contact support to reactivate.")
                            st.stop()
                        plan = center_row["plan"]
                        expiry = center_row["plan_expiry"]
                        is_unlicensed = plan == "Pending"
                        is_expired = bool(expiry) and datetime.strptime(expiry, "%Y-%m-%d").date() < date.today()
                        if is_unlicensed or is_expired:
                            if role_lower == "admin":
                                # Admins can still log in (read-only, renewal only) so they can
                                # pay/activate a license to restore full access for their staff.
                                license_expired = True
                            elif is_unlicensed:
                                st.error(
                                    "🚫 This clinic hasn't been licensed yet. Please ask your clinic "
                                    "Admin to activate a license key."
                                )
                                st.stop()
                            else:
                                st.error(
                                    f"⏰ Your clinic's **{plan}** plan expired on {expiry}. "
                                    f"Please ask your clinic Admin to renew the plan."
                                )
                                st.stop()

                    st.session_state["logged_in"] = True
                    st.session_state["user_id"] = user["id"]
                    st.session_state["username"] = user["username"]
                    st.session_state["full_name"] = user["full_name"] or user["username"]
                    st.session_state["role"] = role_lower
                    st.session_state["center_id"] = user["center_id"] if "center_id" in user.keys() else None
                    st.session_state["license_expired"] = license_expired
                    st.success("Login Successful!")
                    st.rerun()
                elif user:
                    st.error("This account has been deactivated. Contact your clinic admin.")
                else:
                    st.error("Invalid Username or Password")

        # ---- REGISTER NEW CLINIC (new tenant / SaaS signup) ----
        with auth_tab2:
            st.subheader("Register Your Clinic")
            st.caption("Creates a brand-new, isolated workspace for your clinic and makes you the "
                       "Admin. A valid license key is required to activate it — no free trial.")
            clinic_name = st.text_input("Clinic / Hospital Name *", key="rc_name")
            clinic_city = st.text_input("City *", key="rc_city")
            clinic_address = st.text_input("Address", key="rc_address")
            clinic_phone = st.text_input("Contact Phone", key="rc_phone")
            st.markdown("**Admin Account**")
            rc_user = st.text_input("Admin Username *", key="rc_user").strip()
            rc_full_name = st.text_input("Your Full Name *", key="rc_full_name")
            rc_pass = st.text_input("Password *", type="password", key="rc_pass")
            rc_conf = st.text_input("Confirm Password *", type="password", key="rc_conf")
            st.markdown("**License**")
            rc_license_key = st.text_input(
                "License Key *", key="rc_license_key",
                placeholder="SNCLY-XXXXX-XXXXX-XXXXX or SNCLM-XXXXX-XXXXX-XXXXX",
            ).strip()

            if st.button("Create My Clinic", use_container_width=True, key="rc_btn"):
                if not all([clinic_name, clinic_city, rc_user, rc_full_name, rc_pass, rc_license_key]):
                    st.error("Please fill all required (*) fields, including the license key.")
                elif rc_pass != rc_conf:
                    st.error("Passwords do not match!")
                else:
                    key_valid, key_msg, _ = lic.validate_key(rc_license_key)
                    if not key_valid:
                        st.error(f"License key problem: {key_msg}")
                    else:
                        conn = db.get_db()
                        try:
                            code = db.next_center_code()
                            conn.execute(
                                """INSERT INTO center (center_code, name, city, address, phone, plan, plan_expiry, is_active, created_at)
                                   VALUES (?, ?, ?, ?, ?, 'Pending', NULL, 1, ?)""",
                                (code, clinic_name, clinic_city, clinic_address, clinic_phone, db.now()),
                            )
                            new_center_id = conn.execute(
                                "SELECT id FROM center WHERE center_code=?", (code,)
                            ).fetchone()["id"]

                            new_salt, new_hash = db.make_password(rc_pass)
                            conn.execute(
                                """INSERT INTO user (username, password_hash, password_salt, full_name, role, center_id, is_active, created_at)
                                   VALUES (?, ?, ?, ?, 'admin', ?, 1, ?)""",
                                (rc_user, new_hash, new_salt, rc_full_name, new_center_id, db.now()),
                            )
                            conn.commit()

                            activated, activate_msg, _ = lic.activate_key(rc_license_key, new_center_id)
                            if activated:
                                st.success(
                                    f"🎉 '{clinic_name}' registered and activated (Code: {code})! "
                                    f"{activate_msg} Please login with your new admin account."
                                )
                            else:
                                # Extremely rare race condition (key used by someone else between
                                # validate and activate) — clinic exists but isn't licensed yet.
                                st.warning(
                                    f"Clinic '{clinic_name}' was created, but the license could not "
                                    f"be activated: {activate_msg} Please log in as Admin and try "
                                    f"activating a key again from Billing & Upgrade."
                                )
                        except Exception as e:
                            conn.rollback()
                            if "UNIQUE" in str(e):
                                st.error("That username is already taken. Please choose another.")
                            else:
                                st.error(f"Could not create clinic: {e}")
                        finally:
                            conn.close()

        # Staff accounts (doctor/receptionist/hr) are no longer self-signed-up.
        # A clinic's Admin creates them directly from Users Management after
        # logging in, and shares the username/password with that staff
        # member — this is the only way a new login gets added to a clinic,
        # so nobody can pick an arbitrary clinic off a public dropdown and
        # grant themselves access to it.

    st.stop()


# -----------------------------------------------------------------------------
# 3. SIDEBAR NAVIGATION
# -----------------------------------------------------------------------------
st.sidebar.title("🏥 SN Clinic")
center_label = db.get_center_name(st.session_state["center_id"]) if st.session_state["role"] != "superadmin" else "All Clinics"
st.sidebar.write(f"**{st.session_state['full_name']}**")
st.sidebar.caption(f"`{st.session_state['role']}` · {center_label}")

if st.session_state["role"] != "superadmin" and st.session_state["center_id"]:
    _conn_plan = db.get_db()
    _c = _conn_plan.execute("SELECT plan, plan_expiry FROM center WHERE id=?", (st.session_state["center_id"],)).fetchone()
    _conn_plan.close()
    if _c:
        _days_left = None
        if _c["plan_expiry"]:
            _days_left = (datetime.strptime(_c["plan_expiry"], "%Y-%m-%d").date() - date.today()).days
        badge_text = f"{_c['plan']} Plan"
        if _days_left is not None:
            badge_text += f" · {_days_left} day(s) left" if _days_left >= 0 else " · Expired"
        st.sidebar.markdown(f'<span class="plan-badge">{badge_text}</span>', unsafe_allow_html=True)

selected_city = "All Cities"
if st.session_state["role"] == "superadmin":
    all_cities = db.get_unique_cities()
    selected_city = st.sidebar.selectbox("🌆 Filter by City / Branch", options=all_cities)
    st.sidebar.markdown("---")
else:
    selected_city = db.get_user_city(st.session_state["center_id"])

menu = ROLE_MENU.get(st.session_state["role"], ["Dashboard"])
if st.session_state.get("license_expired"):
    menu = ["Billing & Upgrade"]
    st.sidebar.error("⏰ Your plan needs attention. Activate a license below to restore full access.")

if "nav_choice" not in st.session_state or st.session_state["nav_choice"] not in menu:
    st.session_state["nav_choice"] = menu[0]

st.sidebar.markdown("##### Menu")
for idx, item in enumerate(menu):
    color = MENU_COLORS.get(item, "#0284c7")
    icon = MENU_ICONS.get(item, "•")
    is_active = st.session_state["nav_choice"] == item
    btn_key = f"navbtn_{idx}"
    with st.sidebar.container(key=btn_key):
        if st.button(f"{icon}  {item}", use_container_width=True, key=f"nav_{item}"):
            st.session_state["nav_choice"] = item
            st.rerun()
    ring = "0 0 0 3px rgba(0,0,0,0.35) inset" if is_active else "none"
    st.sidebar.markdown(
        f"""<style>
        .st-key-{btn_key} button {{
            background-color: {color} !important;
            color: white !important;
            border: none !important;
            font-weight: 600 !important;
            box-shadow: {ring} !important;
            text-align: left !important;
        }}
        .st-key-{btn_key} button:hover {{ filter: brightness(1.12); color: white !important; }}
        .st-key-{btn_key} button p {{ color: white !important; font-weight: 600 !important; }}
        </style>""",
        unsafe_allow_html=True,
    )

choice = st.session_state["nav_choice"]

st.sidebar.markdown("---")
with st.sidebar.container(key="navbtn_logout"):
    logout_clicked = st.button("🔴  Logout", use_container_width=True, key="logout_btn")
st.sidebar.markdown(
    """<style>
    .st-key-navbtn_logout button {
        background-color: #ef4444 !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
    }
    .st-key-navbtn_logout button:hover { filter: brightness(1.1); }
    .st-key-navbtn_logout button p { color: white !important; font-weight: 600 !important; }
    </style>""",
    unsafe_allow_html=True,
)
if logout_clicked:
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()

conn = db.get_db()
today_str = date.today().isoformat()

# scope: which center(s) the current user is allowed to see
my_center_id = st.session_state["center_id"]
is_superadmin = st.session_state["role"] == "superadmin"

# -----------------------------------------------------------------------------
# MODULE: DASHBOARD
# -----------------------------------------------------------------------------
if choice == "Dashboard":
    st.markdown(
        f"<h1>📊 Clinic Overview {f'({selected_city})' if is_superadmin and selected_city != 'All Cities' else ''}</h1>",
        unsafe_allow_html=True,
    )

    if st.session_state["role"] == "admin" and my_center_id:
        demo_present = dd.has_demo_data(my_center_id)
        with st.expander("🧪 Demo Data (sample patients, staff, bills, etc. for exploring the app)"):
            if demo_present:
                st.info("Demo data is currently loaded in this clinic.")
                if st.button("🗑️ Remove All Demo Data", key="remove_demo_btn"):
                    result = dd.remove_demo_data(my_center_id)
                    if result["removed"]:
                        st.success("Demo data removed successfully.")
                        st.rerun()
                    else:
                        st.error(f"Could not remove demo data: {result.get('reason')}")
            else:
                st.caption("Instantly fill this clinic with sample patients, staff, appointments, "
                           "bills, medicines, and more — great for exploring the app or giving a demo. "
                           "Everything added here is clearly tagged and can be removed with one click.")
                if st.button("➕ Add Sample Demo Data", key="add_demo_btn"):
                    result = dd.add_demo_data(my_center_id)
                    if result["added"]:
                        c = result["counts"]
                        st.success(
                            f"Demo data added: {c['patients']} patients, {c['staff']} staff, "
                            f"{c['appointments']} appointments, {c['bills']} bills, "
                            f"{c['medicines']} medicines, {c['expenses']} expenses, and more."
                        )
                        st.rerun()
                    else:
                        st.error(f"Could not add demo data: {result.get('reason')}")

    try:
        if is_superadmin:
            if selected_city == "All Cities":
                total_patients = conn.execute("SELECT COUNT(*) FROM patient").fetchone()[0]
                new_today = conn.execute("SELECT COUNT(*) FROM patient WHERE DATE(created_at)=?", (today_str,)).fetchone()[0]
                appts_today = conn.execute("SELECT COUNT(*) FROM appointment WHERE appt_date=?", (today_str,)).fetchone()[0]
                fees_today = conn.execute("SELECT SUM(total) FROM fee WHERE DATE(paid_on)=?", (today_str,)).fetchone()[0] or 0
                followups_due = conn.execute("SELECT COUNT(*) FROM consultation WHERE next_visit IS NOT NULL AND next_visit >= ?", (today_str,)).fetchone()[0]
                low_stock = conn.execute("SELECT COUNT(*) FROM medicine WHERE stock <= low_stock_alert").fetchone()[0]
                total_centers = conn.execute("SELECT COUNT(*) FROM center WHERE is_active=1").fetchone()[0]
            else:
                total_patients = conn.execute("SELECT COUNT(*) FROM patient p JOIN center c ON p.center_id=c.id WHERE c.city=?", (selected_city,)).fetchone()[0]
                new_today = conn.execute("SELECT COUNT(*) FROM patient p JOIN center c ON p.center_id=c.id WHERE DATE(p.created_at)=? AND c.city=?", (today_str, selected_city)).fetchone()[0]
                appts_today = conn.execute("SELECT COUNT(*) FROM appointment a JOIN patient p ON a.patient_id=p.id JOIN center c ON p.center_id=c.id WHERE a.appt_date=? AND c.city=?", (today_str, selected_city)).fetchone()[0]
                fees_today = conn.execute("SELECT SUM(f.total) FROM fee f JOIN patient p ON f.patient_id=p.id JOIN center c ON p.center_id=c.id WHERE DATE(f.paid_on)=? AND c.city=?", (today_str, selected_city)).fetchone()[0] or 0
                followups_due = conn.execute("SELECT COUNT(*) FROM consultation con JOIN patient p ON con.patient_id=p.id JOIN center c ON p.center_id=c.id WHERE con.next_visit IS NOT NULL AND con.next_visit >= ? AND c.city=?", (today_str, selected_city)).fetchone()[0]
                low_stock = conn.execute("SELECT COUNT(*) FROM medicine m JOIN center c ON m.center_id=c.id WHERE m.stock <= m.low_stock_alert AND c.city=?", (selected_city,)).fetchone()[0]
                total_centers = conn.execute("SELECT COUNT(*) FROM center WHERE city=? AND is_active=1", (selected_city,)).fetchone()[0]
        else:
            total_patients = conn.execute("SELECT COUNT(*) FROM patient WHERE center_id=?", (my_center_id,)).fetchone()[0]
            new_today = conn.execute("SELECT COUNT(*) FROM patient WHERE DATE(created_at)=? AND center_id=?", (today_str, my_center_id)).fetchone()[0]
            appts_today = conn.execute("SELECT COUNT(*) FROM appointment WHERE appt_date=? AND center_id=?", (today_str, my_center_id)).fetchone()[0]
            fees_today = conn.execute("SELECT SUM(total) FROM fee WHERE DATE(paid_on)=? AND center_id=?", (today_str, my_center_id)).fetchone()[0] or 0
            followups_due = conn.execute("SELECT COUNT(*) FROM consultation WHERE next_visit IS NOT NULL AND next_visit >= ? AND center_id=?", (today_str, my_center_id)).fetchone()[0]
            low_stock = conn.execute("SELECT COUNT(*) FROM medicine WHERE stock <= low_stock_alert AND center_id=?", (my_center_id,)).fetchone()[0]
            total_centers = 1
    except Exception:
        total_patients = new_today = appts_today = followups_due = low_stock = total_centers = 0
        fees_today = 0.0

    cols = st.columns(4) if is_superadmin else st.columns(3)
    colored_metric(cols[0], "Total Patients", total_patients, "#0284c7", f"+{new_today} Today", "🧑‍🤝‍🧑")
    colored_metric(cols[1], "Today's Appointments", appts_today, "#7c3aed", icon="📅")
    colored_metric(cols[2], "Today's Collection", f"₹{fees_today:,.2f}", "#059669", icon="💰")
    if is_superadmin:
        colored_metric(cols[3], "Active Clinics", total_centers, "#dc2626", icon="🏢")

    st.write("")
    c4, c5 = st.columns(2)
    colored_metric(c4, "Low Stock Alert", low_stock, "#d97706", icon="💊")
    colored_metric(c5, "Follow-ups Scheduled", followups_due, "#db2777", icon="🔁")

    st.markdown("---")
    st.markdown("<h3>📋 Today's Appointments</h3>", unsafe_allow_html=True)

    try:
        appt_query = """SELECT a.id, p.patient_code, p.name as patient_name, c.city, c.name as center_name,
                                a.doctor_name, a.appt_time, a.status
                       FROM appointment a
                       LEFT JOIN patient p ON a.patient_id = p.id
                       LEFT JOIN center c ON p.center_id = c.id
                       WHERE a.appt_date = ?"""
        params = [today_str]
        if is_superadmin:
            if selected_city != "All Cities":
                appt_query += " AND c.city = ?"
                params.append(selected_city)
        else:
            appt_query += " AND a.center_id = ?"
            params.append(my_center_id)
        appt_query += " ORDER BY a.id DESC"

        appts_df = db.read_sql(appt_query, conn, params=params)
        if not appts_df.empty:
            st.dataframe(appts_df, use_container_width=True, hide_index=True)
        else:
            st.info("No appointments scheduled for today.")
    except Exception:
        st.info("No appointments found.")

# -----------------------------------------------------------------------------
# MODULE: PATIENTS
# -----------------------------------------------------------------------------
elif choice == "Patients":
    st.title("👨‍👩‍👧‍👦 Patient Management")

    t1, t2, t3 = st.tabs(["📋 Patients List", "➕ Register New Patient", "📄 Patient Detail & History"])

    with t1:
        q = st.text_input("🔍 Search Patient by Name, Mobile or Code", "")
        try:
            query = """SELECT p.id, p.patient_code, p.name, p.guardian_name, p.age, p.gender, p.mobile,
                              p.address, c.name as center_name, c.city
                       FROM patient p LEFT JOIN center c ON p.center_id=c.id WHERE 1=1"""
            params = []
            if is_superadmin:
                if selected_city != "All Cities":
                    query += " AND c.city = ?"
                    params.append(selected_city)
            else:
                query += " AND p.center_id = ?"
                params.append(my_center_id)

            if q:
                query += " AND (p.name LIKE ? OR p.mobile LIKE ? OR p.patient_code LIKE ?)"
                params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

            query += " ORDER BY p.id DESC"
            df = db.read_sql(query, conn, params=params)
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"{len(df)} patient(s) found")
            if not df.empty:
                st.download_button(
                    "⬇️ Download as CSV", df.to_csv(index=False).encode("utf-8"),
                    file_name=f"patients_{today_str}.csv", mime="text/csv",
                )
        except Exception as e:
            st.error(f"Error reading patient records: {e}")

    with t2:
        with st.form("add_patient_form", clear_on_submit=True):
            st.subheader("Register New Patient")
            colA, colB = st.columns(2)
            with colA:
                name = st.text_input("Patient Name *")
                guardian = st.text_input("Guardian / Father's Name")
                age = st.number_input("Age", min_value=0, max_value=130, value=0)
                gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            with colB:
                mobile = st.text_input("Mobile Number")
                address = st.text_area("Address")
                if is_superadmin:
                    centers_map = db.get_centers_dropdown(active_only=True)
                    reg_center_id = st.selectbox(
                        "Register At Clinic *", options=list(centers_map.keys()),
                        format_func=lambda x: centers_map[x]
                    ) if centers_map else None
                else:
                    reg_center_id = my_center_id

            if st.form_submit_button("✅ Register Patient", use_container_width=True):
                if not name:
                    st.error("Patient Name is required.")
                elif not reg_center_id:
                    st.error("No clinic/center available to register this patient under.")
                else:
                    code = db.next_patient_code()
                    conn.execute(
                        """INSERT INTO patient (patient_code, name, guardian_name, age, gender, mobile,
                                                 address, center_id, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (code, name, guardian, int(age), gender, mobile, address, reg_center_id, db.now()),
                    )
                    conn.commit()
                    st.toast(f"✅ Patient '{name}' registered with code {code}!", icon="✅")
                    st.rerun()

    with t3:
        patient_map = db.get_patients_dropdown(center_id=None if is_superadmin else my_center_id)
        if not patient_map:
            st.info("No patients registered yet.")
        else:
            selected_pid = st.selectbox(
                "Select Patient", options=list(patient_map.keys()),
                format_func=lambda x: patient_map[x], key="pt_hist_sel"
            )
            p = conn.execute("SELECT * FROM patient WHERE id=?", (selected_pid,)).fetchone()

            if p:
                st.write(
                    f"**Code:** {p['patient_code']} | **Guardian:** {p['guardian_name'] or '-'} | "
                    f"**Age/Gender:** {p['age'] or '-'} / {p['gender']} | **Mobile:** {p['mobile']} | "
                    f"**Address:** {p['address'] or '-'}"
                )

                pt1, pt2, pt3 = st.tabs(["🩺 Consultation History", "💳 Fee History", "➕ Add Consultation"])
                with pt1:
                    c_df = db.read_sql(
                        "SELECT visit_date, doctor_name, symptoms, diagnosis, prescription, next_visit "
                        "FROM consultation WHERE patient_id=? ORDER BY id DESC",
                        conn, params=[selected_pid],
                    )
                    st.dataframe(c_df, use_container_width=True, hide_index=True)
                with pt2:
                    f_df = db.read_sql(
                        "SELECT paid_on, consultation_fee, medicine_fee, other_charges, discount, total, payment_mode "
                        "FROM fee WHERE patient_id=? ORDER BY id DESC",
                        conn, params=[selected_pid],
                    )
                    st.dataframe(f_df, use_container_width=True, hide_index=True)
                with pt3:
                    doctor_rows = conn.execute(
                        "SELECT name, qualification, registration_no FROM staff "
                        "WHERE center_id=? AND designation LIKE '%Doctor%' AND status='Active'",
                        (p["center_id"],)
                    ).fetchall()
                    doctor_options = {r["name"]: {"qualification": r["qualification"], "registration_no": r["registration_no"]}
                                      for r in doctor_rows}
                    doctor_names_list = list(doctor_options.keys()) + ["Other (type manually)"]

                    if "consult_nonce" not in st.session_state:
                        st.session_state["consult_nonce"] = 0
                    if "rx_items" not in st.session_state:
                        st.session_state["rx_items"] = []
                    nonce = st.session_state["consult_nonce"]

                    doc_choice = st.selectbox("Doctor *", doctor_names_list, key=f"consult_doc_choice_{nonce}")
                    if doc_choice == "Other (type manually)":
                        doc_name_final = st.text_input("Doctor Name", key=f"consult_doc_manual_{nonce}")
                        doc_qual, doc_reg = "", ""
                    else:
                        doc_name_final = doc_choice
                        doc_qual = doctor_options.get(doc_choice, {}).get("qualification") or ""
                        doc_reg = doctor_options.get(doc_choice, {}).get("registration_no") or ""

                    colA, colB = st.columns(2)
                    with colA:
                        chief_complaints = st.text_area("Chief Complaints", key=f"consult_cc_{nonce}")
                        diagnosis = st.text_area("Diagnosis", key=f"consult_diag_{nonce}")
                        weight = st.number_input("Weight (Kg)", min_value=0.0, value=0.0, step=0.5, key=f"consult_wt_{nonce}")
                    with colB:
                        clinical_findings = st.text_area("Clinical Findings", key=f"consult_cf_{nonce}")
                        advice = st.text_area("Advice", key=f"consult_advice_{nonce}")
                        height = st.number_input("Height (Cm)", min_value=0.0, value=0.0, step=1.0, key=f"consult_ht_{nonce}")

                    colC, colD, colE = st.columns(3)
                    with colC:
                        bp = st.text_input("BP (e.g. 120/80)", key=f"consult_bp_{nonce}")
                    with colD:
                        next_v = st.date_input("Follow Up / Next Visit", value=None, key=f"consult_nv_{nonce}")
                    with colE:
                        consult_fee = st.number_input("Consultation Fee (₹)", min_value=0.0, value=0.0, step=50.0, key=f"consult_fee_{nonce}")

                    st.markdown("###### 💊 Prescription (Rx)")
                    if st.session_state["rx_items"]:
                        rx_df = pd.DataFrame(st.session_state["rx_items"])
                        st.dataframe(rx_df, use_container_width=True, hide_index=True)
                        if st.button("🗑️ Clear All Medicines", key=f"clear_rx_{nonce}"):
                            st.session_state["rx_items"] = []
                            st.rerun()

                    with st.expander("➕ Add Medicine to Prescription"):
                        rx_name = st.text_input("Medicine Name", key=f"rx_name_{nonce}")
                        rx_comp = st.text_input("Composition (optional)", key=f"rx_comp_{nonce}")
                        rx_dosage = st.text_input("Dosage (e.g. 1 Morning, 1 Night)", key=f"rx_dosage_{nonce}")
                        rx_duration = st.text_input("Duration (e.g. 5 Days)", key=f"rx_duration_{nonce}")
                        rx_qty = st.text_input("Total Quantity (e.g. Tot: 10 Tab)", key=f"rx_qty_{nonce}")
                        if st.button("Add Medicine", key=f"add_rx_{nonce}"):
                            if rx_name:
                                st.session_state["rx_items"].append({
                                    "medicine_name": rx_name, "composition": rx_comp,
                                    "dosage": rx_dosage, "duration": rx_duration, "total_qty": rx_qty,
                                })
                                st.rerun()
                            else:
                                st.warning("Medicine name is required.")

                    st.markdown("###### 🧪 Order Lab Tests (optional)")
                    lab_tests_catalog = conn.execute(
                        "SELECT test_name, price, normal_range, unit FROM lab_test_catalog WHERE center_id=?", (p["center_id"],)
                    ).fetchall()
                    lab_test_labels = [f"{r['test_name']} (₹{r['price']:.0f})" for r in lab_tests_catalog]
                    selected_tests = st.multiselect("Select tests to order for this patient", lab_test_labels, key=f"lab_tests_{nonce}")
                    if not lab_test_labels:
                        st.caption("No tests in your Lab Test Catalog yet — add some under the Pathology Lab menu.")

                    if st.button("💾 Save Consultation", key=f"save_consult_{nonce}", use_container_width=True):
                        if not doc_name_final:
                            st.error("Doctor name is required.")
                        else:
                            v_date = db.now()
                            nv_str = str(next_v) if next_v else None
                            cur = conn.execute(
                                """INSERT INTO consultation (patient_id, visit_date, symptoms, diagnosis, prescription,
                                                              next_visit, doctor_name, center_id, chief_complaints,
                                                              clinical_findings, weight, height, bp, advice)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (selected_pid, v_date, chief_complaints, diagnosis, "", nv_str, doc_name_final,
                                 p["center_id"], chief_complaints, clinical_findings,
                                 weight or None, height or None, bp, advice),
                            )
                            new_consult_id = cur.lastrowid
                            for item in st.session_state["rx_items"]:
                                conn.execute(
                                    """INSERT INTO prescription_item (consultation_id, medicine_name, composition,
                                                                        dosage, duration, total_qty, center_id)
                                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                                    (new_consult_id, item["medicine_name"], item["composition"], item["dosage"],
                                     item["duration"], item["total_qty"], p["center_id"]),
                                )
                            new_fee_id = None
                            if consult_fee > 0:
                                fee_cur = conn.execute(
                                    """INSERT INTO fee (patient_id, consultation_fee, medicine_fee, other_charges,
                                                         discount, total, payment_mode, paid_on, center_id)
                                       VALUES (?, ?, 0, 0, 0, ?, 'Cash', ?, ?)""",
                                    (selected_pid, consult_fee, consult_fee, db.now(), p["center_id"]),
                                )
                                new_fee_id = fee_cur.lastrowid
                            new_lab_order_id = None
                            if selected_tests:
                                lab_cur = conn.execute(
                                    """INSERT INTO lab_order (patient_id, doctor_name, order_date, status, center_id, consultation_id)
                                       VALUES (?, ?, ?, 'Ordered', ?, ?)""",
                                    (selected_pid, doc_name_final, db.now(), p["center_id"], new_consult_id),
                                )
                                new_lab_order_id = lab_cur.lastrowid
                                for t in selected_tests:
                                    test_name_only = t.rsplit(" (₹", 1)[0]
                                    price_row = next((r for r in lab_tests_catalog if r["test_name"] == test_name_only), None)
                                    price_val = price_row["price"] if price_row else 0
                                    range_val = price_row["normal_range"] if price_row else ""
                                    unit_val = price_row["unit"] if price_row else ""
                                    conn.execute(
                                        """INSERT INTO lab_order_item (order_id, test_name, price, normal_range, unit, status)
                                           VALUES (?, ?, ?, ?, ?, 'Pending')""",
                                        (new_lab_order_id, test_name_only, price_val, range_val, unit_val),
                                    )
                            conn.commit()

                            st.session_state["_last_consult_id"] = new_consult_id
                            st.session_state["_last_consult_doc"] = {
                                "name": doc_name_final, "qualification": doc_qual, "registration_no": doc_reg,
                            }
                            st.session_state["_last_fee_id"] = new_fee_id
                            st.session_state["_last_lab_order_id"] = new_lab_order_id
                            st.session_state["_last_lab_count"] = len(selected_tests)
                            st.session_state["rx_items"] = []
                            st.session_state["consult_nonce"] += 1
                            st.success("Consultation saved successfully!")
                            st.rerun()

                    # ---- After save: offer prescription / receipt downloads ----
                    if st.session_state.get("_last_consult_id"):
                        cid = st.session_state["_last_consult_id"]
                        c_row = conn.execute("SELECT * FROM consultation WHERE id=?", (cid,)).fetchone()
                        if c_row and c_row["patient_id"] == selected_pid:
                            rx_items_saved = conn.execute(
                                "SELECT * FROM prescription_item WHERE consultation_id=?", (cid,)
                            ).fetchall()
                            investigations_saved = conn.execute(
                                """SELECT loi.test_name FROM lab_order_item loi
                                   JOIN lab_order lo ON loi.order_id = lo.id
                                   WHERE lo.consultation_id=?""", (cid,)
                            ).fetchall()
                            clinic_row = conn.execute("SELECT * FROM center WHERE id=?", (p["center_id"],)).fetchone()
                            doctor_info = st.session_state.get("_last_consult_doc", {})
                            pdf_bytes = inv.build_prescription_pdf(
                                dict(clinic_row), doctor_info, dict(p), dict(c_row),
                                [dict(r) for r in rx_items_saved],
                                [dict(r) for r in investigations_saved],
                            )
                            st.download_button(
                                "🖨️ Download Prescription PDF", pdf_bytes,
                                file_name=f"prescription_{cid}.pdf", mime="application/pdf", key=f"dl_rx_{cid}",
                            )

                            if st.session_state.get("_last_fee_id"):
                                fee_row = conn.execute(
                                    "SELECT * FROM fee WHERE id=?", (st.session_state["_last_fee_id"],)
                                ).fetchone()
                                if fee_row:
                                    bill_pdf = inv.build_invoice_pdf(dict(clinic_row), dict(p), dict(fee_row))
                                    st.download_button(
                                        "🧾 Download Doctor's Fee Receipt", bill_pdf,
                                        file_name=f"doctor_receipt_{fee_row['id']}.pdf", mime="application/pdf",
                                        key=f"dl_docfee_{cid}",
                                    )

                            if st.session_state.get("_last_lab_order_id"):
                                st.info(
                                    f"🧪 {st.session_state.get('_last_lab_count', 0)} lab test(s) ordered — "
                                    f"go to Pathology Lab to process them and print reports/bills."
                                )

# -----------------------------------------------------------------------------
# MODULE: APPOINTMENTS
# -----------------------------------------------------------------------------
elif choice == "Appointments":
    st.title("📅 Appointments")

    t1, t2 = st.tabs(["📋 All Appointments", "➕ Book Appointment"])

    with t1:
        colf1, colf2 = st.columns(2)
        with colf1:
            filter_date = st.date_input("Filter by Date", value=date.today())
        with colf2:
            status_filter = st.selectbox("Status", ["All", "Booked", "Completed", "Cancelled", "No-Show"])

        query = """SELECT a.id, p.patient_code, p.name as patient_name, a.doctor_name, a.appt_date,
                          a.appt_time, a.reason, a.status
                   FROM appointment a LEFT JOIN patient p ON a.patient_id=p.id WHERE a.appt_date=?"""
        params = [str(filter_date)]
        if not is_superadmin:
            query += " AND a.center_id=?"
            params.append(my_center_id)
        elif selected_city != "All Cities":
            query += " AND a.center_id IN (SELECT id FROM center WHERE city=?)"
            params.append(selected_city)
        if status_filter != "All":
            query += " AND a.status=?"
            params.append(status_filter)
        query += " ORDER BY a.appt_time"

        df = db.read_sql(query, conn, params=params)
        st.dataframe(df, use_container_width=True, hide_index=True)

        if not df.empty:
            st.markdown("##### Update Appointment Status")
            appt_id = st.selectbox("Select Appointment ID", df["id"].tolist())
            new_status = st.selectbox("New Status", ["Booked", "Completed", "Cancelled", "No-Show"])
            if st.button("Update Status"):
                conn.execute("UPDATE appointment SET status=? WHERE id=?", (new_status, appt_id))
                conn.commit()
                st.success("Appointment status updated.")
                st.rerun()

    with t2:
        patient_map = db.get_patients_dropdown(center_id=None if is_superadmin else my_center_id)
        if not patient_map:
            st.info("Please register a patient first.")
        else:
            appt_doctor_rows = conn.execute(
                "SELECT DISTINCT name FROM staff WHERE center_id=? AND designation LIKE '%Doctor%' AND status='Active'"
                if not is_superadmin else
                "SELECT DISTINCT name FROM staff WHERE designation LIKE '%Doctor%' AND status='Active'",
                (my_center_id,) if not is_superadmin else (),
            ).fetchall()
            appt_doctor_names = [r["name"] for r in appt_doctor_rows] + ["Other (type manually)"]

            with st.form("book_appt_form", clear_on_submit=True):
                pid = st.selectbox("Patient *", options=list(patient_map.keys()), format_func=lambda x: patient_map[x])
                doctor_choice = st.selectbox("Doctor *", options=appt_doctor_names)
                doctor_manual = st.text_input("Doctor Name (if 'Other' selected above)") \
                    if doctor_choice == "Other (type manually)" else ""
                appt_date_in = st.date_input("Appointment Date", value=date.today())
                appt_time_in = st.time_input("Appointment Time")
                reason = st.text_area("Reason for Visit")
                if st.form_submit_button("📌 Book Appointment", use_container_width=True):
                    doctor = doctor_manual if doctor_choice == "Other (type manually)" else doctor_choice
                    patient_row = conn.execute("SELECT * FROM patient WHERE id=?", (pid,)).fetchone()
                    center_for_appt = patient_row["center_id"]
                    conn.execute(
                        """INSERT INTO appointment (patient_id, doctor_name, appt_date, appt_time, reason,
                                                     status, center_id, created_at)
                           VALUES (?, ?, ?, ?, ?, 'Booked', ?, ?)""",
                        (pid, doctor, str(appt_date_in), str(appt_time_in), reason, center_for_appt, db.now()),
                    )
                    conn.commit()
                    st.success("Appointment booked successfully!")

                    # Prepare a "Click to WhatsApp" link, pre-filled with the confirmation
                    # message — staff review and tap Send inside WhatsApp themselves.
                    clinic_row = conn.execute("SELECT name FROM center WHERE id=?", (center_for_appt,)).fetchone()
                    clinic_name = clinic_row["name"] if clinic_row else "Our Clinic"
                    wa_link, wa_note = wa.build_whatsapp_link(
                        mobile=patient_row["mobile"],
                        patient_name=patient_row["name"],
                        clinic_name=clinic_name,
                        doctor_name=doctor,
                        appt_date=str(appt_date_in),
                        appt_time=str(appt_time_in),
                    )
                    st.session_state["_last_appt_wa_link"] = wa_link
                    st.session_state["_last_appt_wa_note"] = wa_note
                    st.session_state["_last_appt_wa_preview"] = wa.build_appointment_message(
                        patient_row["name"], clinic_name, doctor, str(appt_date_in), str(appt_time_in)
                    )

            if st.session_state.get("_last_appt_wa_link"):
                st.markdown("##### 📲 Send WhatsApp Confirmation")
                st.code(st.session_state["_last_appt_wa_preview"])
                st.link_button(
                    "📲 Open WhatsApp & Send", st.session_state["_last_appt_wa_link"],
                    use_container_width=True,
                )
            elif st.session_state.get("_last_appt_wa_note"):
                st.info(f"ℹ️ {st.session_state['_last_appt_wa_note']}")

# -----------------------------------------------------------------------------
# MODULE: FOLLOW-UPS
# -----------------------------------------------------------------------------
elif choice == "Follow-ups":
    st.title("🔁 Follow-ups Due")

    query = """SELECT p.patient_code, p.name, p.mobile, con.next_visit, con.doctor_name, con.diagnosis
               FROM consultation con JOIN patient p ON con.patient_id=p.id
               WHERE con.next_visit IS NOT NULL AND con.next_visit >= ?"""
    params = [today_str]
    if not is_superadmin:
        query += " AND con.center_id=?"
        params.append(my_center_id)
    elif selected_city != "All Cities":
        query += " AND con.center_id IN (SELECT id FROM center WHERE city=?)"
        params.append(selected_city)
    query += " ORDER BY con.next_visit ASC"

    df = db.read_sql(query, conn, params=params)
    if df.empty:
        st.info("No upcoming follow-ups scheduled.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"{len(df)} follow-up(s) due.")

# -----------------------------------------------------------------------------
# MODULE: FEES & BILLING
# -----------------------------------------------------------------------------
elif choice == "Fees & Billing":
    st.title("💳 Fees & Billing")

    t1, t2 = st.tabs(["🧾 Create Bill", "📜 Billing History"])

    with t1:
        patient_map = db.get_patients_dropdown(center_id=None if is_superadmin else my_center_id)
        if not patient_map:
            st.info("Please register a patient first.")
        else:
            if "bill_form_nonce" not in st.session_state:
                st.session_state["bill_form_nonce"] = 0
            nonce = st.session_state["bill_form_nonce"]

            pid = st.selectbox("Patient *", options=list(patient_map.keys()), format_func=lambda x: patient_map[x], key="bill_pid")
            colA, colB = st.columns(2)
            with colA:
                consult_fee = st.number_input("Consultation Fee (₹)", min_value=0.0, value=0.0, step=50.0, key=f"bill_consult_fee_{nonce}")
                medicine_fee = st.number_input("Medicine Fee (₹)", min_value=0.0, value=0.0, step=50.0, key=f"bill_medicine_fee_{nonce}")
            with colB:
                other_charges = st.number_input("Other Charges (₹)", min_value=0.0, value=0.0, step=50.0, key=f"bill_other_charges_{nonce}")
                discount = st.number_input("Discount (₹)", min_value=0.0, value=0.0, step=10.0, key=f"bill_discount_{nonce}")
            payment_mode = st.selectbox("Payment Mode", ["Cash", "UPI", "Card", "Insurance", "Pending"], key="bill_payment_mode")

            total = consult_fee + medicine_fee + other_charges - discount
            st.metric("Total Payable", f"₹{total:,.2f}")

            if st.button("💾 Save Bill", use_container_width=True, key="save_bill_btn"):
                center_for_fee = conn.execute("SELECT center_id FROM patient WHERE id=?", (pid,)).fetchone()["center_id"]
                conn.execute(
                    """INSERT INTO fee (patient_id, consultation_fee, medicine_fee, other_charges, discount,
                                        total, payment_mode, paid_on, center_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (pid, consult_fee, medicine_fee, other_charges, discount, total, payment_mode,
                     db.now(), center_for_fee),
                )
                conn.commit()
                new_bill_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                st.toast(f"✅ Bill saved! Total: ₹{total:,.2f}", icon="✅")
                st.session_state["_last_bill_id"] = new_bill_id
                # Bump the nonce so the fee widgets get fresh keys (and default to 0) on rerun
                st.session_state["bill_form_nonce"] += 1
                st.rerun()

            if st.session_state.get("_last_bill_id"):
                bill_row = conn.execute("SELECT * FROM fee WHERE id=?", (st.session_state["_last_bill_id"],)).fetchone()
                if bill_row:
                    patient_row = conn.execute("SELECT * FROM patient WHERE id=?", (bill_row["patient_id"],)).fetchone()
                    clinic_row = conn.execute("SELECT * FROM center WHERE id=?", (bill_row["center_id"],)).fetchone()
                    pdf_bytes = inv.build_invoice_pdf(dict(clinic_row), dict(patient_row), dict(bill_row))
                    st.download_button(
                        "🧾 Download Invoice PDF", pdf_bytes,
                        file_name=f"invoice_INV-{bill_row['id']:06d}.pdf", mime="application/pdf",
                        key="dl_last_bill",
                    )

    with t2:
        query = """SELECT f.id, p.patient_code, p.name, f.consultation_fee, f.medicine_fee, f.other_charges,
                          f.discount, f.total, f.payment_mode, f.paid_on
                   FROM fee f LEFT JOIN patient p ON f.patient_id=p.id WHERE 1=1"""
        params = []
        if not is_superadmin:
            query += " AND f.center_id=?"
            params.append(my_center_id)
        elif selected_city != "All Cities":
            query += " AND f.center_id IN (SELECT id FROM center WHERE city=?)"
            params.append(selected_city)
        query += " ORDER BY f.id DESC"

        df = db.read_sql(query, conn, params=params)
        st.dataframe(df, use_container_width=True, hide_index=True)
        if not df.empty:
            st.metric("Total Collected (shown rows)", f"₹{df['total'].sum():,.2f}")
            st.download_button(
                "⬇️ Download Billing History as CSV", df.to_csv(index=False).encode("utf-8"),
                file_name=f"billing_{today_str}.csv", mime="text/csv",
            )

            st.markdown("##### 🧾 Reprint an Invoice")
            reprint_id = st.selectbox(
                "Select Bill", df["id"].tolist(),
                format_func=lambda x: f"INV-{x:06d} — {df[df['id']==x]['name'].values[0]}",
                key="reprint_bill_sel",
            )
            if st.button("Generate Invoice PDF", key="reprint_btn"):
                bill_row = conn.execute("SELECT * FROM fee WHERE id=?", (reprint_id,)).fetchone()
                patient_row = conn.execute("SELECT * FROM patient WHERE id=?", (bill_row["patient_id"],)).fetchone()
                clinic_row = conn.execute("SELECT * FROM center WHERE id=?", (bill_row["center_id"],)).fetchone()
                pdf_bytes = inv.build_invoice_pdf(dict(clinic_row), dict(patient_row), dict(bill_row))
                st.download_button(
                    "🧾 Download Invoice PDF", pdf_bytes,
                    file_name=f"invoice_INV-{reprint_id:06d}.pdf", mime="application/pdf",
                    key="dl_reprint_bill",
                )

# -----------------------------------------------------------------------------
# MODULE: MEDICINES INVENTORY
# -----------------------------------------------------------------------------
elif choice == "Medicines Inventory":
    st.title("💊 Medicines Inventory")

    t1, t2, t3, t4 = st.tabs(["📦 Stock List", "➕ Add / Restock Medicine", "🛒 Sell Medicine", "🧾 Sales History"])

    with t1:
        query = "SELECT id, name, batch_no, expiry_date, stock, low_stock_alert, unit_price FROM medicine WHERE 1=1"
        params = []
        if not is_superadmin:
            query += " AND center_id=?"
            params.append(my_center_id)
        elif selected_city != "All Cities":
            query += " AND center_id IN (SELECT id FROM center WHERE city=?)"
            params.append(selected_city)
        query += " ORDER BY name"

        df = db.read_sql(query, conn, params=params)
        if not df.empty:
            def flag_low(row):
                return ["background-color: #fee2e2" if row["stock"] <= row["low_stock_alert"] else "" for _ in row]
            st.dataframe(df.style.apply(flag_low, axis=1), use_container_width=True, hide_index=True)
            low = df[df["stock"] <= df["low_stock_alert"]]
            if not low.empty:
                st.warning(f"⚠️ {len(low)} medicine(s) at or below reorder level.")
        else:
            st.info("No medicines in inventory yet.")

    with t2:
        with st.form("med_form", clear_on_submit=True):
            m_name = st.text_input("Medicine Name *")
            colA, colB, colC = st.columns(3)
            with colA:
                batch = st.text_input("Batch No.")
            with colB:
                expiry = st.date_input("Expiry Date", value=None)
            with colC:
                unit_price = st.number_input("Unit Price (₹)", min_value=0.0, value=0.0, step=1.0)
            colD, colE = st.columns(2)
            with colD:
                stock_qty = st.number_input("Stock Quantity", min_value=0, value=0, step=1)
            with colE:
                low_alert = st.number_input("Low Stock Alert Threshold", min_value=0, value=10, step=1)

            if st.form_submit_button("💾 Save Medicine", use_container_width=True):
                if not m_name:
                    st.error("Medicine name is required.")
                else:
                    target_center = my_center_id if not is_superadmin else (
                        list(db.get_centers_dropdown().keys())[0] if db.get_centers_dropdown() else None
                    )
                    conn.execute(
                        """INSERT INTO medicine (name, batch_no, expiry_date, stock, low_stock_alert, unit_price, center_id)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (m_name, batch, str(expiry) if expiry else None, int(stock_qty), int(low_alert),
                         unit_price, target_center),
                    )
                    conn.commit()
                    st.success(f"'{m_name}' added to inventory.")

    with t3:
        st.caption("Sell medicines directly to a walk-in customer or patient — stock is deducted automatically "
                   "and a printable receipt is generated.")

        med_query = "SELECT id, name, stock, unit_price FROM medicine WHERE stock > 0"
        med_params = []
        if not is_superadmin:
            med_query += " AND center_id=?"
            med_params.append(my_center_id)
        med_query += " ORDER BY name"
        available_meds = conn.execute(med_query, med_params).fetchall()
        med_lookup = {f"{m['name']} (Stock: {m['stock']}, ₹{m['unit_price']:.2f})": m for m in available_meds}

        if "sale_nonce" not in st.session_state:
            st.session_state["sale_nonce"] = 0
        if "sale_cart" not in st.session_state:
            st.session_state["sale_cart"] = []
        s_nonce = st.session_state["sale_nonce"]

        patient_map_sale = db.get_patients_dropdown(center_id=None if is_superadmin else my_center_id)
        colw1, colw2 = st.columns(2)
        with colw1:
            sale_patient = st.selectbox(
                "Link to Patient (optional)", options=[None] + list(patient_map_sale.keys()),
                format_func=lambda x: "Walk-in / No patient record" if x is None else patient_map_sale[x],
                key=f"sale_patient_{s_nonce}",
            )
        with colw2:
            if sale_patient is None:
                walkin_name = st.text_input("Customer Name", key=f"walkin_name_{s_nonce}")
                walkin_mobile = st.text_input("Customer Mobile", key=f"walkin_mobile_{s_nonce}")
            else:
                walkin_name, walkin_mobile = "", ""

        if st.session_state["sale_cart"]:
            cart_df = pd.DataFrame(st.session_state["sale_cart"])
            st.dataframe(cart_df, use_container_width=True, hide_index=True)
            if st.button("🗑️ Clear Cart", key=f"clear_cart_{s_nonce}"):
                st.session_state["sale_cart"] = []
                st.rerun()

        if not med_lookup:
            st.info("No medicines with available stock. Restock under 'Add / Restock Medicine'.")
        else:
            with st.expander("➕ Add Medicine to Cart"):
                med_choice = st.selectbox("Medicine", options=list(med_lookup.keys()), key=f"cart_med_{s_nonce}")
                cart_qty = st.number_input("Quantity", min_value=1, value=1, step=1, key=f"cart_qty_{s_nonce}")
                if st.button("Add to Cart", key=f"add_cart_{s_nonce}"):
                    med_row = med_lookup[med_choice]
                    if cart_qty > med_row["stock"]:
                        st.error(f"Only {med_row['stock']} unit(s) in stock.")
                    else:
                        st.session_state["sale_cart"].append({
                            "medicine_id": med_row["id"], "medicine_name": med_row["name"],
                            "quantity": int(cart_qty), "unit_price": med_row["unit_price"],
                            "subtotal": round(med_row["unit_price"] * cart_qty, 2),
                        })
                        st.rerun()

        if st.session_state["sale_cart"]:
            cart_subtotal = sum(i["subtotal"] for i in st.session_state["sale_cart"])
            colx1, colx2, colx3 = st.columns(3)
            with colx1:
                sale_discount = st.number_input("Discount (₹)", min_value=0.0, value=0.0, step=10.0, key=f"sale_disc_{s_nonce}")
            with colx2:
                sale_payment_mode = st.selectbox("Payment Mode", ["Cash", "UPI", "Card"], key=f"sale_pay_{s_nonce}")
            with colx3:
                st.metric("Total Payable", f"₹{cart_subtotal - sale_discount:,.2f}")

            if st.button("💾 Complete Sale", use_container_width=True, key=f"complete_sale_{s_nonce}"):
                sale_center = my_center_id if not is_superadmin else conn.execute(
                    "SELECT center_id FROM medicine WHERE id=?", (st.session_state["sale_cart"][0]["medicine_id"],)
                ).fetchone()["center_id"]
                total_amt = cart_subtotal - sale_discount
                cust_name = patient_map_sale.get(sale_patient) if sale_patient else walkin_name
                cust_mobile = conn.execute("SELECT mobile FROM patient WHERE id=?", (sale_patient,)).fetchone()["mobile"] \
                    if sale_patient else walkin_mobile
                sale_cur = conn.execute(
                    """INSERT INTO medicine_sale (patient_id, customer_name, mobile, subtotal, discount, total,
                                                   payment_mode, sold_on, center_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (sale_patient, cust_name, cust_mobile, cart_subtotal, sale_discount, total_amt,
                     sale_payment_mode, db.now(), sale_center),
                )
                new_sale_id = sale_cur.lastrowid
                for item in st.session_state["sale_cart"]:
                    conn.execute(
                        """INSERT INTO medicine_sale_item (sale_id, medicine_id, medicine_name, quantity,
                                                             unit_price, subtotal)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (new_sale_id, item["medicine_id"], item["medicine_name"], item["quantity"],
                         item["unit_price"], item["subtotal"]),
                    )
                    conn.execute("UPDATE medicine SET stock = stock - ? WHERE id=?",
                                 (item["quantity"], item["medicine_id"]))
                conn.commit()

                st.session_state["_last_sale_id"] = new_sale_id
                st.session_state["sale_cart"] = []
                st.session_state["sale_nonce"] += 1
                st.success(f"Sale completed! Total: ₹{total_amt:,.2f}")
                st.rerun()

        if st.session_state.get("_last_sale_id"):
            sale_row = conn.execute("SELECT * FROM medicine_sale WHERE id=?", (st.session_state["_last_sale_id"],)).fetchone()
            if sale_row:
                sale_items = conn.execute(
                    "SELECT * FROM medicine_sale_item WHERE sale_id=?", (sale_row["id"],)
                ).fetchall()
                clinic_row = conn.execute("SELECT * FROM center WHERE id=?", (sale_row["center_id"],)).fetchone()
                receipt_pdf = inv.build_medicine_sale_receipt(
                    dict(clinic_row), sale_row["customer_name"], sale_row["mobile"],
                    [dict(r) for r in sale_items], dict(sale_row),
                )
                st.download_button(
                    "🖨️ Download Medicine Sale Receipt", receipt_pdf,
                    file_name=f"medicine_sale_{sale_row['id']}.pdf", mime="application/pdf",
                    key=f"dl_medsale_{sale_row['id']}",
                )

    with t4:
        sales_query = """SELECT ms.id, ms.customer_name, ms.mobile, ms.subtotal, ms.discount, ms.total,
                                 ms.payment_mode, ms.sold_on
                          FROM medicine_sale ms WHERE 1=1"""
        sales_params = []
        if not is_superadmin:
            sales_query += " AND ms.center_id=?"
            sales_params.append(my_center_id)
        sales_query += " ORDER BY ms.id DESC"
        sales_df = db.read_sql(sales_query, conn, params=sales_params)
        st.dataframe(sales_df, use_container_width=True, hide_index=True)
        if not sales_df.empty:
            st.metric("Total Medicine Sales Revenue (shown rows)", f"₹{sales_df['total'].sum():,.2f}")
            st.download_button(
                "⬇️ Download as CSV", sales_df.to_csv(index=False).encode("utf-8"),
                file_name=f"medicine_sales_{today_str}.csv", mime="text/csv",
            )

# -----------------------------------------------------------------------------
# MODULE: PATHOLOGY LAB (OPD-ordered tests -> lab processing -> report & bill)
# -----------------------------------------------------------------------------
elif choice == "Pathology Lab":
    st.title("🧪 Pathology Lab")

    lab_t1, lab_t2, lab_t3, lab_t4 = st.tabs([
        "🆕 Order Test", "⏳ Pending / Enter Results", "📋 Test Catalog", "✅ Completed Reports & Billing",
    ])

    # ---- Order a lab test directly (standalone, not tied to a consultation) ----
    with lab_t1:
        st.caption("Tests ordered here (or during a patient's consultation) all show up under "
                   "'Pending / Enter Results' for the lab to process.")
        patient_map_lab = db.get_patients_dropdown(center_id=None if is_superadmin else my_center_id)
        if not patient_map_lab:
            st.info("Please register a patient first.")
        else:
            lab_patient = st.selectbox("Patient *", options=list(patient_map_lab.keys()),
                                        format_func=lambda x: patient_map_lab[x], key="lab_order_patient")
            lab_doctor = st.text_input("Ordered By (Doctor Name)", key="lab_order_doctor")

            catalog_query = "SELECT test_name, price, normal_range, unit FROM lab_test_catalog WHERE center_id=?"
            patient_center = conn.execute("SELECT center_id FROM patient WHERE id=?", (lab_patient,)).fetchone()["center_id"]
            catalog_rows = conn.execute(catalog_query, (patient_center,)).fetchall()
            catalog_labels = [f"{r['test_name']} (₹{r['price']:.0f})" for r in catalog_rows]

            chosen = st.multiselect("Select Test(s) *", catalog_labels, key="lab_order_tests")
            if not catalog_labels:
                st.warning("No tests in the catalog yet — add some under the 'Test Catalog' tab first.")

            if st.button("📌 Place Lab Order", use_container_width=True, key="place_lab_order_btn"):
                if not chosen:
                    st.error("Select at least one test.")
                else:
                    order_cur = conn.execute(
                        "INSERT INTO lab_order (patient_id, doctor_name, order_date, status, center_id) "
                        "VALUES (?, ?, ?, 'Ordered', ?)",
                        (lab_patient, lab_doctor, db.now(), patient_center),
                    )
                    new_order_id = order_cur.lastrowid
                    for label in chosen:
                        test_name_only = label.rsplit(" (₹", 1)[0]
                        row = next((r for r in catalog_rows if r["test_name"] == test_name_only), None)
                        conn.execute(
                            "INSERT INTO lab_order_item (order_id, test_name, price, normal_range, unit, status) "
                            "VALUES (?, ?, ?, ?, ?, 'Pending')",
                            (new_order_id, test_name_only, row["price"] if row else 0,
                             row["normal_range"] if row else "", row["unit"] if row else ""),
                        )
                    conn.commit()
                    st.success(f"Lab order #{new_order_id} placed with {len(chosen)} test(s).")
                    st.rerun()

    # ---- Pending orders: enter results, mark complete ----
    with lab_t2:
        pending_query = """SELECT lo.id, p.name as patient_name, p.patient_code, lo.doctor_name, lo.order_date, lo.status
                            FROM lab_order lo LEFT JOIN patient p ON lo.patient_id = p.id
                            WHERE lo.status != 'Completed'"""
        pending_params = []
        if not is_superadmin:
            pending_query += " AND lo.center_id=?"
            pending_params.append(my_center_id)
        pending_query += " ORDER BY lo.id DESC"
        pending_orders = db.read_sql(pending_query, conn, params=pending_params)

        if pending_orders.empty:
            st.info("No pending lab orders.")
        else:
            st.dataframe(pending_orders, use_container_width=True, hide_index=True)
            order_id_choice = st.selectbox("Select Order ID to process", pending_orders["id"].tolist(), key="lab_process_order")
            items = conn.execute("SELECT * FROM lab_order_item WHERE order_id=?", (order_id_choice,)).fetchall()

            st.markdown("###### Enter Results")
            result_values = {}
            for item in items:
                result_values[item["id"]] = st.text_input(
                    f"{item['test_name']} (Normal: {item['normal_range'] or '-'} {item['unit'] or ''})",
                    value=item["result_value"] or "", key=f"lab_result_{item['id']}",
                )
            if st.button("💾 Save Results & Mark Completed", use_container_width=True, key="save_lab_results_btn"):
                for item_id, val in result_values.items():
                    conn.execute("UPDATE lab_order_item SET result_value=?, status='Completed' WHERE id=?", (val, item_id))
                conn.execute("UPDATE lab_order SET status='Completed' WHERE id=?", (order_id_choice,))
                conn.commit()
                st.success(f"Order #{order_id_choice} marked completed with results saved.")
                st.rerun()

    # ---- Test Catalog management ----
    with lab_t3:
        catalog_query2 = "SELECT id, test_name, price, normal_range, unit FROM lab_test_catalog WHERE 1=1"
        catalog_params2 = []
        if not is_superadmin:
            catalog_query2 += " AND center_id=?"
            catalog_params2.append(my_center_id)
        catalog_df = db.read_sql(catalog_query2, conn, params=catalog_params2)
        st.dataframe(catalog_df, use_container_width=True, hide_index=True)

        with st.expander("➕ Add Test to Catalog"):
            new_test_name = st.text_input("Test Name *", key="new_test_name")
            colt1, colt2, colt3 = st.columns(3)
            with colt1:
                new_test_price = st.number_input("Price (₹)", min_value=0.0, value=0.0, step=10.0, key="new_test_price")
            with colt2:
                new_test_range = st.text_input("Normal Range (optional)", key="new_test_range")
            with colt3:
                new_test_unit = st.text_input("Unit (optional)", key="new_test_unit")
            if st.button("Add Test", key="add_test_btn"):
                if not new_test_name:
                    st.error("Test name is required.")
                else:
                    target_center = my_center_id if not is_superadmin else (
                        list(db.get_centers_dropdown().keys())[0] if db.get_centers_dropdown() else None
                    )
                    existing_test = conn.execute(
                        "SELECT id FROM lab_test_catalog WHERE center_id=? AND LOWER(TRIM(test_name))=LOWER(TRIM(?))",
                        (target_center, new_test_name),
                    ).fetchone()
                    if existing_test:
                        st.error(f"A test named '{new_test_name}' already exists in the catalog. "
                                 f"Edit or delete it below instead of adding a duplicate.")
                    else:
                        conn.execute(
                            "INSERT INTO lab_test_catalog (test_name, price, normal_range, unit, center_id) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (new_test_name, new_test_price, new_test_range, new_test_unit, target_center),
                        )
                        conn.commit()
                        st.success(f"'{new_test_name}' added to the test catalog.")
                        st.rerun()

        if not catalog_df.empty:
            with st.expander("✏️ Edit or Delete a Test"):
                cat_map = dict(zip(catalog_df["id"], catalog_df["test_name"]))
                edit_test_id = st.selectbox("Select Test", options=list(cat_map.keys()),
                                             format_func=lambda x: cat_map[x], key="edit_test_sel")
                existing_row = conn.execute("SELECT * FROM lab_test_catalog WHERE id=?", (edit_test_id,)).fetchone()
                et_name = st.text_input("Test Name", value=existing_row["test_name"], key="et_name")
                cole1, cole2, cole3 = st.columns(3)
                with cole1:
                    et_price = st.number_input("Price (₹)", min_value=0.0, value=float(existing_row["price"] or 0), step=10.0, key="et_price")
                with cole2:
                    et_range = st.text_input("Normal Range", value=existing_row["normal_range"] or "", key="et_range")
                with cole3:
                    et_unit = st.text_input("Unit", value=existing_row["unit"] or "", key="et_unit")
                cbtn1, cbtn2 = st.columns(2)
                if cbtn1.button("💾 Save Changes", key="save_test_edit", use_container_width=True):
                    conn.execute(
                        "UPDATE lab_test_catalog SET test_name=?, price=?, normal_range=?, unit=? WHERE id=?",
                        (et_name, et_price, et_range, et_unit, edit_test_id),
                    )
                    conn.commit()
                    st.success("Test updated.")
                    st.rerun()
                if cbtn2.button("🗑️ Delete Test", key="delete_test_btn", use_container_width=True):
                    conn.execute("DELETE FROM lab_test_catalog WHERE id=?", (edit_test_id,))
                    conn.commit()
                    st.success("Test deleted.")
                    st.rerun()

    # ---- Completed orders: reports + billing ----
    with lab_t4:
        completed_query = """SELECT lo.id, p.name as patient_name, lo.doctor_name, lo.order_date
                              FROM lab_order lo LEFT JOIN patient p ON lo.patient_id = p.id
                              WHERE lo.status='Completed'"""
        completed_params = []
        if not is_superadmin:
            completed_query += " AND lo.center_id=?"
            completed_params.append(my_center_id)
        completed_query += " ORDER BY lo.id DESC"
        completed_orders = conn.execute(completed_query, completed_params).fetchall()

        if not completed_orders:
            st.info("No completed lab orders yet.")
        else:
            completed_map = {r["id"]: f"#{r['id']} — {r['patient_name']} ({r['order_date']})" for r in completed_orders}
            chosen_order = st.selectbox("Select Completed Order", options=list(completed_map.keys()),
                                         format_func=lambda x: completed_map[x], key="completed_order_sel")
            order_row = conn.execute("SELECT * FROM lab_order WHERE id=?", (chosen_order,)).fetchone()
            order_items_rows = conn.execute("SELECT * FROM lab_order_item WHERE order_id=?", (chosen_order,)).fetchall()
            patient_row = conn.execute("SELECT * FROM patient WHERE id=?", (order_row["patient_id"],)).fetchone()
            clinic_row = conn.execute("SELECT * FROM center WHERE id=?", (order_row["center_id"],)).fetchone()

            st.dataframe(pd.DataFrame([dict(r) for r in order_items_rows]), use_container_width=True, hide_index=True)
            total_lab_amount = sum(r["price"] or 0 for r in order_items_rows)
            st.metric("Total Test Amount", f"₹{total_lab_amount:,.2f}")
            lab_payment_mode = st.selectbox("Payment Mode", ["Cash", "UPI", "Card", "Pending"], key="lab_bill_pay_mode")

            colr1, colr2 = st.columns(2)
            with colr1:
                report_pdf = inv.build_lab_report_pdf(
                    dict(clinic_row), dict(patient_row), dict(order_row), [dict(r) for r in order_items_rows]
                )
                st.download_button(
                    "🖨️ Download Lab Report", report_pdf,
                    file_name=f"lab_report_{chosen_order}.pdf", mime="application/pdf", key=f"dl_labreport_{chosen_order}",
                )
            with colr2:
                bill_pdf = inv.build_lab_bill_pdf(
                    dict(clinic_row), dict(patient_row), dict(order_row),
                    [dict(r) for r in order_items_rows], total_lab_amount, lab_payment_mode,
                )
                st.download_button(
                    "🧾 Download Lab Bill", bill_pdf,
                    file_name=f"lab_bill_{chosen_order}.pdf", mime="application/pdf", key=f"dl_labbill_{chosen_order}",
                )

# -----------------------------------------------------------------------------
# MODULE: STAFF DIRECTORY
# -----------------------------------------------------------------------------
elif choice == "Staff Directory":
    st.title("🧑‍⚕️ Staff Directory")

    t1, t2, t3 = st.tabs(["📋 Staff List", "➕ Add Staff Member", "✏️ Edit Staff Member"])

    with t1:
        query = """SELECT s.employee_code, s.name, s.designation, s.qualification, s.registration_no,
                          s.mobile, s.city, s.joining_date, s.salary, s.status, c.name as center_name
                   FROM staff s LEFT JOIN center c ON s.center_id=c.id WHERE 1=1"""
        params = []
        if not is_superadmin:
            query += " AND s.center_id=?"
            params.append(my_center_id)
        elif selected_city != "All Cities":
            query += " AND c.city=?"
            params.append(selected_city)
        query += " ORDER BY s.name"

        df = db.read_sql(query, conn, params=params)
        st.dataframe(df, use_container_width=True, hide_index=True)

    with t2:
        with st.form("staff_form", clear_on_submit=True):
            s_name = st.text_input("Full Name *")
            colA, colB = st.columns(2)
            with colA:
                designation = st.text_input("Designation")
                mobile = st.text_input("Mobile Number")
                joining = st.date_input("Joining Date", value=date.today())
                qualification = st.text_input("Qualification (e.g. M.S., MBBS) — for Doctors")
            with colB:
                city = st.text_input("City")
                address = st.text_area("Address")
                salary = st.number_input("Monthly Salary (₹)", min_value=0.0, value=0.0, step=500.0)
                registration_no = st.text_input("Registration No. (e.g. MMC 2018) — for Doctors")

            if is_superadmin:
                centers_map = db.get_centers_dropdown(active_only=True)
                staff_center = st.selectbox(
                    "Assign to Clinic *", options=list(centers_map.keys()), format_func=lambda x: centers_map[x]
                ) if centers_map else None
            else:
                staff_center = my_center_id

            if st.form_submit_button("✅ Add Staff Member", use_container_width=True):
                if not s_name:
                    st.error("Name is required.")
                elif not staff_center:
                    st.error("No clinic available to assign this staff member to.")
                else:
                    emp_code = db.next_employee_code()
                    conn.execute(
                        """INSERT INTO staff (employee_code, name, designation, mobile, city, address,
                                               joining_date, salary, status, center_id, created_at,
                                               qualification, registration_no)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active', ?, ?, ?, ?)""",
                        (emp_code, s_name, designation, mobile, city, address, str(joining), salary,
                         staff_center, db.now(), qualification, registration_no),
                    )
                    conn.commit()
                    st.success(f"Staff member '{s_name}' added with code {emp_code}.")

    with t3:
        staff_query = "SELECT id, employee_code, name FROM staff WHERE 1=1"
        staff_params = []
        if not is_superadmin:
            staff_query += " AND center_id=?"
            staff_params.append(my_center_id)
        staff_query += " ORDER BY name"
        staff_options = conn.execute(staff_query, staff_params).fetchall()

        if not staff_options:
            st.info("No staff members to edit yet.")
        else:
            staff_map = {r["id"]: f"{r['name']} ({r['employee_code']})" for r in staff_options}
            edit_id = st.selectbox(
                "Select Staff Member to Edit", options=list(staff_map.keys()),
                format_func=lambda x: staff_map[x], key="edit_staff_sel"
            )
            s_row = conn.execute("SELECT * FROM staff WHERE id=?", (edit_id,)).fetchone()

            if s_row:
                with st.form("edit_staff_form"):
                    e_name = st.text_input("Full Name *", value=s_row["name"])
                    colA, colB = st.columns(2)
                    with colA:
                        e_designation = st.text_input("Designation", value=s_row["designation"] or "")
                        e_mobile = st.text_input("Mobile Number", value=s_row["mobile"] or "")
                        e_joining = st.date_input(
                            "Joining Date",
                            value=datetime.strptime(s_row["joining_date"], "%Y-%m-%d").date()
                            if s_row["joining_date"] else date.today(),
                        )
                        e_qualification = st.text_input("Qualification", value=s_row["qualification"] or "")
                    with colB:
                        e_city = st.text_input("City", value=s_row["city"] or "")
                        e_address = st.text_area("Address", value=s_row["address"] or "")
                        e_salary = st.number_input(
                            "Monthly Salary (₹)", min_value=0.0,
                            value=float(s_row["salary"] or 0), step=500.0
                        )
                        e_registration_no = st.text_input("Registration No.", value=s_row["registration_no"] or "")
                    e_status = st.selectbox(
                        "Status", ["Active", "Inactive"],
                        index=0 if s_row["status"] == "Active" else 1,
                    )

                    colbtn1, colbtn2 = st.columns(2)
                    save_clicked = colbtn1.form_submit_button("💾 Save Changes", use_container_width=True)
                    delete_clicked = colbtn2.form_submit_button("🗑️ Delete Staff Member", use_container_width=True)

                    if save_clicked:
                        if not e_name:
                            st.error("Name is required.")
                        else:
                            conn.execute(
                                """UPDATE staff SET name=?, designation=?, mobile=?, city=?, address=?,
                                                     joining_date=?, salary=?, status=?, qualification=?,
                                                     registration_no=? WHERE id=?""",
                                (e_name, e_designation, e_mobile, e_city, e_address,
                                 str(e_joining), e_salary, e_status, e_qualification, e_registration_no, edit_id),
                            )
                            conn.commit()
                            st.success(f"'{e_name}' updated successfully.")
                            st.rerun()

                    if delete_clicked:
                        conn.execute("DELETE FROM staff WHERE id=?", (edit_id,))
                        conn.commit()
                        st.success("Staff member deleted.")
                        st.rerun()

# -----------------------------------------------------------------------------
# MODULE: DAILY ATTENDANCE
# -----------------------------------------------------------------------------
elif choice == "Daily Attendance":
    st.title("🗓️ Daily Attendance")

    att_date = st.date_input("Attendance Date", value=date.today())

    staff_query = "SELECT id, employee_code, name FROM staff WHERE status='Active'"
    staff_params = []
    if not is_superadmin:
        staff_query += " AND center_id=?"
        staff_params.append(my_center_id)
    elif selected_city != "All Cities":
        staff_query += " AND center_id IN (SELECT id FROM center WHERE city=?)"
        staff_params.append(selected_city)
    staff_query += " ORDER BY name"

    staff_df = db.read_sql(staff_query, conn, params=staff_params)

    if staff_df.empty:
        st.info("No active staff found.")
    else:
        existing = db.read_sql(
            "SELECT staff_id, status FROM attendance WHERE att_date=?", conn, params=[str(att_date)]
        )
        existing_map = dict(zip(existing["staff_id"], existing["status"])) if not existing.empty else {}

        with st.form("attendance_form"):
            st.caption(f"Marking attendance for {att_date}")
            statuses = {}
            for _, row in staff_df.iterrows():
                default = existing_map.get(row["id"], "Present")
                statuses[row["id"]] = st.selectbox(
                    f"{row['name']} ({row['employee_code']})",
                    ["Present", "Absent", "Half Day", "Leave"],
                    index=["Present", "Absent", "Half Day", "Leave"].index(default) if default in ["Present", "Absent", "Half Day", "Leave"] else 0,
                    key=f"att_{row['id']}",
                )
            if st.form_submit_button("💾 Save Attendance", use_container_width=True):
                for staff_id, status_val in statuses.items():
                    already = conn.execute(
                        "SELECT id FROM attendance WHERE staff_id=? AND att_date=?", (staff_id, str(att_date))
                    ).fetchone()
                    if already:
                        conn.execute("UPDATE attendance SET status=? WHERE id=?", (status_val, already["id"]))
                    else:
                        conn.execute(
                            "INSERT INTO attendance (staff_id, att_date, status) VALUES (?, ?, ?)",
                            (staff_id, str(att_date), status_val),
                        )
                conn.commit()
                st.success("Attendance saved successfully!")
                st.rerun()

    st.markdown("---")
    st.markdown("##### 📊 Attendance History")
    hist_query = """SELECT s.employee_code, s.name, a.att_date, a.status
                     FROM attendance a JOIN staff s ON a.staff_id=s.id WHERE 1=1"""
    hist_params = []
    if not is_superadmin:
        hist_query += " AND s.center_id=?"
        hist_params.append(my_center_id)
    hist_query += " ORDER BY a.att_date DESC LIMIT 200"
    hist_df = db.read_sql(hist_query, conn, params=hist_params)
    st.dataframe(hist_df, use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# MODULE: CENTER MANAGEMENT (SaaS tenant admin - superadmin only)
# -----------------------------------------------------------------------------
elif choice == "Center Management":
    st.title("🏢 Center / Clinic Management")

    if not is_superadmin:
        st.error("You do not have permission to view this page.")
    else:
        t1, t2, t3 = st.tabs(["📋 All Clinics", "➕ Add New Clinic", "🔑 License Keys"])

        with t1:
            df = db.read_sql(
                "SELECT id, center_code, name, city, phone, plan, plan_expiry, is_active, created_at FROM center ORDER BY id DESC",
                conn,
            )
            st.dataframe(df, use_container_width=True, hide_index=True)

            if not df.empty:
                st.markdown("##### Update Clinic Plan / Status")
                cid = st.selectbox("Select Clinic", df["id"].tolist(),
                                    format_func=lambda x: df[df["id"] == x]["name"].values[0])
                new_plan = st.selectbox("Plan", ["Trial", "Licensed - Monthly", "Licensed - Yearly",
                                                  "Basic", "Pro", "Enterprise"])
                new_expiry = st.date_input("Plan Expiry", value=None)
                active_toggle = st.checkbox("Active", value=True)
                if st.button("Update Clinic"):
                    conn.execute(
                        "UPDATE center SET plan=?, plan_expiry=?, is_active=? WHERE id=?",
                        (new_plan, str(new_expiry) if new_expiry else None, int(active_toggle), cid),
                    )
                    conn.commit()
                    st.success("Clinic updated.")
                    st.rerun()

        with t2:
            with st.form("center_form", clear_on_submit=True):
                c_name = st.text_input("Clinic Name *")
                c_city = st.text_input("City *")
                c_address = st.text_input("Address")
                c_phone = st.text_input("Phone")
                c_plan = st.selectbox("Starting Plan", ["Trial", "Licensed - Monthly", "Licensed - Yearly",
                                                          "Basic", "Pro", "Enterprise"])
                if st.form_submit_button("✅ Add Clinic", use_container_width=True):
                    if not c_name or not c_city:
                        st.error("Name and City are required.")
                    else:
                        code = db.next_center_code()
                        conn.execute(
                            """INSERT INTO center (center_code, name, city, address, phone, plan, is_active, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                            (code, c_name, c_city, c_address, c_phone, c_plan, db.now()),
                        )
                        conn.commit()
                        st.success(f"Clinic '{c_name}' added with code {code}.")

        with t3:
            st.caption("These are the 1-year activation codes clinics enter under "
                       "Billing & Upgrade → Activate License Key.")
            key_rows = lic.list_keys()
            key_df = pd.DataFrame(key_rows)
            if not key_df.empty:
                unused_count = (key_df["status"] == "Unused").sum()
                used_count = (key_df["status"] == "Used").sum()
                colk1, colk2 = st.columns(2)
                colored_metric(colk1, "Unused Keys", unused_count, "#059669", icon="🔑")
                colored_metric(colk2, "Activated Keys", used_count, "#7c3aed", icon="✅")
                st.write("")
                st.download_button(
                    "⬇️ Download All Keys as CSV", key_df.to_csv(index=False).encode("utf-8"),
                    file_name="license_keys.csv", mime="text/csv",
                )
            else:
                st.info("No license keys found.")

            st.markdown("---")
            st.subheader("Generate More Keys")
            gen_type = st.selectbox("Key Type", ["Monthly (30 days)", "Yearly (365 days)", "Custom"])
            if gen_type == "Custom":
                gen_duration = st.number_input("Duration (days)", min_value=1, max_value=3650, value=30)
            else:
                gen_duration = 30 if gen_type.startswith("Monthly") else 365
            gen_count = st.number_input("How many new keys?", min_value=1, max_value=100, value=10)
            if st.button("🔑 Generate Keys", use_container_width=True):
                new_keys = lic.create_new_keys(count=int(gen_count), duration_days=int(gen_duration))
                st.success(f"Generated {len(new_keys)} new license key(s), valid {int(gen_duration)} days each.")
                st.code("\n".join(new_keys))

# -----------------------------------------------------------------------------
# MODULE: REPORTS & ANALYTICS
# -----------------------------------------------------------------------------
elif choice == "Reports & Analytics":
    st.title("📈 Reports & Analytics")

    colf1, colf2, colf3 = st.columns([2, 2, 1.3])
    with colf1:
        start_d = st.date_input("From Date", value=date.today().replace(day=1))
    with colf2:
        end_d = st.date_input("To Date", value=date.today())
    with colf3:
        group_by = st.selectbox("Group By", ["Day", "Month"])
    date_fmt = "%Y-%m-%d" if group_by == "Day" else "%Y-%m"
    sql_date_fmt = "%Y-%m-%d" if group_by == "Day" else "%Y-%m"

    scope_sql, scope_params = "", []
    if not is_superadmin:
        scope_sql = " AND center_id=?"
        scope_params = [my_center_id]
    elif selected_city != "All Cities":
        scope_sql = " AND center_id IN (SELECT id FROM center WHERE city=?)"
        scope_params = [selected_city]

    rep_tabs = st.tabs([
        "💰 Fees Collection", "🧑‍🤝‍🧑 Patients", "📅 Appointments",
        "🗓️ Attendance", "💵 Salary", "🧾 Expenses",
    ])

    # ---- Fees Collection ----
    with rep_tabs[0]:
        st.markdown(f"##### 💰 Fees Collection ({group_by}-wise)")
        rev_df = db.read_sql(
            f"SELECT STRFTIME('{sql_date_fmt}', paid_on) as period, SUM(total) as revenue, COUNT(*) as bills "
            f"FROM fee WHERE DATE(paid_on) BETWEEN ? AND ?{scope_sql} GROUP BY period ORDER BY period",
            conn, params=[str(start_d), str(end_d)] + scope_params,
        )
        if not rev_df.empty:
            st.bar_chart(rev_df.set_index("period")["revenue"])
            colr1, colr2 = st.columns(2)
            colored_metric(colr1, "Total Collected", f"₹{rev_df['revenue'].sum():,.2f}", "#059669", icon="💰")
            colored_metric(colr2, "Total Bills", int(rev_df["bills"].sum()), "#0284c7", icon="🧾")
            st.write("")
            st.dataframe(rev_df, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Download as CSV", rev_df.to_csv(index=False).encode("utf-8"),
                file_name=f"fees_collection_{start_d}_to_{end_d}.csv", mime="text/csv",
            )
        else:
            st.info("No billing data for this period.")

    # ---- Patients ----
    with rep_tabs[1]:
        st.markdown(f"##### 🧑‍🤝‍🧑 New Patient Registrations ({group_by}-wise)")
        reg_df = db.read_sql(
            f"SELECT STRFTIME('{sql_date_fmt}', created_at) as period, COUNT(*) as new_patients "
            f"FROM patient WHERE DATE(created_at) BETWEEN ? AND ?{scope_sql} GROUP BY period ORDER BY period",
            conn, params=[str(start_d), str(end_d)] + scope_params,
        )
        if not reg_df.empty:
            st.line_chart(reg_df.set_index("period")["new_patients"])
            st.metric("Total New Patients (Period)", int(reg_df["new_patients"].sum()))
        else:
            st.info("No new registrations for this period.")

        st.markdown("---")
        st.markdown("##### 📋 Patient Details List")
        pat_query = """SELECT p.patient_code, p.name, p.age, p.gender, p.mobile, DATE(p.created_at) as registered_on,
                              c.name as center_name
                       FROM patient p LEFT JOIN center c ON p.center_id=c.id
                       WHERE DATE(p.created_at) BETWEEN ? AND ?"""
        pat_params = [str(start_d), str(end_d)]
        if not is_superadmin:
            pat_query += " AND p.center_id=?"
            pat_params.append(my_center_id)
        elif selected_city != "All Cities":
            pat_query += " AND c.city=?"
            pat_params.append(selected_city)
        pat_query += " ORDER BY p.created_at DESC"
        pat_df = db.read_sql(pat_query, conn, params=pat_params)
        st.dataframe(pat_df, use_container_width=True, hide_index=True)
        if not pat_df.empty:
            st.download_button(
                "⬇️ Download Patient List as CSV", pat_df.to_csv(index=False).encode("utf-8"),
                file_name=f"patients_{start_d}_to_{end_d}.csv", mime="text/csv",
            )

    # ---- Appointments ----
    with rep_tabs[2]:
        st.markdown("##### 📅 Appointment Status Breakdown")
        stat_df = db.read_sql(
            f"SELECT status, COUNT(*) as count FROM appointment WHERE appt_date BETWEEN ? AND ?{scope_sql} GROUP BY status",
            conn, params=[str(start_d), str(end_d)] + scope_params,
        )
        if not stat_df.empty:
            st.bar_chart(stat_df.set_index("status")["count"])
            st.dataframe(stat_df, use_container_width=True, hide_index=True)
        else:
            st.info("No appointment data for this period.")

    # ---- Attendance ----
    with rep_tabs[3]:
        st.markdown(f"##### 🗓️ Attendance Report ({group_by}-wise)")
        att_query = f"""SELECT STRFTIME('{sql_date_fmt}', a.att_date) as period, s.name as staff_name,
                               a.status, COUNT(*) as days
                        FROM attendance a JOIN staff s ON a.staff_id=s.id
                        WHERE a.att_date BETWEEN ? AND ?"""
        att_params = [str(start_d), str(end_d)]
        if not is_superadmin:
            att_query += " AND s.center_id=?"
            att_params.append(my_center_id)
        att_query += " GROUP BY period, s.name, a.status ORDER BY period, s.name"
        att_df = db.read_sql(att_query, conn, params=att_params)

        if not att_df.empty:
            pivot = att_df.pivot_table(
                index=["period", "staff_name"], columns="status", values="days", fill_value=0
            ).reset_index()
            st.dataframe(pivot, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Download Attendance Report as CSV", pivot.to_csv(index=False).encode("utf-8"),
                file_name=f"attendance_{start_d}_to_{end_d}.csv", mime="text/csv",
            )
        else:
            st.info("No attendance data for this period.")

    # ---- Salary ----
    with rep_tabs[4]:
        st.markdown("##### 💵 Salary Details")
        st.caption("Shows monthly salary per staff member, along with attendance in the selected period "
                   "for reference when calculating payouts.")
        sal_query = "SELECT id, employee_code, name, designation, salary, status FROM staff WHERE 1=1"
        sal_params = []
        if not is_superadmin:
            sal_query += " AND center_id=?"
            sal_params.append(my_center_id)
        sal_query += " ORDER BY name"
        staff_df = db.read_sql(sal_query, conn, params=sal_params)

        if staff_df.empty:
            st.info("No staff members found.")
        else:
            att_summary = db.read_sql(
                """SELECT staff_id,
                          SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) as present_days,
                          SUM(CASE WHEN status='Absent' THEN 1 ELSE 0 END) as absent_days,
                          SUM(CASE WHEN status='Half Day' THEN 1 ELSE 0 END) as half_days,
                          SUM(CASE WHEN status='Leave' THEN 1 ELSE 0 END) as leave_days
                   FROM attendance WHERE att_date BETWEEN ? AND ? GROUP BY staff_id""",
                conn, params=[str(start_d), str(end_d)],
            )
            merged = staff_df.merge(att_summary, left_on="id", right_on="staff_id", how="left").fillna(0)
            merged["payable_estimate"] = merged["salary"]  # full monthly salary shown; adjust manually if needed
            display_cols = ["employee_code", "name", "designation", "salary", "present_days",
                             "absent_days", "half_days", "leave_days", "status"]
            st.dataframe(merged[display_cols], use_container_width=True, hide_index=True)
            st.metric("Total Monthly Salary Payroll", f"₹{staff_df['salary'].sum():,.2f}")
            st.download_button(
                "⬇️ Download Salary Report as CSV", merged[display_cols].to_csv(index=False).encode("utf-8"),
                file_name=f"salary_{start_d}_to_{end_d}.csv", mime="text/csv",
            )

    # ---- Expenses ----
    with rep_tabs[5]:
        st.markdown("##### 🧾 Expenses")
        with st.expander("➕ Add New Expense"):
            with st.form("expense_form", clear_on_submit=True):
                exp_category = st.selectbox(
                    "Category", ["Rent", "Electricity", "Salaries", "Medicine Purchase",
                                 "Equipment", "Maintenance", "Marketing", "Other"]
                )
                exp_desc = st.text_input("Description")
                exp_amount = st.number_input("Amount (₹)", min_value=0.0, value=0.0, step=100.0)
                exp_date = st.date_input("Expense Date", value=date.today())
                if st.form_submit_button("💾 Save Expense", use_container_width=True):
                    exp_center = my_center_id if not is_superadmin else (
                        list(db.get_centers_dropdown().keys())[0] if db.get_centers_dropdown() else None
                    )
                    conn.execute(
                        """INSERT INTO expense (category, description, amount, expense_date, center_id, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (exp_category, exp_desc, exp_amount, str(exp_date), exp_center, db.now()),
                    )
                    conn.commit()
                    st.success("Expense recorded.")
                    st.rerun()

        exp_query = "SELECT category, description, amount, expense_date FROM expense WHERE expense_date BETWEEN ? AND ?"
        exp_params = [str(start_d), str(end_d)]
        if not is_superadmin:
            exp_query += " AND center_id=?"
            exp_params.append(my_center_id)
        elif selected_city != "All Cities":
            exp_query += " AND center_id IN (SELECT id FROM center WHERE city=?)"
            exp_params.append(selected_city)
        exp_query += " ORDER BY expense_date DESC"
        exp_df = db.read_sql(exp_query, conn, params=exp_params)

        if not exp_df.empty:
            cat_summary = exp_df.groupby("category")["amount"].sum().reset_index().sort_values("amount", ascending=False)
            st.bar_chart(cat_summary.set_index("category")["amount"])

            total_expenses = exp_df["amount"].sum()
            total_revenue_period = conn.execute(
                f"SELECT SUM(total) FROM fee WHERE DATE(paid_on) BETWEEN ? AND ?{scope_sql}",
                [str(start_d), str(end_d)] + scope_params,
            ).fetchone()[0] or 0
            net = total_revenue_period - total_expenses

            colx1, colx2, colx3 = st.columns(3)
            colored_metric(colx1, "Total Expenses", f"₹{total_expenses:,.2f}", "#dc2626", icon="🧾")
            colored_metric(colx2, "Total Revenue", f"₹{total_revenue_period:,.2f}", "#059669", icon="💰")
            colored_metric(colx3, "Net (Revenue − Expenses)", f"₹{net:,.2f}", "#0284c7" if net >= 0 else "#dc2626", icon="📊")

            st.write("")
            st.dataframe(exp_df, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Download Expenses as CSV", exp_df.to_csv(index=False).encode("utf-8"),
                file_name=f"expenses_{start_d}_to_{end_d}.csv", mime="text/csv",
            )
        else:
            st.info("No expenses recorded for this period yet.")

# -----------------------------------------------------------------------------
# MODULE: USERS MANAGEMENT
# -----------------------------------------------------------------------------
elif choice == "Users Management":
    st.title("👤 Users Management")

    t1, t2, t3 = st.tabs(["📋 All Users", "➕ Add User", "🔑 Change My Password"])

    with t1:
        query = """SELECT u.id, u.username, u.full_name, u.role, c.name as center_name, u.is_active,
                          u.is_demo_account
                   FROM user u LEFT JOIN center c ON u.center_id=c.id WHERE 1=1"""
        params = []
        if not is_superadmin:
            query += " AND u.center_id=?"
            params.append(my_center_id)
        query += " ORDER BY u.id DESC"

        df = db.read_sql(query, conn, params=params)
        st.dataframe(df, use_container_width=True, hide_index=True)

        if not df.empty:
            st.markdown("##### Activate / Deactivate User")
            uid = st.selectbox("Select User", df["id"].tolist(),
                                format_func=lambda x: df[df["id"] == x]["username"].values[0],
                                key="user_status_select")
            toggle = st.checkbox("Active", value=True)
            if st.button("Update User Status"):
                conn.execute("UPDATE user SET is_active=? WHERE id=?", (int(toggle), uid))
                conn.commit()
                st.success("User updated.")
                st.rerun()

            st.markdown("---")
            st.markdown("##### 🔑 Reset a User's Password")
            st.caption("Set a new password for any staff member — share it with them directly afterwards.")
            reset_uid = st.selectbox("Select User", df["id"].tolist(),
                                      format_func=lambda x: df[df["id"] == x]["username"].values[0],
                                      key="user_reset_select")
            colp1, colp2 = st.columns(2)
            with colp1:
                new_pw1 = st.text_input("New Password", type="password", key="reset_pw1")
            with colp2:
                new_pw2 = st.text_input("Confirm New Password", type="password", key="reset_pw2")
            reset_is_demo = bool(df[df["id"] == reset_uid]["is_demo_account"].values[0])
            if reset_is_demo:
                st.info(
                    "🎭 This user is a Demo Account. Its password is locked and cannot be reset here — "
                    "un-tick 'Mark as Demo Account' below first if you really need to change it."
                )
            if st.button("🔑 Reset Password", use_container_width=True, disabled=reset_is_demo):
                if reset_is_demo:
                    st.error("Demo Account passwords are locked.")
                elif not new_pw1:
                    st.error("Enter a new password.")
                elif new_pw1 != new_pw2:
                    st.error("Passwords do not match.")
                else:
                    reset_salt, reset_hash = db.make_password(new_pw1)
                    conn.execute("UPDATE user SET password_hash=?, password_salt=? WHERE id=?",
                                 (reset_hash, reset_salt, reset_uid))
                    conn.commit()
                    reset_username = df[df["id"] == reset_uid]["username"].values[0]
                    st.success(f"Password reset for '{reset_username}'. Share the new password with them directly.")

            st.markdown("---")
            st.markdown("##### 🗑️ Remove a User")
            st.caption("Permanently deletes their login — this does not delete any patients, bills, or "
                       "other records they created.")
            del_uid = st.selectbox("Select User", df["id"].tolist(),
                                    format_func=lambda x: df[df["id"] == x]["username"].values[0],
                                    key="user_delete_select")
            if del_uid == st.session_state.get("user_id"):
                st.info("You can't remove your own account while logged in as it.")
            else:
                confirm_del = st.checkbox("I understand this cannot be undone.", key="confirm_del_user")
                if st.button("🗑️ Delete User", use_container_width=True, disabled=not confirm_del):
                    conn.execute("DELETE FROM user WHERE id=?", (del_uid,))
                    conn.commit()
                    st.success("User removed.")
                    st.rerun()

            st.markdown("---")
            st.markdown("##### 🎭 Demo Account Lock")
            if not is_superadmin:
                st.info(
                    "Demo Account locks are managed by the software vendor (Super Admin) only. "
                    "A locked demo login's password cannot be changed from inside this clinic."
                )
            else:
                st.caption("For a login you plan to share with multiple people (e.g. sales demos) — mark it "
                           "as a Demo Account and nobody, including the clinic's own Admin, can change or "
                           "reset its password. Only you (Super Admin) can lift the lock here.")
                demo_uid = st.selectbox("Select User", df["id"].tolist(),
                                         format_func=lambda x: df[df["id"] == x]["username"].values[0],
                                         key="user_demo_select")
                current_demo_flag = bool(df[df["id"] == demo_uid]["is_demo_account"].values[0])
                demo_toggle = st.checkbox("Mark as Demo Account (password-change disabled for this login)",
                                           value=current_demo_flag, key="demo_toggle_checkbox")
                if st.button("Save Demo Account Setting", use_container_width=True):
                    conn.execute("UPDATE user SET is_demo_account=? WHERE id=?", (int(demo_toggle), demo_uid))
                    conn.commit()
                    st.success("Updated.")
                    st.rerun()

    with t2:
        with st.form("add_user_form", clear_on_submit=True):
            u_name = st.text_input("Username *")
            u_full = st.text_input("Full Name *")
            u_pass = st.text_input("Password *", type="password")
            u_role = st.selectbox("Role", ["admin", "doctor", "receptionist", "hr"] + (["superadmin"] if is_superadmin else []))
            u_is_demo = st.checkbox("This is a Demo Account (shared for sales demos) — "
                                     "disable self password-change for this login")
            if is_superadmin:
                centers_map = db.get_centers_dropdown(active_only=True)
                u_center = st.selectbox("Assign to Clinic", options=list(centers_map.keys()),
                                         format_func=lambda x: centers_map[x]) if centers_map else None
            else:
                u_center = my_center_id

            if st.form_submit_button("✅ Create User", use_container_width=True):
                if not all([u_name, u_full, u_pass]):
                    st.error("Please fill all required fields.")
                else:
                    try:
                        new_salt, new_hash = db.make_password(u_pass)
                        conn.execute(
                            """INSERT INTO user (username, password_hash, password_salt, full_name, role, center_id, is_active, created_at, is_demo_account)
                               VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                            (u_name, new_hash, new_salt, u_full, u_role, u_center, db.now(), int(u_is_demo)),
                        )
                        conn.commit()
                        st.success(f"User '{u_name}' created.")
                    except Exception as e:
                        st.error("Username already exists." if "UNIQUE" in str(e) else str(e))

    with t3:
        my_current_row = conn.execute("SELECT * FROM user WHERE id=?", (st.session_state.get("user_id"),)).fetchone()
        if my_current_row and my_current_row["is_demo_account"]:
            st.warning(
                "🎭 This is a shared Demo Account — password changes are disabled for it so it can be "
                "safely handed out for demos without anyone locking others out. If you need a different "
                "password, ask your Admin/Super Admin to reset it from **All Users**."
            )
        else:
            st.caption(f"Change the password for your own account (**{st.session_state.get('username', '')}**).")
            with st.form("change_own_password_form", clear_on_submit=True):
                cur_pw = st.text_input("Current Password", type="password")
                new_pw1_self = st.text_input("New Password", type="password")
                new_pw2_self = st.text_input("Confirm New Password", type="password")
                if st.form_submit_button("🔑 Change My Password", use_container_width=True):
                    my_row = conn.execute("SELECT * FROM user WHERE id=?", (st.session_state.get("user_id"),)).fetchone()
                    if not my_row or not db.verify_password(cur_pw, my_row["password_hash"], my_row["password_salt"]):
                        st.error("Current password is incorrect.")
                    elif not new_pw1_self:
                        st.error("Enter a new password.")
                    elif new_pw1_self != new_pw2_self:
                        st.error("New passwords do not match.")
                    else:
                        self_salt, self_hash = db.make_password(new_pw1_self)
                        conn.execute("UPDATE user SET password_hash=?, password_salt=? WHERE id=?",
                                     (self_hash, self_salt, st.session_state.get("user_id")))
                        conn.commit()
                        st.success("Your password has been changed. Use it next time you log in.")


# -----------------------------------------------------------------------------
# MODULE: BILLING & UPGRADE (admin pays for their clinic's plan via Razorpay)
# -----------------------------------------------------------------------------
elif choice == "Billing & Upgrade":
    st.title("💰 Billing & Plan Upgrade")

    my_center = conn.execute("SELECT * FROM center WHERE id=?", (my_center_id,)).fetchone()

    colp1, colp2 = st.columns(2)
    with colp1:
        st.metric("Current Plan", my_center["plan"] if my_center else "-")
    with colp2:
        st.metric("Valid Until", my_center["plan_expiry"] if my_center and my_center["plan_expiry"] else "-")

    st.markdown("---")

    tab_license, tab_pay = st.tabs(["🔑 Activate License Key", "💳 Pay Online"])

    with tab_license:
        st.subheader("Activate a License Key")
        st.caption("Enter the license key you received from your software provider — "
                   "a **Monthly** key (SNCLM-...) gives 30 days of access, a **Yearly** key "
                   "(SNCLY-...) gives 365 days, both starting from the moment you activate it.")
        key_input = st.text_input("License Key", placeholder="SNCLY-XXXXX-XXXXX-XXXXX or SNCLM-XXXXX-XXXXX-XXXXX", key="license_key_input")
        if st.button("✅ Activate License", use_container_width=True):
            ok, message, new_expiry = lic.activate_key(key_input, my_center_id)
            if ok:
                st.success(message)
                st.session_state["license_expired"] = False
                st.rerun()
            else:
                st.error(message)

    with tab_pay:
        if not billing.is_configured():
            st.warning(
                "Online payments aren't set up on this server yet. Ask your platform "
                "provider to configure Razorpay (see `billing.py` for setup steps), "
                "or use the Activate License Key tab instead."
            )
        else:
            st.subheader("Choose a Plan")
            plan_choice = st.selectbox("Plan", list(billing.PLAN_PRICING.keys()))
            price = billing.PLAN_PRICING[plan_choice]
            st.metric(f"{plan_choice} Plan — Monthly Price", f"₹{price:,}")

            if st.button("💳 Generate Payment Link", use_container_width=True):
                try:
                    link = billing.create_payment_link(
                        amount_rupees=price, plan=plan_choice,
                        clinic_name=my_center["name"], customer_name=st.session_state["full_name"],
                        center_id=my_center_id,
                    )
                    conn.execute(
                        "UPDATE center SET pending_plan=?, razorpay_link_id=?, razorpay_link_url=?, razorpay_link_status=? WHERE id=?",
                        (plan_choice, link["id"], link["short_url"], link["status"], my_center_id),
                    )
                    conn.commit()
                    st.success("Payment link created below. Complete the payment, then click Verify.")
                except RuntimeError as e:
                    st.error(str(e))

        my_center = conn.execute("SELECT * FROM center WHERE id=?", (my_center_id,)).fetchone()
        if my_center and my_center["razorpay_link_url"] and my_center["razorpay_link_status"] != "paid":
            st.markdown("---")
            st.info(f"Pending payment for **{my_center['pending_plan']}** plan.")
            st.link_button("🔗 Open Payment Page", my_center["razorpay_link_url"], use_container_width=True)
            if st.button("✅ I've Completed Payment — Verify Now", use_container_width=True):
                try:
                    status = billing.fetch_payment_link_status(my_center["razorpay_link_id"])
                    if status == "paid":
                        new_expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
                        conn.execute(
                            "UPDATE center SET plan=?, plan_expiry=?, is_active=1, razorpay_link_status=? WHERE id=?",
                            (my_center["pending_plan"], new_expiry, status, my_center_id),
                        )
                        conn.commit()
                        st.success(f"Payment confirmed! Your clinic is now on the {my_center['pending_plan']} plan.")
                        st.session_state["license_expired"] = False
                        st.rerun()
                    else:
                        st.warning(f"Payment status: **{status}**. Complete the payment and try again.")
                except RuntimeError as e:
                    st.error(str(e))

conn.close()
