import re
import unicodedata

import streamlit as st

st.set_page_config(
    page_title="Inscription · Suivi Qualité Production",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from auth_db import VALIDATION_ADMIN, ErreurBase, creer_utilisateur  # noqa: E402
from login_ui import afficher_page  # noqa: E402


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


droite = afficher_page()

with droite:
    sous_titre = (
        "Renseignez vos informations. Votre compte sera activé par un administrateur."
        if VALIDATION_ADMIN
        else "Renseignez vos informations pour créer votre compte."
    )
    st.markdown(
        '<div class="right"><p class="eyebrow">Nouveau compte</p><p class="titre">Inscription</p>'
        f'<p class="sous">{sous_titre}</p></div>',
        unsafe_allow_html=True,
    )

    with st.form("inscription", clear_on_submit=False):
        matricule = st.text_input("Matricule", placeholder="Matricule")
        c1, c2 = st.columns(2)
        nom = c1.text_input("Nom", placeholder="Nom")
        prenom = c2.text_input("Prénom", placeholder="Prénom")
        username = st.text_input("Nom d'utilisateur (facultatif)", placeholder="••••••••")
        mot_de_passe = st.text_input("Mot de passe", type="password", placeholder="8 caractères minimum")
        confirmation = st.text_input("Confirmer le mot de passe", type="password", placeholder="••••••••")
        valider = st.form_submit_button("Créer mon compte")

    if valider:
        matricule, nom, prenom, username = (v.strip() for v in (matricule, nom, prenom, username))

        if not (matricule and nom and prenom and mot_de_passe):
            st.error("Renseignez le matricule, le nom, le prénom et le mot de passe.")
        elif not re.fullmatch(r"[A-Za-z0-9]{1,20}", matricule):
            st.error("Le matricule ne doit contenir que des chiffres et des lettres (20 maximum).")
        elif len(mot_de_passe) < 8:
            st.error("Le mot de passe doit contenir au moins 8 caractères.")
        elif mot_de_passe != confirmation:
            st.error("Les deux mots de passe ne sont pas identiques.")
        else:
            if not username:
                username = re.sub(r"\s+", "", _sans_accents(f"{prenom}.{nom}")).lower()
            try:
                actif = creer_utilisateur(matricule, nom, prenom, username, mot_de_passe)
            except ErreurBase as e:
                st.error(str(e))
            else:
                if actif:
                    st.success("Compte créé. Vous pouvez maintenant vous connecter.")
                else:
                    st.success("Compte créé. Il sera utilisable dès son activation par un administrateur.")

    st.page_link("login_suivi_qualite.py", label="Déjà un compte ? Se connecter")
    st.markdown(
        '<div class="right"><p class="legal">Epsilon · Suivi Qualité Production · '
        'Accès réservé au personnel autorisé</p></div>',
        unsafe_allow_html=True,
    )
