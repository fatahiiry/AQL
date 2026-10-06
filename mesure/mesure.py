import os
import numbers
import warnings
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from python_calamine import CalamineWorkbook

warnings.filterwarnings("ignore")

# ------------------------------------------------------------------
# 1. Paramètres
# ------------------------------------------------------------------
def norm(s):
    return " ".join(str(s).upper().split())

tb_filtres = ["CEPOVETT  LAFONT", "FRISTADS", "PETIT BATEAU", "LOCAL", "WENAAS", "HEXONIA"]
liste_filtres = [norm(x) for x in tb_filtres if str(x).strip()]

chemin_racine = r"\\appserver\EPSILON\3- DOSSIERS SERVICES\Qualité\Contrôle\MANUEL DE PROCEDURE\PROCEDURE\DOCUMENTS DE CONTROLE\FICHE CONTROLE\TM"

ONGLETS_EXCLUS = {"CHEMISE", "CHEMISE MIRANA", "RECTO"}
NB_THREADS = 8
SORTIE_XLSX = "Resultat_Format_Final.xlsx"
COLONNES_FINALES = ["Dossier_Source", "Fichier_Source", "Chemin_Complet",
                    "Modèle_Onglet", "Point de Mesure", "Tolérance", "Taille", "Valeur"]


# ------------------------------------------------------------------
# 2. Utilitaires
# ------------------------------------------------------------------
def txt(v):
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, numbers.Real):
        if v != v:
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
fichiers_cibles = []
for root, dirs, files in os.walk(chemin_racine):
    chemin_acces = norm(root.rstrip("\\") + "\\")
    if not any(f in chemin_acces for f in liste_filtres):
        continue
    dossier_source = os.path.basename(root.rstrip("\\"))
    for f in files:
        if f.startswith("~$"):
            continue
        if f.lower().endswith((".xlsx", ".xls")):
            fichiers_cibles.append((os.path.join(root, f), f, root + "\\", dossier_source))

print(f"{len(fichiers_cibles)} fichiers trouvés")


# ------------------------------------------------------------------
# 4. TraiterOnglet (logique Power Query)
# ------------------------------------------------------------------
def traiter_onglet(rows):
    if not rows:
        return [], "onglet vide"

    largeur = max(len(r) for r in rows)
    data = [(list(r) + [None] * (largeur - len(r)))[1:] for r in rows]   # Column1 supprimée
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
def lire_fichier(item):
    chemin, nom_fichier, chemin_dossier, dossier_source = item
    sortie, raisons = [], set()
    try:
        wb = CalamineWorkbook.from_path(chemin)
        for m in wb.sheets_metadata:
            onglet = m.name
            if "hidden" in str(m.visible).lower() or "sheet" not in str(m.typ).lower():
                continue
            if onglet.strip().upper() in ONGLETS_EXCLUS:
                continue
            rows = wb.get_sheet_by_name(onglet).to_python(skip_empty_area=False)
            res, raison = traiter_onglet(rows)
            if raison:
                raisons.add(f"{onglet.strip()}: {raison}")
            for pm, tol, taille, val in res:
                sortie.append((dossier_source, nom_fichier, chemin_dossier,
                               onglet, pm, tol, taille, val))
    except Exception as e:
        return item, sortie, [f"ERREUR {type(e).__name__}: {e}"]
    return item, sortie, sorted(raisons)


# ------------------------------------------------------------------
# 6. Exécution parallèle
# ------------------------------------------------------------------
lignes_finales, fichiers_vides = [], []

with ThreadPoolExecutor(max_workers=NB_THREADS) as ex:
    futures = [ex.submit(lire_fichier, it) for it in fichiers_cibles]
    for n, fut in enumerate(as_completed(futures), 1):
        item, sortie, raisons = fut.result()
        lignes_finales.extend(sortie)
        if not sortie:
            fichiers_vides.append({
                "Dossier_Source": item[3],
                "Fichier_Source": item[1],
                "Chemin_Complet": item[2],
                "Raisons": " | ".join(raisons[:10]) if raisons else "aucun onglet exploitable",
            })
        if n % 10 == 0:
            print(f"  {n}/{len(fichiers_cibles)} fichiers traités")


# ------------------------------------------------------------------
# 7. Résultat + export Excel
# ------------------------------------------------------------------
df_final = pd.DataFrame(lignes_finales, columns=COLONNES_FINALES)
df_final = df_final.drop_duplicates(
    subset=["Dossier_Source", "Fichier_Source", "Modèle_Onglet", "Point de Mesure", "Taille"],
    keep="first",
)

resume = (df_final.groupby("Dossier_Source")
          .agg(Fichiers=("Fichier_Source", "nunique"),
               Onglets=("Modèle_Onglet", "nunique"),
               Lignes=("Valeur", "size"))
          .reset_index()
          .sort_values("Lignes", ascending=False))

df_vides = pd.DataFrame(fichiers_vides,
                        columns=["Dossier_Source", "Fichier_Source", "Chemin_Complet", "Raisons"])


def ecrire_feuille(writer, df, nom, largeur_max=60):
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


def exporter(chemin):
    with pd.ExcelWriter(chemin, engine="xlsxwriter") as writer:
        ecrire_feuille(writer, df_final, "Données")
        ecrire_feuille(writer, resume, "Résumé_dossiers")
        ecrire_feuille(writer, df_vides, "Fichiers_0_ligne")

try:
    exporter(SORTIE_XLSX)
except PermissionError:
    SORTIE_XLSX = "Resultat_Format_Final_2.xlsx"
    print("Fichier ouvert dans Excel, écriture dans", SORTIE_XLSX)
    exporter(SORTIE_XLSX)

print(f"\nExtraction terminée : {len(df_final)} lignes")
print(f"Dossiers : {df_final['Dossier_Source'].nunique()} | Fichiers : {df_final['Fichier_Source'].nunique()}")
print(f"Fichiers à 0 ligne : {len(fichiers_vides)}")
print(f"Excel écrit : {os.path.abspath(SORTIE_XLSX)}")