import pandas as pd
from sqlalchemy import text
import database as db


def importer_typologie_defauts(uploaded_file):
    """
    Extrait la première colonne de la feuille 'TYPOLOGIE DEFAUT'
    et synchronise la liste des retouches/défauts dans la table SQL Server 'typologie_defauts'.
    """
    try:
        # ── 1. Lecture de la feuille Excel ──
        df = pd.read_excel(uploaded_file, sheet_name="TYPOLOGIE DEFAUT")

        if df.empty:
            raise ValueError("La feuille 'TYPOLOGIE DEFAUT' est vide.")

        # ── 2. Récupération de la 1ère colonne (ex: RETOUCHE TROUVES SUR INSPECTION FINAL) ──
        col_source = df.columns[0]
        df = df[[col_source]].rename(columns={col_source: "libelle_defaut"})

        # ── 3. Nettoyage et formatage des données ──
        # Conversion en texte et suppression des espaces superflus
        df["libelle_defaut"] = df["libelle_defaut"].astype(str).str.strip()

        # Filtration des valeurs vides ou 'nan'
        df = df[
            (df["libelle_defaut"] != "")
            & (df["libelle_defaut"].str.lower() != "nan")
        ]

        # Suppression des doublons dans le fichier Excel
        df = df.drop_duplicates()

        if df.empty:
            raise ValueError("Aucune donnée valide trouvée après nettoyage.")

        # ── 4. Synchronisation avec SQL Server ──
        with db.engine.begin() as conn:
            # Vidage de la table existante (Remplace l'ancienne liste)
            conn.execute(text("TRUNCATE TABLE typologie_defauts"))

            # Insertion des nouvelles données
            df.to_sql(
                name="typologie_defauts",
                con=conn,
                if_exists="append",
                index=False,
            )

        return len(df)

    except Exception as e:
        raise Exception(
            f"Erreur lors du traitement de 'TYPOLOGIE DEFAUT' : {e}"
        )


def fetch_typologie_defauts():
    """
    Récupère la liste de tous les défauts enregistrés en BDD.
    Utile pour charger les options dans vos formulaires Streamlit.
    """
    try:
        query = "SELECT id, libelle_defaut FROM typologie_defauts ORDER BY libelle_defaut ASC"
        df = pd.read_sql(query, db.engine)
        return df["libelle_defaut"].tolist()
    except Exception as e:
        print(f"Erreur lors de la récupération des défauts : {e}")
        return []