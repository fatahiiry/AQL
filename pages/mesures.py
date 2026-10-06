"""Page réservée aux administrateurs : consulter et corriger les points de mesure
importés dans la table [QualiteDB].[dbo].[mesures_modele]."""
import datetime

import pandas as pd
import streamlit as st
from sqlalchemy import text

st.set_page_config(
    page_title="Mesures modèles",
    page_icon="📏",
    layout="wide",
    initial_sidebar_state="expanded"
)

from auth_db import ROLES_ADMIN  # noqa: E402
from session import assurer_jeton, fermer_session, restaurer_session  # noqa: E402

# ── Accès réservé : connecté ET administrateur
restaurer_session()
if not st.session_state.get("utilisateur"):
    st.switch_page("login_suivi_qualite.py")
    st.stop()

utilisateur = st.session_state.utilisateur
assurer_jeton(utilisateur)

if utilisateur["role"] not in ROLES_ADMIN:
    st.error("Cette page est réservée aux administrateurs.")
    st.stop()

import database as db  # noqa: E402
import styles  # noqa: E402
from theme_app import appliquer_theme, entete  # noqa: E402

styles.apply_custom_styles()
appliquer_theme()

with st.sidebar:
    st.caption(f"👤 **{utilisateur['prenom']} {utilisateur['nom']}** · {utilisateur['role']}")
    st.page_link("pages/application.py", label="← Retour à l'application")
    if st.button("🚪 Se déconnecter", key="btn_logout"):
        fermer_session()
        st.switch_page("login_suivi_qualite.py")

TABLE = "mesures_modele"
COLONNES = ["id", "nom_modele", "point_de_mesure", "tolerance", "taille", "valeur_cible", "date_import"]
COLONNES_MODIFIABLES = ["nom_modele", "point_de_mesure", "tolerance", "taille", "valeur_cible"]

st.markdown(entete("📏 Mesures modèles", "Consulter et corriger les points de mesure importés"), unsafe_allow_html=True)


@st.cache_data(ttl=60)
def charger():
    return pd.read_sql(
        f"SELECT {', '.join(COLONNES)} FROM {TABLE} ORDER BY nom_modele, point_de_mesure", db.engine
    )


try:
    df = charger()
except Exception as e:
    st.error(f"Impossible de lire la table {TABLE} : {e}")
    st.stop()

# ── Indicateurs
c1, c2, c3 = st.columns(3)
c1.metric("Lignes", len(df))
c2.metric("Modèles distincts", int(df["nom_modele"].nunique()) if not df.empty else 0)
if not df.empty and df["date_import"].notna().any():
    dernier = pd.to_datetime(df["date_import"]).max().strftime("%d/%m/%Y %H:%M")
else:
    dernier = "—"
c3.metric("Dernier import", dernier)

# ── 1. Sélection du Modèle (Filtre Principal)
modeles = ["Tous"] + sorted(df["nom_modele"].dropna().unique().tolist()) if not df.empty else ["Tous"]

f1, f2, f3 = st.columns([1, 1, 2])
choix_modele = f1.selectbox("Filtrer par modèle", modeles)

# Filtrer les données par rapport au modèle sélectionné
df_modele_filtre = df.copy()
if choix_modele != "Tous":
    df_modele_filtre = df_modele_filtre[df_modele_filtre["nom_modele"] == choix_modele]

# Tailles extraites uniquement à partir du modèle sélectionné
tailles_du_modele = sorted(df_modele_filtre["taille"].dropna().astype(str).unique().tolist()) if not df_modele_filtre.empty else []
tailles_options = ["Toutes"] + tailles_du_modele

choix_taille = f2.selectbox("Filtrer par taille", tailles_options)
recherche = f3.text_input("Rechercher (point de mesure…)", placeholder="Ex. Tour de poitrine")

