import streamlit as st
import pandas as pd
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
import os

st.set_page_config(page_title="German Embassy Islamabad Appointment Tracker", page_icon="📅", layout="wide")

DB_PATH = "appointments.db"
CSV_PATH = "appointments_backup.csv"

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id TEXT PRIMARY KEY,
            name TEXT,
            reference_no TEXT,
            apply_date TEXT,
            received_date TEXT,
            interview_date TEXT,
            created_at TEXT
        )
    """)
    return conn

def save_to_csv(df):
    """Save dataframe to CSV for backup"""
    df.to_csv(CSV_PATH, index=False, encoding='utf-8')

def to_iso(d):
    return d.isoformat() if isinstance(d, (date, datetime)) else (d or "")

def parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None

def calculate_wait_time(start_date, end_date):
    """Calculate accurate wait time between two dates in months and days"""
    if not start_date or not end_date:
        return None, None
    
    try:
        if start_date >= end_date:
            return 0, 0
        
        rd = relativedelta(end_date, start_date)
        total_months = rd.years * 12 + rd.months
        
        temp_date = start_date + relativedelta(months=total_months)
        remaining_days = (end_date - temp_date).days
        
        if remaining_days < 0:
            total_months -= 1
            temp_date = start_date + relativedelta(months=total_months)
            remaining_days = (end_date - temp_date).days
        
        return total_months, remaining_days
    except:
        return None, None

def seed_if_empty(conn):
    cur = conn.execute("SELECT COUNT(*) FROM appointments")
    n = cur.fetchone()[0]
    if n > 0:
        return

    seed = [
        # Existing appointments
        {"name":"Saeed Ahmad", "reference_no":"1999", "apply_date":"2023-11-13", "received_date":"2025-12-16", "interview_date":"2026-02-12"},
        {"name":"", "reference_no":"1996", "apply_date":"2023-11-10", "received_date":"2025-12-16", "interview_date":"2026-02-09"},
        {"name":"", "reference_no":"1986", "apply_date":"", "received_date":"", "interview_date":"2026-02-04"},
        {"name":"Honey Badal", "reference_no":"", "apply_date":"2023-10-03", "received_date":"2025-11-17", "interview_date":"2025-12-16"},
        {"name":"Osama Adil", "reference_no":"", "apply_date":"2023-10-04", "received_date":"2025-11-16", "interview_date":"2025-12-16"},
        {"name":"", "reference_no":"1950", "apply_date":"2023-09-30", "received_date":"", "interview_date":"2025-12-11"},
        
        # New appointments from the posts - ONLY data explicitly mentioned
        {"name":"", "reference_no":"1993", "apply_date":"", "received_date":"", "interview_date":"2026-02-06"},
        {"name":"", "reference_no":"1991", "apply_date":"2023-11-08", "received_date":"2025-12-11", "interview_date":""},
        {"name":"", "reference_no":"1885", "apply_date":"", "received_date":"", "interview_date":"2025-08-13"},
        {"name":"", "reference_no":"1979", "apply_date":"2023-10-31", "received_date":"", "interview_date":"2026-01-28"},
        {"name":"", "reference_no":"1980", "apply_date":"2023-11-01", "received_date":"", "interview_date":""},
        {"name":"", "reference_no":"1975", "apply_date":"2023-10-23", "received_date":"2025-12-11", "interview_date":"2026-01-20"},
        {"name":"", "reference_no":"1971", "apply_date":"2023-10-13", "received_date":"2025-12-11", "interview_date":"2026-01-13"},
        {"name":"", "reference_no":"1955", "apply_date":"2023-09-25", "received_date":"", "interview_date":""},
        {"name":"", "reference_no":"1940", "apply_date":"2023-09-10", "received_date":"", "interview_date":""},
        {"name":"", "reference_no":"1935", "apply_date":"2023-09-05", "received_date":"", "interview_date":""},
    ]

    for r in seed:
        conn.execute(
            """INSERT INTO appointments
               (id, name, reference_no, apply_date, received_date, interview_date, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                r["name"],
                r["reference_no"],
                r["apply_date"],
                r["received_date"],
                r["interview_date"],
                datetime.now(timezone.utc).isoformat(),
            )
        )
    conn.commit()

