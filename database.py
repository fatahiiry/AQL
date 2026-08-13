import os
import pandas as pd
import pyodbc
from sqlalchemy import create_engine
import streamlit as st
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()


SERVER = os.getenv("DB_SERVER", "nvserveur")
DATABASE = os.getenv("DB_NAME", "QualiteDB")
DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

connection_url = f"mssql+pyodbc://@{SERVER}/{DATABASE}?driver={DRIVER}&trusted_connection=yes&TrustServerCertificate=yes"
engine = create_engine(connection_url)

def get_connection():
    conn_str = (
        f"DRIVER={{{DRIVER}}};SERVER={SERVER};DATABASE={DATABASE};"
        "Trusted_Connection=yes;TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)

@st.cache_data(
    ttl=300
)  # Cache le RÉSULTAT pendant 5 minutes, pas la connexion
def fetch_db_chaines():
  """Récupère la liste dynamique des chaînes depuis SQL Server."""
  conn = None
  try:
    conn = get_connection()  # Ouvre une nouvelle connexion propre
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
  finally:
    if conn:
      try:
        conn.close()  # Se ferme proprement après lecture
      except Exception:
        pass

def get_norme_values(qte_presentee):
    """Recherche la qte_echantillon, defaut_majeur_max et defaut_mineur_max correspondant à qte_presentee."""
    try:
        qte = int(qte_presentee) if qte_presentee else 0
    except (ValueError, TypeError):
        return 0, 0, 0

    if qte <= 0:
        return 0, 0, 0

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Utilisation des vrais noms de colonnes de votre table QualiteDB
        query = """
            SELECT TOP 1 
                ISNULL(qte_echantillon, 0), 
                ISNULL(defaut_majeur_max, 0), 
                ISNULL(defaut_mineur_max, 0)
            FROM [QualiteDB].[dbo].[grille_echantillonnage]
            WHERE qte_min <= ? AND qte_max >= ?
        """
        cursor.execute(query, (qte, qte))
        row = cursor.fetchone()

        if row:
            return int(row[0]), int(row[1]), int(row[2])
        else:
            print(
                f"⚠️ Aucune tranche trouvée dans grille_echantillonnage pour Qté = {qte}"
            )
            return 0, 0, 0

    except Exception as e:
        print(
            f"❌ Erreur SQL lors de la récupération de l'échantillon pour {qte_presentee} : {e}"
        )
        return 0, 0, 0

def add_db_chaine(nouvelle_chaine):
    """Ajoute une chaîne dans QualiteDB.dbo.chaines."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM chaines WHERE LOWER(TRIM(nom_chaine)) = ?",
            (nouvelle_chaine.lower(),),
        )
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO chaines (nom_chaine) VALUES (?)", (nouvelle_chaine,))
            conn.commit()
            return True, f"✅ Chaîne {nouvelle_chaine} ajoutée avec succès !"
        else:
            return False, "⚠️ Cette chaîne existe déjà."
    except Exception as e:
        return False, f"❌ Erreur SQL lors de l'ajout : {e}"

def delete_db_chaine(chaine_a_supprimer):
    """Supprime une chaîne de QualiteDB.dbo.chaines."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chaines WHERE nom_chaine = ?", (chaine_a_supprimer,))
        conn.commit()
        return True, f"❌ Chaîne {chaine_a_supprimer} supprimée !"
    except Exception as e:
        return False, f"❌ Erreur SQL lors de la suppression : {e}"

