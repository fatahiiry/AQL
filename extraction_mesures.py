"""Extraction des fiches de mesure depuis le partage réseau et synchronisation
vers la table SQL [QualiteDB].[dbo].[mesures_modele].

Ce module reprend tel quel le script d'extraction fourni (parcours du dossier
réseau, détection du modèle par onglet façon Power Query, export Excel) et y
ajoute l'étape manquante : charger les colonnes D à H de la feuille « Données »
dans la base.

    Colonne feuille « Données »   Colonne SQL
    ----------------------------  ----------------
    D  Modèle_Onglet          ->  nom_modele
    E  Point de Mesure        ->  point_de_mesure
    F  Tolérance              ->  tolerance
    G  Taille                 ->  taille
    H  Valeur                 ->  valeur_cible
                                   date_import  (posée à l'exécution)

Les colonnes A à C (Dossier_Source, Fichier_Source, Chemin_Complet) restent
dans le fichier Excel exporté pour la traçabilité, mais ne sont pas envoyées
en base : elles n'ont pas de colonne correspondante dans mesures_modele.

Utilisation depuis database.py (voir l'exemple d'intégration fourni à part) :

    from extraction_mesures import extraire_et_synchroniser
    stats = extraire_et_synchroniser(engine)   # engine = votre moteur SQLAlchemy existant
"""
import datetime
import numbers
import os
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
from sqlalchemy import text

warnings.filterwarnings("ignore")

# ------------------------------------------------------------------
# 1. Paramètres (identiques au script d'origine, modifiables à l'appel)
# ------------------------------------------------------------------
CHEMIN_RACINE_DEFAUT = (
    r"\\appserver\EPSILON\3- DOSSIERS SERVICES\Qualité\Contrôle\MANUEL DE PROCEDURE"
    r"\PROCEDURE\DOCUMENTS DE CONTROLE\FICHE CONTROLE\TM"
)
FILTRES_DOSSIERS_DEFAUT = ["CEPOVETT  LAFONT", "FRISTADS", "PETIT BATEAU", "LOCAL", "WENAAS", "HEXONIA"]
ONGLETS_EXCLUS = {"CHEMISE", "CHEMISE MIRANA", "RECTO"}
NB_THREADS = 8
SORTIE_XLSX_DEFAUT = "Resultat_Format_Final.xlsx"
COLONNES_FINALES = ["Dossier_Source", "Fichier_Source", "Chemin_Complet",
                     "Modèle_Onglet", "Point de Mesure", "Tolérance", "Taille", "Valeur"]
TABLE_MESURES = "mesures_modele"

# Correspondance colonnes D→H de la feuille « Données » -> colonnes de la table SQL
COLONNES_SQL = {
    "Modèle_Onglet": "nom_modele",
    "Point de Mesure": "point_de_mesure",
    "Tolérance": "tolerance",
    "Taille": "taille",
    "Valeur": "valeur_cible",
}


def norm(s):
    return " ".join(str(s).upper().split())


# ------------------------------------------------------------------
# 2. Utilitaires (inchangés)
# ------------------------------------------------------------------
def txt(v):
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, numbers.Real):
        if v != v:  # NaN
            return None
        if float(v).is_integer():
            return str(int(v))
    return str(v)


def pm_txt(v):
    t = txt(v)
    return t.strip() if t is not None else None


# ------------------------------------------------------------------
# 3. Listing des fichiers
# ------------------------------------------------------------------
def lister_fichiers(chemin_racine, filtres):
    liste_filtres = [norm(x) for x in filtres if str(x).strip()]
    fichiers_cibles = []
    for root, _dirs, files in os.walk(chemin_racine):
        chemin_acces = norm(root.rstrip("\\") + "\\")
        if not any(f in chemin_acces for f in liste_filtres):
            continue
        dossier_source = os.path.basename(root.rstrip("\\"))
        for f in files:
            if f.startswith("~$"):
                continue
            if f.lower().endswith((".xlsx", ".xls")):
                fichiers_cibles.append((os.path.join(root, f), f, root + "\\", dossier_source))
    return fichiers_cibles


