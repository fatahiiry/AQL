import os
import pyodbc
from dotenv import load_dotenv

# Chargement des variables d'environnement (.env)
load_dotenv()


def get_connection():
    server = os.getenv("DB_SERVER", "nvserveur")
    database = os.getenv("DB_NAME", "QualiteDB")
    driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

    conn_str = (
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
        "Trusted_Connection=yes;TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


def generate_table_structure():
    print("🔌 Connexion à SQL Server en cours...")
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 1. Sécurité : Suppression si elle existe déjà
        print("🧹 Nettoyage de l'ancienne table...")
        cursor.execute("DROP TABLE IF EXISTS controle_qualite;")

        # 2. Création de la nouvelle table structure complète
        print("🏗️ Création de la nouvelle table 'controle_qualite'...")
        query_create = """
        CREATE TABLE controle_qualite (
            id INT IDENTITY(1,1) PRIMARY KEY,
            date_controle DATE NOT NULL,
            chaine VARCHAR(50) NOT NULL,
            client VARCHAR(100) NOT NULL,
            controleur_final VARCHAR(100) NOT NULL,
            [of] VARCHAR(50) NOT NULL,
            article VARCHAR(150) NOT NULL,
            reference VARCHAR(100) NULL,
            norme VARCHAR(100) NULL,
            coloris VARCHAR(50) NULL,
            qte_of INT NULL DEFAULT 0,
            qte_presentee INT NOT NULL DEFAULT 0,
            cartons_presentes INT NULL DEFAULT 0,
            numero_palette VARCHAR(50) NULL,
            qte_controlee INT NOT NULL DEFAULT 0,
            pourcentage_controle NUMERIC(7,2) NULL, -- Nouvelle colonne intégrée !
            total_defaut INT NOT NULL DEFAULT 0,
            pourcentage_defaut NUMERIC(7,2) NULL,
            defaut_majeur INT NULL DEFAULT 0,
            defaut_mineur INT NULL DEFAULT 0,
            defaut_securitaire INT NULL DEFAULT 0,
            description_nc NVARCHAR(MAX) NULL,
            decision VARCHAR(50) NULL,
            quantite_triee INT NOT NULL DEFAULT 0,
            total_defaut_tri INT NULL DEFAULT 0,
            nb_defauts_tri INT NULL DEFAULT 0,
            description_nc1 NVARCHAR(MAX) NULL,
            pourcentage_defaut_tri NUMERIC(7,2) NULL,
            numero_qc VARCHAR(50) NULL,
            temps_tri_mn NUMERIC(10,2) NULL DEFAULT 0.00,
            cout_mn NUMERIC(10,2) NULL DEFAULT 0.00,
            cout_tri NUMERIC(10,2) NULL DEFAULT 0.00,
            date_saisie DATETIME DEFAULT GETDATE() -- Horodatage automatique
        );
        """

        cursor.execute(query_create)
        conn.commit()
        print("✅ La base de données a été recréée avec succès avec toutes les formules !")

    except Exception as e:
        print(f"❌ Erreur lors de la génération de la structure : {e}")
    finally:
        if 'conn' in locals():
            conn.close()


if __name__ == "__main__":
    generate_table_structure()