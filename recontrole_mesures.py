"""
Contre-contrôle des mesures hors tolérance : une ligne par point en rouge,
5 cases de mesure, résultat calculé, enregistrement dans une table SÉPARÉE
(controle_sur_mesure_recontrole). Les tables existantes ne sont jamais modifiées.
"""
import pandas as pd
from sqlalchemy import text

NB_MESURES = 5
NB_PIECES_INITIALES = 4
EPS = 1e-9
COLS_M = [f'M{n}' for n in range(1, NB_MESURES + 1)]
NOM_TABLE = 'controle_sur_mesure_recontrole'


# ───────────── Outils purs ─────────────
def _vers_float(v):
    try:
        f = float(str(v).replace(',', '.'))
        return None if pd.isna(f) else f
    except (ValueError, TypeError):
        return None


def _saisi(v):
    return v is not None and str(v).strip() not in ('', 'nan', 'None')


def extraire_hors_tolerance(mesures_par_taille, ordre_tailles):
    """Liste des (taille, point) ayant au moins une pièce hors tolérance."""
    lignes = []
    for t in ordre_tailles:
        for rec in mesures_par_taille.get(t, []):
            c, tol = rec['CIBLE (cm)'], rec['TOL (+/-)']
            hors = []
            for n in range(1, NB_PIECES_INITIALES + 1):
                brut = rec[f'Pièce {n}']
                v = _vers_float(brut)
                if v is not None and (v < c - tol - EPS or v > c + tol + EPS):
                    hors.append(str(brut).strip())
            if hors:
                lignes.append({'taille': t, 'point': rec['POINTS DE MESURE'],
                               'cible': c, 'tol': tol, 'hors': hors})
    return lignes


def construire_grille_recontrole(hors, saisies):
    rows = []
    for h in hors:
        vals = saisies.get((h['taille'], h['point']), [''] * NB_MESURES)
        r = {'TAILLE': h['taille'], 'POINT': h['point'], 'CIBLE': h['cible'],
             'TOL': h['tol'], 'HORS_TOL': ' ; '.join(h['hors'])}
        for k, col in enumerate(COLS_M):
            r[col] = vals[k]
        rows.append(r)
    return pd.DataFrame(rows)


def lire_saisies(df):
    """{(taille, point): [M1..M5]} pour conserver la saisie entre deux rafraîchissements."""
    out = {}
    for _, r in df.iterrows():
        out[(str(r['TAILLE']), str(r['POINT']))] = [
            '' if not _saisi(r[c]) else str(r[c]).strip() for c in COLS_M
        ]
    return out


def evaluer_ligne(cible, tol, valeurs):
    """(nb_saisies, nb_hors_tol, 'Conforme' | 'Non conforme' | '')."""
    nb, hors = 0, 0
    for brut in valeurs:
        v = _vers_float(brut)
        if v is None:
            continue
        nb += 1
        if v < cible - tol - EPS or v > cible + tol + EPS:
            hors += 1
    resultat = '' if nb == 0 else ('Conforme' if hors == 0 else 'Non conforme')
    return nb, hors, resultat


def bilan(df):
    """(points_mesures, conformes, non_conformes)."""
    mesures = conformes = nc = 0
    for _, r in df.iterrows():
        _, _, res = evaluer_ligne(_vers_float(r['CIBLE']) or 0.0, _vers_float(r['TOL']) or 0.0,
                                  [r[c] for c in COLS_M])
        if res:
            mesures += 1
            conformes += res == 'Conforme'
            nc += res == 'Non conforme'
    return mesures, conformes, nc


def hauteur_recontrole(nb_lignes):
    return min(90 + 38 * nb_lignes, 600)


