import difflib
import re

from sqlalchemy import text

SEUIL_PROXIMITE = 0.80


# ───────────────────────── Logique pure (testable) ─────────────────────────
def normaliser(nom):
    """Majuscules, uniquement lettres et chiffres."""
    return re.sub(r"[^A-Z0-9]", "", str(nom or "").upper())


def cles_modele(nom):
    """Toutes les clés sous lesquelles un nom_modele peut être retrouvé."""
    nom = str(nom or "")
    cles = {normaliser(nom)}
    for partie in re.split(r"[-/]", nom):          # noms composés : 7330-7331 ...
        cles.add(normaliser(partie))
    for mot in nom.split():                        # "23954 FOLK" -> 23954
        n = normaliser(mot)
        if len(n) >= 4 and re.search(r"\d", n):
            cles.add(n)
    return {c for c in cles if len(c) >= 3}


def construire_index(noms_base):
    index = {}
    for nom in noms_base:
        for cle in cles_modele(nom):
            index.setdefault(cle, set()).add(nom)
    return index


def _suffixe_valide(suffixe, court):
    # petit suffixe avec au moins une lettre : 1354 / 1354CP
    if 1 <= len(suffixe) <= 3 and re.search(r"[A-Z]", suffixe):
        return True
    # code article : modèle + 4 chiffres (90509883 = 9050 + 9883, 9D993068 = 9D99 + 3068)
    return len(suffixe) == 4 and suffixe.isdigit() and len(court) >= 4


def trouver_candidats(ref, noms_base, alias=None):
    """Retourne (statut, [noms_modele_de_la_base])."""
    cle_alias = str(ref or "").strip().upper()
    if not cle_alias:
        return "aucun", []
    if alias and cle_alias in alias:
        return "alias", [alias[cle_alias]]

    n = normaliser(ref)
    index = construire_index(noms_base)

    if n in index:
        return "exact", sorted(index[n])

    retenus, mini = set(), None
    for cle, noms in index.items():
        court, long_ = (cle, n) if len(cle) < len(n) else (n, cle)
        if len(court) < 3 or len(court) == len(long_) or not long_.startswith(court):
            continue
        suffixe = long_[len(court):]
        if not _suffixe_valide(suffixe, court):
            continue
        if mini is None or len(suffixe) < mini:
            mini, retenus = len(suffixe), set(noms)
        elif len(suffixe) == mini:
            retenus |= noms
    if retenus:
        return "prefixe", sorted(retenus)

    proches = difflib.get_close_matches(n, list(index.keys()), n=5, cutoff=SEUIL_PROXIMITE)
    if proches:
        vus, resultat = set(), []
        for p in proches:
            for nom in sorted(index[p]):
                if nom not in vus:
                    vus.add(nom)
                    resultat.append(nom)
        return "suggestion", resultat

    return "aucun", []


# ───────────────────────── Accès base (SQL Server) ─────────────────────────
def creer_table_alias(engine):
    with engine.begin() as conn:
        conn.execute(text("""
            IF OBJECT_ID('alias_modele_mesure', 'U') IS NULL
            CREATE TABLE alias_modele_mesure (
                nom_controle NVARCHAR(100) NOT NULL PRIMARY KEY,
                nom_base     NVARCHAR(100) NOT NULL,
                created_at   DATETIME DEFAULT GETDATE()
            )
        """))


def lister_modeles_base(engine):
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT DISTINCT nom_modele FROM mesures_modele WHERE nom_modele IS NOT NULL"
        )).fetchall()
    return sorted(str(r[0]).strip() for r in rows if str(r[0]).strip())


def nb_mesures(engine, nom_modele):
    """Nombre de lignes de mesures d'un modèle (lecture seule)."""
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT COUNT(*) FROM mesures_modele "
            "WHERE LOWER(LTRIM(RTRIM(nom_modele))) = LOWER(LTRIM(RTRIM(:n)))"
        ), {"n": str(nom_modele)}).scalar() or 0


def charger_alias(engine):
    creer_table_alias(engine)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT nom_controle, nom_base FROM alias_modele_mesure"
        )).fetchall()
    return {str(r[0]).strip().upper(): str(r[1]).strip() for r in rows}


def enregistrer_alias(engine, nom_controle, nom_base):
    cle = str(nom_controle).strip().upper()
    creer_table_alias(engine)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM alias_modele_mesure WHERE nom_controle = :c"), {"c": cle})
        conn.execute(text(
            "INSERT INTO alias_modele_mesure (nom_controle, nom_base) VALUES (:c, :b)"
        ), {"c": cle, "b": str(nom_base).strip()})


# ───────────────────────── Aide pour l'interface Streamlit ─────────────────────────
def choisir_modele_base(ref_val, version, engine):
    """Retourne le nom_modele de mesures_modele à utiliser (ou None si non choisi).

    Le modèle trouvé automatiquement est proposé par défaut, et un menu permet
    toujours d'en choisir un autre si les mesures affichées ne conviennent pas.
    """
    import streamlit as st

    noms_base = lister_modeles_base(engine)
    alias = charger_alias(engine)
    statut, cands = trouver_candidats(ref_val, noms_base, alias)

    auto = cands[0] if (statut in ("alias", "exact", "prefixe") and len(cands) == 1) else None
    auto_vide = bool(auto) and nb_mesures(engine, auto) == 0
    auto_ok = bool(auto) and not auto_vide

    if auto_ok:
        if statut == "prefixe":
            st.caption(f"ℹ️ « {ref_val} » associé automatiquement au modèle « {auto} ».")
    elif auto_vide:
        st.warning(f"⚠️ Le modèle « {auto} » ne contient aucune mesure. Choisissez-en un autre.")
    elif statut == "suggestion":
        st.warning(f"⚠️ « {ref_val} » n'existe pas tel quel. Modèles proches : {', '.join(cands)}")
    elif cands:
        st.warning(f"⚠️ Plusieurs modèles possibles pour « {ref_val} ». Choisissez le bon.")
    else:
        st.warning(f"⚠️ Aucun modèle de mesures trouvé pour « {ref_val} ». Choisissez-le manuellement.")

    cle_select = f"sel_modele_base_{ref_val}_{version}"
    placeholder = "✅ Modèle automatique" if auto_ok else "-- Choisir le modèle --"
    options = [m for m in cands if m != auto] + [m for m in noms_base if m not in cands]
    if auto_ok:
        options = [auto] + options

    with st.expander("🔄 Les mesures affichées ne conviennent pas ? Choisir un autre modèle",
                     expanded=not auto_ok):
        choix = st.selectbox("Modèle de mesures dans la base", [placeholder] + options,
                             key=cle_select)
        if choix != placeholder and st.button("💾 Mémoriser cette correspondance",
                                              key=f"btn_alias_{ref_val}_{version}"):
            enregistrer_alias(engine, ref_val, choix)
            st.session_state.pop(cle_select, None)
            st.success(f"✅ « {ref_val} » → « {choix} » mémorisé.")
            st.rerun()

    if choix != placeholder:
        return choix
    return auto if auto_ok else None
