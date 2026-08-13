from datetime import date, datetime
import os
import time
import pandas as pd
import pyodbc
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Contrôle Qualité",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Style css
st.markdown(
    """
<style>
    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%);
        padding: 1.5rem 2rem; border-radius: 12px;
        margin-bottom: 1.5rem; color: white; text-align: center;
    }
    .main-header h1 { margin: 0; font-size: 1.8rem; font-weight: 700; }
    .main-header p  { margin: 0.3rem 0 0; opacity: .85; font-size: .95rem; }
    .section-header {
        background: #f0f4f8; border-left: 4px solid #2d6a9f;
        padding: .6rem 1rem; border-radius: 0 8px 8px 0;
        margin: 1.2rem 0 .8rem; font-weight: 600; color: #1e3a5f; font-size: 1rem;
    }
    .calc-box {
        background: #e8f4fd; border: 1px solid #bee3f8;
        border-radius: 8px; padding: .8rem 1rem; margin: .4rem 0;
    }
    .calc-box .label { font-size: .8rem; color: #4a6fa5; font-weight: 600; margin-bottom: .2rem; }
    .calc-box .value { font-size: 1.3rem; font-weight: 700; color: #1e3a5f; }
    .calc-box .value.warning { color: #d97706; }
    .calc-box .value.danger  { color: #dc2626; }

    .stButton > button[key="save_btn"] {
        width: 100%;
        background: linear-gradient(135deg, #16a34a, #15803d);
        color: white; border: none; border-radius: 8px;
        padding: .8rem 1.5rem; font-size: 1.1rem; font-weight: 600;
    }
</style>
""",
    unsafe_allow_html=True,
)

@st.cache_resource
def get_connection():
    server = os.getenv("DB_SERVER", "nvserveur")
    database = os.getenv("DB_NAME", "QualiteDB")
    driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
    conn_str = (
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
        "Trusted_Connection=yes;TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


# ── Gestion Dynamique des Chaînes
def get_db_chaines():
    """Récupère la liste dynamique des chaînes depuis la table"""
    try:
        conn = get_connection()
        query = (
            "SELECT nom_chaine FROM chaines "
            "WHERE nom_chaine IS NOT NULL AND TRIM(nom_chaine) != '' "
            "ORDER BY nom_chaine"
        )
        df = pd.read_sql(query, conn)
        chaines_list = list(df["nom_chaine"].astype(str).str.strip().unique())
        return [""] + chaines_list
    except Exception as e:
        st.sidebar.error(f"⚠️ Erreur lecture table 'chaines' : {e}")
        return ["", "CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8"]

# ── Recherche de la norme d'échantillonnage
def get_norme_values(qte):
    """Recherche la tranche d'échantillonnage dans la BDD et renvoie l'échantillon et les seuils."""
    if not qte or qte <= 0:
        return 0, 0, 0
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            SELECT qte_echantillon, defaut_majeur_max, defaut_mineur_max 
            FROM grille_echantillonnage 
            WHERE ? BETWEEN qte_min AND qte_max
        """
        cursor.execute(query, (qte,))
        row = cursor.fetchone()
        if row:
            return row[0], row[1], row[2]
    except Exception as e:
        # Silencieux si la table n'existe pas encore ou en cas d'erreur de connexion
        pass
    return 0, 0, 0

def add_db_chaine(nouvelle_chaine):
    """Ajoute une chaîne dans QualiteDB.dbo.chaines"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM chaines WHERE LOWER(TRIM(nom_chaine)) = ?",
            (nouvelle_chaine.lower(),),
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                "INSERT INTO chaines (nom_chaine) VALUES (?)",
                (nouvelle_chaine,),
            )
            conn.commit()
            return True, f"✅ Chaîne {nouvelle_chaine} ajoutée avec succès !"
        else:
            return False, "⚠️ Cette chaîne existe déjà."
    except Exception as e:
        return False, f"❌ Erreur SQL lors de l'ajout : {e}"

def delete_db_chaine(chaine_a_supprimer):
    """Supprime une chaîne de QualiteDB.dbo.chaines"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM chaines WHERE nom_chaine = ?", (chaine_a_supprimer,)
        )
        conn.commit()
        return True, f"❌ Chaîne {chaine_a_supprimer} supprimée !"
    except Exception as e:
        return False, f"❌ Erreur SQL lors de la suppression : {e}"

def search_of_suggestions(search_query):
    """Recherche dynamique et STRICTEMENT exacte de l'OF"""
    if not search_query or len(search_query.strip()) < 1:
        return []
    try:
        conn = get_connection()
        query = "SELECT DISTINCT num_of FROM donnees_production ORDER BY num_of DESC"
        df = pd.read_sql(query, conn)
        all_ofs = df["num_of"].dropna().astype(str).str.strip()
        search_clean = search_query.strip()
        return [of for of in all_ofs if of == search_clean]
    except Exception:
        return []

def get_of_records(of_val):
    """Récupère toutes les lignes de l'OF sélectionné de manière stricte"""
    if not of_val:
        return pd.DataFrame()
    try:
        conn = get_connection()
        query = "SELECT * FROM donnees_production"
        df = pd.read_sql(query, conn)
        df["num_of_clean"] = df["num_of"].astype(str).str.strip()
        target_of = str(of_val).strip()
        return df[df["num_of_clean"] == target_of]
    except Exception:
        return pd.DataFrame()

