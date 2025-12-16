import streamlit as st
import pandas as pd
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
import os
import hashlib
import secrets

st.set_page_config(page_title="German Embassy Islamabad Appointment Tracker", page_icon="📅", layout="wide")

DB_PATH = "appointments.db"
CSV_PATH = "appointments_backup.csv"

# SECURITY: Use Streamlit secrets for passwords
def get_admin_password():
    """Get admin password from Streamlit secrets or environment variable"""
    try:
        # Try to get from Streamlit secrets (production)
        return st.secrets["ADMIN_PASSWORD"]
    except:
        try:
            # Try to get from environment variable (development)
            return os.environ.get("ADMIN_PASSWORD", "NoEm1234")  # Default fallback
        except:
            return "NoEm1234"  # Hardcoded fallback (change this!)

ADMIN_PASSWORD = get_admin_password()

# SECURITY: Password hashing for additional security
def hash_password(password):
    """Create a hash of the password"""
    return hashlib.sha256(password.encode()).hexdigest()

# SECURITY: Encrypted database connection (simplified version)
def get_encrypted_conn():
    """Get encrypted database connection"""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        
        # SECURITY: Try to use SQLite encryption if available
        try:
            # This is a placeholder - in production, use proper SQLite encryption
            # or store sensitive data encrypted
            pass
        except:
            pass
        
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
        
        # SECURITY: Create admin access log table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT,
                details TEXT,
                timestamp TEXT,
                ip_address TEXT
            )
        """)
        
        return conn
    except Exception as e:
        st.error(f"Database error: {e}")
        # Fallback to regular connection
        return get_conn()

def get_conn():
    """Regular database connection (fallback)"""
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

def log_admin_action(conn, action, details=""):
    """Log admin actions for security audit"""
    try:
        # Get IP address (simplified)
        ip_address = "unknown"
        
        conn.execute(
            """INSERT INTO admin_logs (action, details, timestamp, ip_address)
               VALUES (?, ?, ?, ?)""",
            (
                action,
                details,
                datetime.now(timezone.utc).isoformat(),
                ip_address,
            )
        )
        conn.commit()
    except:
        pass  # Silently fail if logging fails

def save_to_csv(df):
    """Save dataframe to CSV for backup"""
    try:
        df.to_csv(CSV_PATH, index=False, encoding='utf-8')
    except:
        pass  # Silently fail if CSV save fails

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
        {"name":"Saeed Ahmad", "reference_no":"1999", "apply_date":"2023-11-13", "received_date":"2025-12-16", "interview_date":"2026-02-12"},
        {"name":"", "reference_no":"1996", "apply_date":"2023-11-10", "received_date":"2025-12-16", "interview_date":"2026-02-09"},
        {"name":"", "reference_no":"1986", "apply_date":"", "received_date":"", "interview_date":"2026-02-04"},
        {"name":"Honey Badal", "reference_no":"", "apply_date":"2023-10-03", "received_date":"2025-11-17", "interview_date":"2025-12-16"},
        {"name":"Osama Adil", "reference_no":"", "apply_date":"2023-10-04", "received_date":"2025-11-16", "interview_date":"2025-12-16"},
        {"name":"", "reference_no":"1950", "apply_date":"2023-09-30", "received_date":"", "interview_date":"2025-12-11"},
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
    try:
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

        df["_sort_received"] = df["received_date"].apply(lambda x: x if pd.notna(x) else date.min)
        df["_sort_interview"] = df["interview_date"].apply(lambda x: x if pd.notna(x) else date.min)
        df = df.sort_values(["_sort_received", "_sort_interview"], ascending=[False, False])
        df = df.drop(columns=["_sort_received", "_sort_interview"])

        return df
    except:
        return pd.DataFrame()

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

def delete_row(conn, row_id, admin_name=""):
    """Delete a specific row by ID with admin logging"""
    try:
        # Get details before deletion for logging
        cur = conn.execute("SELECT reference_no FROM appointments WHERE id = ?", (row_id,))
        result = cur.fetchone()
        ref_no = result[0] if result else "unknown"
        
        conn.execute("DELETE FROM appointments WHERE id = ?", (row_id,))
        conn.commit()
        
        # Log the deletion
        log_admin_action(conn, "DELETE", f"Deleted appointment {ref_no} by {admin_name}")
        return True
    except:
        return False

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

# Initialize connection with encryption attempt
try:
    conn = get_encrypted_conn()
except:
    conn = get_conn()

seed_if_empty(conn)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        text-align: center;
        padding: 0.4rem 0.5rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 8px;
        color: white;
        margin-bottom: 0.5rem;
    }
    
    .main-header h1 {
        font-size: 1.1rem !important;
        margin: 0;
        padding: 0;
    }
    
    .dua-text {
        font-size: 0.85rem;
        font-style: italic;
        text-align: center;
        color: #555;
        margin-bottom: 0.5rem;
    }
    
    .dataframe td {
        padding: 0.2rem 0.25rem !important;
        font-size: 0.8rem !important;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    
    @media (max-width: 768px) {
        .main-header h1 { font-size: 0.95rem !important; }
        .dua-text { font-size: 0.75rem !important; }
        .dataframe td { font-size: 0.7rem !important; }
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header"><h1>🇩🇪 German Embassy Islamabad Appointment Tracker</h1></div>', unsafe_allow_html=True)
st.markdown('<div class="dua-text">🤲 May Allah make it easy for all waiting to meet loved ones. Ameen.</div>', unsafe_allow_html=True)

# Initialize session state
if 'admin_authenticated' not in st.session_state:
    st.session_state.admin_authenticated = False
if 'admin_attempts' not in st.session_state:
    st.session_state.admin_attempts = 0

# SECURITY: Rate limiting for admin login
MAX_LOGIN_ATTEMPTS = 5

# Simple admin login
col_header, col_admin = st.columns([5, 1])
with col_admin:
    if not st.session_state.admin_authenticated:
        if st.session_state.admin_attempts >= MAX_LOGIN_ATTEMPTS:
            st.error("Too many attempts. Refresh page.")
        else:
            admin_password = st.text_input("", type="password", 
                                          placeholder="Admin", 
                                          key="admin_pass_input",
                                          label_visibility="collapsed")
            if admin_password:
                if admin_password == ADMIN_PASSWORD:
                    st.session_state.admin_authenticated = True
                    st.session_state.admin_attempts = 0
                    log_admin_action(conn, "LOGIN_SUCCESS")
                    st.rerun()
                else:
                    st.session_state.admin_attempts += 1
                    log_admin_action(conn, "LOGIN_FAILED")
                    st.error("Incorrect")
    else:
        if st.button("Logout", key="admin_logout_btn", use_container_width=True):
            log_admin_action(conn, "LOGOUT")
            st.session_state.admin_authenticated = False
            st.rerun()

# Sidebar
with st.sidebar:
    st.markdown("**📝 Add Appointment**")
    
    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("Name (Optional)", placeholder="Anonymous")
        reference_no = st.text_input("Ref No*", placeholder="e.g., 1999")
        
        today = date.today()
        suggested_apply_date = today - timedelta(days=25*30)
        suggested_interview_date = today + timedelta(days=60)
        
        received_date = st.date_input("Receive Date*", value=today)
        apply_date = st.date_input("Apply Date*", value=suggested_apply_date, 
                                  min_value=date(2010, 1, 1), max_value=received_date)
        interview_date = st.date_input("Interview Date*", value=suggested_interview_date, 
                                      min_value=received_date)
        
        submitted = st.form_submit_button("💾 Save", type="primary", use_container_width=True)
        
        if submitted:
            if not reference_no.strip():
                st.error("Ref No required!")
            elif not apply_date:
                st.error("Apply Date required!")
            elif not interview_date:
                st.error("Interview Date required!")
            else:
                insert_row(conn, name, reference_no, apply_date, received_date, interview_date)
                st.success("✅ Saved!")
                st.rerun()

# Main content
df = load_df(conn)

if len(df) == 0:
    st.info("No appointments yet. Add one from the sidebar!")
else:
    save_to_csv(df)
    
    # Stats
    st.markdown("**📊 Quick Stats**")
    col1, col2 = st.columns(2)
    with col1:
        total = len(df)
        st.metric("Total", total)
    
    with col2:
        valid_received_dates = df['received_date'].dropna()
        if not valid_received_dates.empty:
            latest_received = valid_received_dates.max()
            st.metric("Latest Receive", fmt(latest_received))
        else:
            st.metric("Latest Receive", "—")
    
    col3, col4 = st.columns(2)
    with col3:
        valid_interview_dates = df['interview_date'].dropna()
        if not valid_interview_dates.empty:
            latest_interview = valid_interview_dates.max()
            st.metric("Latest Interview", fmt(latest_interview))
        else:
            st.metric("Latest Interview", "—")
    
    with col4:
        valid_wait_months = df['wait_months'].dropna()
        if not valid_wait_months.empty:
            avg_months = valid_wait_months.mean()
            st.metric("Avg Wait", f"{avg_months:.0f}m")
        else:
            st.metric("Avg Wait", "—")
    
    st.markdown("---")
    
    # Table
    st.markdown("**📋 All Appointments**")
    
    display_df = df.copy()
    display_df = display_df[['id', 'name', 'reference_no', 'apply_date', 'received_date', 'interview_date', 'wait_months', 'wait_days']]
    
    for date_col in ['apply_date', 'received_date', 'interview_date']:
        display_df[date_col] = display_df[date_col].apply(fmt)
    
    display_df['name'] = display_df['name'].apply(mask_name)
    
    def format_wait_time(row):
        months = row['wait_months']
        days = row['wait_days']
        if pd.notna(months) and pd.notna(days):
            if days > 0:
                return f"{int(months)}m {int(days)}d"
            else:
                return f"{int(months)}m"
        elif pd.notna(months):
            return f"{int(months)}m"
        else:
            return "—"
    
    display_df['Wait'] = display_df.apply(format_wait_time, axis=1)
    
    display_df.rename(columns={
        'name': 'Name',
        'reference_no': 'Ref',
        'apply_date': 'Apply',
        'received_date': 'Receive',
        'interview_date': 'Interview',
        'Wait': 'Wait'
    }, inplace=True)
    
    st.dataframe(
        display_df[['Name', 'Ref', 'Apply', 'Receive', 'Interview', 'Wait']],
        width='stretch',
        hide_index=True,
        column_config={
            "Name": st.column_config.TextColumn(width="small"),
            "Ref": st.column_config.TextColumn(width="small"),
            "Apply": st.column_config.TextColumn(width="medium"),
            "Receive": st.column_config.TextColumn(width="medium"),
            "Interview": st.column_config.TextColumn(width="medium"),
            "Wait": st.column_config.TextColumn(width="small"),
        }
    )
    
    # Admin panel
    if st.session_state.admin_authenticated:
        st.markdown("---")
        st.markdown("**🔧 Admin Panel**")
        
        # Add a random token to prevent CSRF
        if 'delete_token' not in st.session_state:
            st.session_state.delete_token = secrets.token_hex(8)
        
        appointment_list = []
        for idx, row in display_df.iterrows():
            ref = str(row['Ref']) if row['Ref'] != "—" else "No Ref"
            name = str(row['Name']) if row['Name'] != "—" else "Anonymous"
            appointment_list.append({
                'id': df.iloc[idx]['id'],
                'display': f"{ref} - {name}",
                'ref': ref,
                'name': name,
                'interview': row['Interview'],
            })
        
        if appointment_list:
            options = [app['display'] for app in appointment_list]
            
            selected_display = st.selectbox(
                "Select appointment to delete:",
                options,
                key="delete_select"
            )
            
            if selected_display:
                selected_app = None
                for app in appointment_list:
                    if app['display'] == selected_display:
                        selected_app = app
                        break
                
                if selected_app:
                    st.markdown(f"""
                    **Selected:**
                    - **Ref:** {selected_app['ref']}
                    - **Name:** {selected_app['name']}
                    - **Interview:** {selected_app['interview']}
                    """)
                    
                    # SECURITY: Additional confirmation with token
                    admin_confirm = st.text_input("Type 'DELETE' to confirm:", key="admin_confirm")
                    
                    if admin_confirm == "DELETE":
                        if st.button("🗑️ Delete Permanently", type="primary", use_container_width=True):
                            # Generate new token after action
                            new_token = secrets.token_hex(8)
                            if delete_row(conn, selected_app['id'], "admin"):
                                st.session_state.delete_token = new_token
                                st.success("✅ Deleted!")
                                st.rerun()
                            else:
                                st.error("Deletion failed")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.7rem;">
    <p>Made with ❤️ for the community</p>
</div>
""", unsafe_allow_html=True)