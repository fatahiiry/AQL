"""
Grille de mesures « fiche papier » dans UN SEUL tableau :
les tailles sont découpées en blocs de 4 (S M L XL, puis 2XL 3XL 4XL 5XL...),
chaque bloc est empilé sous le précédent avec sa ligne de titre.

Ce module ne lit et n'écrit rien en base : il met seulement en forme
le DataFrame lu dans mesures_modele, puis relit la saisie.
"""
import pandas as pd

NB_PIECES = 4
TAILLES_PAR_BLOC = 4          # mettre 3 ou 2 pour un tableau moins large
EPS = 1e-9
ORDRE_CONNU = ['XXS', 'XS', 'S', 'M', 'L', 'XL', 'XXL', '2XL', 'XXXL',
               '3XL', '4XL', '5XL', '6XL']
PIECES = [f'p{n}' for n in range(1, NB_PIECES + 1)]


# ───────────── Outils purs ─────────────
def _cle_taille(t):
    t = str(t).strip().upper()
    if t in ORDRE_CONNU:
        return (0, ORDRE_CONNU.index(t), '')
    try:
        return (1, float(t.replace(',', '.')), '')
    except ValueError:
        return (2, 0, t)


def trier_tailles(tailles):
    """S, M, L, XL, 2XL... puis tailles numériques, puis le reste."""
    uniques = {str(t).strip() for t in tailles if str(t).strip() not in ('', 'nan', 'None')}
    return sorted(uniques, key=_cle_taille)


def decouper(indices, n):
    return [indices[i:i + n] for i in range(0, len(indices), n)]


def lettre(i):
    s, i = '', i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _vers_float(v):
    try:
        f = float(str(v).replace(',', '.'))
        return None if pd.isna(f) else f
    except (ValueError, TypeError):
        return None


def _saisi(v):
    return v is not None and str(v).strip() not in ('', 'nan', 'None')


# ───────────── Construction de la grille empilée ─────────────
def construire_grille(df_raw, tailles, par_bloc=TAILLES_PAR_BLOC):
    """Retourne (DataFrame, blocs, nb_slots).

    blocs = liste de listes d'indices de tailles ; nb_slots = nb de tailles côte à côte.
    Colonnes : _TYPE ('titre'|'mesure'), _BLOC, REP, POINT, TOL,
               s{j}_cible, s{j}_tol, s{j}_p1..p4  (j = position de la taille dans le bloc).
    """
    df = df_raw.copy()
    df['taille'] = df['taille'].astype(str).str.strip()
    df['point_de_mesure'] = df['point_de_mesure'].astype(str).str.strip()
    points = list(dict.fromkeys(df['point_de_mesure']))       # ordre d'origine (ORDER BY id)
    df = df.drop_duplicates(subset=['point_de_mesure', 'taille'])
    par_taille = {t: df[df['taille'] == t].set_index('point_de_mesure') for t in tailles}

    nb_slots = max(1, min(par_bloc, len(tailles)))
    blocs = decouper(list(range(len(tailles))), nb_slots)

    def ligne(type_, bloc):
        r = {'_TYPE': type_, '_BLOC': bloc, 'REP': '', 'POINT': '', 'TOL': None}
        for j in range(nb_slots):
            r[f's{j}_cible'] = None
            r[f's{j}_tol'] = None
            for p in PIECES:
                r[f's{j}_{p}'] = ''
        return r

    lignes = []
    for b, indices in enumerate(blocs):
        titre = ligne('titre', b)
        titre['POINT'] = 'TAILLE'
        titre['TOL'] = 'Tol (+/-)'
        for j, i in enumerate(indices):
            titre[f's{j}_cible'] = tailles[i]            # le nom de la taille sert d'en-tête
        for j in range(len(indices), nb_slots):
            titre[f's{j}_cible'] = ''
        lignes.append(titre)

        k = 0
        for pt in points:
            r = ligne('mesure', b)
            toles = []
            for j, i in enumerate(indices):
                sub = par_taille[tailles[i]]
                if pt in sub.index:
                    r[f's{j}_cible'] = _vers_float(sub.at[pt, 'valeur_cible'])
                    r[f's{j}_tol'] = _vers_float(sub.at[pt, 'tolerance'])
                    toles.append(r[f's{j}_tol'])
            if all(r[f's{j}_cible'] is None for j in range(len(indices))):
                continue                                  # point absent pour ce bloc de tailles
            r['REP'] = lettre(k)
            r['POINT'] = pt
            r['TOL'] = next((t for t in toles if t is not None), None)
            lignes.append(r)
            k += 1

    return pd.DataFrame(lignes), blocs, nb_slots


def hauteur_grille(nb_lignes):
    return min(34 * nb_lignes + 24, 900)


