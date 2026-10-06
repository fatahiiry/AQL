"""Thème de l'application (après connexion) : même identité que la page de connexion.

Appelé APRÈS styles.apply_custom_styles() : il affine le rendu sans le remplacer.
Pour revenir à l'ancien design, il suffit de retirer l'appel appliquer_theme().
"""
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --fond: #1b3a6b; --fond-hover: #24508f; --fond-rgb: 27,58,107;
    --rouge: #d0021b; --gris: #f3f5f9; --bord: #e3e7ee; --texte: #111827; --doux: #8a94a6;
}

/* Police (les icônes Material sont des <span> : on ne les touche pas) */
html, body, p, label, li, td, th, input, textarea, button, h1, h2, h3, h4, h5, h6,
[data-testid="stMarkdownContainer"] { font-family: 'Inter', system-ui, sans-serif; }

.stApp { background: var(--gris); }
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stMainBlockContainer"], .block-container { padding-top: 1.6rem !important; max-width: 1400px; }

/* ---------- Bandeau principal ---------- */
.main-header {
    display: flex !important; align-items: center; justify-content: space-between; gap: 24px;
    background: var(--fond) !important; background-image: none !important;
    border: 0 !important; border-radius: 16px !important; padding: 22px 30px !important;
    box-shadow: 0 10px 28px rgba(var(--fond-rgb), .18); margin-bottom: 22px !important;
}
.main-header h1 { color: #fff !important; font-size: 26px; font-weight: 700; letter-spacing: -.4px; margin: 0; padding: 0; }
.main-header p  { color: #b9c4d8 !important; font-size: 14px; margin: 6px 0 0; padding: 0; }
.main-header .marque { color: #fff; font-size: 28px; letter-spacing: -.8px; line-height: 1; padding-bottom: 6px; border-bottom: 3px solid var(--rouge); white-space: nowrap; }

/* ---------- Barre latérale ---------- */
[data-testid="stSidebar"] { background: #fff; border-right: 1px solid var(--bord); }
[data-testid="stSidebar"] h3 { font-size: 13px !important; font-weight: 600 !important; color: var(--fond); letter-spacing: .2px; margin: 8px 0 8px !important; }
[data-testid="stSidebar"] hr { border-color: var(--bord); }

/* Menu principal en « pastilles » */
[data-testid="stSidebar"] [role="radiogroup"] { gap: 4px; }
[data-testid="stSidebar"] label[data-baseweb="radio"] {
    padding: 10px 14px; border-radius: 10px; margin: 0; width: 100%; transition: background .15s;
}
[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child { display: none; }
[data-testid="stSidebar"] label[data-baseweb="radio"]:hover { background: #eef2f8; }
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) { background: var(--fond); }
[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) p { color: #fff !important; font-weight: 600; }

/* Titres de section de la barre latérale */
.side-titre { margin: 20px 0 8px; font-size: 11px; font-weight: 700; letter-spacing: 1.6px; text-transform: uppercase; color: var(--doux); }

/* Carte utilisateur */
.user-card { display: flex; align-items: center; gap: 12px; padding: 12px 14px; margin: 8px 0 4px;
    background: var(--gris); border: 1px solid var(--bord); border-radius: 14px; }
.user-card .avatar { flex: none; width: 40px; height: 40px; border-radius: 50%; background: var(--fond); color: #fff;
    display: grid; place-items: center; font-weight: 700; font-size: 14px; letter-spacing: .5px; }
.user-card .infos { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.user-card strong { font-size: 14px; color: var(--texte); line-height: 1.2; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.user-card .role { align-self: flex-start; font-size: 11px; font-weight: 600; padding: 2px 9px; border-radius: 999px; }
.user-card .role.admin { background: #fde8ea; color: var(--rouge); }
.user-card .role.ope   { background: #e6ecf8; color: var(--fond); }

/* Lien « Gestion des utilisateurs » et expander dans la barre latérale */
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] { padding: 10px 14px; border-radius: 10px; }
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover { background: #eef2f8; }
[data-testid="stSidebar"] [data-testid="stExpander"] summary { font-weight: 600; }
[data-testid="stSidebar"] .stButton > button, [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] { width: 100%; }
.st-key-btn_logout button { border-color: #f3c6cb !important; color: #b00016 !important; background: #fff !important; }
.st-key-btn_logout button:hover { background: #fde8ea !important; }

/* ---------- Boutons ---------- */
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"],
.stButton > button, [data-testid="stFormSubmitButton"] > button { border-radius: 8px; font-weight: 600; transition: background .15s, border-color .15s; }
[data-testid="stBaseButton-primary"], .stButton > button[kind="primary"] { background: var(--fond); border: 1px solid var(--fond); color: #fff; }
[data-testid="stBaseButton-primary"]:hover, .stButton > button[kind="primary"]:hover { background: var(--fond-hover); border-color: var(--fond-hover); color: #fff; }
[data-testid="stBaseButton-secondary"] { background: #fff; border: 1px solid var(--bord); color: var(--texte); }
[data-testid="stBaseButton-secondary"]:hover { border-color: var(--fond); color: var(--fond); }

/* ---------- Champs, cartes, alertes ---------- */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] { border-radius: 8px !important; }
[data-testid="stAlert"] { border-radius: 12px; }
[data-testid="stExpander"] { background: #fff; border: 1px solid var(--bord) !important; border-radius: 12px; }
[data-testid="stFileUploaderDropzone"] { background: #fff; border: 1.5px dashed #c3cbdb; border-radius: 12px; }
[data-testid="stMetric"] { background: #fff; border: 1px solid var(--bord); border-radius: 12px; padding: 14px 18px; box-shadow: 0 4px 14px rgba(var(--fond-rgb), .06); }
[data-testid="stMetricLabel"] p { color: var(--doux); font-size: 13px; }
[data-testid="stDataFrame"], [data-testid="stDataEditor"] { border-radius: 12px; overflow: hidden; border: 1px solid var(--bord); }
[data-testid="stMainBlockContainer"] h2 { color: var(--fond); font-weight: 700; letter-spacing: -.3px; }
[data-testid="stMainBlockContainer"] h3, [data-testid="stMainBlockContainer"] h4 { color: var(--fond); font-weight: 600; }

/* Onglets */
[data-baseweb="tab-highlight"] { background: var(--rouge) !important; }
[data-baseweb="tab-list"] button[aria-selected="true"] p { color: var(--fond); font-weight: 600; }

/* ---------- [AJOUT] Cartes de contenu (formulaire, blocs st.container(border=True)) ---------- */
[data-testid="stForm"] {
    background: #fff; border: 1px solid var(--bord) !important; border-radius: 14px;
    padding: 22px 24px !important; box-shadow: 0 4px 16px rgba(var(--fond-rgb), .05);
}
[data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] {
    border-radius: 14px;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div[data-testid="stVerticalBlock"]) {
    border-radius: 14px; box-shadow: 0 3px 10px rgba(var(--fond-rgb), .05);
}

/* Alertes : liseré coloré à gauche, plus lisible qu'un simple fond pastel */
[data-testid="stAlert"] { border-left: 4px solid var(--doux); padding: 12px 16px; }
[data-testid="stAlert"] p { font-size: 13.5px; }
[data-testid="stNotification"] { border-radius: 12px; }

/* Titres de section : un peu d'air et un repère visuel discret */
[data-testid="stMainBlockContainer"] h3 { margin-top: 28px; padding-left: 12px; border-left: 3px solid var(--rouge); }

/* st.code (mot de passe temporaire, etc.) plus lisible */
[data-testid="stCodeBlock"] pre { border-radius: 10px; border: 1px solid var(--bord); font-size: 15px; }

/* Sélecteur radio horizontal (dans le contenu, pas la sidebar) plus soigné */
[data-testid="stMainBlockContainer"] [role="radiogroup"] label { padding: 4px 2px; }
/* [AJOUT] Réduit la marge par défaut de Streamlit en haut et sur les côtés de la sidebar */
[data-testid="stSidebarUserContent"] { padding-top: 1.2rem !important; padding-left: 0.9rem !important; padding-right: 0.9rem !important; }
[data-testid="stSidebarHeader"] { min-height: 0 !important; padding: 0 !important; }

</style>
"""


def appliquer_theme() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def entete(titre: str, sous_titre: str) -> str:
    """Bandeau principal (même structure que celui de l'application)."""
    return (
        '<div class="main-header"><div class="titres">'
        f"<h1>{titre}</h1><p>{sous_titre}</p></div>"
        '<span class="marque">epsilon</span></div>'
    )
