from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import sqlite3
from datetime import date

# FastAPI crée l'application et génère automatiquement la doc interactive
# accessible à http://localhost:8000/docs
app = FastAPI(
    title="DentalScheduler API",
    description="REST API de gestion de rendez-vous pour cabinet dentaire",
    version="1.0.0"
)

# On stocke tout dans un fichier SQLite local.
# Pas besoin d'installer Postgres ou MySQL : SQLite crée le fichier
# automatiquement au premier lancement.
DB = "dental.db"


def get_db():
    """Ouvre une connexion à la base de données.
    row_factory = sqlite3.Row permet de récupérer les résultats
    sous forme de dictionnaires plutôt que de tuples bruts.
    """
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crée les tables si elles n'existent pas encore,
    puis insère quelques données de démonstration au premier lancement.
    Le IF NOT EXISTS et le check COUNT(*) garantissent
    que cette fonction est idempotente : on peut l'appeler
    plusieurs fois sans dupliquer les données.
    """
    conn = get_db()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            nom            TEXT NOT NULL,
            prenom         TEXT NOT NULL,
            email          TEXT UNIQUE NOT NULL,
            telephone      TEXT,
            date_naissance TEXT,
            created_at     TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS rendez_vous (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            date       TEXT NOT NULL,
            heure      TEXT NOT NULL,
            motif      TEXT NOT NULL,
            statut     TEXT DEFAULT 'confirme',
            notes      TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        );
    """)

    # On ne seed les données qu'une seule fois (base vide = premier lancement)
    count = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    if count == 0:
        conn.executescript("""
            INSERT INTO patients (nom, prenom, email, telephone, date_naissance) VALUES
                ('Dupont',  'Marie',   'marie.dupont@email.com', '0612345678', '1990-05-14'),
                ('Martin',  'Lucas',   'lucas.martin@email.com', '0698765432', '1985-11-22'),
                ('Fall',    'Aminata', 'aminata.fall@email.com', '0755556677', '2000-03-08');

            INSERT INTO rendez_vous (patient_id, date, heure, motif, statut, notes) VALUES
                (1, '2026-05-05', '09:00', 'Détartrage', 'confirme', 'Première visite de l année'),
                (1, '2026-05-20', '14:30', 'Contrôle',   'confirme', NULL),
                (2, '2026-05-05', '10:00', 'Extraction',  'confirme', 'Dent de sagesse'),
                (3, '2026-05-06', '11:00', 'Blanchiment', 'annule',   NULL),
                (2, '2026-05-12', '09:30', 'Contrôle',   'confirme', NULL);
        """)

    conn.commit()
    conn.close()


# On initialise la base au démarrage de l'API
init_db()


# ── Modèles Pydantic ────────────────────────────────────────────────────────
# Pydantic valide automatiquement les données reçues dans les requêtes POST/PATCH.
# Si un champ obligatoire manque ou a le mauvais type, FastAPI renvoie
# une erreur 422 avec un message clair, sans qu'on ait à écrire de validation manuellement.

class PatientCreate(BaseModel):
    nom: str
    prenom: str
    email: str                      # champ obligatoire, doit être unique en base
    telephone: Optional[str] = None
    date_naissance: Optional[str] = None


class RendezVousCreate(BaseModel):
    patient_id: int                 # doit correspondre à un patient existant
    date: str                       # format attendu : YYYY-MM-DD
    heure: str                      # format attendu : HH:MM
    motif: str
    notes: Optional[str] = None


class StatutUpdate(BaseModel):
    statut: str                     # valeurs acceptées : confirme | annule | en_attente


# ── Endpoints Patients ──────────────────────────────────────────────────────