def insert_record(data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO controle_qualite (
            date_controle, chaine, client, controleur_final, [of], article,
            reference, norme, coloris, qte_of, qte_presentee, cartons_presentes,
            numero_palette, qte_controlee, pourcentage_controle, total_defaut, 
            pourcentage_defaut, defaut_majeur, defaut_mineur, defaut_securitaire, 
            description_nc, description_nc1, decision, quantite_triee, total_defaut_tri, 
            nb_defauts_tri, pourcentage_defaut_tri, numero_qc, temps_tri_mn, cout_mn, cout_tri
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """,
        (
            data["date_controle"],
            data["chaine"],
            data["client"],
            data["controleur_final"],
            data["of"],
            data["article"],
            data["reference"],
            data["norme"],
            data["coloris"],
            data["qte_of"],
            data["qte_presentee"],
            data["cartons_presentes"],
            data["numero_palette"],
            data["qte_controlee"],
            data["pourcentage_controle"],
            data["total_defaut"],
            data["pourcentage_defaut"],
            data["defaut_majeur"],
            data["defaut_mineur"],
            data["defaut_securitaire"],
            data["description_nc"],
            data["description_nc1"],
            data["decision"],
            data["quantite_triee"],
            data["total_defaut_tri"],
            data["nb_defauts_tri"],
            data["pourcentage_defaut_tri"],
            data["numero_qc"],
            data["temps_tri_mn"],
            data["cout_mn"],
            data["cout_tri"],
        ),
    )
    conn.commit()


def load_records(limit=300):
    conn = get_connection()
    return pd.read_sql(
        f"SELECT TOP {limit} * FROM controle_qualite ORDER BY date_controle DESC, id DESC",
        conn,
    )

def get_mesures_by_reference(reference_val):
    if not reference_val or not str(reference_val).strip():
        return pd.DataFrame()
    try:
        conn = get_connection()
        query = """
            SELECT point_de_mesure, tolerance, taille, valeur_cible
            FROM mesures_modele
            WHERE LOWER(TRIM(nom_modele)) = LOWER(TRIM(?))
            ORDER BY id ASC
        """
        df_raw = pd.read_sql(query, conn, params=[str(reference_val).strip()])

        if df_raw.empty:
            return pd.DataFrame()

        # 1. Regroupement (max/first) pour fusionner les None sur une seule ligne par point de mesure
        df_pivot = df_raw.pivot_table(
            index=["point_de_mesure", "tolerance"],
            columns="taille",
            values="valeur_cible",
            aggfunc="first",
        ).reset_index()

        df_pivot.columns.name = None

        # 2. Extraire la liste ordonnée des tailles disponibles
        tailles_cols = [
            c
            for c in df_pivot.columns
            if c not in ["point_de_mesure", "tolerance"]
        ]

        # 3. Reconstruire le DataFrame avec 4 colonnes de saisie sous chaque taille
        new_cols = ["POINTS DE MESURE", "TOL (+/-)"]
        df_final = pd.DataFrame()
        df_final["POINTS DE MESURE"] = df_pivot["point_de_mesure"]
        df_final["TOL (+/-)"] = df_pivot["tolerance"]

        for t in tailles_cols:
            # Colonne Cible (issue de la DB)
            df_final[f"{t} (Cible)"] = df_pivot[t]

            # 4 Colonnes vides pour la saisie manuelle de l'opérateur
            df_final[f"{t}_M1"] = None
            df_final[f"{t}_M2"] = None
            df_final[f"{t}_M3"] = None
            df_final[f"{t}_M4"] = None

        return df_final

    except Exception as e:
        st.error(f"⚠️ Erreur lors du traitement de la grille : {e}")
        return pd.DataFrame()

def get_avancement_of(of_num):
    """Récupère la Qté OF fixe depuis donnees_production ainsi que le cumul des qte_controlee déjà enregistrées."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 1. Récupération de la Qté OF fixe
        query_prod = "SELECT qte_of FROM donnees_production WHERE LOWER(TRIM(of)) = LOWER(TRIM(?))"
        cursor.execute(query_prod, (str(of_num).strip(),))
        row_prod = cursor.fetchone()
        qte_of_fixe = row_prod[0] if row_prod and row_prod[0] else 0

        # 2. Cumul des quantités déjà contrôlées dans l'historique
        query_controle = "SELECT SUM(qte_presentee) FROM controle_qualite WHERE LOWER(TRIM(of)) = LOWER(TRIM(?))"
        cursor.execute(query_controle, (str(of_num).strip(),))
        row_ctrl = cursor.fetchone()
        cumul_controled_db = row_ctrl[0] if row_ctrl and row_ctrl[0] else 0

        return qte_of_fixe, cumul_controled_db
    except Exception as e:
        st.error(f"⚠️ Erreur lors du calcul de l'avancement OF : {e}")
        return 0, 0
# Initialisation des variables d'état
if "maj_counter" not in st.session_state:
    st.session_state.maj_counter = 0
if "min_counter" not in st.session_state:
    st.session_state.min_counter = 0
if "sec_counter" not in st.session_state:
    st.session_state.sec_counter = 0


# Callbacks Tactiles corrigés
def inc_majeur():
    st.session_state.widget_maj += 1

def dec_majeur():
    if st.session_state.get("widget_maj", 0) > 0:
        st.session_state.widget_maj -= 1

def inc_mineur():
    st.session_state.widget_min += 1

def dec_mineur():
    if st.session_state.get("widget_min", 0) > 0:
        st.session_state.widget_min -= 1

def inc_secu():
    st.session_state.widget_sec += 1

def dec_secu():
    if st.session_state.get("widget_sec", 0) > 0:
        st.session_state.widget_sec -= 1

def reset_compteurs():
    keys_to_reset = [
        "widget_maj",
        "widget_min",
        "widget_sec",
        "widget_total_defauts",
        "nc1_area",
        "nc2_area",
    ]

    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]

    # Réinitialisation de la mémoire du Tableau de Mesures
    if "sauvegarde_mesures" in st.session_state:
        st.session_state["sauvegarde_mesures"] = {}


# En-tête
st.markdown(
    """
<div class="main-header">
    <h1>🔍 SUIVI QUALITE</h1>
    <p>Saisie et suivi des non-conformités de production</p>
</div>
""",
    unsafe_allow_html=True,
)

# Sidebar
with st.sidebar:
    if os.path.exists("Logo.png"):
        st.image("Logo.png", use_container_width=True)
    st.markdown("### 🔍 Menu Principal")
    page = st.radio("Navigation", ["📝 Saisie", "📊 Historique"], label_visibility="collapsed")

    st.divider()

    # Paramétrage des Chaînes dans la Sidebar
    st.markdown("### ⚙️ Paramétrage des Chaînes")
    with st.expander("🛠️ Gérer la table Chaînes", expanded=False):
        chaines_actuelles = get_db_chaines()
        chaines_propres = [c for c in chaines_actuelles if c != ""]

        # 1. ajout d'une chaîne
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
                ok, msg = add_db_chaine(nouvelle_chaine)
                if ok:
                    st.toast(msg, icon="🟢")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning(msg)

        st.divider()

        # 2. suppression d'une chaîne
        st.markdown("**Supprimer une chaîne**")
        if chaines_propres:
            chaine_a_supprimer = st.selectbox(
                "Sélectionner la chaîne à supprimer",
                options=chaines_propres,
                key="del_ch_select",
            )
            if st.button("🗑️ Supprimer", key="btn_del_ch"):
                ok, msg = delete_db_chaine(chaine_a_supprimer)
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
            get_connection.clear()
            get_connection()
            st.success("Connexion SQL Server OK !")
        except Exception as e:
            st.error(f"Erreur : {e}")

# PAGE SAISIE
if "📝" in page:

    tab_ident, tab_defauts, tab_traitement,tab_sur_mesure = st.tabs(
        [
            "📋 1. Identification & Volumes",
            "⚠️ 2. Compteurs de Défauts",
            "🔄 3. Décision & Résultats du Tri",
            "📏 4. Tableau de Mesure"
        ]
    )

    # onglet 1 : identifications & volumes
    with tab_ident:
        st.markdown(
            '<div class="section-header">🔍 Recherche et sélection de l\'OF</div>',
            unsafe_allow_html=True,
        )
        of_search_input = st.text_input(
            "Saisissez le N° d'OF à rechercher...", value="", placeholder="Ex: 958..."
        )

        suggestions = search_of_suggestions(of_search_input)
        selected_row = None

        if suggestions:
            chosen_of = st.selectbox(
                "Résultat(s) trouvé(s) - Choisissez l'OF exact :",
                options=suggestions,
                key="of_exact_select",
            )
            records_df = get_of_records(chosen_of)

            if not records_df.empty:
                if len(records_df) > 1:
                    options_labels = [
                        f"Ligne {i + 1} : Article: {r['article']} | Coloris: {r['coloris']} | Qté Réf (Excel cde_mere): {r['cde_mere']}"
                        for i, r in records_df.iterrows()
                    ]

                    chosen_index = st.selectbox(
                        "⚠️ Plusieurs déclinaisons trouvées pour cet OF. Sélectionnez la bonne ligne :",
                        options=range(len(options_labels)),
                        format_func=lambda x: options_labels[x],
                        key="declinaison_select",
                    )
                    selected_row = records_df.iloc[chosen_index]
                else:
                    selected_row = records_df.iloc[0]
        else:
            if len(of_search_input) >= 1:
                st.warning(
                    "⚠️ Aucun OF correspondant trouvé dans la table de."
                )
            else:
                st.info(
                    "💡 Saisissez le numéro d'OF pour activer la recherche automatique."
                )

        def clean_val(row, col_name, default=""):
            if row is not None:
                row_lowercase = {
                    str(k).lower(): v for k, v in row.to_dict().items()
                }
                target_key = col_name.lower()
                if target_key in row_lowercase and pd.notna(
                    row_lowercase[target_key]
                ):
                    return str(row_lowercase[target_key]).strip()
            return default

        auto_client = clean_val(selected_row, "client")
        auto_reference = clean_val(selected_row, "reference")
        auto_of = clean_val(selected_row, "num_of", default=of_search_input)
        auto_article = clean_val(selected_row, "article")
        auto_norme = clean_val(selected_row, "norme")
        auto_coloris = clean_val(selected_row, "coloris")

        try:
            val_cde_mere = clean_val(selected_row, "cde_mere", default="0")
            auto_qte_of = int(float(val_cde_mere)) if val_cde_mere else 0
        except ValueError:
            auto_qte_of = 0

        st.markdown(
            '<div class="section-header">📋 Formulaire d\'identification du lot</div>',
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            date_controle = st.date_input(
                "📅 Date *", value=date.today(), key="ctrl_date_widget"
            )

            liste_chaines_db = get_db_chaines()
            chaine = st.selectbox(
                "Chaîne *", options=liste_chaines_db, key="ctrl_chaine_widget"
            )

            client = st.text_input(
                "Client *", value=auto_client, key=f"ctrl_client_{auto_client}"
            )
        with c2:
            controleur = st.text_input(
                "Contrôleur final *", key="controleur_final"
            )
            of_val = st.text_input(
                "OF *",
                value=auto_of,
                disabled=(selected_row is not None),
                key=f"ctrl_of_{auto_of}",
            )
            article = st.text_input(
                "Article *",
                value=auto_article,
                key=f"ctrl_art_{auto_article}",
            )
        with c3:
            reference = st.text_input(
                "Référence", value=auto_reference, key=f"ctrl_ref_manual_widget_{auto_reference}"
            )
            norme = st.text_input(
                "Norme", value=auto_norme, key=f"ctrl_norme_{auto_norme}"
            )
            coloris = st.text_input(
                "Coloris", value=auto_coloris, key=f"ctrl_col_{auto_coloris}"
            )

        st.markdown(
            '<div class="section-header">📦 Quantités et Échantillonnage</div>',
            unsafe_allow_html=True,
        )
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            qte_of = st.number_input("Cde mere", min_value=0, step=1, value=auto_qte_of,
                                     key=f"ctrl_qteof_{auto_qte_of}")
        with c2:
            qte_presentee = st.number_input("Qté présentée *", min_value=0, step=1, value=0, key="ctrl_qtepres_widget")
        with c3:
            cartons = st.number_input("Cartons présentés", min_value=0, step=1, value=0, key="ctrl_cartons_widget")
        with c4:
            num_palette = st.text_input("N° Palette", key="ctrl_palette_widget")

        # 👇 APPEL DE LA FONCTION :
        qte_ctrl_auto, maj_max_auto, min_max_auto = get_norme_values(qte_presentee)

        # On stocke les limites tolérées dans la session pour l'Onglet 2
        st.session_state["limite_maj_max"] = maj_max_auto
        st.session_state["limite_min_max"] = min_max_auto

        # Champ Qté contrôlée alimenté automatiquement par la BDD
        qte_controlee = st.number_input(
            "Qté contrôlée *",
            min_value=0,
            step=1,
            value=qte_ctrl_auto if qte_ctrl_auto > 0 else 0,
            key="ctrl_qtectrl_widget",
        )

        pct_controle = (
            (int(qte_controlee) / int(qte_presentee) * 100)
            if qte_presentee > 0
            else 0.0
        )
        pct_ctrl_class = (
            "danger"
            if pct_controle < 10
            else ("warning" if pct_controle < 50 else "value")
        )

        st.markdown(
            f"""
            <div class="calc-box">
                <div class="label">📊 % Contrôlé = Qté contrôlée / Qté présentée (Instantané)</div>
                <div class="value {pct_ctrl_class}">{pct_controle:.2f} %</div>
            </div>""",
            unsafe_allow_html=True,
        )
        # ── Calcul et Affichage Automatique (Temps Réel) ─────────────────────────────

        st.markdown("<br>", unsafe_allow_html=True)

        # Déclenchement automatique dès que l'OF est renseigné
        if of_val:
            try:
                conn = get_connection()
                cursor = conn.cursor()

                # 1. Identification de la Qté OF / Cde Mère cible
                qte_target = (
                    int(qte_of)
                    if ("qte_of" in locals() and qte_of and int(qte_of) > 0)
                    else (
                        int(cde_mere)
                        if ("cde_mere" in locals() and cde_mere)
                        else 0
                    )
                )

                # 2. Historique BDD filtré sur l'OF ET la qte_of exacte
                query_ctrl = """
                    SELECT SUM(qte_presentee) 
                    FROM controle_qualite 
                    WHERE LOWER(TRIM([of])) = LOWER(TRIM(?))
                      AND qte_of = ?
                """
                cursor.execute(query_ctrl, (str(of_val).strip(), int(qte_target)))
                row_ctrl = cursor.fetchone()
                cumul_bdd = row_ctrl[0] if (row_ctrl and row_ctrl[0]) else 0

                # 3. Saisie en cours à l'écran
                qte_actuelle = int(qte_presentee) if qte_presentee else 0

                # 4. Cumul total (BDD + Saisie en cours)
                total_cumul = cumul_bdd + qte_actuelle

                # 5. Calcul et affichage si la qte_target est valide
                if qte_target > 0:
                    pct_cumul_val = (float(total_cumul) / float(qte_target)) * 100.0
                    details = f"{total_cumul} / {qte_target} pcs"
                    decompte = f"BDD ({cumul_bdd}) + Saisie ({qte_actuelle})"
                    cumul_class = "danger" if pct_cumul_val < 5 else "value"

                    # Affichage dynamique instantané
                    st.markdown(
                        f"""
                    <div class="calc-box" style="margin-top: 10px; border-left: 5px solid #2d6a9f;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div class="label">📈 % Contrôlé Cumulé — <small>({details})</small></div>
                            <div style="font-size: 0.85em; color: #2d6a9f; background: #eef5fc; padding: 3px 8px; border-radius: 4px; font-weight: 500;">
                                ➕ {decompte}
                            </div>
                        </div>
                        <div class="value {cumul_class}" style="margin-top: 5px;">{pct_cumul_val:.2f} %</div>
                    </div>""",
                        unsafe_allow_html=True,
                    )

            except Exception as e:
                st.error(f"❌ Erreur lors du calcul automatique : {e}")
    with tab_defauts:
        st.markdown(
            '<div class="section-header">🛠️ Saisie Tactile des Défauts</div>',
            unsafe_allow_html=True,
        )

        # Récupération des seuils calculés à l'Onglet 1
        limite_maj = st.session_state.get("limite_maj_max", 0)
        limite_min = st.session_state.get("limite_min_max", 0)

        col_maj, col_min, col_sec = st.columns(3)

        with col_maj:
            st.write(f"**Défauts Majeurs** *(Max toléré : {limite_maj})*")
            sub_c1, sub_c2 = st.columns(2)
            with sub_c1:
                st.button(
                    "➕ Ajouter Majeur", key="add_maj", on_click=inc_majeur
                )
            with sub_c2:
                st.button(
                    "➖ Retirer Majeur", key="rem_maj", on_click=dec_majeur
                )
            defaut_majeur = st.number_input(
                "Valeur enregistrée", min_value=0, step=1, key="widget_maj"
            )

            # Alerte visuelle si le nombre dépasse le NQA
            if defaut_majeur > limite_maj:
                st.error(
                    f"⚠️ Seuil dépassé ! ({defaut_majeur} > {limite_maj} max)"
                )

        with col_min:
            st.write(f"**Défauts Mineurs** *(Max toléré : {limite_min})*")
            sub_c1, sub_c2 = st.columns(2)
            with sub_c1:
                st.button(
                    "➕ Ajouter Mineur", key="add_min", on_click=inc_mineur
                )
            with sub_c2:
                st.button(
                    "➖ Retirer Mineur", key="rem_min", on_click=dec_mineur
                )
            defaut_mineur = st.number_input(
                "Valeur enregistrée", min_value=0, step=1, key="widget_min"
            )

            # Alerte visuelle si le nombre dépasse le NQA
            if defaut_mineur > limite_min:
                st.warning(
                    f"⚠️ Seuil dépassé ! ({defaut_mineur} > {limite_min} max)"
                )

        with col_sec:
            st.write("**Défauts Sécuritaires** *(Max : 0)*")
            sub_c1, sub_c2 = st.columns(2)
            with sub_c1:
                st.button("➕ Ajouter Sécu", key="add_sec", on_click=inc_secu)
            with sub_c2:
                st.button("➖ Retirer Sécu", key="rem_sec", on_click=dec_secu)
            defaut_securitaire = st.number_input(
                "Valeur enregistrée", min_value=0, step=1, key="widget_sec"
            )

            if defaut_securitaire > 0:
                st.error("🚨 Défaut critique/sécuritaire présent !")

        st.markdown("---")

        total_defaut = defaut_majeur + defaut_mineur + defaut_securitaire
        st.session_state["widget_total_defauts"] = total_defaut

        st.markdown(
            f"""
        <div class="calc-box">
            <div class="label">🚨 Total Défauts Saisis</div>
            <div class="value">{total_defaut}</div>
        </div>""",
            unsafe_allow_html=True,
        )

        st.markdown("---")
        description_nc1 = st.text_area(
            "📝 Description NC ",
            height=100,
            placeholder="Détaillez les non-conformités et défauts majeurs/mineurs observés...",
            key="nc1_area",
        )

        pct_defaut = (
            (int(total_defaut) / int(qte_controlee) * 100)
            if qte_controlee > 0
            else 0.0
        )
        pct_def_class = (
            "danger"
            if pct_defaut >= 5
            else ("warning" if pct_defaut >= 2 else "value")
        )

        st.markdown(
            f"""
        <div class="calc-box">
            <div class="label">📊 % Défaut = Total défaut / Qté contrôlée (Instantané)</div>
            <div class="value {pct_def_class}">{pct_defaut:.2f} %</div>
        </div>""",
            unsafe_allow_html=True,
        )

        st.button(
            "🔄 Réinitialiser tous les compteurs à 0", on_click=reset_compteurs
        )

    # onglet 3 : traitement & tri et validation
    with tab_traitement:
        st.markdown(
            '<div class="section-header">⚖️ Conclusion & Décision</div>',
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            # Remarque : La description NC1 est gérée dans l'onglet Compteurs de Défauts
            st.info("💡 La **Description NC 1** est renseignée dans l'onglet Compteurs de Défauts.")
        with c2:
            decision = st.selectbox(
                "✅ Décision",
                [
                    "",
                    "Accepté",
                    "Refusé",
                    "Tri en cours",
                    "Retouche",
                    "Dérogation client",
                    "Destruction",
                    "Autre",
                ],
                key="decision_box",
            )

        st.markdown(
            '<div class="section-header">🔄 Résultats & Coûts du tri</div>',
            unsafe_allow_html=True,
        )

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            quantite_triee = st.number_input(
                "Quantité triée",
                min_value=0,
                step=1,
                value=0,
                key="tri_qte_widget",
            )
        with c2:
            total_defaut_tri = st.number_input(
                "Total défauts au tri",
                min_value=0,
                step=1,
                value=0,
                key="tri_tot_widget",
            )
        with c3:
            nb_defauts_tri = st.number_input(
                "Nb défauts au tri",
                min_value=0,
                step=1,
                value=0,
                key="tri_nb_widget",
            )
        with c4:
            numero_qc = st.text_input("N° QC", key="tri_qc_widget")

        # Description NC 2 propre aux opérations de tri
        description_nc2_val = st.text_area(
            "📝 Description NC 2 (Tri)",
            height=90,
            placeholder="Deuxième description liée aux opérations de tri...",
            key="nc2_area",
        )

        # Calcul % défaut au tri
        pct_defaut_tri = (
            (float(total_defaut_tri) / float(quantite_triee) * 100.0)
            if quantite_triee > 0
            else 0.0
        )
        pct_tri_class = (
            "danger"
            if pct_defaut_tri >= 5
            else ("warning" if pct_defaut_tri >= 2 else "value")
        )

        st.markdown(
            f"""
        <div class="calc-box">
            <div class="label">📊 % Défaut au tri = Total défauts tri / Quantité triée (Automatique)</div>
            <div class="value {pct_tri_class}">{pct_defaut_tri:.2f} %</div>
        </div>""",
            unsafe_allow_html=True,
        )

        st.markdown(
            '<div class="section-header">💰 Évaluation financière</div>',
            unsafe_allow_html=True,
        )

        cc1, cc2 = st.columns(2)
        with cc1:
            temps_tri = st.number_input(
                "Temps de tri (mn)",
                min_value=0.0,
                step=0.5,
                format="%.1f",
                value=0.0,
                key="time_widget",
            )
        with cc2:
            cout_mn = st.number_input(
                "Coût / mn ($)",
                min_value=0.0,
                step=0.01,
                format="%.2f",
                value=0.0,
                key="cost_widget",
            )

        cout_tri_auto = round(float(total_defaut * cout_mn), 2)

        st.markdown(
            f"""
        <div class="calc-box" style="margin-top: 10px; margin-bottom: 25px;">
            <div class="label">💰 Coût total du Tri Calculé (Temps × Coût/mn)</div>
            <div class="value" style="color: #2d6a9f;">{cout_tri_auto:.2f} $</div>
        </div>""",
            unsafe_allow_html=True,
        )

        st.divider()

        submitted = st.button(
            "💾 Enregistrer définitivement le contrôle", key="save_btn"
        )

        if submitted:
            errors = []
            if not chaine:
                errors.append("Chaîne")
            if not client:
                errors.append("Client")
            if not controleur:
                errors.append("Contrôleur final")
            if not of_val:
                errors.append("OF")
            if not article:
                errors.append("Article")
            if qte_controlee == 0:
                errors.append("Qté contrôlée (doit être > 0)")

            if errors:
                st.error(
                    f"❌ Impossible d'enregistrer : Champs obligatoires manquants ➡️ {', '.join(errors)}"
                )
            else:
                # Récupération sécurisée des NC et des défauts
                nc1_saisie = st.session_state.get("nc1_area", "")

                # Récupération des défauts depuis session_state
                defaut_maj_val = int(st.session_state.get("widget_maj", 0))
                defaut_min_val = int(st.session_state.get("widget_min", 0))
                defaut_sec_val = int(st.session_state.get("widget_sec", 0))
                total_defaut_val = defaut_maj_val + defaut_min_val + defaut_sec_val

                record = {
                    "date_controle": date_controle,
                    "chaine": chaine,
                    "client": client,
                    "controleur_final": controleur,
                    "of": of_val,
                    "article": article,
                    "reference": reference,
                    "norme": norme,
                    "coloris": coloris,
                    "qte_of": int(qte_of),
                    "qte_presentee": int(qte_presentee),
                    "cartons_presentes": int(cartons),
                    "numero_palette": num_palette,
                    "qte_controlee": int(qte_controlee),
                    "pourcentage_controle": round(pct_controle, 2),
                    "total_defaut": total_defaut_val,
                    "pourcentage_defaut": round(pct_defaut, 4),
                    "cout_tri": cout_tri_auto,
                    "defaut_majeur": defaut_maj_val,
                    "defaut_mineur": defaut_min_val,
                    "defaut_securitaire": defaut_sec_val,
                    "description_nc": nc1_saisie,  # Stocke NC1
                    "description_nc1": description_nc2_val,  # Stocke NC2 (Tri)
                    "decision": decision,
                    "quantite_triee": int(quantite_triee),
                    "total_defaut_tri": int(total_defaut_tri),
                    "nb_defauts_tri": int(nb_defauts_tri),
                    "pourcentage_defaut_tri": round(pct_defaut_tri, 4),
                    "numero_qc": numero_qc,
                    "temps_tri_mn": temps_tri,
                    "cout_mn": cout_mn,
                }

                try:
                    insert_record(record)

                    if st.session_state.get("sauvegarde_mesures"):
                        save_mesures_controlees(
                            of_num=of_val,
                            nom_modele=reference,
                            sauvegarde_dict=st.session_state["sauvegarde_mesures"],
                        )

                    st.toast("✅ Contrôle enregistré avec succès !", icon="💾")
                    st.success(
                        "✅ Contrôle enregistré avec succès!"
                    )
                    st.balloons()

                    time.sleep(1.5)

                    # Nettoyage sécurisé des clés
                    reset_compteurs()

                    # Rechargement de l'application : tous les widgets repassent à 0 proprement !
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Erreur lors de l'enregistrement : {e}")

    # onglet 4 : sur-mesure
    with tab_sur_mesure:
        st.markdown(
            '<div class="section-header">📏 Grille de Contrôle Sur-Mesure</div>',
            unsafe_allow_html=True,
        )

        # ── 1. Récupération EXACTE des clés de l'Onglet 1 ──────────────────────
        ref_val = auto_reference if "auto_reference" in locals() else ""
        coloris_base = auto_coloris if "auto_coloris" in locals() else ""
        of_base = auto_of if "auto_of" in locals() else ""

        # OF
        of_val = st.session_state.get(f"ctrl_of_{of_base}", of_base)

        # Référence / Modèle
        ref_val = st.session_state.get(
            f"ctrl_ref_manual_widget_{ref_val}", ref_val
        )

        # Chaîne
        chaine_val = st.session_state.get("ctrl_chaine_widget", "")

        # Date
        date_val = st.session_state.get("ctrl_date_widget", date.today())

        # Coloris
        coloris_val = st.session_state.get(f"ctrl_col_{coloris_base}", coloris_base)

        # Contrôleur
        ctrl_val = st.session_state.get("controleur_final", "")
        ctrl_final_nom = (
            str(ctrl_val).strip()
            if ctrl_val and str(ctrl_val).strip()
            else "Non renseigné"
        )

        #Qté controlee
        qte_val = st.session_state.get("ctrl_qtectrl_widget", 0)

        if ref_val:
            # ── 2. En-tête récapitulatif dynamique ──────────────────────────────
            date_str = (
                date_val.strftime("%d/%m/%Y")
                if hasattr(date_val, "strftime")
                else str(date_val)
            )

            st.markdown(
                f"""
                <div style="background-color: #f8fafc; padding: 12px 16px; border-radius: 8px; border: 1px solid #cbd5e1; margin-bottom: 15px;">
                    <small style="color: #475569; font-weight: bold;">📌 RAPPEL DES INFORMATIONS DU CONTRÔLE (ONGLET 1)</small><br>
                    <b>OF :</b> {of_val} | <b>Modèle :</b> {ref_val} | <b>Chaîne :</b> {chaine_val} | <b>Date :</b> {date_str} <br>
                    <b>Qté Contrôlée :</b> {qte_val} | <b>Coloris :</b> {coloris_val} | <b>Contrôleur :</b> {ctrl_final_nom}
                </div>
                """,
                unsafe_allow_html=True,
            )

            conn = get_connection()
            query = """
                SELECT point_de_mesure, tolerance, taille, valeur_cible
                FROM mesures_modele
                WHERE LOWER(TRIM(nom_modele)) = LOWER(TRIM(?))
                ORDER BY id ASC
            """
            df_raw = pd.read_sql(query, conn, params=[str(ref_val).strip()])

            if not df_raw.empty:
                tailles_dispo = sorted(
                    df_raw["taille"].astype(str).unique().tolist()
                )

                if "sauvegarde_mesures" not in st.session_state:
                    st.session_state["sauvegarde_mesures"] = {}

                taille_choisie = st.selectbox(
                    "🎯 Choisissez la Taille à contrôler :",
                    options=tailles_dispo,
                    key=f"select_taille_{ref_val}",
                )

                editor_key = f"editor_{ref_val}_{taille_choisie}"

                # Préparation du DataFrame de saisie
                if taille_choisie in st.session_state["sauvegarde_mesures"]:
                    df_saisie = pd.DataFrame(
                        st.session_state["sauvegarde_mesures"][taille_choisie]
                    )
                else:
                    df_taille = df_raw[
                        df_raw["taille"].astype(str) == str(taille_choisie)
                        ].copy()
                    df_saisie = pd.DataFrame(
                        {
                            "POINTS DE MESURE": df_taille["point_de_mesure"],
                            "TOL (+/-)": df_taille["tolerance"],
                            "CIBLE (cm)": df_taille["valeur_cible"],
                            "Pièce 1": [""] * len(df_taille),
                            "Pièce 2": [""] * len(df_taille),
                            "Pièce 3": [""] * len(df_taille),
                            "Pièce 4": [""] * len(df_taille),
                        }
                    )


                # Callback pour conserver la saisie lors des rechargements
                def update_mesures():
                    edited_data = st.session_state[editor_key]
                    for row_idx, changes in edited_data.get(
                            "edited_rows", {}
                    ).items():
                        for col_name, new_val in changes.items():
                            df_saisie.at[row_idx, col_name] = new_val
                    st.session_state["sauvegarde_mesures"][taille_choisie] = (
                        df_saisie.to_dict(orient="records")
                    )


                # Tableau de saisie des pièces
                st.data_editor(
                    df_saisie,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed",
                    key=editor_key,
                    on_change=update_mesures,
                    column_config={
                        "POINTS DE MESURE": st.column_config.TextColumn(
                            "POINTS DE MESURE", disabled=True
                        ),
                        "TOL (+/-)": st.column_config.NumberColumn(
                            "TOL (+/-)", disabled=True, format="%.1f"
                        ),
                        "CIBLE (cm)": st.column_config.NumberColumn(
                            "CIBLE (cm)", disabled=True, format="%.1f"
                        ),
                        "Pièce 1": st.column_config.TextColumn("Pièce 1"),
                        "Pièce 2": st.column_config.TextColumn("Pièce 2"),
                        "Pièce 3": st.column_config.TextColumn("Pièce 3"),
                        "Pièce 4": st.column_config.TextColumn("Pièce 4"),
                    },
                )

                st.markdown("---")

                # ── 3. Décision ──────────────────────────────────────────────────
                st.markdown("##### ⚖️ Décision Globale")
                col_dec1, col_dec2, col_info = st.columns([1.5, 1.5, 3])

                with col_dec1:
                    is_conforme = st.checkbox(
                        "✅ Conforme", key=f"chk_global_conf_{ref_val}"
                    )
                with col_dec2:
                    is_non_conforme = st.checkbox(
                        "❌ Non Conforme", key=f"chk_global_non_conf_{ref_val}"
                    )

                decision_mesure = "Non définie"
                if is_conforme and not is_non_conforme:
                    decision_mesure = "Conforme"
                elif is_non_conforme and not is_conforme:
                    decision_mesure = "Non Conforme"

                with col_info:
                    badge_color = (
                        "#16a34a"
                        if decision_mesure == "Conforme"
                        else (
                            "#dc2626"
                            if decision_mesure == "Non Conforme"
                            else "#2d6a9f"
                        )
                    )
                    st.markdown(
                        f"""
                        <div style="background: #f0f4f8; padding: 10px; border-radius: 6px; border-left: 5px solid {badge_color};">
                            📌 <b>Contrôleur :</b> {ctrl_final_nom} <br>
                            ⚖️ <b>Décision :</b> <span style="color: {badge_color}; font-weight: bold;">{decision_mesure}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                st.markdown(" ")


                # ── 4. Fonction de conversion sécurisée ─────────────────────────
                def safe_float(val):
                    if (
                            pd.isna(val)
                            or val is None
                            or str(val).strip() in ["", "nan", "None"]
                    ):
                        return None
                    try:
                        return float(str(val).replace(",", ".").strip())
                    except (ValueError, TypeError):
                        return None


                # ── 5. Enregistrement SQL Server ──────────────────────────────────
                if st.button(
                        "💾 Enregistrer le contrôle Sur-Mesure",
                        type="primary",
                        use_container_width=True,
                ):
                    if decision_mesure == "Non définie":
                        st.error(
                            "⚠️ Veuillez sélectionner une décision (Conforme ou Non Conforme) avant d'enregistrer."
                        )
                    else:
                        try:
                            cursor = conn.cursor()
                            insert_query = """
                                INSERT INTO controle_sur_mesure (
                                    of_num, chaine, date_controle, reference, qte_controlee, coloris,
                                    taille, controleur, decision, point_de_mesure, tolerance, valeur_cible,
                                    piece_1, piece_2, piece_3, piece_4
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """

                            records_to_insert = []
                            for _, row in df_saisie.iterrows():
                                records_to_insert.append(
                                    (
                                        str(of_val) if of_val else "",
                                        str(chaine_val) if chaine_val else "",
                                        date_val,
                                        str(ref_val) if ref_val else "",
                                        int(qte_val) if qte_val else 0,
                                        str(coloris_val) if coloris_val else "",
                                        str(taille_choisie) if taille_choisie else "",
                                        str(ctrl_final_nom) if ctrl_final_nom else "",
                                        str(decision_mesure),
                                        str(row["POINTS DE MESURE"])
                                        if row["POINTS DE MESURE"]
                                        else "",
                                        safe_float(row["TOL (+/-)"]),
                                        safe_float(row["CIBLE (cm)"]),
                                        str(row["Pièce 1"])
                                        if row["Pièce 1"] is not None
                                        else "",
                                        str(row["Pièce 2"])
                                        if row["Pièce 2"] is not None
                                        else "",
                                        str(row["Pièce 3"])
                                        if row["Pièce 3"] is not None
                                        else "",
                                        str(row["Pièce 4"])
                                        if row["Pièce 4"] is not None
                                        else "",
                                    )
                                )

                            cursor.executemany(insert_query, records_to_insert)
                            conn.commit()
                            st.success(
                                f"✅ Contrôle Sur-Mesure enregistré avec succès pour l'OF **{of_val}** (Taille {taille_choisie}) !"
                            )

                        except Exception as e:
                            st.error(
                                f"❌ Erreur lors de l'enregistrement en BDD : {e}"
                            )

            else:
                st.warning(
                    f"⚠️ Aucune mesure trouvée pour le modèle **{ref_val}**."
                )
        else:
            st.info(
                "💡 Veuillez d'abord rechercher et charger un OF dans le 1er onglet."
            )

# PAGE HISTORIQUE
else:
    st.markdown(
        '<div class="section-header">📊 Historique des contrôles</div>',
        unsafe_allow_html=True,
    )

    try:
        df_raw = load_records(300)

        if df_raw.empty:
            st.info("Aucun enregistrement trouvé.")
        else:
            st.markdown("##### 🔍 Filtres de recherche")
            f1, f2, f3, f4 = st.columns([2, 2, 2, 1])

            with f1:
                search_of = st.text_input(
                    "Filtrer par N° d'OF", value="", key="hist_filter_of"
                )
            with f2:
                distinct_decisions = ["Tous"] + list(
                    df_raw["decision"].dropna().unique()
                )
                search_decision = st.selectbox(
                    "Filtrer par Décision",
                    distinct_decisions,
                    key="hist_filter_dec",
                )
            with f3:
                distinct_chaines = ["Toutes"] + list(
                    df_raw["chaine"].dropna().unique()
                )
                search_chaine = st.selectbox(
                    "Filtrer par Chaîne",
                    distinct_chaines,
                    key="hist_filter_ch",
                )
            with f4:
                nb_lignes = st.selectbox(
                    "Lignes Max", [20, 50, 100, 200], index=1, key="hist_limit"
                )

            df_filtered = df_raw.copy()
            if search_of:
                df_filtered = df_filtered[
                    df_filtered["of"]
                    .astype(str)
                    .str.contains(search_of, case=False, na=False)
                ]
            if search_decision != "Tous":
                df_filtered = df_filtered[
                    df_filtered["decision"] == search_decision
                ]
            if search_chaine != "Toutes":
                df_filtered = df_filtered[
                    df_filtered["chaine"] == search_chaine
                ]

            df_filtered = df_filtered.head(nb_lignes)

            st.write("")
            st.markdown(
                "💡 *Cliquez sur une ligne pour afficher les détails et descriptions de non-conformité associées.*"
            )

            def color_refused(row):
                if row["decision"] == "Refusé":
                    return ["background-color: rgba(220, 38, 38, 0.15)"] * len(
                        row
                    )
                return [""] * len(row)

            styled_df = df_filtered.style.apply(color_refused, axis=1)

            event = st.dataframe(
                styled_df,
                use_container_width=True,
                hide_index=True,
                column_order=[
                    "date_controle",
                    "chaine",
                    "client",
                    "of",
                    "article",
                    "qte_presentee",
                    "qte_controlee",
                    "total_defaut",
                    "defaut_majeur",
                    "defaut_mineur",
                    "defaut_securitaire",
                    "description_nc",
                    "description_nc1",
                    "pourcentage_defaut",
                    "decision",
                    "cout_tri",
                ],
                column_config={
                    "date_controle": st.column_config.DateColumn(
                        "📅 Date", format="DD/MM/YYYY"
                    ),
                    "of": st.column_config.TextColumn("N° OF"),
                    "qte_presentee": st.column_config.NumberColumn(
                        "Qté Prés.", format="%d"
                    ),
                    "qte_controlee": st.column_config.NumberColumn(
                        "Qté Ctrl.", format="%d"
                    ),
                    "total_defaut": st.column_config.NumberColumn(
                        "Total Déf.", format="%d"
                    ),
                    "defaut_majeur": st.column_config.NumberColumn(
                        "Déf. Majeurs", format="%d"
                    ),
                    "defaut_mineur": st.column_config.NumberColumn(
                        "Déf. Mineurs", format="%d"
                    ),
                    "defaut_securitaire": st.column_config.NumberColumn(
                        "Déf. Sécu.", format="%d"
                    ),
                    "description_nc": st.column_config.TextColumn(
                        "📝 Desc. NC 1"
                    ),
                    "description_nc1": st.column_config.TextColumn(
                        "📝 Desc. NC 2"
                    ),
                    "pourcentage_defaut": st.column_config.NumberColumn(
                        "% Défaut", format="%.2f %%"
                    ),
                    "decision": st.column_config.TextColumn("⚖️ Décision"),
                    "cout_tri": st.column_config.NumberColumn(
                        "💰 Coût Tri", format="%.2f $"
                    ),
                },
                selection_mode="single-row",
                on_select="rerun",
            )

            if event and event.get("selection", {}).get("rows"):
                selected_row_idx = event["selection"]["rows"][0]
                row_data = df_filtered.iloc[selected_row_idx]

                st.markdown("---")
                st.markdown(
                    f'<div class="section-header">🔎 Détails du contrôle du {row_data.get("date_controle", "N/A")} — OF #{row_data.get("of", "N/A")}</div>',
                    unsafe_allow_html=True,
                )

                d1, d2, d3 = st.columns(3)
                with d1:
                    st.write(
                        f"**Contrôleur :** {row_data.get('controleur_final', '-')}"
                    )
                    st.write(
                        f"**Référence :** {row_data.get('reference', '-')}"
                    )
                    st.write(f"**Norme :** {row_data.get('norme', '-')}")
                with d2:
                    st.write(f"**Coloris :** {row_data.get('coloris', '-')}")
                    st.write(
                        f"**Défauts Majeurs :** {row_data.get('defaut_majeur', 0)}"
                    )
                    st.write(
                        f"**Défauts Mineurs :** {row_data.get('defaut_mineur', 0)}"
                    )
                with d3:
                    st.write(
                        f"**Défauts Sécuritaires :** {row_data.get('defaut_securitaire', 0)}"
                    )
                    st.write(f"**N° QC :** {row_data.get('numero_qc', '-')}")
                    st.write(
                        f"**Temps de tri :** {row_data.get('temps_tri_mn', 0)} mn"
                    )

                c_nc1, c_nc2 = st.columns(2)
                with c_nc1:
                    st.text_area(
                        "📝 Description Non-Conformité 1",
                        value=str(
                            row_data.get("description_nc")
                            or "Aucune description"
                        ),
                        disabled=True,
                        key="view_nc1",
                    )
                with c_nc2:
                    st.text_area(
                        "📝 Description Non-Conformité 2",
                        value=str(
                            row_data.get("description_nc1")
                            or "Aucune description"
                        ),
                        disabled=True,
                        key="view_nc2",
                    )

                # ── 🆕 AJOUT : RUPTURE & AFFICHAGE DES MESURES SUR-MESURE ──
                selected_of = str(row_data.get("of", "")).strip()

                if selected_of:
                    try:
                        conn = get_connection()
                        query_sm = """
                            SELECT taille, point_de_mesure, tolerance, valeur_cible,
                                   piece_1, piece_2, piece_3, piece_4, controleur, decision
                            FROM controle_sur_mesure
                            WHERE LOWER(TRIM(of_num)) = LOWER(TRIM(?))
                            ORDER BY created_at DESC
                        """
                        df_sm = pd.read_sql(query_sm, conn, params=[selected_of])

                        st.markdown("##### 📏 Contrôle Sur-Mesure Associé")

                        if not df_sm.empty:
                            dec_sm = df_sm.iloc[0]["decision"]
                            ctrl_sm = df_sm.iloc[0]["controleur"]
                            badge_bg = (
                                "#16a34a"
                                if dec_sm == "Conforme"
                                else (
                                    "#dc2626"
                                    if dec_sm == "Non Conforme"
                                    else "#2d6a9f"
                                )
                            )

                            st.markdown(
                                f"""
                                <div style="background-color: #f8fafc; padding: 10px 14px; border-radius: 6px; border-left: 5px solid {badge_bg}; margin-bottom: 10px;">
                                    📌 <b>Contrôleur Sur-Mesure :</b> {ctrl_sm} | 
                                    ⚖️ <b>Décision Sur-Mesure :</b> <span style="color: {badge_bg}; font-weight: bold;">{dec_sm}</span>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            df_sm_display = df_sm[
                                [
                                    "taille",
                                    "point_de_mesure",
                                    "tolerance",
                                    "valeur_cible",
                                    "piece_1",
                                    "piece_2",
                                    "piece_3",
                                    "piece_4",
                                ]
                            ].rename(
                                columns={
                                    "taille": "Taille",
                                    "point_de_mesure": "Point de mesure",
                                    "tolerance": "TOL (+/-)",
                                    "valeur_cible": "Cible (cm)",
                                    "piece_1": "Pièce 1",
                                    "piece_2": "Pièce 2",
                                    "piece_3": "Pièce 3",
                                    "piece_4": "Pièce 4",
                                }
                            )

                            st.dataframe(
                                df_sm_display,
                                use_container_width=True,
                                hide_index=True,
                            )
                        else:
                            st.info(
                                f"ℹ️ Aucun enregistrement sur-mesure trouvé pour l'OF #{selected_of}."
                            )

                    except Exception as err_sm:
                        st.warning(
                            f"⚠️ Impossible de charger les mesures sur-mesure : {err_sm}"
                        )

    except Exception as e:
        st.error(f"❌ Erreur lors du chargement de l'historique : {e}")