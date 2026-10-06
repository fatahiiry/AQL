import html
import os
import time
import pandas as pd
from sqlalchemy import text
import streamlit as st
import database as db
import defaut_typologie as def_type
import historique as hist
import styles
from formulaire import render_formulaire
from theme_app import appliquer_theme
from auth_db import ROLES_ADMIN
from session import assurer_jeton, fermer_session, restaurer_session
import extraction_mesures

# ── Configuration de la page
st.set_page_config(
    page_title="Contrôle Qualité",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── [AJOUT] Accès réservé : il faut être connecté
restaurer_session()  # reprend la session si un jeton valide est dans l'URL (après un F5)
if not st.session_state.get("utilisateur"):
    st.switch_page("login_suivi_qualite.py")
    st.stop()
utilisateur = st.session_state.utilisateur
assurer_jeton(utilisateur)  # [AJOUT] pose le jeton dans l'URL pour survivre à un F5
est_admin = utilisateur["role"] in ROLES_ADMIN  # [AJOUT] menus réservés aux administrateurs


@st.cache_resource(ttl=900)
def synchro_automatique():
    return db.extraire_et_centraliser()


# Lancement silencieux
synchro_automatique()


styles.apply_custom_styles()
appliquer_theme()  # [AJOUT] nouveau design

# ── Initialisation du Session State
if "maj_counter" not in st.session_state:
    st.session_state.maj_counter = 0
if "min_counter" not in st.session_state:
    st.session_state.min_counter = 0
if "sec_counter" not in st.session_state:
    st.session_state.sec_counter = 0


# ── Fonction d'importation pour la Grille Sur-Mesure
def importer_sur_mesure_excel(uploaded_file):
    """Extrait la feuille 'FICHE MESURE', nettoie les données et synchronise avec SQL Server."""
    df = pd.read_excel(uploaded_file, sheet_name="FICHE MESURE")

    # Renommage des colonnes
    df = df.rename(
        columns={
            "Name": "nom_modele",
            "Point de Mesure": "point_de_mesure",
            "Tolérance": "tolerance",
            "Taille": "taille",
            "Valeur": "valeur_cible",
        }
    )

    cols_attendues = [
        "nom_modele",
        "point_de_mesure",
        "tolerance",
        "taille",
        "valeur_cible",
    ]
    df = df[cols_attendues]

    # Nettoyage des données
    df["nom_modele"] = df["nom_modele"].astype(str).str.strip()
    df["point_de_mesure"] = df["point_de_mesure"].astype(str).str.strip()
    df["taille"] = (
        df["taille"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    )

    df["tolerance"] = (
        pd.to_numeric(
            df["tolerance"].astype(str).str.replace(",", "."), errors="coerce"
        )
        .fillna(0.0)
    )

    df["valeur_cible"] = (
        pd.to_numeric(
            df["valeur_cible"].astype(str).str.replace(",", "."),
            errors="coerce",
        )
        .round(2)
    )

    modeles = [str(m) for m in df["nom_modele"].unique() if pd.notna(m)]

    # Synchronisation avec la BDD via db.engine
    with db.engine.begin() as conn:
        for mod in modeles:
            conn.execute(
                text("DELETE FROM mesures_modele WHERE nom_modele = :m"),
                {"m": mod},
            )

        df.to_sql(
            name="mesures_modele", con=conn, if_exists="append", index=False
        )

    return len(modeles), len(df)


# ── Vue de la page d'Importation (Imports Master)
def render_imports():
    st.markdown("## 📥 Synchronisation des Données Master")
    st.divider()

    st.info(
        "💡 Vous pouvez charger un seul fichier Excel s'il contient les deux feuilles, ou charger des fichiers distincts."
    )

    col_sm, col_def = st.columns(2)

    # ── 1. Import Sur-Mesure
    with col_sm:
        st.subheader("📏 Grille Sur-Mesure")
        st.caption("Feuille : **FICHE MESURE** ➔ Table `mesures_modele`")

        file_sm = st.file_uploader(
            "Fichier Excel Sur-Mesure (.xlsx)",
            type=["xlsx", "xls"],
            key="up_sm_file",
        )

        if file_sm is not None:
            try:
                df_preview_sm = pd.read_excel(
                    file_sm, sheet_name="FICHE MESURE"
                )
                st.markdown("##### 📋 Aperçu des données :")
                st.dataframe(df_preview_sm.head(3), use_container_width=True)

                if st.button(
                    "🚀 Synchroniser Sur-Mesure",
                    key="btn_sm",
                    type="primary",
                ):
                    with st.spinner("Synchronisation des mesures..."):
                        nb_mod, nb_lignes = importer_sur_mesure_excel(file_sm)
                        st.success(
                            f"✅ **{nb_mod} modèle(s)** ({nb_lignes} points de mesure) synchronisés !"
                        )
            except Exception as e:
                st.error(f"❌ Erreur sur la feuille FICHE MESURE : {e}")

    # ── 2. Import Typologie Défauts (Utilise defaut_typologie.py)
    with col_def:
        st.subheader("🛠️ Typologie des Défauts")
        st.caption("Feuille : **TYPOLOGIE DEFAUT** ➔ Table `typologie_defauts`")

        file_def = st.file_uploader(
            "Fichier Excel Typologie (.xlsx)",
            type=["xlsx", "xls"],
            key="up_def_file",
        )

        if file_def is not None:
            try:
                df_preview_def = pd.read_excel(
                    file_def, sheet_name="TYPOLOGIE DEFAUT"
                )
                st.markdown("##### 📋 Aperçu des données :")
                st.dataframe(df_preview_def.head(3), use_container_width=True)

                if st.button(
                    "🚀 Synchroniser Typologie",
                    key="btn_def",
                    type="primary",
                ):
                    with st.spinner("Synchronisation des défauts..."):
                        nb_def = def_type.importer_typologie_defauts(file_def)
                        st.success(
                            f"✅ **{nb_def} retouches/défauts** synchronisés avec succès !"
                        )
            except Exception as e:
                st.error(f"❌ Erreur sur la feuille TYPOLOGIE DEFAUT : {e}")


# ── Header Principal
st.markdown(
    """
<style>
    /* Sidebar plus large, seulement quand elle est ouverte */
[data-testid="stSidebar"][aria-expanded="true"] {
    min-width: 320px !important;
    max-width: 320px !important;
}

/* Quand elle est réduite, on libère complètement la place */
[data-testid="stSidebar"][aria-expanded="false"] {
    min-width: 0 !important;
    max-width: 0 !important;
}
    /* [AJOUT utilisateur] Marges internes du contenu principal */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
        padding-left: 2.5rem !important;
        padding-right: 2.5rem !important;
        max-width: 100% !important;
    }

    section[data-testid="stSidebar"] + section {
        padding-left: 0rem !important;
    }

    .main-header {
        padding: 1.1rem 1.8rem;
        margin-bottom: 1.5rem;
    }
</style>

<div class="main-header">
    <div class="titres">
        <h1 style="font-size: 1.5rem; margin: 0; padding-bottom: 0.3rem;">🔍 SUIVI QUALITE PRODUCTION</h1>
        <p style="font-size: 0.9rem; margin: 0; opacity: 0.85;">Saisie et suivi des non-conformités de production</p>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# ── Barre Latérale (Sidebar)
with st.sidebar:
    if os.path.exists("Logo.png"):
        st.image("Logo.png", use_container_width=True)

    # ── [AJOUT] Carte de l'utilisateur connecté
    prenom, nom = str(utilisateur["prenom"]), str(utilisateur["nom"])
    initiales = (prenom[:1] + nom[:1]).upper()
    libelle_role = {"admin": "Administrateur", "operateur": "Opérateur"}.get(
        utilisateur["role"], str(utilisateur["role"]).capitalize()
    )
    st.markdown(
        '<div class="user-card">'
        f'<div class="avatar">{html.escape(initiales)}</div>'
        '<div class="infos">'
        f"<strong>{html.escape(prenom)} {html.escape(nom)}</strong>"
        f'<span class="role {"admin" if est_admin else "ope"}">{html.escape(libelle_role)}</span>'
        "</div></div>",
        unsafe_allow_html=True,
    )

    # ── Menu principal ("Imports Data" : administrateurs uniquement)
    st.markdown('<p class="side-titre">Menu</p>', unsafe_allow_html=True)
    menu = ["📝 Saisie", "📊 Historique"]
    if est_admin:
        menu.append("📥 Imports Data")
    page = st.radio("Navigation", menu, label_visibility="collapsed")

    # ── Administration (administrateurs uniquement)
    if est_admin:
        st.markdown('<p class="side-titre">Administration</p>', unsafe_allow_html=True)
        st.page_link("pages/administration.py", label="👥 Gestion des utilisateurs")
        st.page_link("pages/mesures.py", label="📏 Mesures modèles")  # [AJOUT]

        with st.expander("🛠️ Gérer la table Chaînes", expanded=False):
            chaines_actuelles = db.fetch_db_chaines()
            chaines_propres = [c for c in chaines_actuelles if c != ""]

            st.markdown("**Ajouter une chaîne**")
            nouvelle_chaine = (
                st.text_input("Nom de la chaîne (ex: CH9)", key="new_ch_input")
                .strip()
                .upper()
                .replace(" ", "")
            )

            if st.button("Enregistrer la chaîne", key="btn_add_ch"):
                if not nouvelle_chaine:
                    st.warning("Veuillez saisir un nom.")
                else:
                    ok, msg = db.add_db_chaine(nouvelle_chaine)
                    if ok:
                        st.toast(msg, icon="🟢")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.warning(msg)

            st.divider()

            st.markdown("**Supprimer une chaîne**")
            if chaines_propres:
                chaine_a_supprimer = st.selectbox(
                    "Sélectionner la chaîne à supprimer",
                    options=chaines_propres,
                    key="del_ch_select",
                )
                if st.button("🗑️ Supprimer", key="btn_del_ch"):
                    ok, msg = db.delete_db_chaine(chaine_a_supprimer)
                    if ok:
                        st.toast(msg, icon="🗑️")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.info("Aucune chaîne à supprimer.")

    # ── Outils
    st.markdown('<p class="side-titre">Outils</p>', unsafe_allow_html=True)
    if est_admin:  # [AJOUT] réservé aux administrateurs
        if st.button("🔄 Synchroniser Excel ➡️ SQL", key="btn_sync"):
            with st.spinner("Mise à jour depuis le fichier Excel..."):
                if db.extraire_et_centraliser():
                    st.success("✅ Base mise à jour !")
                    st.rerun()
                else:
                    st.error("❌ Échec de la synchronisation.")

        # ── [AJOUT] Extraction réseau (fiches de mesure) -> table mesures_modele
        if st.button("🌐 Extraire les mesures (réseau)", key="btn_extraction_reseau"):
            with st.spinner("Lecture du partage réseau et synchronisation en cours… (peut prendre plusieurs minutes)"):
                try:
                    stats = extraction_mesures.extraire_et_synchroniser(db.engine)
                except Exception as e:
                    st.error(f"❌ Échec de l'extraction : {e}")
                else:
                    st.success(
                        f"✅ {stats['nb_lignes_synchronisees']} ligne(s) synchronisée(s) "
                        f"pour {stats['nb_modeles']} modèle(s)."
                    )
                    st.caption(
                        f"{stats['nb_fichiers_lus']} fichier(s) lus · "
                        f"{stats['nb_fichiers_sans_donnees']} sans données exploitables."
                    )

    if st.button("🔄 Tester la connexion"):
        try:
            db.get_connection.clear()
            db.get_connection()
            st.success("Connexion SQL Server OK !")
        except Exception as e:
            st.error(f"Erreur : {e}")

    st.divider()
    if st.button("🚪 Se déconnecter", key="btn_logout"):
        fermer_session()
        st.switch_page("login_suivi_qualite.py")

# ── Routage des vues selon le choix dans le menu
if "📝" in page:
    render_formulaire()

elif "📊" in page:
    hist.render_historique()

elif "📥" in page and est_admin:
    render_imports()