# ------------------------------------------------------------------
# 4. TraiterOnglet (logique Power Query — inchangée)
# ------------------------------------------------------------------
def traiter_onglet(rows):
    if not rows:
        return [], "onglet vide"

    largeur = max(len(r) for r in rows)
    data = [(list(r) + [None] * (largeur - len(r)))[1:] for r in rows]  # Column1 supprimée
    nb_cols = largeur - 1
    if nb_cols < 2:
        return [], "moins de 2 colonnes"

    pm_i = 0

    tol_i = None
    for j in range(nb_cols):
        for r in data[:10]:
            t = txt(r[j])
            if t is None:
                continue
            t = t.lower()
            if "tolérance" in t or "tolerance" in t or "+/-" in t:
                tol_i = j
                break
        if tol_i is not None:
            break
    if tol_i is None:
        tol_i = nb_cols - 1

    mesures_idx = [j for j in range(nb_cols) if j not in (pm_i, tol_i)]

    parasites = ("Chaine", "Controleur", "DECISION", "SIGNATURE", "Responsable Production")
    lignes = []
    for r in data:
        pm = pm_txt(r[pm_i])
        if pm is None or pm == "" or any(p in pm for p in parasites):
            continue
        lignes.append(r)

    tol_col, derniere = [], None
    for r in lignes:
        vt = txt(r[tol_i])
        pm = pm_txt(r[pm_i])
        if (vt is not None and "tolérance" not in vt.lower() and "+/-" not in vt
                and pm != "TAILLE" and pm != "REFERENCE"):
            derniere = vt.strip()
        tol_col.append(derniere)

    unpiv = []
    for k, r in enumerate(lignes):
        pm = pm_txt(r[pm_i])
        for j in mesures_idx:
            v = txt(r[j])
            if v is None:
                continue
            v = v.strip()
            if v == "":
                continue
            unpiv.append({"col": j, "idx": k, "pm": pm, "tol": tol_col[k], "val": v,
                          "taille": v if pm == "TAILLE" else None})

    unpiv.sort(key=lambda d: (d["col"], d["idx"]))
    derniere_taille = None
    for d in unpiv:
        if d["taille"] is not None:
            derniere_taille = d["taille"]
        else:
            d["taille"] = derniere_taille

    res = [(d["pm"], d["tol"], d["taille"], d["val"]) for d in unpiv
           if d["pm"] != "TAILLE" and d["pm"] != "REFERENCE"
           and d["taille"] not in (None, "") and d["taille"] != d["val"]]

    raison = ""
    if not res:
        if not any(pm_txt(r[pm_i]) == "TAILLE" for r in lignes):
            raison = "aucune ligne TAILLE"
        elif not unpiv:
            raison = "aucune valeur saisie"
        else:
            raison = "lignes éliminées par FiltrageStructure"
    return res, raison


# ------------------------------------------------------------------
# 5. Lecture d'un fichier
# ------------------------------------------------------------------
def lire_fichier(item, onglets_exclus=ONGLETS_EXCLUS):
    from python_calamine import CalamineWorkbook  # importé ici : uniquement nécessaire pour le scan réseau

    chemin, nom_fichier, chemin_dossier, dossier_source = item
    sortie, raisons = [], set()
    try:
        wb = CalamineWorkbook.from_path(chemin)
        for m in wb.sheets_metadata:
            onglet = m.name
            if "hidden" in str(m.visible).lower() or "sheet" not in str(m.typ).lower():
                continue
            if onglet.strip().upper() in onglets_exclus:
                continue
            rows = wb.get_sheet_by_name(onglet).to_python(skip_empty_area=False)
            res, raison = traiter_onglet(rows)
            if raison:
                raisons.add(f"{onglet.strip()}: {raison}")
            for pm, tol, taille, val in res:
                sortie.append((dossier_source, nom_fichier, chemin_dossier, onglet, pm, tol, taille, val))
    except Exception as e:
        return item, sortie, [f"ERREUR {type(e).__name__}: {e}"]
    return item, sortie, sorted(raisons)