# ── 2. Module d'ajout rapide (lié au modèle sélectionné)
if choix_modele != "Tous":
    with st.expander(f"➕ **Ajouter un point de mesure pour le modèle : {choix_modele}**"):
        with st.form("form_ajout_mesure"):
            c_pm, c_val, c_tol = st.columns([2, 1, 1])
            nom_point_mesure = c_pm.text_input("Nom du point de mesure", placeholder="Ex. Tour de cuisse")
            valeur_cible_nouv = c_val.number_input("Valeur cible", value=0.0, step=0.5, format="%.2f")
            tolerance_nouv = c_tol.number_input("Tolérance (±)", value=0.0, step=0.1, format="%.2f")

            # Sélection des tailles extraites spécifiquement du filtre modèle ci-dessus
            tailles_choisies = st.multiselect(
                "Appliquer aux tailles",
                options=tailles_du_modele,
                default=tailles_du_modele,
                help="Sélectionnez les tailles qui doivent recevoir ce nouveau point de mesure"
            )

            submit_ajout = st.form_submit_button("Créer le point de mesure sur les tailles sélectionnées", type="primary")

            if submit_ajout:
                if not nom_point_mesure.strip():
                    st.error("Veuillez renseigner le nom du point de mesure.")
                elif not tailles_choisies:
                    st.error("Veuillez choisir au moins une taille.")
                else:
                    try:
                        with db.engine.begin() as conn:
                            for t in tailles_choisies:
                                conn.execute(
                                    text(
                                        f"INSERT INTO {TABLE} (nom_modele, point_de_mesure, tolerance, taille, "
                                        f"valeur_cible, date_import) VALUES (:nm, :pm, :tol, :ta, :vc, :dt)"
                                    ),
                                    {
                                        "nm": choix_modele,
                                        "pm": nom_point_mesure.strip(),
                                        "tol": tolerance_nouv,
                                        "ta": t,
                                        "vc": valeur_cible_nouv,
                                        "dt": datetime.datetime.now(),
                                    },
                                )
                        st.cache_data.clear()
                        st.toast(f"Point de mesure « {nom_point_mesure} » ajouté pour {len(tailles_choisies)} taille(s) !", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur lors de l'enregistrement : {e}")
else:
    st.info("💡 Sélectionnez un **modèle spécifique** dans le filtre ci-dessus pour pouvoir lui ajouter un nouveau point de mesure sur plusieurs tailles.")

# ── 3. Application des filtres restants pour le tableau d'affichage
df_filtre = df_modele_filtre.copy()
if choix_taille != "Toutes":
    df_filtre = df_filtre[df_filtre["taille"].astype(str) == choix_taille]
if recherche:
    r = recherche.lower()
    df_filtre = df_filtre[df_filtre.apply(lambda ligne: r in " ".join(str(v) for v in ligne.values).lower(), axis=1)]

st.caption(
    "Modifiez une cellule directement, ajoutez une ligne (dernière ligne, vide) ou supprimez-en une "
    "(case à cocher à gauche de la ligne), puis cliquez sur **Enregistrer**."
)

edite = st.data_editor(
    df_filtre,
    key="editeur_mesures",
    hide_index=True,
    use_container_width=True,
    num_rows="dynamic",
    disabled=["id", "date_import"],
    column_config={
        "id": st.column_config.NumberColumn("ID", width="small"),
        "nom_modele": st.column_config.TextColumn("Modèle", required=True),
        "point_de_mesure": st.column_config.TextColumn("Point de mesure", required=True),
        "tolerance": st.column_config.NumberColumn("Tolérance", format="%.2f"),
        "taille": st.column_config.TextColumn("Taille"),
        "valeur_cible": st.column_config.NumberColumn("Valeur cible", format="%.2f"),
        "date_import": st.column_config.DatetimeColumn("Importé le", format="DD/MM/YYYY HH:mm", disabled=True),
    },
)

if st.button("💾 Enregistrer les modifications", type="primary"):
    avant = df_filtre.set_index("id")
    ids_avant = set(avant.index)
    ids_apres = set(int(i) for i in edite["id"].dropna())

    supprimes = ids_avant - ids_apres
    ajoutes = edite[edite["id"].isna()]

    modifies = []
    for _, ligne in edite.iterrows():
        if pd.isna(ligne["id"]):
            continue
        idx = int(ligne["id"])
        if idx not in avant.index:
            continue
        ancienne = avant.loc[idx]
        if any(str(ancienne[c]) != str(ligne[c]) for c in COLONNES_MODIFIABLES):
            modifies.append((idx, ligne))

    lignes_incompletes = ajoutes[ajoutes["nom_modele"].isna() | ajoutes["point_de_mesure"].isna()]
    if not lignes_incompletes.empty:
        st.warning("Renseignez au moins « Modèle » et « Point de mesure » pour chaque ligne ajoutée.")
    else:
        try:
            with db.engine.begin() as conn:
                for idx in supprimes:
                    conn.execute(text(f"DELETE FROM {TABLE} WHERE id = :id"), {"id": idx})
                for idx, ligne in modifies:
                    conn.execute(
                        text(
                            f"UPDATE {TABLE} SET nom_modele=:nm, point_de_mesure=:pm, "
                            f"tolerance=:tol, taille=:ta, valeur_cible=:vc WHERE id=:id"
                        ),
                        {
                            "nm": ligne["nom_modele"], "pm": ligne["point_de_mesure"],
                            "tol": ligne["tolerance"], "ta": ligne["taille"],
                            "vc": ligne["valeur_cible"], "id": idx,
                        },
                    )
                for _, ligne in ajoutes.iterrows():
                    conn.execute(
                        text(
                            f"INSERT INTO {TABLE} (nom_modele, point_de_mesure, tolerance, taille, "
                            f"valeur_cible, date_import) VALUES (:nm, :pm, :tol, :ta, :vc, :dt)"
                        ),
                        {
                            "nm": ligne["nom_modele"], "pm": ligne["point_de_mesure"],
                            "tol": ligne["tolerance"], "ta": ligne["taille"],
                            "vc": ligne["valeur_cible"], "dt": datetime.datetime.now(),
                        },
                    )
        except Exception as e:
            st.error(f"Erreur lors de l'enregistrement : {e}")
        else:
            nb = len(supprimes) + len(modifies) + len(ajoutes)
            if nb:
                st.cache_data.clear()
                st.toast(f"{nb} modification(s) enregistrée(s).", icon="💾")
                st.rerun()
            else:
                st.info("Aucune modification à enregistrer.")