def options_grille_empilee(nb_slots):
    """gridOptions AgGrid : pas d'en-tête classique, lignes de titre par bloc."""
    from st_aggrid import JsCode

    titre = ("'backgroundColor':'#1e3a5f','color':'white',"
             "'fontWeight':'bold','textAlign':'center'")

    def style(base):
        return JsCode("function(p){ if (p.data && p.data._TYPE === 'titre') "
                      "{ return {%s}; } return {%s}; }" % (titre, base))

    def style_piece(j):
        return JsCode(f"""
        function(params) {{
            var d = params.data;
            if (d && d._TYPE === 'titre') {{ return {{{titre}}}; }}
            var base = {{'textAlign': 'center'}};
            if (params.value === null || params.value === undefined || String(params.value).trim() === '') return base;
            var val = parseFloat(String(params.value).replace(',', '.'));
            var cible = parseFloat(String(d['s{j}_cible']).replace(',', '.'));
            var tol = parseFloat(String(d['s{j}_tol']).replace(',', '.'));
            if (!isNaN(val) && !isNaN(cible) && !isNaN(tol)) {{
                if (val < (cible - tol - 1e-9) || val > (cible + tol + 1e-9)) {{
                    return {{'color': '#dc2626', 'backgroundColor': '#fee2e2', 'fontWeight': 'bold', 'textAlign': 'center'}};
                }}
            }}
            return base;
        }}
        """)

    virgule = JsCode(
        "function(p){ return (p.value===null||p.value===undefined||p.value==='')"
        " ? '' : String(p.value).replace('.', ','); }"
    )
    editable_mesure = JsCode("function(p){ return !!p.data && p.data._TYPE === 'mesure'; }")
    span_titre = JsCode(
        f"function(p){{ return (p.data && p.data._TYPE === 'titre') ? {1 + NB_PIECES} : 1; }}"
    )

    # colonnes cachées en premier (n'influencent pas les fusions de cellules)
    cols = [{'field': '_TYPE', 'hide': True}, {'field': '_BLOC', 'hide': True}]
    cols += [{'field': f's{j}_tol', 'hide': True} for j in range(nb_slots)]

    cols += [
        {'field': 'REP', 'headerName': '', 'width': 44, 'minWidth': 36, 'pinned': 'left',
         'editable': False, 'cellStyle': style("'color':'#64748b','fontSize':'0.8em'")},
        {'field': 'POINT', 'headerName': 'Points de mesure', 'width': 220, 'minWidth': 150,
         'pinned': 'left', 'editable': False, 'cellStyle': style("'fontWeight':'bold'")},
    ]
    for j in range(nb_slots):
        cols.append({'field': f's{j}_cible', 'headerName': 'Cible', 'width': 64, 'minWidth': 54,
                     'editable': False, 'colSpan': span_titre, 'valueFormatter': virgule,
                     'cellStyle': style("'backgroundColor':'#f1f5f9','fontWeight':'bold','textAlign':'center'")})
        for n, p in enumerate(PIECES, start=1):
            cols.append({'field': f's{j}_{p}', 'headerName': f'P{n}', 'width': 54, 'minWidth': 42,
                         'editable': editable_mesure, 'cellStyle': style_piece(j)})
    cols.append({'field': 'TOL', 'headerName': 'Tol.', 'width': 84, 'minWidth': 64,
                 'pinned': 'right', 'editable': False, 'valueFormatter': virgule,
                 'cellStyle': style("'textAlign':'center'")})

    return {
        'columnDefs': cols,
        'defaultColDef': {'resizable': True, 'sortable': False},
        'suppressMovableColumns': True,
        'headerHeight': 0,
        'rowHeight': 34,
    }


# ───────────── Retour vers le format de l'historique ─────────────
def grille_vers_records(df, tailles, blocs):
    """{taille: [ {POINTS DE MESURE, TOL (+/-), CIBLE (cm), Pièce 1..4} ]}
    uniquement pour les tailles où au moins une pièce a été saisie."""
    resultat = {}
    for _, r in df.iterrows():
        if r.get('_TYPE') != 'mesure':
            continue
        indices = blocs[int(float(r['_BLOC']))]
        for j, i in enumerate(indices):
            cible = _vers_float(r[f's{j}_cible'])
            if cible is None:
                continue
            tol = _vers_float(r[f's{j}_tol'])
            rec = {'POINTS DE MESURE': r['POINT'],
                   'TOL (+/-)': 0.0 if tol is None else tol,
                   'CIBLE (cm)': cible}
            for n, p in enumerate(PIECES, start=1):
                v = r[f's{j}_{p}']
                rec[f'Pièce {n}'] = v if _saisi(v) else ''
            resultat.setdefault(tailles[i], []).append(rec)
    return {t: recs for t, recs in resultat.items()
            if any(_saisi(rec[f'Pièce {n}']) for rec in recs for n in range(1, NB_PIECES + 1))}


def compter_hors_tolerance(records_par_taille):
    nb = 0
    for recs in records_par_taille.values():
        for r in recs:
            for n in range(1, NB_PIECES + 1):
                v = _vers_float(r[f'Pièce {n}'])
                if v is None:
                    continue
                c, t = r['CIBLE (cm)'], r['TOL (+/-)']
                if v < c - t - EPS or v > c + t + EPS:
                    nb += 1
    return nb