def load_df(conn):
    df = pd.read_sql_query("SELECT * FROM appointments", conn)

    for col in ["apply_date", "received_date", "interview_date"]:
        if col in df.columns:
            df[col] = df[col].apply(parse_iso)

    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

    df["wait_months"] = None
    df["wait_days"] = None
    
    for idx, row in df.iterrows():
        months, days = calculate_wait_time(row["apply_date"], row["interview_date"])
        df.at[idx, "wait_months"] = months
        df.at[idx, "wait_days"] = days

    # Sort by reference number (descending) instead of interview date
    # Handle non-numeric reference numbers
    def ref_to_int(ref):
        try:
            return int(ref) if ref and str(ref).strip() else 0
        except:
            return 0
    
    df["_sort_ref"] = df["reference_no"].apply(ref_to_int)
    df = df.sort_values("_sort_ref", ascending=False)
    df = df.drop(columns=["_sort_ref"])

    return df

def insert_row(conn, name, ref, apply_d, recv_d, int_d):
    conn.execute(
        """INSERT INTO appointments
           (id, name, reference_no, apply_date, received_date, interview_date, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            str(uuid.uuid4()),
            (name or "").strip(),
            (ref or "").strip(),
            to_iso(apply_d) if apply_d else "",
            to_iso(recv_d) if recv_d else "",
            to_iso(int_d) if int_d else "",
            datetime.now(timezone.utc).isoformat(),
        )
    )
    conn.commit()

def delete_row(conn, row_id):
    """Delete a specific row by ID"""
    conn.execute("DELETE FROM appointments WHERE id = ?", (row_id,))
    conn.commit()

def fmt(d):
    if d is None or pd.isna(d):
        return "—"
    if hasattr(d, "strftime"):
        return d.strftime("%d-%b-%y")
    return str(d)

def mask_name(name):
    """Mask name with asterisks in the middle"""
    if not name or pd.isna(name) or not str(name).strip():
        return "—"
    
    name_str = str(name).strip()
    if len(name_str) <= 2:
        return name_str[0] + "*"
    elif len(name_str) <= 4:
        return name_str[0] + "**" + name_str[-1]
    else:
        return name_str[:2] + "***" + name_str[-2:]

# Initialize connection
conn = get_conn()
seed_if_empty(conn)

# Ultra-compact CSS
st.markdown("""
    <style>
    /* Hide everything unnecessary */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    
    /* Ultra compact header */
    .compact-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.1rem 0.3rem;
        margin-bottom: 0.2rem;
    }
    
    .header-title {
        font-size: 2.2rem !important;
        font-weight: bold;
        color: #333;
        margin: 0;
        padding: 0.4rem 0;
        line-height: 1.1;
    }
    
    .dua-text {
        font-size: 0.95rem;
        font-style: italic;
        text-align: center;
        color: #555;
        margin-bottom: 0.6rem;
        padding: 0;
    }
    
    /* Stats bar - comfortable spacing */
    .stats-bar {
        display: flex;
        justify-content: space-between;
        margin: 0.3rem 0 0.8rem 0;
        font-size: 0.85rem;
        background: #f8f9fa;
        padding: 0.4rem 0.6rem;
        border-radius: 6px;
        border: 1px solid #e0e0e0;
        line-height: 1.3;
    }
    
    .stat-item {
        text-align: center;
        flex: 1;
        padding: 0.1rem;
    }
    
    .stat-label {
        font-size: 0.75rem;
        color: #666;
        margin-bottom: 0.15rem;
        white-space: nowrap;
        font-weight: 500;
    }
    
    .stat-value {
        font-size: 0.9rem;
        font-weight: bold;
        color: #333;
        white-space: nowrap;
    }
    
    /* Table - most important part */
    .dataframe {
        font-size: 0.85rem !important;
    }
    
    .dataframe td {
        padding: 0.2rem 0.3rem !important;
        font-size: 0.8rem !important;
    }
    
    .dataframe th {
        padding: 0.3rem 0.4rem !important;
        font-size: 0.8rem !important;
        background-color: #f0f0f0 !important;
    }
    
    .stDataFrame {
        border: 1px solid #ddd;
        border-radius: 4px;
        padding: 2px;
    }
    
    /* Sidebar compact */
    .sidebar .sidebar-content {
        padding: 0.3rem;
    }
    
    /* Small inputs */
    .stTextInput input, .stDateInput input {
        padding: 0.2rem 0.3rem !important;
        font-size: 0.8rem !important;
    }
    
    /* Small buttons */
    .stButton button {
        padding: 0.2rem !important;
        font-size: 0.8rem !important;
    }
    
    /* Mobile optimizations */
    @media (max-width: 768px) {
        .header-title {
            font-size: 1.6rem !important;
            padding: 0.3rem 0;
        }
        
        .dua-text {
            font-size: 0.9rem !important;
        }
        
        .stats-bar {
            font-size: 0.75rem;
            padding: 0.3rem 0.4rem;
        }
        
        .stat-label {
            font-size: 0.7rem;
        }
        
        .stat-value {
            font-size: 0.8rem;
        }
        
        .dataframe td {
            font-size: 0.75rem !important;
            padding: 0.15rem 0.2rem !important;
        }
        
        .dataframe th {
            font-size: 0.75rem !important;
            padding: 0.2rem 0.3rem !important;
        }
    }
    
    /* Very small phones */
    @media (max-width: 480px) {
        .header-title {
            font-size: 1.3rem !important;
            padding: 0.2rem 0;
        }
        
        .stats-bar {
            flex-wrap: wrap;
        }
        
        .stat-item {
            flex: 0 0 50%;
            margin-bottom: 0.2rem;
        }
    }
    
    /* Admin login styling */
    .admin-login-box {
        background: #fff;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        padding: 0.3rem;
        margin-bottom: 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)

