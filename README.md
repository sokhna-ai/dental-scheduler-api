# dental-scheduler-api

I built this project to practice building a real REST API from scratch with Python.

The idea: a small back-end for a dental practice. You can create patients, book appointments, filter them by date or status, and get a quick stats summary. Nothing fancy, but everything works and the code is clean.

---

## Endpoints

| Endpoint | Method | What it does |
|---|---|---|
| `/patients` | GET | List all patients |
| `/patients/{id}` | GET | Get one patient by ID |
| `/patients` | POST | Add a new patient |
| `/rendez-vous` | GET | List appointments (filterable) |
| `/rendez-vous` | POST | Book an appointment |
| `/rendez-vous/{id}/statut` | PATCH | Update status: confirme / annule / en_attente |
| `/stats` | GET | Quick cabinet overview |

The `/rendez-vous` endpoint accepts optional query params you can combine freely: `?date=2026-05-05`, `?statut=confirme`, `?patient_id=1`.

---

## Stack

- Python 3.10+
- FastAPI (REST framework, auto-generates interactive docs at `/docs`)
- SQLite (no database setup needed, the file is created automatically)
- Pydantic (request validation)

---

## Run it locally

```bash
git clone https://github.com/sokhna-ai/dental-scheduler-api.git
cd dental-scheduler-api

pip install -r requirements.txt

uvicorn main:app --reload
```

Go to **http://localhost:8000/docs** and you get a full interactive interface to test every endpoint directly in the browser. FastAPI generates it automatically from the code.

The database is created and seeded on first run (3 patients, 5 appointments ready to use).

---

## Example responses

**GET /stats**
```json
{
  "total_patients": 3,
  "total_rdv": 5,
  "rdv_confirmes": 4,
  "rdv_annules": 1,
  "rdv_aujourd_hui": 0
}
```

**GET /rendez-vous?date=2026-05-05**
```json
[
  { "id": 1, "heure": "09:00", "motif": "Détartrage", "statut": "confirme", "nom": "Dupont", "prenom": "Marie" },
  { "id": 3, "heure": "10:00", "motif": "Extraction", "statut": "confirme", "nom": "Martin", "prenom": "Lucas" }
]
```

**POST /patients** (request body)
```json
{ "nom": "Fall", "prenom": "Sokhna", "email": "s@example.com", "telephone": "0600000000" }
```

---

## What I learned building this

Designing REST endpoints cleanly is harder than it looks. I had to think about when to use path params vs query params, which HTTP status codes actually make sense (201 for creation, 409 when an email already exists, 404 when a resource is not found), and how to write JOIN queries so the API returns useful data instead of just raw foreign key IDs.
