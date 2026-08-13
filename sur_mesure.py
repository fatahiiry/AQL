import io
import pandas as pd
from sqlalchemy import text
import streamlit as st


def importer_sur_mesure_depuis_streamlit(uploaded_file, engine):
    """Reprend exactement votre structure en lisant la feuille 'FICHE MESURE'."""
    # ── 1. Lecture directe de la feuille 'FICHE MESURE' depuis l'uploader ──
    df = pd.read_excel(uploaded_file, sheet_name="FICHE MESURE")

    # Renommage explicite pour correspondre à la base SQL
    df = df.rename(
        columns={
            "Name": "nom_modele",
            "Point de Mesure": "point_de_mesure",
            "Tolérance": "tolerance",
            "Taille": "taille",
            "Valeur": "valeur_cible",
        }
    )

    # Liste stricte des colonnes attendues en base de données
    cols_attendues = [
        "nom_modele",
        "point_de_mesure",
        "tolerance",
        "taille",
        "valeur_cible",
    ]
    df = df[cols_attendues]

    # Nettoyage des chaînes de texte
    df["nom_modele"] = df["nom_modele"].astype(str).str.strip()
    df["point_de_mesure"] = df["point_de_mesure"].astype(str).str.strip()

    # Nettoyage spécifique du champ Taille (évite le piège des '35.0')
    df["taille"] = (
        df["taille"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    )

    # Conversion propre des nombres (gestion des virgules et arrondis Excel)
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

    with engine.begin() as conn:
        # Suppression des anciennes mesures uniquement pour les modèles présents dans le fichier
        for mod in modeles:
            conn.execute(
                text("DELETE FROM mesures_modele WHERE nom_modele = :m"),
                {"m": mod},
            )

        # Insertion des nouvelles lignes nettoyées
        df.to_sql(
            name="mesures_modele", con=conn, if_exists="append", index=False
        )

    return len(modeles), len(df)