def search_of_suggestions(search_query):
    """Recherche dynamique des numéros d'OF."""
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
    """Récupère les enregistrements pour un OF donné."""
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
    """Insère un contrôle qualité en base de données."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO controle_qualite (
            date_controle, chaine, client, controleur_final, [of], article,
            reference, norme, coloris, qte_of, qte_presentee, cartons_presentes,
            carton_controle, numero_palette, qte_controlee, pourcentage_controle, 
            total_defaut, pourcentage_defaut, defaut_majeur, defaut_mineur, 
            defaut_securitaire, description_nc, description_nc1, decision, 
            quantite_triee, total_defaut_tri, nb_defauts_tri, pourcentage_defaut_tri, 
            numero_qc, temps_tri_mn, cout_mn, cout_tri
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            data.get("date_controle"),
            data.get("chaine"),
            data.get("client"),
            data.get("controleur_final"),
            data.get("of"),
            data.get("article"),
            data.get("reference"),
            data.get("norme"),
            data.get("coloris"),
            data.get("qte_of", 0),
            data.get("qte_presentee", 0),
            str(data.get("cartons_presentes", "")),
            str(data.get("carton_controle", "")),             data.get("numero_palette"),
            data.get("qte_controlee", 0),
            data.get("pourcentage_controle", 0.0),
            data.get("total_defaut", 0),
            data.get("pourcentage_defaut", 0.0),
            data.get("defaut_majeur", 0),
            data.get("defaut_mineur", 0),
            data.get("defaut_securitaire", 0),
            data.get("description_nc"),
            data.get("description_nc1"),
            data.get("decision"),
            data.get("quantite_triee", 0),
            data.get("total_defaut_tri", 0),
            data.get("nb_defauts_tri", 0),
            data.get("pourcentage_defaut_tri", 0.0),
            data.get("numero_qc"),
            data.get("temps_tri_mn", 0),
            data.get("cout_mn", 0.0),
            data.get("cout_tri", 0.0),
        ),
    )
    conn.commit()
    conn.close()

def load_records(limit=300):
    try:
        conn = get_connection()
        query = f"SELECT TOP {limit} * FROM controle_qualite ORDER BY id DESC"
        return pd.read_sql(query, conn)
    except Exception as e:
        print(f"Erreur SQL load_records: {e}")
        return pd.DataFrame()

def get_mesures_by_reference(reference_val):
    """Récupère la grille de mesures associée à une référence."""
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

        df_pivot = df_raw.pivot_table(
            index=["point_de_mesure", "tolerance"],
            columns="taille",
            values="valeur_cible",
            aggfunc="first",
        ).reset_index()
        df_pivot.columns.name = None

        tailles_cols = [c for c in df_pivot.columns if c not in ["point_de_mesure", "tolerance"]]

        df_final = pd.DataFrame()
        df_final["POINTS DE MESURE"] = df_pivot["point_de_mesure"]
        df_final["TOL (+/-)"] = df_pivot["tolerance"]

        for t in tailles_cols:
            df_final[f"{t} (Cible)"] = df_pivot[t]
            df_final[f"{t}_M1"] = None
            df_final[f"{t}_M2"] = None
            df_final[f"{t}_M3"] = None
            df_final[f"{t}_M4"] = None

        return df_final
    except Exception as e:
        st.error(f"⚠️ Erreur lors du traitement de la grille : {e}")
        return pd.DataFrame()

def get_cumul_controled_db(of_val, qte_target):
    """Récupère le cumul contrôlé en BDD pour un OF donné."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            SELECT SUM(qte_presentee) 
            FROM controle_qualite 
            WHERE LOWER(TRIM([of])) = LOWER(TRIM(?))
              AND qte_of = ?
        """
        cursor.execute(query, (str(of_val).strip(), int(qte_target)))
        row = cursor.fetchone()
        return row[0] if (row and row[0]) else 0
    except Exception:
        return 0

def fetch_db_typologie_defauts():
  """Récupère la liste des libellés de défauts depuis la table typologie_defauts."""
  try:
    with engine.connect() as conn:
      query = text("""
                SELECT DISTINCT libelle_defaut 
                FROM typologie_defauts 
                WHERE libelle_defaut IS NOT NULL 
                  AND TRIM(libelle_defaut) != '' 
                ORDER BY libelle_defaut ASC
            """)
      result = conn.execute(query)
      # Extraction du premier élément de chaque ligne pour avoir une liste simple de str
      return [str(row[0]).strip() for row in result.fetchall()]
  except Exception as e:
    print(f"Erreur lors de la récupération des typologies : {e}")
    return []

def insert_photo_record(data_photo):
  """Insère un enregistrement dans la table QualiteDB.dbo.controle_photos."""
  try:
    conn = get_connection()  # Utilisez le nom de votre fonction de connexion
    cursor = conn.cursor()

    query = """
            INSERT INTO [QualiteDB].[dbo].[controle_photos] (
                of_val, reference, nom_fichier, chemin_fichier, photo_bytes, date_capture
            ) VALUES (?, ?, ?, ?, ?, GETDATE())
        """

    params = (
        data_photo.get('of_val'),
        data_photo.get('reference'),
        data_photo.get('nom_fichier'),
        data_photo.get('chemin_fichier'),
        data_photo.get('photo_bytes'),
    )

    cursor.execute(query, params)
    conn.commit()
    cursor.close()
    conn.close()
    return True
  except Exception as e:
    print(
        "Erreur lors de l'insertion de la photo dans controle_photos :"
        f" {e}"
    )
    return False