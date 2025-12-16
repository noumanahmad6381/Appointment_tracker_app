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
ADMIN_PASSWORD = "NoEm1234"

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
        font-size: 0.9rem !important;
        font-weight: bold;
        color: #333;
        margin: 0;
    }
    
    .dua-text {
        font-size: 0.75rem;
        font-style: italic;
        text-align: center;
        color: #555;
        margin-bottom: 0.3rem;
        padding: 0;
    }
    
    /* Stats bar - single line */
    .stats-bar {
        display: flex;
        justify-content: space-between;
        margin-bottom: 0.5rem;
        font-size: 0.75rem;
        background: #f8f9fa;
        padding: 0.2rem 0.4rem;
        border-radius: 4px;
        border: 1px solid #e0e0e0;
    }
    
    .stat-item {
        text-align: center;
        flex: 1;
    }
    
    .stat-label {
        font-size: 0.65rem;
        color: #666;
        margin-bottom: 0.1rem;
    }
    
    .stat-value {
        font-size: 0.8rem;
        font-weight: bold;
        color: #333;
    }
    
    /* Table - most important part */
    .dataframe {
        font-size: 0.8rem !important;
    }
    
    .dataframe td {
        padding: 0.15rem 0.2rem !important;
        font-size: 0.75rem !important;
    }
    
    .dataframe th {
        padding: 0.2rem 0.3rem !important;
        font-size: 0.7rem !important;
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
            font-size: 0.8rem !important;
        }
        
        .dua-text {
            font-size: 0.7rem !important;
        }
        
        .stats-bar {
            font-size: 0.7rem;
            padding: 0.15rem 0.3rem;
        }
        
        .stat-label {
            font-size: 0.6rem;
        }
        
        .stat-value {
            font-size: 0.75rem;
        }
        
        .dataframe td {
            font-size: 0.7rem !important;
            padding: 0.1rem 0.15rem !important;
        }
        
        .dataframe th {
            font-size: 0.65rem !important;
            padding: 0.15rem 0.2rem !important;
        }
    }
    
    /* Very small phones */
    @media (max-width: 480px) {
        .header-title {
            font-size: 0.75rem !important;
        }
        
        .stats-bar {
            flex-wrap: wrap;
        }
        
        .stat-item {
            flex: 0 0 50%;
            margin-bottom: 0.2rem;
        }
    }
    </style>
""", unsafe_allow_html=True)

# ULTRA COMPACT HEADER (minimal space)
col1, col2 = st.columns([4, 1])
with col1:
    st.markdown('<div class="compact-header"><div class="header-title">🇩🇪 German Embassy Islamabad Appointments</div></div>', unsafe_allow_html=True)

# Simple admin login
with col2:
    if 'admin_authenticated' not in st.session_state:
        st.session_state.admin_authenticated = False
    
    if not st.session_state.admin_authenticated:
        admin_pass = st.text_input("", type="password", placeholder="🔐", 
                                  label_visibility="collapsed", key="admin_pass")
        if admin_pass == ADMIN_PASSWORD:
            st.session_state.admin_authenticated = True
            st.rerun()
    else:
        if st.button("🚪", help="Logout", key="logout_btn"):
            st.session_state.admin_authenticated = False
            st.rerun()

st.markdown('<div class="dua-text">🤲 May Allah make it easy for all waiting</div>', unsafe_allow_html=True)

# Sidebar - ultra compact
with st.sidebar:
    st.markdown("**+ Add**")
    
    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("Name", placeholder="(Optional)")
        reference_no = st.text_input("Ref*", placeholder="Required")
        
        today = date.today()
        received_date = st.date_input("Recv*", value=today)
        apply_date = st.date_input("Apply*", value=today - timedelta(days=25*30), 
                                  max_value=received_date)
        interview_date = st.date_input("Int*", value=today + timedelta(days=60), 
                                      min_value=received_date)
        
        submitted = st.form_submit_button("💾 Save")
        
        if submitted:
            if not reference_no.strip():
                st.error("Ref required")
            else:
                insert_row(conn, name, reference_no, apply_date, received_date, interview_date)
                st.rerun()

# Load data
df = load_df(conn)

if len(df) == 0:
    st.info("No appointments yet.")
else:
    # Save backup
    save_to_csv(df)
    
    # ULTRA COMPACT STATS BAR (single line)
    valid_received = df['received_date'].dropna()
    valid_interview = df['interview_date'].dropna()
    valid_wait = df['wait_months'].dropna()
    
    latest_received = valid_received.max() if not valid_received.empty else None
    latest_interview = valid_interview.max() if not valid_interview.empty else None
    avg_wait = valid_wait.mean() if not valid_wait.empty else None
    
    st.markdown(f"""
    <div class="stats-bar">
        <div class="stat-item">
            <div class="stat-label">Total</div>
            <div class="stat-value">{len(df)}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">Latest Recv</div>
            <div class="stat-value">{fmt(latest_received)}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">Latest Int</div>
            <div class="stat-value">{fmt(latest_interview)}</div>
        </div>
        <div class="stat-item">
            <div class="stat-label">Avg Wait</div>
            <div class="stat-value">{f"{avg_wait:.0f}m" if avg_wait else "—"}</div>
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
            return f"{int(months)}m{int(days)}d" if days > 0 else f"{int(months)}m"
        elif pd.notna(months):
            return f"{int(months)}m"
        return "—"
    
    display_df['Wait'] = display_df.apply(format_wait, axis=1)
    
    # Rename columns for compact display
    display_df.columns = ['Name', 'Ref', 'Apply', 'Receive', 'Interview', '_m', '_d', 'Wait']
    
    # Display the table - MOST IMPORTANT PART
    st.dataframe(
        display_df[['Name', 'Ref', 'Apply', 'Receive', 'Interview', 'Wait']],
        width='stretch',
        hide_index=True,
        column_config={
            "Name": st.column_config.TextColumn(width="small"),
            "Ref": st.column_config.TextColumn(width="small"),
            "Apply": st.column_config.TextColumn(width="small"),
            "Receive": st.column_config.TextColumn(width="small"),
            "Interview": st.column_config.TextColumn(width="small"),
            "Wait": st.column_config.TextColumn(width="small"),
        }
    )
    
    # Minimal admin panel (only when authenticated)
    if st.session_state.admin_authenticated:
        st.markdown("---")
        st.markdown("**🔧 Admin**")
        
        # Simple delete option
        appointment_options = []
        for idx, row in df.iterrows():
            ref = str(row['reference_no']) if pd.notna(row['reference_no']) else "No Ref"
            appointment_options.append((row['id'], ref))
        
        if appointment_options:
            selected_ref = st.selectbox("Select to delete:", [opt[1] for opt in appointment_options])
            
            if selected_ref:
                # Find the ID
                selected_id = None
                for opt_id, opt_ref in appointment_options:
                    if opt_ref == selected_ref:
                        selected_id = opt_id
                        break
                
                if selected_id and st.button("🗑️ Delete", type="secondary"):
                    delete_row(conn, selected_id)
                    st.success("Deleted")
                    st.rerun()

# Minimal footer
st.markdown("""
<div style="text-align: center; color: #999; font-size: 0.6rem; margin-top: 0.5rem;">
    Community App
</div>
""", unsafe_allow_html=True)