# ULTRA COMPACT HEADER (minimal space)
col1, col2 = st.columns([4, 1])
with col1:
    st.markdown('<div class="compact-header"><div class="header-title">🇩🇪 German Embassy Islamabad Appointments</div></div>', unsafe_allow_html=True)

# Initialize session state for admin
if 'admin_authenticated' not in st.session_state:
    st.session_state.admin_authenticated = False
if 'admin_login_open' not in st.session_state:
    st.session_state.admin_login_open = False

# Get admin password securely from Streamlit secrets or environment
def get_admin_password():
    """Get admin password from Streamlit secrets or environment variable"""
    try:
        # Try Streamlit secrets first
        return st.secrets["ADMIN_PASSWORD"]
    except:
        try:
            # Try environment variable
            return os.environ.get("ADMIN_PASSWORD", "NoEm1234")
        except:
            # Default fallback (not recommended for production)
            return "NoEm1234"

ADMIN_PASSWORD = get_admin_password()

# Admin login - HIDDEN FROM REGULAR USERS
with col2:
    # Only show admin toggle if not already authenticated
    if not st.session_state.admin_authenticated:
        if st.button("🔐", help="Admin login", key="admin_toggle"):
            st.session_state.admin_login_open = not st.session_state.admin_login_open
            st.rerun()
    else:
        if st.button("🚪", help="Logout", key="logout_btn"):
            st.session_state.admin_authenticated = False
            st.session_state.admin_login_open = False
            st.rerun()

# Show login form if toggled open
if st.session_state.admin_login_open and not st.session_state.admin_authenticated:
    with st.expander("Admin Login", expanded=True):
        admin_pass = st.text_input("Enter Admin Password:", type="password", key="admin_pass_input")
        col_login1, col_login2 = st.columns(2)
        with col_login1:
            if st.button("Login", key="admin_login_btn", use_container_width=True):
                if admin_pass == ADMIN_PASSWORD:
                    st.session_state.admin_authenticated = True
                    st.session_state.admin_login_open = False
                    st.rerun()
                else:
                    st.error("Incorrect password")
        with col_login2:
            if st.button("Cancel", key="admin_cancel", use_container_width=True):
                st.session_state.admin_login_open = False
                st.rerun()

st.markdown('<div class="dua-text">🤲 May Allah make it easy for all of us in this waiting period. Ameen!</div>', unsafe_allow_html=True)

# Sidebar - FIXED SEQUENCE: Apply date, Received date, Appointment in embassy
with st.sidebar:
    st.markdown("**+ Add Appointment Record**")
    
    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("Name", placeholder="(Optional)")
        reference_no = st.text_input("Reference Number*", placeholder="Required")
        
        today = date.today()
        
        # FIXED SEQUENCE: Apply Date first
        apply_date = st.date_input("Apply Date*", 
                                  value=today - timedelta(days=25*30),
                                  min_value=date(2010, 1, 1))
        
        # Received Date second (must be after or equal to Apply Date)
        received_date = st.date_input("Received Date*", 
                                     value=today,
                                     min_value=apply_date)
        
        # Appointment in Embassy third (must be after or equal to Received Date)
        appointment_date = st.date_input("Appointment in Embassy*", 
                                        value=today + timedelta(days=60),
                                        min_value=received_date)
        
        submitted = st.form_submit_button("💾 Save Appointment")
        
        if submitted:
            if not reference_no.strip():
                st.error("Reference Number is required")
            else:
                insert_row(conn, name, reference_no, apply_date, received_date, appointment_date)
                st.rerun()

# Load data
df = load_df(conn)

if len(df) == 0:
    st.info("No appointments yet.")