# ------------------------------------------------------------------
# 6. Exécution parallèle sur tous les fichiers trouvés
# ------------------------------------------------------------------
def extraire_toutes_les_donnees(chemin_racine=CHEMIN_RACINE_DEFAUT, filtres=None,
                                 onglets_exclus=ONGLETS_EXCLUS, nb_threads=NB_THREADS, on_progress=None):
    """Retourne (df_final, resume, df_vides) — mêmes DataFrames que le script d'origine.
    on_progress(n, total), si fourni, est appelé après chaque fichier traité (pour une barre de progression)."""
    filtres = filtres if filtres is not None else FILTRES_DOSSIERS_DEFAUT
    fichiers_cibles = lister_fichiers(chemin_racine, filtres)

    lignes_finales, fichiers_vides = [], []
    with ThreadPoolExecutor(max_workers=nb_threads) as ex:
        futures = [ex.submit(lire_fichier, it, onglets_exclus) for it in fichiers_cibles]
        for n, fut in enumerate(as_completed(futures), 1):
            item, sortie, raisons = fut.result()
            lignes_finales.extend(sortie)
            if not sortie:
                fichiers_vides.append({
                    "Dossier_Source": item[3], "Fichier_Source": item[1], "Chemin_Complet": item[2],
                    "Raisons": " | ".join(raisons[:10]) if raisons else "aucun onglet exploitable",
                })
            if on_progress:
                on_progress(n, len(fichiers_cibles))

    df_final = pd.DataFrame(lignes_finales, columns=COLONNES_FINALES)
    df_final = df_final.drop_duplicates(
        subset=["Dossier_Source", "Fichier_Source", "Modèle_Onglet", "Point de Mesure", "Taille"], keep="first")

    resume = (df_final.groupby("Dossier_Source")
              .agg(Fichiers=("Fichier_Source", "nunique"), Onglets=("Modèle_Onglet", "nunique"),
                   Lignes=("Valeur", "size")).reset_index().sort_values("Lignes", ascending=False))

    df_vides = pd.DataFrame(fichiers_vides, columns=["Dossier_Source", "Fichier_Source", "Chemin_Complet", "Raisons"])
    return df_final, resume, df_vides


# ------------------------------------------------------------------
# 7. Export Excel (feuilles Données / Résumé_dossiers / Fichiers_0_ligne)
# ------------------------------------------------------------------
def _ecrire_feuille(writer, df, nom, largeur_max=60):
    df.to_excel(writer, sheet_name=nom, index=False, startrow=1, header=False)
    ws = writer.sheets[nom]
    if df.empty:
        return
    ws.add_table(0, 0, len(df), len(df.columns) - 1, {
        "columns": [{"header": c} for c in df.columns],
        "style": "Table Style Medium 2",
    })
    ws.freeze_panes(1, 0)
    for i, c in enumerate(df.columns):
        contenu = df[c].astype(str).str.len().quantile(0.95)
        ws.set_column(i, i, min(max(len(str(c)), contenu) + 2, largeur_max))


def exporter_excel(df_final, resume, df_vides, chemin_sortie=SORTIE_XLSX_DEFAUT):
    """Écrit le fichier Excel de traçabilité. Si le fichier est déjà ouvert (PermissionError),
    écrit dans un second fichier (« ..._2.xlsx ») comme le faisait le script d'origine."""
    def _ecrire(chemin):
        with pd.ExcelWriter(chemin, engine="xlsxwriter") as writer:
            _ecrire_feuille(writer, df_final, "Données")
            _ecrire_feuille(writer, resume, "Résumé_dossiers")
            _ecrire_feuille(writer, df_vides, "Fichiers_0_ligne")

    try:
        _ecrire(chemin_sortie)
        return chemin_sortie
    except PermissionError:
        secours = chemin_sortie.rsplit(".", 1)[0] + "_2.xlsx"
        _ecrire(secours)
        return secours


