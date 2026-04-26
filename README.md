# dental-scheduler-api

I built this project to practice building a full-stack application from scratch: a REST API on the back-end and a real interface on the front-end.

The idea: a management tool for a dental practice. You can create patients, book appointments, update their status, filter by date or by patient, and see live stats on the dashboard. It is the kind of thing DentalCall actually builds, so it felt like a good subject to practice on.

---

## What it looks like

The front-end is a Streamlit app that talks to the FastAPI back-end:

- Dashboard with 4 live stats (total patients, appointments, confirmed, today)
- Appointment list with filters by date, status and patient
- One-click status update (confirm / cancel) directly from the list
- Patient detail page with their full appointment history
- Forms to create new patients and book new appointments

---

## How it works

```
app.py (Streamlit)  <-->  main.py (FastAPI)  <-->  dental.db (SQLite)
```

The front-end sends HTTP requests to the API. The API reads and writes to the database. The database file is created automatically on first run, no setup needed.

---

## Stack

- Python 3.10+
- FastAPI (REST back-end, auto-generates interactive docs at `/docs`)
- SQLite (lightweight database, no installation required)
- Streamlit (front-end interface)
- Pydantic (request validation)
- Requests (HTTP calls from the front-end to the API)

---

## Run it locally

You need two terminals open at the same time.

**Terminal 1: start the API**
```bash
git clone https://github.com/sokhna-ai/dental-scheduler-api.git
cd dental-scheduler-api
pip install -r requirements.txt
uvicorn main:app --reload
```

**Terminal 2: start the interface**
```bash
streamlit run app.py
```

Then open **http://localhost:8501** for the interface, or **http://localhost:8000/docs** if you want to test the API directly.

The database seeds itself on first run with 3 patients and 5 appointments so you can explore right away.

---

## API endpoints

| Endpoint | Method | What it does |
|---|---|---|
| `/patients` | GET | List all patients |
| `/patients/{id}` | GET | Get one patient |
| `/patients` | POST | Create a patient |
| `/rendez-vous` | GET | List appointments (filterable by date, status, patient) |
| `/rendez-vous` | POST | Book an appointment |
| `/rendez-vous/{id}/statut` | PATCH | Update status: confirme / annule / en_attente |
| `/stats` | GET | Dashboard stats |

---

## What I learned building this

Making the front-end and the back-end talk to each other cleanly is harder than building either one alone. I had to think about error handling on both sides (what the API returns, how the interface displays it), how to keep state between re-renders in Streamlit, and how to design the API so the front-end never has to do extra work to display something useful.
