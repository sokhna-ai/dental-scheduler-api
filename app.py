import streamlit as st
import requests
import os
from datetime import date

# URL de l'API back-end. On la met en variable pour pouvoir
# la changer facilement si on déploie ailleurs.
API = os.getenv("API_URL", "http://localhost:8000")

# ── Configuration de la page ────────────────────────────────────────────────
st.set_page_config(
    page_title="DentalScheduler",
    page_icon="🦷",
    layout="wide"
)

st.title("🦷 DentalScheduler")
st.caption("Interface de gestion des patients et rendez-vous")

# ── Fonctions d'appel à l'API ───────────────────────────────────────────────
# On centralise tous les appels HTTP ici pour ne pas répéter
# le try/except partout dans l'interface.

def get(endpoint, params=None):
    """Appel GET vers l'API. Retourne le JSON ou None en cas d'erreur."""
    try:
        r = requests.get(f"{API}{endpoint}", params=params, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Erreur API : {e}")
        return None

def post(endpoint, data):
    """Appel POST vers l'API. Retourne le JSON créé ou None."""
    try:
        r = requests.post(f"{API}{endpoint}", json=data, timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        detail = e.response.json().get("detail", str(e))
        st.error(f"Erreur : {detail}")
        return None

def patch(endpoint, data):
    """Appel PATCH vers l'API pour les mises à jour partielles."""
    try:
        r = requests.patch(f"{API}{endpoint}", json=data, timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        detail = e.response.json().get("detail", str(e))
        st.error(f"Erreur : {detail}")
        return None

# ── Tableau de bord (stats en haut de page) ─────────────────────────────────
stats = get("/stats")
if stats:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Patients", stats["total_patients"])
    col2.metric("RDV total", stats["total_rdv"])
    col3.metric("Confirmés", stats["rdv_confirmes"])
    col4.metric("Aujourd'hui", stats["rdv_aujourd_hui"])

st.divider()

# ── Navigation par onglets ───────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📅 Rendez-vous", "👤 Patients", "➕ Nouveau RDV", "➕ Nouveau patient"
])

# ════════════════════════════════════════════════════════════════════════════
# ONGLET 1 : Liste des rendez-vous avec filtres
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Rendez-vous")

    # Filtres côte à côte
    f1, f2, f3 = st.columns(3)
    with f1:
        filtre_date = st.date_input(
            "Filtrer par date",
            value=None,
            help="Laisse vide pour voir tous les RDV"
        )
    with f2:
        filtre_statut = st.selectbox(
            "Filtrer par statut",
            ["Tous", "confirme", "annule", "en_attente"]
        )
    with f3:
        # Récupère la liste des patients pour le filtre par nom
        patients = get("/patients") or []
        noms = ["Tous"] + [f"{p['prenom']} {p['nom']}" for p in patients]
        filtre_patient = st.selectbox("Filtrer par patient", noms)

    # Construction des paramètres de filtre à envoyer à l'API
    params = {}
    if filtre_date:
        params["date"] = filtre_date.isoformat()
    if filtre_statut != "Tous":
        params["statut"] = filtre_statut
    if filtre_patient != "Tous":
        # On retrouve l'ID du patient sélectionné
        prenom, nom = filtre_patient.split(" ", 1)
        match = next((p for p in patients if p["prenom"] == prenom and p["nom"] == nom), None)
        if match:
            params["patient_id"] = match["id"]

    rdvs = get("/rendez-vous", params=params) or []

    if not rdvs:
        st.info("Aucun rendez-vous trouvé pour ces filtres.")
    else:
        # Couleur du badge selon le statut
        couleur = {"confirme": "🟢", "annule": "🔴", "en_attente": "🟡"}

        for rdv in rdvs:
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 3, 2])
                with c1:
                    st.write(f"**{rdv['date']} à {rdv['heure']}**")
                    st.caption(f"{rdv['prenom']} {rdv['nom']}")
                with c2:
                    st.write(f"**{rdv['motif']}**")
                    if rdv.get("notes"):
                        st.caption(rdv["notes"])
                with c3:
                    emoji = couleur.get(rdv["statut"], "⚪")
                    st.write(f"{emoji} {rdv['statut']}")

                    # Boutons pour changer le statut directement depuis l'interface
                    if rdv["statut"] != "confirme":
                        if st.button("Confirmer", key=f"conf_{rdv['id']}"):
                            patch(f"/rendez-vous/{rdv['id']}/statut", {"statut": "confirme"})
                            st.rerun()
                    if rdv["statut"] != "annule":
                        if st.button("Annuler", key=f"ann_{rdv['id']}"):
                            patch(f"/rendez-vous/{rdv['id']}/statut", {"statut": "annule"})
                            st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# ONGLET 2 : Liste des patients
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Patients enregistrés")
    patients = get("/patients") or []

    if not patients:
        st.info("Aucun patient enregistré.")
    else:
        for p in patients:
            with st.expander(f"**{p['prenom']} {p['nom']}** | {p['email']}"):
                c1, c2 = st.columns(2)
                c1.write(f"Téléphone : {p.get('telephone') or 'non renseigné'}")
                c2.write(f"Né(e) le : {p.get('date_naissance') or 'non renseigné'}")
                c1.caption(f"ID : {p['id']}  |  Créé le : {p['created_at'][:10]}")

                # Affiche les RDV de ce patient directement dans la fiche
                rdvs_patient = get("/rendez-vous", params={"patient_id": p["id"]}) or []
                if rdvs_patient:
                    st.write(f"**{len(rdvs_patient)} rendez-vous :**")
                    for r in rdvs_patient:
                        st.caption(f"  {r['date']} à {r['heure']} : {r['motif']} ({r['statut']})")
                else:
                    st.caption("Aucun rendez-vous.")

