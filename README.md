# Embassy Appointment Tracker (Streamlit)

A tiny interactive app to track:
- Apply date
- Appointment received date
- Interview date (sorted so latest interview appears on top)
- Optional name, reference number, embassy/city, notes

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy for free (easiest)
### Option A: Streamlit Community Cloud
1. Create a GitHub repo and upload `app.py` + `requirements.txt`.
2. Go to Streamlit Community Cloud and deploy from your repo.
3. Your app gets a public link.

### Option B: Render / Railway
Use a Streamlit template and set the start command:
```bash
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

## Notes about storage
The app stores data in a small SQLite file (`appointments.db`). On some free platforms, storage can reset.  
Use **Download CSV backup** to keep your data safe and restore later.
