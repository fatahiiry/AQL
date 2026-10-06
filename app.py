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

# ── Configuration de la page
st.set_page_config(
    page_title="Contrôle Qualité",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)
@st.cache_resource(ttl=900)
def synchro_automatique():
    return db.extraire_et_centraliser()


# Lancement silencieux
synchro_automatique()


# 2. BOUTON DE SYNCHRO MANUELLE DANS LA BARRE LATÉRALE
with st.sidebar:
    st.markdown("---")
    st.caption("⚙️ **Synchronisation Données**")
    if st.button("🔄 Synchroniser Excel ➡️ SQL"):
        with st.spinner("Mise à jour depuis le fichier Excel..."):
            if db.extraire_et_centraliser():
                st.success("✅ Base mise à jour !")
                st.rerun()
            else:
                st.error("❌ Échec de la synchronisation.")
styles.apply_custom_styles()

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
<div class="main-header">
    <h1>🔍 SUIVI QUALITE PRODUCTION</h1>
    <p>Saisie et suivi des non-conformités de production</p>
</div>
""",
    unsafe_allow_html=True,
)

# ── Barre Latérale (Sidebar)
with st.sidebar:
    if os.path.exists("Logo.png"):
        st.image("Logo.png", use_container_width=True)

    st.markdown("### 🔍 Menu Principal")
    page = st.radio(
        "Navigation",
        ["📝 Saisie", "📊 Historique", "📥 Imports Data"],
        label_visibility="collapsed",
    )

    st.divider()

    st.markdown("### ⚙️ Paramétrage des Chaînes")
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

    st.divider()

    if st.button("🔄 Tester la connexion"):
        try:
            db.get_connection.clear()
            db.get_connection()
            st.success("Connexion SQL Server OK !")
        except Exception as e:
            st.error(f"Erreur : {e}")

# ── Routage des vues selon le choix dans le menu
if "📝" in page:
    render_formulaire()

elif "📊" in page:
    hist.render_historique()

elif "📥" in page:
    render_imports()