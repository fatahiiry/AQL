import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Utilisateurs · Suivi Qualité",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="expanded",
)

from session import assurer_jeton, fermer_session, restaurer_session  # noqa: E402

# ── Accès réservé : connecté ET administrateur
restaurer_session()  # reprend la session si un jeton valide est dans l'URL (après un F5)
if not st.session_state.get("utilisateur"):
    st.switch_page("login_suivi_qualite.py")
    st.stop()
utilisateur = st.session_state.utilisateur
assurer_jeton(utilisateur)  # pose le jeton dans l'URL pour survivre à un F5

import styles  # noqa: E402  (votre feuille de styles existante)
from auth_db import (  # noqa: E402
    ROLES, ROLES_ADMIN, ErreurBase, definir_actif, definir_role,
    lister_utilisateurs, reinitialiser_mot_de_passe, supprimer_utilisateur,
)
from theme_app import appliquer_theme, entete  # noqa: E402

styles.apply_custom_styles()
appliquer_theme()

with st.sidebar:
    st.caption(f"👤 **{utilisateur['prenom']} {utilisateur['nom']}** · {utilisateur['role']}")
    st.page_link("pages/application.py", label="← Retour à l'application")
    if st.button("🚪 Se déconnecter", key="btn_logout"):
        fermer_session()
        st.switch_page("login_suivi_qualite.py")

st.markdown(entete("👥 GESTION DES UTILISATEURS", "Activer les comptes et gérer les rôles"), unsafe_allow_html=True)

if utilisateur["role"] not in ROLES_ADMIN:
    st.error("Cette page est réservée aux administrateurs.")
    st.stop()


def _agir(fonction, *args, message: str):
    try:
        fonction(*args)
    except ErreurBase as e:
        st.error(str(e))
    else:
        st.toast(message, icon="✅")
        st.rerun()


try:
    comptes = lister_utilisateurs()
except ErreurBase as e:
    st.error(str(e))
    st.stop()

en_attente = [c for c in comptes if not c["actif"]]

m1, m2, m3 = st.columns(3)
m1.metric("En attente d'activation", len(en_attente))
m2.metric("Comptes actifs", len(comptes) - len(en_attente))
m3.metric("Total", len(comptes))

# ── 1. Comptes en attente
st.markdown("### ⏳ Comptes en attente d'activation")
if not en_attente:
    st.info("Aucun compte en attente.")

for c in en_attente:
    with st.container(border=True):
        col_id, col_role, col_ok, col_ko = st.columns([4, 2, 1.4, 1.4], vertical_alignment="center")
        date = c["created_at"].strftime("%d/%m/%Y %H:%M") if c["created_at"] else "—"
        col_id.markdown(
            f"**{c['prenom']} {c['nom']}**  \nMatricule {c['matricule']} · {c['username']} · inscrit le {date}"
        )
        role = col_role.selectbox(
            "Rôle", ROLES, index=ROLES.index(c["role"]) if c["role"] in ROLES else 0,
            key=f"role_{c['id']}", label_visibility="collapsed",
        )
        if col_ok.button("✅ Activer", key=f"act_{c['id']}", type="primary", use_container_width=True):
            if role != c["role"]:
                definir_role(c["id"], role)
            _agir(definir_actif, c["id"], True, message=f"Compte {c['matricule']} activé")

        if st.session_state.get(f"conf_{c['id']}"):
            if col_ko.button("Confirmer", key=f"yes_{c['id']}", use_container_width=True):
                st.session_state.pop(f"conf_{c['id']}", None)
                _agir(supprimer_utilisateur, c["id"], message=f"Compte {c['matricule']} supprimé")
        elif col_ko.button("Refuser", key=f"no_{c['id']}", use_container_width=True):
            st.session_state[f"conf_{c['id']}"] = True
            st.rerun()

# ── 2. Réinitialiser le mot de passe d'un utilisateur
st.markdown("### 🔑 Réinitialiser un mot de passe")
comptes_tries = sorted(comptes, key=lambda c: (c["nom"], c["prenom"]))
options = {f"{c['matricule']} — {c['prenom']} {c['nom']}": c["id"] for c in comptes_tries}

with st.form("reset_mdp", clear_on_submit=False):
    choix = st.selectbox("Utilisateur", list(options), index=None, placeholder="Choisir un utilisateur…")
    confirmer = st.form_submit_button("Générer un nouveau mot de passe")

if confirmer:
    if not choix:
        st.warning("Sélectionnez un utilisateur.")
    else:
        try:
            temporaire = reinitialiser_mot_de_passe(options[choix])
        except ErreurBase as e:
            st.error(str(e))
        else:
            st.success(f"Mot de passe réinitialisé pour **{choix}**.")
            st.code(temporaire, language=None)
            st.caption(
                "Transmettez ce mot de passe temporaire à l'utilisateur par un canal sûr "
                "(de vive voix, par exemple) — il ne sera plus jamais affiché."
            )

# ── 3. Tous les comptes
st.markdown("### 👥 Tous les comptes")
recherche = st.text_input("Rechercher (matricule, nom, prénom)", key="recherche_compte")

df = pd.DataFrame(comptes)
if recherche.strip():
    q = recherche.strip().lower()
    masque = df[["matricule", "nom", "prenom", "username"]].astype(str).apply(
        lambda col: col.str.lower().str.contains(q, regex=False)
    ).any(axis=1)
    df = df[masque]

colonnes = ["matricule", "nom", "prenom", "username", "role", "actif", "created_at"]
modifie = st.data_editor(
    df[colonnes],
    hide_index=True,
    use_container_width=True,
    disabled=["matricule", "nom", "prenom", "username", "created_at"],
    column_config={
        "matricule": "Matricule", "nom": "Nom", "prenom": "Prénom", "username": "Utilisateur",
        "role": st.column_config.SelectboxColumn("Rôle", options=ROLES, required=True),
        "actif": st.column_config.CheckboxColumn("Actif"),
        "created_at": st.column_config.DatetimeColumn("Inscrit le", format="DD/MM/YYYY HH:mm"),
    },
    key="editeur_comptes",
)

if st.button("💾 Enregistrer les modifications", type="primary"):
    nb, refuses = 0, []
    try:
        for idx in df.index:
            uid = int(df.at[idx, "id"])
            nouveau_actif, nouveau_role = bool(modifie.at[idx, "actif"]), modifie.at[idx, "role"]
            if nouveau_actif == df.at[idx, "actif"] and nouveau_role == df.at[idx, "role"]:
                continue
            if uid == utilisateur["id"] and (not nouveau_actif or nouveau_role not in ROLES_ADMIN):
                refuses.append("Vous ne pouvez pas désactiver ou rétrograder votre propre compte.")
                continue
            if nouveau_actif != df.at[idx, "actif"]:
                definir_actif(uid, nouveau_actif)
            if nouveau_role != df.at[idx, "role"]:
                definir_role(uid, nouveau_role)
            nb += 1
    except ErreurBase as e:
        st.error(str(e))
    else:
        for r in set(refuses):
            st.warning(r)
        if nb:
            st.toast(f"{nb} compte(s) mis à jour", icon="✅")
            st.rerun()
        elif not refuses:
            st.info("Aucune modification à enregistrer.")