# ════════════════════════════════════════════════════════════════════════════
# ONGLET 3 : Formulaire de création d'un rendez-vous
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Nouveau rendez-vous")

    patients = get("/patients") or []
    if not patients:
        st.warning("Aucun patient enregistré. Commencez par créer un patient.")
    else:
        # On construit une liste lisible pour le selectbox
        options = {f"{p['prenom']} {p['nom']}": p["id"] for p in patients}

        with st.form("form_rdv"):
            patient_choisi = st.selectbox("Patient", list(options.keys()))
            col1, col2 = st.columns(2)
            with col1:
                rdv_date = st.date_input("Date", min_value=date.today())
            with col2:
                rdv_heure = st.time_input("Heure")
            motif = st.selectbox("Motif", [
                "Contrôle", "Détartrage", "Extraction", "Blanchiment",
                "Pose de couronne", "Traitement de canal", "Autre"
            ])
            notes = st.text_area("Notes (optionnel)")
            submit = st.form_submit_button("Réserver le rendez-vous", type="primary")

        if submit:
            result = post("/rendez-vous", {
                "patient_id": options[patient_choisi],
                "date": rdv_date.isoformat(),
                "heure": rdv_heure.strftime("%H:%M"),
                "motif": motif,
                "notes": notes if notes else None
            })
            if result:
                st.success(f"Rendez-vous créé : {result['date']} à {result['heure']} pour {patient_choisi}.")

# ════════════════════════════════════════════════════════════════════════════
# ONGLET 4 : Formulaire de création d'un patient
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("Nouveau patient")

    with st.form("form_patient"):
        col1, col2 = st.columns(2)
        with col1:
            nom = st.text_input("Nom *")
            email = st.text_input("Email *")
            date_naissance = st.date_input("Date de naissance", value=None)
        with col2:
            prenom = st.text_input("Prénom *")
            telephone = st.text_input("Téléphone")

        submit_p = st.form_submit_button("Créer le patient", type="primary")

    if submit_p:
        if not nom or not prenom or not email:
            st.error("Nom, prénom et email sont obligatoires.")
        else:
            result = post("/patients", {
                "nom": nom,
                "prenom": prenom,
                "email": email,
                "telephone": telephone if telephone else None,
                "date_naissance": date_naissance.isoformat() if date_naissance else None
            })
            if result:
                st.success(f"Patient créé : {result['prenom']} {result['nom']} (ID {result['id']}).")