@app.get("/patients", tags=["Patients"])
def liste_patients():
    """Retourne tous les patients triés par nom."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM patients ORDER BY nom").fetchall()
    conn.close()
    # dict(r) convertit chaque Row SQLite en dictionnaire JSON-sérialisable
    return [dict(r) for r in rows]


@app.get("/patients/{patient_id}", tags=["Patients"])
def get_patient(patient_id: int):
    """Récupère un patient par son ID.
    Renvoie 404 si l'ID n'existe pas en base.
    """
    conn = get_db()
    row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Patient introuvable")
    return dict(row)


@app.post("/patients", tags=["Patients"], status_code=201)
def creer_patient(p: PatientCreate):
    """Crée un nouveau patient.
    Renvoie 201 (Created) en cas de succès.
    Renvoie 409 (Conflict) si l'email est déjà utilisé
    (contrainte UNIQUE sur la colonne email en base).
    """
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO patients (nom, prenom, email, telephone, date_naissance) VALUES (?,?,?,?,?)",
            (p.nom, p.prenom, p.email, p.telephone, p.date_naissance)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM patients WHERE id = ?", (cur.lastrowid,)).fetchone()
        conn.close()
        return dict(row)
    except sqlite3.IntegrityError:
        # IntegrityError est levée par SQLite quand la contrainte UNIQUE est violée
        conn.close()
        raise HTTPException(status_code=409, detail="Cet email est déjà utilisé")


# ── Endpoints Rendez-vous ───────────────────────────────────────────────────

@app.get("/rendez-vous", tags=["Rendez-vous"])
def liste_rdv(
    date:       Optional[str] = Query(None, description="Filtrer par date YYYY-MM-DD"),
    statut:     Optional[str] = Query(None, description="confirme | annule | en_attente"),
    patient_id: Optional[int] = Query(None, description="ID du patient")
):
    """Liste les rendez-vous avec filtres optionnels combinables.
    On construit la requête SQL dynamiquement selon les paramètres
    fournis : WHERE 1=1 permet d'ajouter des AND sans cas particulier
    pour le premier filtre.
    La jointure avec patients évite de renvoyer juste un patient_id brut.
    """
    conn = get_db()
    sql = """
        SELECT r.*, p.nom, p.prenom, p.email
        FROM rendez_vous r
        JOIN patients p ON r.patient_id = p.id
        WHERE 1=1
    """
    params = []

    if date:
        sql += " AND r.date = ?"
        params.append(date)
    if statut:
        sql += " AND r.statut = ?"
        params.append(statut)
    if patient_id:
        sql += " AND r.patient_id = ?"
        params.append(patient_id)

    sql += " ORDER BY r.date, r.heure"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/rendez-vous", tags=["Rendez-vous"], status_code=201)
def creer_rdv(rdv: RendezVousCreate):
    """Crée un rendez-vous pour un patient existant.
    On vérifie d'abord que le patient_id existe bien en base
    avant d'insérer, pour renvoyer un 404 explicite plutôt
    qu'une erreur de contrainte SQLite peu lisible.
    """
    conn = get_db()
    patient = conn.execute("SELECT id FROM patients WHERE id = ?", (rdv.patient_id,)).fetchone()
    if not patient:
        conn.close()
        raise HTTPException(status_code=404, detail="Patient introuvable")

    cur = conn.execute(
        "INSERT INTO rendez_vous (patient_id, date, heure, motif, notes) VALUES (?,?,?,?,?)",
        (rdv.patient_id, rdv.date, rdv.heure, rdv.motif, rdv.notes)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM rendez_vous WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)


@app.patch("/rendez-vous/{rdv_id}/statut", tags=["Rendez-vous"])
def update_statut(rdv_id: int, body: StatutUpdate):
    """Met à jour uniquement le statut d'un rendez-vous.
    On utilise PATCH (mise à jour partielle) plutôt que PUT (remplacement complet)
    car on ne touche qu'à un seul champ.
    La validation des valeurs autorisées est faite ici manuellement
    avant d'envoyer quoi que ce soit en base.
    """
    valeurs_autorisees = ("confirme", "annule", "en_attente")
    if body.statut not in valeurs_autorisees:
        raise HTTPException(
            status_code=400,
            detail=f"Statut invalide. Valeurs acceptées : {', '.join(valeurs_autorisees)}"
        )

    conn = get_db()
    conn.execute("UPDATE rendez_vous SET statut = ? WHERE id = ?", (body.statut, rdv_id))
    conn.commit()
    row = conn.execute("SELECT * FROM rendez_vous WHERE id = ?", (rdv_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Rendez-vous introuvable")
    return dict(row)


# ── Endpoint Stats ──────────────────────────────────────────────────────────

@app.get("/stats", tags=["Stats"])
def stats():
    """Retourne un résumé rapide de l'activité du cabinet.
    Toutes les valeurs sont calculées en une seule ouverture de connexion
    pour éviter d'ouvrir/fermer la base plusieurs fois inutilement.
    """
    conn = get_db()
    today = date.today().isoformat()  # format YYYY-MM-DD, identique à ce qu'on stocke en base

    result = {
        "total_patients":  conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0],
        "total_rdv":       conn.execute("SELECT COUNT(*) FROM rendez_vous").fetchone()[0],
        "rdv_confirmes":   conn.execute("SELECT COUNT(*) FROM rendez_vous WHERE statut='confirme'").fetchone()[0],
        "rdv_annules":     conn.execute("SELECT COUNT(*) FROM rendez_vous WHERE statut='annule'").fetchone()[0],
        "rdv_aujourd_hui": conn.execute(
            "SELECT COUNT(*) FROM rendez_vous WHERE date = ? AND statut = 'confirme'", (today,)
        ).fetchone()[0],
    }

    conn.close()
    return result


# ── Lancement ───────────────────────────────────────────────────────────────
# Ce bloc est utilisé par Railway (et tout hébergeur) pour démarrer l'API.
# La variable PORT est injectée automatiquement par la plateforme.
# En local, si PORT n'est pas défini, on utilise 8000 par défaut.

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
