"""Habillage commun : styles, panneau gauche (synthèse Accepté / Refusé), mise en page."""
import base64
from pathlib import Path

import streamlit as st

from auth_db import stats_accepte_refuse

# ------------------------------------------------------------------
# Option : déposez "fond.jpg" (ou .png / .webp) à côté de ce fichier,
# elle remplacera le graphique de synthèse dans le panneau gauche.
# ------------------------------------------------------------------
def _image_de_fond():
    for f in sorted(Path(__file__).parent.glob("fond.*")):
        if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            mime = "jpeg" if f.suffix.lower() in {".jpg", ".jpeg"} else f.suffix.lower().lstrip(".")
            return f"data:image/{mime};base64," + base64.b64encode(f.read_bytes()).decode()
    return None


IMAGE = _image_de_fond()


# ------------------------------------------------------------------
# Courbe de contrôle (points hors limites en rouge) + compteurs Accepté / Refusé
# ------------------------------------------------------------------
def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", "\u202f")


def _pct(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def courbe_svg() -> str:
    # Série illustrative : à remplacer plus tard par vos vraies mesures si vous le souhaitez.
    valeurs = [132, 118, 140, 125, 110, 138, 122, 146, 130, 114, 128,
               38, 120, 136, 124, 150, 118, 132, 142, 228, 128]
    x0, pas = 34, 26
    pts = [(x0 + i * pas, y) for i, y in enumerate(valeurs)]
    ligne = "M " + " L ".join(f"{x},{y}" for x, y in pts)
    haut, bas, moy = 62, 198, 130

    grille = "".join(f'<line x1="0" y1="{y}" x2="600" y2="{y}" class="g"/>' for y in range(20, 260, 40))
    points = ""
    for i, (x, y) in enumerate(pts):
        if y < haut or y > bas:
            points += (f'<circle cx="{x}" cy="{y}" r="6" class="halo"/>'
                       f'<circle cx="{x}" cy="{y}" r="5" class="nc"/>')
        else:
            points += f'<circle cx="{x}" cy="{y}" r="3" class="ok" style="animation-delay:{0.6 + i*0.07:.2f}s"/>'

    return (
        '<svg class="spc" viewBox="0 0 600 260" role="img" aria-label="Courbe de contrôle avec deux points hors limites">'
        f'{grille}'
        f'<line x1="0" y1="{haut}" x2="600" y2="{haut}" class="lim"/>'
        f'<line x1="0" y1="{bas}" x2="600" y2="{bas}" class="lim"/>'
        f'<line x1="0" y1="{moy}" x2="600" y2="{moy}" class="moy"/>'
        f'<path d="{ligne}" pathLength="1" class="courbe"/>{points}</svg>'
    )


def synthese_html() -> str:
    d = stats_accepte_refuse()
    a, r = d["accepte"], d["refuse"]
    total = a + r
    pa = a * 100 / total if total else 0.0
    pr = 100 - pa if total else 0.0

    html = (
        '<div class="synthese">' + courbe_svg() + '<div class="stats">'
        '<div class="stat"><span class="lib"><i class="dot ok"></i>Accepté</span></div>'
        '<div class="stat"><span class="lib"><i class="dot ko"></i>Refusé</span></div>'
        '</div>'
    )
    return html + "</div>"


def panneau_gauche_html() -> str:
    visuel = "" if IMAGE else synthese_html()
    return (
        '<span class="marker-left"></span><div class="left"><span class="logo">epsilon</span>'
        '<div class="milieu"><div class="centre"><h1>SUIVI QUALITE PRODUCTION</h1>'
        '<p class="desc">Saisie et suivi des non-conformités de production</p></div>'
        f'{visuel}</div><span class="version">v1.0 @ERP 2026</span></div>'
    )


# ------------------------------------------------------------------
# Styles
# ------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono&display=swap');

:root {
    --fond: #1b3a6b;         /* bleu Epsilon : panneau gauche + boutons */
    --fond-hover: #24508f;
    --fond-focus: 27,58,107; /* RGB pour les halos de focus */
    --texte-doux: #b9c4d8;
    --texte-version: #5f7396;
    --ok: #5fd39a;
    --ko: #ff3b4e;
}

/* ---------- Nettoyage du chrome Streamlit ---------- */
header[data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stSidebar"], [data-testid="stSidebarNav"],
[data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display: none !important; }
.stApp { background: #ffffff; }
.block-container, [data-testid="stMainBlockContainer"] { padding: 0 !important; max-width: 100% !important; }
[data-testid="stAppViewContainer"] > .main, section.main { padding: 0 !important; }
[data-testid="stHorizontalBlock"] { gap: 0 !important; align-items: stretch !important; }
[data-testid="stVerticalBlock"] { gap: 0; }

.left, .left *, .right, .right *, .right label, .right label p, .right input,
.right button, .right button p, .right [data-testid="stAlert"] p { font-family: 'Inter', system-ui, sans-serif !important; }

/* ================= COLONNE GAUCHE ================= */
[data-testid="stColumn"]:has(.marker-left), [data-testid="column"]:has(.marker-left) {
    position: relative; overflow: hidden; background: var(--fond); min-height: 100vh;
}
[data-testid="stColumn"]:has(.marker-left) > *, [data-testid="column"]:has(.marker-left) > * { position: relative; z-index: 1; }

.left { min-height: 100vh; padding: 36px 34px 30px; color: #fff; display: flex; flex-direction: column; justify-content: space-between; }
.left .logo { display: inline-block; align-self: flex-start; font-size: 44px; letter-spacing: -1px; line-height: 1; padding-bottom: 8px; border-bottom: 3px solid #d0021b; }
.left .centre { text-align: center; }
.left h1 { margin: 0; padding: 0; font-size: clamp(28px, 2.6vw, 44px); font-weight: 700; line-height: 1.1; letter-spacing: -.5px; color: var(--ko); text-align: center; }
.left p.desc { margin: 22px auto 0; text-align: center; max-width: 360px; font-size: 14px; line-height: 1.65; color: var(--texte-doux); }
.left .version { font-family: 'JetBrains Mono', monospace !important; font-size: 11px; color: var(--texte-version); letter-spacing: 1px; }
.left .milieu { display: flex; flex-direction: column; gap: 40px; }

/* ---------- Synthèse : courbe + compteurs ---------- */
.left .synthese { display: flex; flex-direction: column; align-items: center; gap: 26px; }
.left .spc { width: 100%; height: auto; display: block; overflow: visible; }
.left .spc .g   { stroke: rgba(255,255,255,.06); stroke-width: 1; }
.left .spc .lim { stroke: var(--ko); stroke-width: 1.2; stroke-dasharray: 5 5; opacity: .55; }
.left .spc .moy { stroke: rgba(255,255,255,.35); stroke-width: 1; }
.left .spc .courbe {
    fill: none; stroke: #e7ebf0; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round;
    stroke-dasharray: 1; stroke-dashoffset: 1; animation: trace 2.2s .2s ease-out forwards;
}
.left .spc .ok   { fill: #e7ebf0; opacity: 0; animation: apparait .3s forwards; }
.left .spc .nc   { fill: var(--ko); stroke: #fff; stroke-width: 1.5; opacity: 0; animation: apparait .3s 1.4s forwards; }
.left .spc .halo { fill: var(--ko); opacity: 0; animation: pulse 2.2s 1.6s ease-out infinite; transform-box: fill-box; transform-origin: center; }
.left .stats { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; width: 100%; max-width: 460px; }
.left .stat { background: rgba(255,255,255,.07); border-radius: 12px; padding: 14px 16px; display: flex; flex-direction: column; gap: 4px; }
.left .stat .lib { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--texte-doux); }
.left .stat strong { font-size: 28px; font-weight: 700; letter-spacing: -.5px; line-height: 1.1; }
.left .stat strong.ko { color: #ff8a95; }
.left .stat em { font-style: normal; font-size: 12.5px; color: var(--texte-doux); }
.left .dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.left .dot.ok { background: var(--ok); } .left .dot.ko { background: var(--ko); }
.left .demo { margin: -8px 0 0; font-size: 11px; color: var(--texte-version); }
@keyframes trace    { to { stroke-dashoffset: 0; } }
@keyframes apparait { to { opacity: 1; } }
@keyframes pulse    { 0% { opacity: .55; transform: scale(1); } 100% { opacity: 0; transform: scale(3.2); } }
@media (prefers-reduced-motion: reduce) {
    .left .spc * { animation: none !important; }
    .left .spc .courbe { stroke-dashoffset: 0; } .left .spc .ok, .left .spc .nc { opacity: 1; }
}

/* ================= COLONNE DROITE (cadre) ================= */
[data-testid="stColumn"]:has(.marker-right), [data-testid="column"]:has(.marker-right) {
    background: #f3f5f9; padding: 40px max(20px, 5vw) !important; min-height: 100vh;
    display: flex; flex-direction: column; justify-content: center;
}
[data-testid="stColumn"]:has(.marker-right) > [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has(.marker-right) > div > [data-testid="stVerticalBlock"],
[data-testid="column"]:has(.marker-right) > [data-testid="stVerticalBlock"],
[data-testid="column"]:has(.marker-right) > div > [data-testid="stVerticalBlock"] {
    width: 100%; max-width: 500px; align-self: center;
    flex: 0 0 auto !important; height: auto !important; min-height: 0 !important;
    background: #fff; border: 1px solid #e3e7ee; border-radius: 16px;
    box-shadow: 0 12px 32px rgba(27,58,107,.10); padding: 28px 40px 20px;
}
[data-testid="stColumn"]:has(.marker-right) [data-testid="stHorizontalBlock"] { gap: 14px !important; }

.right p.eyebrow { color: #d0021b; font-size: 11px; font-weight: 700; letter-spacing: 2.6px; text-transform: uppercase; margin: 0 0 8px; }
.right p.titre   { font-size: 24px; font-weight: 600; letter-spacing: -.3px; margin: 0; color: #111827; line-height: 1.2; }
.right p.sous    { font-size: 13.5px; color: #8a94a6; margin: 6px 0 22px; line-height: 1.5; }
.right p.legal   { text-align: center; font-size: 11.5px; color: #c3c9d4; margin: 14px 0 0; }

/* Lien de navigation (S'inscrire / Se connecter) : centré, en bleu */
[data-testid="stElementContainer"]:has([data-testid="stPageLink"]) { width: 100% !important; }
[data-testid="stPageLink"] { width: 100%; display: flex; justify-content: center; margin-top: 10px; }
[data-testid="stPageLink"] a, [data-testid="stPageLink-NavLink"] {
    justify-content: center; text-decoration: none !important; padding: 6px 12px; border-radius: 8px;
}
[data-testid="stPageLink"] *, [data-testid="stPageLink-NavLink"] * { color: var(--fond) !important; }
[data-testid="stPageLink"] p { font-size: 13.5px; font-weight: 600; }
[data-testid="stPageLink"] a:hover, [data-testid="stPageLink-NavLink"]:hover { background: rgba(var(--fond-focus), .07); }

/* Formulaire */
[data-testid="stForm"] { border: 0 !important; padding: 0 !important; background: transparent; }
[data-testid="stTextInput"] { margin-bottom: 8px; }
[data-testid="stTextInput"] label p { font-size: 13.5px !important; font-weight: 500; color: #111827; }
[data-testid="stTextInput"] [data-baseweb="input"] {
    background: #fff !important; border: 1px solid #e3e7ee !important; border-radius: 8px !important; height: 44px; overflow: hidden;
}
[data-testid="stTextInput"] [data-baseweb="base-input"] { background: transparent !important; border: 0 !important; }
[data-testid="stTextInput"] [data-baseweb="input"]:focus-within { border-color: var(--fond) !important; box-shadow: 0 0 0 3px rgba(var(--fond-focus),.15); }
[data-testid="stTextInput"] input { font-size: 14px !important; color: #111827; padding-left: 14px; }
[data-testid="stTextInput"] input::placeholder { color: #c3c9d4; }
[data-testid="stTextInput"] [data-baseweb="input"] > div:last-child, [data-testid="stTextInput"] button { background: transparent !important; }

[data-testid="stElementContainer"]:has([data-testid="stFormSubmitButton"]) { width: 100% !important; }
[data-testid="stFormSubmitButton"], [data-testid="stFormSubmitButton"] div { width: 100% !important; }
[data-testid="stFormSubmitButton"] button { width: 100% !important; height: 44px; border: 0; border-radius: 8px; background: var(--fond); color: #fff; margin-top: 6px; }
[data-testid="stFormSubmitButton"] button p { font-size: 14px; font-weight: 600; color: #fff; }
[data-testid="stFormSubmitButton"] button:hover { background: var(--fond-hover); color: #fff; }
[data-testid="stFormSubmitButton"] button:focus-visible { box-shadow: 0 0 0 3px rgba(var(--fond-focus),.3); }

/* ================= MOBILE ================= */
@media (max-width: 820px) {
    [data-testid="stColumn"]:has(.marker-left), [data-testid="column"]:has(.marker-left) { min-height: auto; }
    .left { min-height: auto; padding: 24px 22px 28px; gap: 28px; }
    .left h1 { font-size: 30px; }
    .left .version { display: none; }
    [data-testid="stColumn"]:has(.marker-right), [data-testid="column"]:has(.marker-right) { padding: 24px 16px 32px !important; min-height: auto; }
    [data-testid="stColumn"]:has(.marker-right) > [data-testid="stVerticalBlock"],
    [data-testid="stColumn"]:has(.marker-right) > div > [data-testid="stVerticalBlock"],
    [data-testid="column"]:has(.marker-right) > [data-testid="stVerticalBlock"],
    [data-testid="column"]:has(.marker-right) > div > [data-testid="stVerticalBlock"] { padding: 24px 20px 18px; }
}
</style>
"""


def afficher_page():
    """Applique les styles, dessine le panneau gauche et retourne la colonne droite."""
    st.markdown(CSS, unsafe_allow_html=True)
    if IMAGE:
        st.markdown(
            f"""<style>
[data-testid="stColumn"]:has(.marker-left), [data-testid="column"]:has(.marker-left) {{
    background: linear-gradient(180deg, rgba(27,58,107,.70) 0%, rgba(27,58,107,.90) 100%),
                url("{IMAGE}") center / cover no-repeat !important;
}}
</style>""",
            unsafe_allow_html=True,
        )
    gauche, droite = st.columns([9, 11])  # droite un peu plus large
    with gauche:
        st.markdown(panneau_gauche_html(), unsafe_allow_html=True)
    with droite:
        st.markdown('<span class="marker-right"></span>', unsafe_allow_html=True)
    return droite
