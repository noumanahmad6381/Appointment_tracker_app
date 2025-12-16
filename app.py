import streamlit as st
import pandas as pd
import sqlite3
import uuid
from datetime import date, datetime, timedelta
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

def calculate_months_between(start_date, end_date):
    """Calculate months between two dates"""
    if not start_date or not end_date:
        return None
    try:
        months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
        if end_date.day < start_date.day:
            months -= 1
        return max(0, months)
    except:
        return None

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
                datetime.utcnow().isoformat(),
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

    # Calculate months between apply and interview
    df["months_wait"] = df.apply(
        lambda row: calculate_months_between(row["apply_date"], row["interview_date"]), 
        axis=1
    )

    # Sort: latest received date first, then interview date
    df["_sort_received"] = df["received_date"].apply(lambda x: x if x is not None else date.min)
    df["_sort_interview"] = df["interview_date"].apply(lambda x: x if x is not None else date.min)
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
            datetime.utcnow().isoformat(),
        )
    )
    conn.commit()

def fmt(d):
    if d is None:
        return "—"
    if hasattr(d, "strftime"):
        return d.strftime("%d-%b-%Y")
    return str(d)

# Initialize connection
conn = get_conn()
seed_if_empty(conn)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        text-align: center;
        padding: 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
    }
    .dua-text {
        font-size: 1.2rem;
        font-style: italic;
        text-align: center;
        color: #555;
        margin-bottom: 1rem;
    }
    .compact-table {
        font-size: 0.9rem;
    }
    .dataframe td {
        padding: 0.5rem !important;
    }
    .stDataFrame {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 10px;
    }
    .sidebar .sidebar-content {
        background-color: #f8f9fa;
    }
    .success-box {
        background-color: #d4edda;
        color: #155724;
        padding: 10px;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
        margin: 10px 0;
    }
    </style>
""", unsafe_allow_html=True)

# Header with Dua
st.markdown('<div class="main-header"><h1>🇩🇪 German Embassy Islamabad Appointment Tracker</h1></div>', unsafe_allow_html=True)
st.markdown('<div class="dua-text">🤲 May Allah make it easy for all people who are waiting to meet their loved ones. Ameen.</div>', unsafe_allow_html=True)

# Sidebar for adding new appointments
with st.sidebar:
    st.markdown("### 📝 Add New Appointment")
    st.caption("Quick and simple form for everyone")
    
    with st.form("add_form", clear_on_submit=True):
        # Simple inputs
        name = st.text_input("Name (Optional)", placeholder="Leave empty if unknown")
        reference_no = st.text_input("Reference Number", placeholder="Required*", help="This is important for tracking")
        
        # Get today's date for smart defaults
        today = date.today()
        
        # Appointment receive date (most important)
        received_date = st.date_input(
            "📅 Appointment Receive Date*",
            value=today,
            help="When did you receive the appointment letter?"
        )
        
        # Calculate suggested dates
        suggested_apply_date = received_date - timedelta(days=25*30)  # ~25 months before
        suggested_interview_date = received_date + timedelta(days=60)  # ~2 months after
        
        # Apply date with smart suggestion
        apply_date = st.date_input(
            "📅 Apply Date (Optional)",
            value=None,
            min_value=date(2010, 1, 1),
            max_value=received_date,
            help=f"Suggested: {suggested_apply_date.strftime('%d %b %Y')} (~25 months before receive)"
        )
        
        # Interview date with smart suggestion
        interview_date = st.date_input(
            "📅 Interview Date (Optional)",
            value=None,
            min_value=received_date,
            help=f"Suggested: {suggested_interview_date.strftime('%d %b %Y')} (~2 months after receive)"
        )
        
        submitted = st.form_submit_button("💾 Save Appointment", type="primary")
        
        if submitted:
            if not reference_no.strip():
                st.error("Please enter Reference Number!")
            elif not received_date:
                st.error("Please select Appointment Receive Date!")
            else:
                insert_row(conn, name, reference_no, apply_date, received_date, interview_date)
                st.markdown('<div class="success-box">✅ Appointment saved successfully!</div>', unsafe_allow_html=True)
                st.rerun()

# Load and display data
df = load_df(conn)

if len(df) == 0:
    st.info("No appointments yet. Add one from the sidebar!")
else:
    # Save to CSV backup
    save_to_csv(df)
    
    # Show summary stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total = len(df)
        st.metric("Total Appointments", total)
    with col2:
        latest_received = df['received_date'].max()
        st.metric("Latest Receive Date", fmt(latest_received))
    with col3:
        latest_interview = df['interview_date'].max()
        st.metric("Latest Interview Date", fmt(latest_interview))
    with col4:
        avg_wait = df['months_wait'].mean()
        st.metric("Avg Wait (Months)", f"{avg_wait:.1f}" if pd.notna(avg_wait) else "—")
    
    st.markdown("---")
    st.markdown("### 📋 All Appointments (Latest First)")
    
    # Create display dataframe with formatted columns
    display_df = df.copy()
    display_df = display_df[['name', 'reference_no', 'apply_date', 'received_date', 'interview_date', 'months_wait']]
    
    # Format dates
    for date_col in ['apply_date', 'received_date', 'interview_date']:
        display_df[date_col] = display_df[date_col].apply(fmt)
    
    # Format name column
    display_df['name'] = display_df['name'].apply(lambda x: x if x and str(x).strip() else "—")
    
    # Format months wait
    display_df['months_wait'] = display_df['months_wait'].apply(
        lambda x: f"{int(x)} months" if pd.notna(x) else "—"
    )
    
    # Rename columns for display
    display_df.columns = ['Name', 'Ref No.', 'Apply Date', 'Receive Date', 'Interview Date', 'Total Wait']
    
    # Display as compact table
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Name": st.column_config.TextColumn(width="small"),
            "Ref No.": st.column_config.TextColumn(width="small"),
            "Apply Date": st.column_config.TextColumn(width="small"),
            "Receive Date": st.column_config.TextColumn(width="small"),
            "Interview Date": st.column_config.TextColumn(width="small"),
            "Total Wait": st.column_config.TextColumn(width="small"),
        }
    )
    
    # Download CSV button
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Full Data (CSV)",
        data=csv,
        file_name=f"appointments_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        help="Download complete database for backup"
    )
    
    # Auto-save notification
    st.caption(f"💾 Data auto-saved to: `{CSV_PATH}` | Last updated: {datetime.now().strftime('%d %b %Y %H:%M')}")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; font-size: 0.9rem;">
    <p>Made with ❤️ for the community | Updates automatically | Simple & Easy to use</p>
    <p>📌 Tip: Always fill at least <b>Reference Number</b> and <b>Appointment Receive Date</b></p>
</div>
""", unsafe_allow_html=True)