else:
    # Save backup
    save_to_csv(df)
    
    # Show how many appointments we have
    st.markdown(f"**Showing {len(df)} appointments**")
    
    # COMFORTABLE STATS BAR
    valid_received = df['received_date'].dropna()
    valid_appointment = df['interview_date'].dropna()
    valid_wait = df['wait_months'].dropna()
    
    latest_received = valid_received.max() if not valid_received.empty else None
    latest_appointment = valid_appointment.max() if not valid_appointment.empty else None
    avg_wait = valid_wait.mean() if not valid_wait.empty else None
    
    st.markdown(f"""
    <div class="stats-bar">
        <div class="stat-item">
            <div class="stat-label">Total Appointments</div>
            <div class="stat-value">{len(df)}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">Latest Received</div>
            <div class="stat-value">{fmt(latest_received)}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">Latest Appointment</div>
            <div class="stat-label">at Embassy</div>
            <div class="stat-value">{fmt(latest_appointment)}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">Average Wait</div>
            <div class="stat-label">Time</div>
            <div class="stat-value">{f"{avg_wait:.0f} months" if avg_wait else "—"}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # MAIN CONTENT - ALL APPOINTMENTS TABLE (Most Important)
    st.markdown("**📋 All Appointments**")
    
    # Prepare display data
    display_df = df.copy()[['name', 'reference_no', 'apply_date', 'received_date', 'interview_date', 'wait_months', 'wait_days']]
    
    # Format dates with year
    for date_col in ['apply_date', 'received_date', 'interview_date']:
        display_df[date_col] = display_df[date_col].apply(fmt)
    
    # Mask names
    display_df['name'] = display_df['name'].apply(mask_name)
    
    # Format wait time
    def format_wait(row):
        months = row['wait_months']
        days = row['wait_days']
        if pd.notna(months) and pd.notna(days):
            return f"{int(months)}m {int(days)}d" if days > 0 else f"{int(months)}m"
        elif pd.notna(months):
            return f"{int(months)}m"
        return "—"
    
    display_df['Wait Time'] = display_df.apply(format_wait, axis=1)
    
    # Use full words for column headers with corrected name
    display_df.columns = ['Name', 'Reference', 'Apply Date', 'Receive Date', 'Embassy Date', '_m', '_d', 'Wait Time']
    
    # Display the table - MOST IMPORTANT PART - FIXED COLUMN NAMES
    st.dataframe(
        display_df[['Name', 'Reference', 'Apply Date', 'Receive Date', 'Embassy Date', 'Wait Time']],
        width='stretch',
        hide_index=True,
        column_config={
            "Name": st.column_config.TextColumn(width="small"),
            "Reference": st.column_config.TextColumn(width="small"),
            "Apply Date": st.column_config.TextColumn(width="small"),
            "Receive Date": st.column_config.TextColumn(width="small"),
            "Embassy Date": st.column_config.TextColumn(width="small"),
            "Wait Time": st.column_config.TextColumn(width="small"),
        }
    )
    
    # ADMIN PANEL - ONLY VISIBLE WHEN AUTHENTICATED
    if st.session_state.admin_authenticated:
        st.markdown("---")
        st.markdown("**🔧 Admin Panel**")
        
        # Simple delete option
        appointment_options = []
        for idx, row in df.iterrows():
            ref = str(row['reference_no']) if pd.notna(row['reference_no']) and str(row['reference_no']).strip() else "No Reference"
            name = mask_name(row['name'])
            appointment_options.append((row['id'], f"{ref} - {name}"))
        
        if appointment_options:
            selected_option = st.selectbox("Select appointment to delete:", 
                                         [opt[1] for opt in appointment_options],
                                         key="delete_select")
            
            if selected_option:
                # Find the ID
                selected_id = None
                for opt_id, opt_display in appointment_options:
                    if opt_display == selected_option:
                        selected_id = opt_id
                        break
                
                if selected_id:
                    # Show warning and confirmation
                    st.warning("⚠️ This action cannot be undone!")
                    confirm = st.checkbox("I confirm I want to delete this appointment", key="confirm_delete")
                    
                    if confirm and st.button("🗑️ Delete Appointment", type="secondary"):
                        delete_row(conn, selected_id)
                        st.success("Appointment deleted successfully")
                        st.rerun()

# Minimal footer
st.markdown("""
<div style="text-align: center; color: #999; font-size: 0.7rem; margin-top: 0.5rem;">
    Community App - German Embassy Islamabad Appointment Tracker
</div>
""", unsafe_allow_html=True)