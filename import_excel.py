import os
import pandas as pd
import pyodbc
from dotenv import load_dotenv

# Chargement des variables du fichier .env
load_dotenv()


def extraire_et_centraliser():
    file_path = os.getenv("FILE_PRODUCTION")
    sheet_name = os.getenv("SHEET_PRODUCTION", "RECAP GLOBAL COMMANDE")

    print(f"⏳ Ouverture et extraction du fichier : {file_path}")
    print(f"📄 Onglet ciblé : {sheet_name}")

    if not file_path:
        print("❌ Erreur : La variable FILE_PRODUCTION n'est pas définie dans le fichier .env")
        return

    try:
        # Liste des index de colonnes à extraire : C(2), K(10), L(11), M(12), N(13), O(14), U(20), X(23), Z(25)
        indices_colonnes = [2, 10, 11, 12, 13, 14, 20, 23, 25]

        df = pd.read_excel(
            file_path,
            sheet_name=sheet_name,
            engine='openpyxl',
            header=9,
            usecols=indices_colonnes
        )

        if df.empty:
            print("❌ Aucune donnée trouvée à partir de la ligne 10 dans cet onglet.")
            return

        # Pandas extrait les colonnes dans l'ordre de leur position dans le fichier Excel.
        # Donc l'ordre dans le DataFrame est : C, K, L, M, N, O, U, X, Z
        df.columns = ['Col_C', 'Col_K', 'Col_L', 'Col_M', 'Col_N', 'Col_O', 'Col_U', 'Col_X', 'Col_Z']

        # Sécurité : Supprimer uniquement les lignes où le numéro d'OF (Colonne L) est vide
        df = df.dropna(subset=['Col_L'])

        # Nettoyage et conversion en chaînes de caractères propres
        df['Col_C'] = df['Col_C'].fillna('Client Inconnu').astype(str).str.strip()  # client
        df['Col_K'] = df['Col_K'].fillna('').astype(str).str.strip()  # cde_mere
        df['Col_L'] = df['Col_L'].fillna('').astype(str).str.strip()  # num_of
        df['Col_O'] = df['Col_O'].fillna('').astype(str).str.strip()  # opt
        df['Col_U'] = df['Col_U'].fillna('').astype(str).str.strip()  # reference (Colonne U)
        df['Col_X'] = df['Col_X'].fillna('').astype(str).str.strip()  # norme
        df['Col_Z'] = df['Col_Z'].fillna('').astype(str).str.strip()  # article

        # Fusion des colonnes M et N pour former le champ 'coloris' complet
        df['Col_M'] = df['Col_M'].fillna('').astype(str).str.strip()
        df['Col_N'] = df['Col_N'].fillna('').astype(str).str.strip()
        df['Coloris_Combine'] = (df['Col_M'] + ' ' + df['Col_N']).str.strip()

        print(f"📋 {len(df)} lignes valides prêtes pour l'injection SQL (Doublons logiques conservés).")

        # Connexion SQL Server via .env
        server = os.getenv("DB_SERVER", "nvserveur")
        database = os.getenv("DB_NAME", "QualiteDB")
        driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

        conn_str = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};Trusted_Connection=yes;TrustServerCertificate=yes;"
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Vidage de la table temporaire/staging
        print("🗄️ Nettoyage de la table 'donnees_production'...")
        cursor.execute("TRUNCATE TABLE donnees_production")

        # Insertion de masse incluant la colonne 'reference'
        print("💾 Synchronisation avec SQL Server...")
        query = """
            INSERT INTO donnees_production (client, cde_mere, num_of, coloris, opt, reference, article, norme)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        cursor.fast_executemany = True
        insert_data = []
        for _, row in df.iterrows():
            insert_data.append((
                row['Col_C'],  # client (C)
                row['Col_K'],  # cde_mere (K)
                row['Col_L'],  # num_of (L)
                row['Coloris_Combine'],  # coloris (M + N)
                row['Col_O'],  # opt (O)
                row['Col_U'],  # reference (U)
                row['Col_Z'],  # article (Z)
                row['Col_X']   # norme (X)
            ))

        cursor.executemany(query, insert_data)
        conn.commit()

        print("✅ Base de staging 'donnees_production' mise à jour avec succès !")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ Erreur critique lors de l'extraction : {e}")


if __name__ == "__main__":
    extraire_et_centraliser()