import streamlit as st

st.set_page_config(
    page_title="Connexion · Suivi Qualité Production",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from auth_db import ErreurBase, authentifier  # noqa: E402
from login_ui import afficher_page  # noqa: E402
from session import ouvrir_session, restaurer_session  # noqa: E402

APPLICATION = "pages/application.py"

st.session_state.setdefault("utilisateur", None)
restaurer_session()  # [AJOUT] reprend la session si un jeton valide est dans l'URL (après un F5)

# Déjà connecté : on va directement à l'application
if st.session_state.utilisateur:
    st.switch_page(APPLICATION)

droite = afficher_page()

with droite:
    st.markdown(
        '<div class="right"><p class="eyebrow">Espace sécurisé</p><p class="titre">Connexion</p>'
        '<p class="sous">Saisissez votre matricule et votre mot de passe.</p></div>',
        unsafe_allow_html=True,
    )

    with st.form("login", clear_on_submit=False):
        matricule = st.text_input("Matricule", placeholder="Ex. 4350")
        mot_de_passe = st.text_input("Mot de passe", type="password", placeholder="••••••••")
        valider = st.form_submit_button("Se connecter")

    if valider:
        if not matricule.strip():
            st.error("Saisissez votre matricule.")
        elif not mot_de_passe:
            st.error("Saisissez votre mot de passe.")
        else:
            try:
                statut, user = authentifier(matricule.strip(), mot_de_passe)
            except ErreurBase as e:
                st.error(str(e))
            else:
                if statut == "ok":
                    ouvrir_session(user)  # [AJOUT] session_state + jeton dans l'URL
                    st.switch_page(APPLICATION)
                elif statut == "inactif":
                    st.warning("Votre compte n'est pas encore activé. Contactez votre administrateur.")
                else:
                    st.error("Matricule ou mot de passe incorrect.")

    st.page_link("pages/inscription.py", label="Pas encore de compte ? S'inscrire")
    st.markdown(
        '<div class="right"><p class="legal">Epsilon · Suivi Qualité Production · '
        'Accès réservé au personnel autorisé</p></div>',
        unsafe_allow_html=True,
    )
