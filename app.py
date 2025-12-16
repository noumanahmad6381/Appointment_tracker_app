import streamlit as st
import pandas as pd
import sqlite3
import uuid
from datetime import date, datetime

st.set_page_config(page_title="German Embassy Islamabad Appointment Tracker", page_icon="📅", layout="wide")

DB_PATH = "appointments.db"

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

def to_iso(d):
    return d.isoformat() if isinstance(d, (date, datetime)) else (d or "")

def parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None

def seed_if_empty(conn):
    cur = conn.execute("SELECT COUNT(*) FROM appointments")
    n = cur.fetchone()[0]
    if n > 0:
        return

    seed = [
        # From your example screenshots
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

    # Sort: latest interview date first; missing dates last
    df["_sort"] = df["interview_date"].apply(lambda x: x if x is not None else date.min)
    df = df.sort_values(["_sort", "created_at"], ascending=[False, False]).drop(columns=["_sort"])

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
        return d.strftime("%d %b %Y")
    return str(d)

conn = get_conn()
seed_if_empty(conn)

st.title("🇩🇪 German Embassy Islamabad Appointment Tracker")
st.caption("Add entries below. Records are shown automatically with the **latest interview date on top**. (No delete / no CSV export.)")

with st.sidebar:
    st.header("➕ Add new entry")
    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("Name (optional)", placeholder="e.g., Saeed Ahmad")
        reference_no = st.text_input("Reference No. (optional)", placeholder="e.g., 1999")
        apply_date = st.date_input("Apply date (optional)", value=None)
        received_date = st.date_input("Appointment receive date (optional)", value=None)
        interview_date = st.date_input("Interview date (optional)", value=None)
        submitted = st.form_submit_button("Save")

    if submitted:
        insert_row(conn, name, reference_no, apply_date, received_date, interview_date)
        st.success("Saved ✅ (cannot be deleted)")
        st.rerun()

df = load_df(conn)

if len(df) == 0:
    st.info("No records yet. Add one from the left sidebar.")
    st.stop()

# Simple, clean cards
for _, r in df.iterrows():
    title = r["name"].strip() if str(r.get("name","")).strip() else "Anonymous"

    with st.container(border=True):
        top = st.columns([2.5, 1.4, 1.4])
        with top[0]:
            st.subheader(title)
        with top[1]:
            ref = str(r.get("reference_no","")).strip()
            st.markdown(f"**Reference:** `{ref}`" if ref else "**Reference:** —")
        with top[2]:
            st.markdown(f"**Interview:** {fmt(r.get('interview_date'))}")

        cols = st.columns(3)
        with cols[0]:
            st.write(f"**Applied:** {fmt(r.get('apply_date'))}")
        with cols[1]:
            st.write(f"**Received:** {fmt(r.get('received_date'))}")
        with cols[2]:
            st.write("")  # spacer
