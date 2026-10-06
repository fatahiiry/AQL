"""Garde l'utilisateur connecté après un rafraîchissement de page (F5).

Pourquoi c'est nécessaire : st.session_state vit en mémoire côté serveur,
attaché à la connexion (websocket) de l'onglet. Un F5 ferme cette connexion
et en ouvre une nouvelle : session_state repart à zéro. Pour survivre au
rafraîchissement, on stocke un jeton signé dans l'URL (st.query_params),
qui lui survit, et on reconstruit la session à partir de ce jeton.

Sécurité : signez toujours avec une vraie clé secrète. Ajoutez dans votre
.env : SESSION_SECRET=une_longue_chaine_aleatoire (par ex. générée avec
`python -c "import secrets; print(secrets.token_hex(32))"`).
Le jeton apparaît dans l'URL : il expire (8 h par défaut) et n'importe qui
qui l'intercepterait pourrait l'utiliser tant qu'il est valide — comme un
cookie de session classique. Ne partagez pas un lien contenant "?session=...".
"""
import base64
import hashlib
import hmac
import json
import os
import time

import streamlit as st

DUREE_VALIDITE_SECONDES = 8 * 3600  # 8 heures
PARAM = "session"


def _cle_secrete() -> bytes:
    cle = os.getenv("SESSION_SECRET")
    if not cle:
        # Repli non sécurisé : évite un plantage si la variable n'est pas définie,
        # mais tout le monde qui lit ce code peut alors forger un jeton.
        # -> Définissez SESSION_SECRET dans votre .env dès que possible.
        cle = "ATTENTION_definir_SESSION_SECRET_dans_le_fichier_env"
    return cle.encode()


def _signer(corps: str) -> str:
    return hmac.new(_cle_secrete(), corps.encode(), hashlib.sha256).hexdigest()[:32]


def generer_jeton(utilisateur: dict) -> str:
    charge = {**utilisateur, "exp": int(time.time()) + DUREE_VALIDITE_SECONDES}
    corps = base64.urlsafe_b64encode(json.dumps(charge).encode()).decode().rstrip("=")
    return f"{corps}.{_signer(corps)}"


def lire_jeton(jeton: str):
    try:
        corps, signature = jeton.split(".", 1)
        if not hmac.compare_digest(signature, _signer(corps)):
            return None  # signature invalide : jeton altéré ou clé différente
        charge = json.loads(base64.urlsafe_b64decode(corps + "=" * (-len(corps) % 4)))
        if charge.get("exp", 0) < time.time():
            return None  # jeton expiré
        charge.pop("exp", None)
        return charge
    except Exception:
        return None


def restaurer_session() -> None:
    """À appeler tout en haut de chaque page (avant de tester st.session_state.utilisateur)."""
    if st.session_state.get("utilisateur"):
        return
    jeton = st.query_params.get(PARAM)
    if jeton:
        utilisateur = lire_jeton(jeton)
        if utilisateur:
            st.session_state.utilisateur = utilisateur


def ouvrir_session(utilisateur: dict) -> None:
    """À appeler juste après une connexion réussie, avant st.switch_page.

    Ne pose PAS le jeton dans l'URL ici : st.switch_page change de page et
    repart avec une URL sans paramètres, donc un jeton posé juste avant serait
    aussitôt perdu. st.session_state, lui, survit à switch_page — c'est donc
    lui qui porte l'utilisateur jusqu'à la page de destination, où
    assurer_jeton() pose le jeton pour de bon."""
    st.session_state.utilisateur = utilisateur


def assurer_jeton(utilisateur: dict) -> None:
    """À appeler sur chaque page protégée, une fois l'utilisateur confirmé connecté.
    Pose le jeton dans l'URL s'il n'y est pas déjà (juste après une connexion,
    ou si l'utilisateur a modifié l'URL à la main)."""
    if not st.query_params.get(PARAM):
        st.query_params[PARAM] = generer_jeton(utilisateur)


def fermer_session() -> None:
    """À appeler à la déconnexion."""
    st.session_state.utilisateur = None
    st.query_params.pop(PARAM, None)
