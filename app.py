import streamlit as st
import pandas as pd
import sqlite3
import uuid
from datetime import date, datetime

st.set_page_config(page_title="Embassy Appointment Tracker", page_icon="📅", layout="wide")

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
            country_city TEXT,
            notes TEXT,
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

def load_df(conn):
    df = pd.read_sql_query("SELECT * FROM appointments", conn)
    # Convert ISO strings -> date
    for col in ["apply_date", "received_date", "interview_date", "created_at"]:
        if col in df.columns:
            if col == "created_at":
                df[col] = pd.to_datetime(df[col], errors="coerce")
            else:
                df[col] = df[col].apply(parse_iso)
    if "interview_date" in df.columns:
        # Sort: newest interview date first; missing dates last
        df["_sort"] = df["interview_date"].apply(lambda x: x if x is not None else date.min)
        df = df.sort_values(["_sort", "created_at"], ascending=[False, False]).drop(columns=["_sort"])
    return df

def insert_row(conn, row):
    conn.execute(
        """INSERT INTO appointments
        (id, name, reference_no, apply_date, received_date, interview_date, country_city, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            row["id"], row["name"], row["reference_no"], row["apply_date"], row["received_date"],
            row["interview_date"], row["country_city"], row["notes"], row["created_at"]
        )
    )
    conn.commit()

def update_row(conn, row_id, fields):
    sets = ", ".join([f"{k}=?" for k in fields.keys()])
    vals = list(fields.values()) + [row_id]
    conn.execute(f"UPDATE appointments SET {sets} WHERE id=?", vals)
    conn.commit()

def delete_row(conn, row_id):
    conn.execute("DELETE FROM appointments WHERE id=?", (row_id,))
    conn.commit()

def df_to_export(df):
    out = df.copy()
    for c in ["apply_date","received_date","interview_date"]:
        if c in out.columns:
            out[c] = out[c].apply(lambda x: x.isoformat() if pd.notna(x) and x is not None else "")
    if "created_at" in out.columns:
        out["created_at"] = out["created_at"].astype(str)
    return out

conn = get_conn()

st.title("📅 Embassy Appointment Tracker")
st.caption("Track: apply date → appointment received → interview date. Latest interview date always shows on top. Name is optional.")

with st.sidebar:
    st.header("➕ Add new entry")
    with st.form("add_form", clear_on_submit=True):
        name = st.text_input("Name (optional)", placeholder="e.g., Saeed Ahmad")
        reference_no = st.text_input("Reference number (optional)", placeholder="e.g., 1999")
        country_city = st.text_input("Embassy / City (optional)", placeholder="e.g., Germany - Islamabad")
        apply_date = st.date_input("Apply date", value=None)
        received_date = st.date_input("Appointment received date", value=None)
        interview_date = st.date_input("Interview date", value=None)
        notes = st.text_area("Notes (optional)", placeholder="Any extra details…")
        submitted = st.form_submit_button("Add")

    if submitted:
        row = {
            "id": str(uuid.uuid4()),
            "name": name.strip(),
            "reference_no": reference_no.strip(),
            "apply_date": to_iso(apply_date) if apply_date else "",
            "received_date": to_iso(received_date) if received_date else "",
            "interview_date": to_iso(interview_date) if interview_date else "",
            "country_city": country_city.strip(),
            "notes": notes.strip(),
            "created_at": datetime.utcnow().isoformat()
        }
        insert_row(conn, row)
        st.success("Saved ✅")

    st.divider()
    st.header("📦 Backup / Restore")
    df_now = load_df(conn)
    export_df = df_to_export(df_now)
    csv_bytes = export_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV backup", data=csv_bytes, file_name="appointments_backup.csv", mime="text/csv")

    uploaded = st.file_uploader("Restore from CSV (replaces duplicates by id)", type=["csv"])
    if uploaded is not None:
        up = pd.read_csv(uploaded)
        required = {"id","name","reference_no","apply_date","received_date","interview_date","country_city","notes","created_at"}
        if not required.issubset(set(up.columns)):
            st.error("CSV format not recognized.")
        else:
            # Upsert
            existing = set(pd.read_sql_query("SELECT id FROM appointments", conn)["id"].tolist())
            inserted = 0
            updated = 0
            for _, r in up.iterrows():
                rid = str(r["id"])
                fields = {
                    "name": str(r.get("name","")),
                    "reference_no": str(r.get("reference_no","")),
                    "apply_date": str(r.get("apply_date","")),
                    "received_date": str(r.get("received_date","")),
                    "interview_date": str(r.get("interview_date","")),
                    "country_city": str(r.get("country_city","")),
                    "notes": str(r.get("notes","")),
                    "created_at": str(r.get("created_at","")),
                }
                if rid in existing:
                    update_row(conn, rid, fields)
                    updated += 1
                else:
                    fields["id"] = rid
                    insert_row(conn, fields)
                    inserted += 1
            st.success(f"Restore complete ✅ Inserted: {inserted}, Updated: {updated}")

    st.divider()
    if st.button("🧹 Delete ALL entries", type="secondary"):
        conn.execute("DELETE FROM appointments")
        conn.commit()
        st.warning("All entries deleted.")

# Main area
df = load_df(conn)

c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.2, 2.0])
with c1:
    q = st.text_input("Search", placeholder="name / ref / city / notes")
with c2:
    only_with_interview = st.checkbox("Only with interview date", value=False)
with c3:
    show_cards = st.checkbox("Card view", value=True)
with c4:
    st.info(f"Total entries: **{len(df)}**")

if q:
    ql = q.lower()
    def row_match(r):
        return any(ql in str(r.get(col,"")).lower() for col in ["name","reference_no","country_city","notes"])
    df = df[df.apply(row_match, axis=1)]

if only_with_interview and "interview_date" in df.columns:
    df = df[df["interview_date"].notna()]

def fmt(d):
    if d is None or (isinstance(d, float) and pd.isna(d)) or (isinstance(d, pd.Timestamp) and pd.isna(d)):
        return ""
    if isinstance(d, pd.Timestamp):
        d = d.date()
    if hasattr(d, "strftime"):
        return d.strftime("%d %b %Y")
    return str(d)

def days_between(a, b):
    if not a or not b:
        return ""
    try:
        return (b - a).days
    except Exception:
        return ""

if len(df) == 0:
    st.warning("No entries yet. Add one from the sidebar.")
    st.stop()

# Cards view (like Facebook posts)
if show_cards:
    for _, r in df.iterrows():
        with st.container(border=True):
            top = st.columns([2.5, 1.5, 1.0, 0.6])
            title = r["name"] if str(r.get("name","")).strip() else "Anonymous"
            ref = str(r.get("reference_no","")).strip()
            place = str(r.get("country_city","")).strip()

            with top[0]:
                st.subheader(title)
                if place:
                    st.caption(place)
            with top[1]:
                if ref:
                    st.markdown(f"**Ref:** `{ref}`")
            with top[2]:
                st.markdown(f"**Interview:** {fmt(r.get('interview_date')) or '—'}")
            with top[3]:
                st.caption("")

            line = st.columns(3)
            with line[0]:
                st.write(f"**Applied:** {fmt(r.get('apply_date')) or '—'}")
            with line[1]:
                st.write(f"**Received:** {fmt(r.get('received_date')) or '—'}")
            with line[2]:
                # simple duration: applied -> interview
                d = days_between(r.get("apply_date"), r.get("interview_date"))
                st.write(f"**Days (apply → interview):** {d if d!='' else '—'}")

            if str(r.get("notes","")).strip():
                st.write(r["notes"])

            actions = st.columns([1,1,6])
            with actions[0]:
                if st.button("✏️ Edit", key=f"edit_{r['id']}"):
                    st.session_state["editing_id"] = r["id"]
            with actions[1]:
                if st.button("🗑️ Delete", key=f"del_{r['id']}"):
                    delete_row(conn, r["id"])
                    st.toast("Deleted")
                    st.rerun()

        # Edit panel
        if st.session_state.get("editing_id") == r["id"]:
            with st.expander("Edit entry", expanded=True):
                with st.form(f"edit_form_{r['id']}"):
                    name2 = st.text_input("Name (optional)", value=str(r.get("name","") or ""))
                    ref2 = st.text_input("Reference number (optional)", value=str(r.get("reference_no","") or ""))
                    place2 = st.text_input("Embassy / City (optional)", value=str(r.get("country_city","") or ""))
                    a2 = st.date_input("Apply date", value=r.get("apply_date"))
                    rec2 = st.date_input("Appointment received date", value=r.get("received_date"))
                    int2 = st.date_input("Interview date", value=r.get("interview_date"))
                    notes2 = st.text_area("Notes", value=str(r.get("notes","") or ""))
                    save = st.form_submit_button("Save changes")
                    cancel = st.form_submit_button("Cancel")
                if save:
                    update_row(conn, r["id"], {
                        "name": name2.strip(),
                        "reference_no": ref2.strip(),
                        "country_city": place2.strip(),
                        "apply_date": to_iso(a2) if a2 else "",
                        "received_date": to_iso(rec2) if rec2 else "",
                        "interview_date": to_iso(int2) if int2 else "",
                        "notes": notes2.strip(),
                    })
                    st.session_state["editing_id"] = None
                    st.success("Updated ✅")
                    st.rerun()
                if cancel:
                    st.session_state["editing_id"] = None
                    st.rerun()

else:
    # Table view
    view = df.copy()
    view["Name"] = view["name"].apply(lambda x: x if str(x).strip() else "Anonymous")
    view["Ref"] = view["reference_no"]
    view["Embassy/City"] = view["country_city"]
    view["Applied"] = view["apply_date"].apply(fmt)
    view["Received"] = view["received_date"].apply(fmt)
    view["Interview"] = view["interview_date"].apply(fmt)
    view["Notes"] = view["notes"]
    st.dataframe(view[["Name","Ref","Embassy/City","Applied","Received","Interview","Notes"]], use_container_width=True, hide_index=True)

st.caption("Tip: Use **Download CSV backup** in the sidebar to keep a copy. On free hosting, storage can reset sometimes.")