# ───────────── Tableau AgGrid ─────────────
def options_grille_recontrole():
    from st_aggrid import JsCode

    virgule = JsCode(
        "function(p){ return (p.value===null||p.value===undefined||p.value==='')"
        " ? '' : String(p.value).replace('.', ','); }"
    )
    ks = ','.join(f"'{c}'" for c in COLS_M)

    style_m = JsCode("""
    function(params) {
        var base = {'textAlign': 'center'};
        if (params.value === null || params.value === undefined || String(params.value).trim() === '') return base;
        var v = parseFloat(String(params.value).replace(',', '.'));
        var c = parseFloat(params.data.CIBLE), t = parseFloat(params.data.TOL);
        if (isNaN(v) || isNaN(c) || isNaN(t)) return base;
        if (v < (c - t - 1e-9) || v > (c + t + 1e-9)) {
            return {'color': '#dc2626', 'backgroundColor': '#fee2e2', 'fontWeight': 'bold', 'textAlign': 'center'};
        }
        return {'color': '#166534', 'backgroundColor': '#dcfce7', 'fontWeight': 'bold', 'textAlign': 'center'};
    }
    """)

    getter = JsCode(f"""
    function(p) {{
        var c = parseFloat(p.data.CIBLE), t = parseFloat(p.data.TOL), n = 0, bad = 0;
        [{ks}].forEach(function(k) {{
            var s = p.data[k];
            if (s === null || s === undefined || String(s).trim() === '') return;
            var v = parseFloat(String(s).replace(',', '.'));
            if (isNaN(v) || isNaN(c) || isNaN(t)) return;
            n++;
            if (v < (c - t - 1e-9) || v > (c + t + 1e-9)) bad++;
        }});
        return n === 0 ? '' : (bad === 0 ? 'Conforme' : 'Non conforme');
    }}
    """)

    style_res = JsCode("""
    function(p) {
        if (p.value === 'Conforme') return {'color': '#166534', 'fontWeight': 'bold', 'textAlign': 'center'};
        if (p.value === 'Non conforme') return {'color': '#dc2626', 'fontWeight': 'bold', 'textAlign': 'center'};
        return {'textAlign': 'center'};
    }
    """)

    cols = [
        {'field': 'TAILLE', 'headerName': 'Taille', 'width': 84, 'minWidth': 64, 'pinned': 'left',
         'editable': False,
         'cellStyle': {'backgroundColor': '#fee2e2', 'color': '#b91c1c', 'fontWeight': 'bold',
                       'textAlign': 'center'}},
        {'field': 'POINT', 'headerName': 'Point de mesure', 'width': 210, 'minWidth': 140,
         'pinned': 'left', 'editable': False, 'cellStyle': {'fontWeight': 'bold'}},
        {'field': 'CIBLE', 'headerName': 'Cible', 'width': 80, 'minWidth': 60, 'editable': False,
         'valueFormatter': virgule, 'cellStyle': {'textAlign': 'center', 'fontWeight': 'bold'}},
        {'field': 'TOL', 'headerName': 'Tol. (+/-)', 'width': 80, 'minWidth': 60, 'editable': False,
         'valueFormatter': virgule, 'cellStyle': {'textAlign': 'center'}},
        {'field': 'HORS_TOL', 'headerName': 'Hors tol. (1er contrôle)', 'width': 150, 'minWidth': 110,
         'editable': False, 'cellStyle': {'color': '#dc2626', 'fontWeight': 'bold', 'textAlign': 'center'}},
    ]
    for c in COLS_M:
        cols.append({'field': c, 'headerName': c, 'width': 74, 'minWidth': 56, 'editable': True,
                     'cellStyle': style_m})
    cols.append({'headerName': 'Résultat', 'colId': 'RESULTAT', 'valueGetter': getter, 'width': 120,
                 'minWidth': 96, 'pinned': 'right', 'editable': False, 'cellStyle': style_res})

    return {'columnDefs': cols, 'defaultColDef': {'resizable': True, 'sortable': False},
            'suppressMovableColumns': True, 'rowHeight': 36, 'headerHeight': 38}


# ───────────── Base de données (nouvelle table uniquement) ─────────────
def creer_table_recontrole(engine):
    with engine.begin() as conn:
        conn.execute(text(f"""
            IF OBJECT_ID('dbo.{NOM_TABLE}', 'U') IS NULL
            CREATE TABLE dbo.{NOM_TABLE} (
                id               INT IDENTITY(1,1) PRIMARY KEY,
                num_of           NVARCHAR(50)  NULL,
                reference        NVARCHAR(100) NULL,
                modele_mesures   NVARCHAR(100) NULL,
                taille           NVARCHAR(20)  NULL,
                point_de_mesure  NVARCHAR(200) NULL,
                valeur_cible     FLOAT NULL,
                tolerance        FLOAT NULL,
                valeurs_hors_tol NVARCHAR(200) NULL,
                mesure_1 NVARCHAR(20) NULL, mesure_2 NVARCHAR(20) NULL, mesure_3 NVARCHAR(20) NULL,
                mesure_4 NVARCHAR(20) NULL, mesure_5 NVARCHAR(20) NULL,
                nb_hors_tol      INT NULL,
                resultat         NVARCHAR(20) NULL,
                controleur       NVARCHAR(100) NULL,
                date_controle    DATE NULL,
                created_at       DATETIME DEFAULT GETDATE()
            )
        """))


def enregistrer_recontrole(engine, entete, df):
    """Insère une ligne par point dont au moins une case est remplie. Retourne le nombre de lignes."""
    lignes = []
    for _, r in df.iterrows():
        valeurs = [r[c] for c in COLS_M]
        cible, tol = _vers_float(r['CIBLE']) or 0.0, _vers_float(r['TOL']) or 0.0
        nb, hors, resultat = evaluer_ligne(cible, tol, valeurs)
        if nb == 0:
            continue
        ligne = {
            'num_of': entete.get('num_of'), 'reference': entete.get('reference'),
            'modele_mesures': entete.get('modele_mesures'),
            'taille': str(r['TAILLE']), 'point_de_mesure': str(r['POINT']),
            'valeur_cible': cible, 'tolerance': tol, 'valeurs_hors_tol': str(r['HORS_TOL']),
            'nb_hors_tol': hors, 'resultat': resultat,
            'controleur': entete.get('controleur'), 'date_controle': entete.get('date_controle'),
        }
        for k, v in enumerate(valeurs, start=1):
            ligne[f'mesure_{k}'] = str(v).strip() if _saisi(v) else None
        lignes.append(ligne)
    if not lignes:
        return 0
    creer_table_recontrole(engine)
    with engine.begin() as conn:
        conn.execute(text(f"""
            INSERT INTO dbo.{NOM_TABLE}
              (num_of, reference, modele_mesures, taille, point_de_mesure, valeur_cible, tolerance,
               valeurs_hors_tol, mesure_1, mesure_2, mesure_3, mesure_4, mesure_5,
               nb_hors_tol, resultat, controleur, date_controle)
            VALUES
              (:num_of, :reference, :modele_mesures, :taille, :point_de_mesure, :valeur_cible, :tolerance,
               :valeurs_hors_tol, :mesure_1, :mesure_2, :mesure_3, :mesure_4, :mesure_5,
               :nb_hors_tol, :resultat, :controleur, :date_controle)
        """), lignes)
    return len(lignes)