# ------------------------------------------------------------------
# 8. [AJOUT] Préparation des données pour la base (colonnes D à H de « Données »)
# ------------------------------------------------------------------
def preparer_donnees_pour_sql(df_final):
    """Isole les colonnes D à H de la feuille « Données » (Modèle_Onglet ... Valeur),
    les renomme pour coller à mesures_modele et nettoie les types, comme le fait déjà
    importer_sur_mesure_excel() pour l'import manuel dans l'application."""
    manquantes = [c for c in COLONNES_SQL if c not in df_final.columns]
    if manquantes:
        raise ValueError(f"Colonnes manquantes dans la feuille Données : {manquantes}")

    df = df_final[list(COLONNES_SQL)].rename(columns=COLONNES_SQL).copy()

    df["nom_modele"] = df["nom_modele"].astype(str).str.strip()
    df["point_de_mesure"] = df["point_de_mesure"].astype(str).str.strip()
    df["taille"] = df["taille"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    df["tolerance"] = pd.to_numeric(df["tolerance"].astype(str).str.replace(",", "."), errors="coerce")
    df["valeur_cible"] = pd.to_numeric(df["valeur_cible"].astype(str).str.replace(",", "."), errors="coerce").round(2)
    df["date_import"] = datetime.datetime.now()
    return df


# ------------------------------------------------------------------
# 9. [AJOUT] Chargement en base (remplace les mesures des modèles concernés)
# ------------------------------------------------------------------
def synchroniser_vers_sql(df_sql, engine):
    """DELETE puis INSERT par modèle, dans une seule transaction — même logique que
    importer_sur_mesure_excel() pour ne jamais dupliquer une fiche déjà importée."""
    if df_sql.empty:
        return 0
    modeles = [m for m in df_sql["nom_modele"].unique() if m]
    with engine.begin() as conn:
        for mod in modeles:
            conn.execute(text(f"DELETE FROM {TABLE_MESURES} WHERE nom_modele = :m"), {"m": mod})
        df_sql.to_sql(name=TABLE_MESURES, con=conn, if_exists="append", index=False)
    return len(df_sql)


# ------------------------------------------------------------------
# 10. [AJOUT] Point d'entrée unique : extraction + export + synchronisation SQL
# ------------------------------------------------------------------
def extraire_et_synchroniser(engine, chemin_racine=CHEMIN_RACINE_DEFAUT, filtres=None,
                              sortie_xlsx=SORTIE_XLSX_DEFAUT, on_progress=None):
    """À appeler depuis database.py (voir l'exemple d'intégration fourni à part) ou depuis
    le bouton « Synchroniser Excel ➡️ SQL » de l'application. Retourne un résumé chiffré."""
    df_final, resume, df_vides = extraire_toutes_les_donnees(
        chemin_racine=chemin_racine, filtres=filtres, on_progress=on_progress)
    chemin_excel = exporter_excel(df_final, resume, df_vides, sortie_xlsx)
    df_sql = preparer_donnees_pour_sql(df_final)
    nb_lignes = synchroniser_vers_sql(df_sql, engine)
    return {
        "nb_fichiers_lus": int(df_final["Fichier_Source"].nunique()) if not df_final.empty else 0,
        "nb_modeles": int(df_sql["nom_modele"].nunique()) if not df_sql.empty else 0,
        "nb_lignes_synchronisees": nb_lignes,
        "nb_fichiers_sans_donnees": len(df_vides),
        "chemin_excel": chemin_excel,
    }


# ------------------------------------------------------------------
# Exécution en script autonome (sans base de données) : ne produit que l'Excel, comme avant
# ------------------------------------------------------------------
if __name__ == "__main__":
    _df_final, _resume, _df_vides = extraire_toutes_les_donnees()
    _chemin = exporter_excel(_df_final, _resume, _df_vides)
    print(f"\nExtraction terminée : {len(_df_final)} lignes")
    print(f"Dossiers : {_df_final['Dossier_Source'].nunique()} | Fichiers : {_df_final['Fichier_Source'].nunique()}")
    print(f"Fichiers à 0 ligne : {len(_df_vides)}")
    print(f"Excel écrit : {os.path.abspath(_chemin)}")
