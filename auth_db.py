"""Accès à la base SQL Server [QualiteDB].[dbo].[utilisateurs] + statistiques."""
import hashlib
import hmac
import os
import secrets
from contextlib import closing
from pathlib import Path

import streamlit as st

try:
    import pyodbc
except ImportError:  # message clair plus bas
    pyodbc = None

TABLE = "[QualiteDB].[dbo].[utilisateurs]"
ITERATIONS = 240_000

# True  : un nouveau compte est créé inactif (actif = 0) et doit être activé par un administrateur.
# False : le compte est actif immédiatement après l'inscription.
VALIDATION_ADMIN = True
ROLE_PAR_DEFAUT = "operateur"
ROLES = ["operateur", "admin"]   # rôles proposés dans l'écran d'administration
ROLES_ADMIN = {"admin"}          # rôles autorisés à gérer les comptes

# Requête de synthèse Accepté / Refusé : elle doit renvoyer UNE ligne, DEUX colonnes
# (nombre d'acceptés, nombre de refusés). Tant qu'elle vaut None, des chiffres de
# démonstration sont affichés. Exemple à adapter à votre table :
#   SQL_STATS = ("SELECT SUM(CASE WHEN decision = 'ACCEPTE' THEN 1 ELSE 0 END), "
#                "SUM(CASE WHEN decision = 'REFUSE' THEN 1 ELSE 0 END) "
#                "FROM [QualiteDB].[dbo].[controles]")
SQL_STATS = None

# Chiffres affichés à gauche de la page de connexion tant que SQL_STATS vaut None.
# Modifiez-les librement : ils restent fixes jusqu'à ce que vous branchiez la requête ci-dessus.
STATS_MANUELLES = {"accepte": 2486, "refuse": 112}


class ErreurBase(Exception):
    """Erreur affichable telle quelle à l'utilisateur."""


# ------------------------------------------------------------------ fichier .env
def _charger_env() -> None:
    """Lit le fichier .env (dossier du projet ou dossier courant) sans module externe."""
    for dossier in (Path(__file__).parent, Path.cwd()):
        fichier = dossier / ".env"
        if not fichier.is_file():
            continue
        for ligne in fichier.read_text(encoding="utf-8-sig").splitlines():
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#") or "=" not in ligne:
                continue
            cle, valeur = ligne.split("=", 1)
            cle = cle.strip().removeprefix("export ").strip()
            valeur = valeur.strip().strip('"').strip("'")
            os.environ.setdefault(cle, valeur)  # une vraie variable d'environnement reste prioritaire
        return


_charger_env()


# ------------------------------------------------------------------ connexion
def _config() -> dict:
    cfg = {}
    try:
        cfg = dict(st.secrets.get("sqlserver", {}))
    except Exception:
        pass
    return {
        "driver": cfg.get("driver") or os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server"),
        "server": cfg.get("server") or os.getenv("DB_SERVER", "localhost"),
        "database": cfg.get("database") or os.getenv("DB_NAME", "QualiteDB"),
        "user": cfg.get("user") or os.getenv("DB_USER", ""),
        "password": cfg.get("password") or os.getenv("DB_PASSWORD", ""),
    }


def connexion():
    if pyodbc is None:
        raise ErreurBase("Le module pyodbc n'est pas installé (pip install pyodbc).")
    c = _config()
    parts = [
        f"DRIVER={{{c['driver']}}}",
        f"SERVER={c['server']}",
        f"DATABASE={c['database']}",
        "TrustServerCertificate=yes",
    ]
    if c["user"]:
        parts += [f"UID={c['user']}", f"PWD={{{c['password']}}}"]
    else:
        parts.append("Trusted_Connection=yes")  # authentification Windows
    try:
        return pyodbc.connect(";".join(parts), timeout=5)
    except pyodbc.Error as exc:
        raise ErreurBase("Connexion à la base de données impossible. Contactez le support.") from exc


# ------------------------------------------------------------ mots de passe
def hasher_mot_de_passe(mot_de_passe: str) -> str:
    sel = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode(), bytes.fromhex(sel), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${sel}${h}"


def verifier_mot_de_passe(mot_de_passe: str, stocke: str) -> bool:
    try:
        _, it, sel, h = stocke.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode(), bytes.fromhex(sel), int(it)).hex()
        return hmac.compare_digest(calc, h)
    except (ValueError, AttributeError):
        return False


# ------------------------------------------------------------- utilisateurs
def authentifier(matricule: str, mot_de_passe: str):
    """Retourne (statut, utilisateur) avec statut = 'ok' | 'inactif' | 'invalide'."""
    sql = (
        f"SELECT TOP (1) id, matricule, nom, prenom, username, [password], [role], actif "
        f"FROM {TABLE} WHERE matricule = ?"
    )
    with closing(connexion()) as cn:
        ligne = cn.cursor().execute(sql, matricule).fetchone()

    if ligne is None:
        verifier_mot_de_passe(mot_de_passe, "x$1$00$00")  # évite de révéler si le matricule existe
        return "invalide", None
    if not verifier_mot_de_passe(mot_de_passe, ligne.password or ""):
        return "invalide", None
    if not ligne.actif:
        return "inactif", None

    utilisateur = {
        "id": ligne.id, "matricule": ligne.matricule, "nom": ligne.nom,
        "prenom": ligne.prenom, "username": ligne.username, "role": ligne.role,
    }
    return "ok", utilisateur


def creer_utilisateur(matricule, nom, prenom, username, mot_de_passe) -> bool:
    """Crée le compte. Retourne True si le compte est actif tout de suite."""
    actif = 0 if VALIDATION_ADMIN else 1
    with closing(connexion()) as cn:
        cur = cn.cursor()
        if cur.execute(f"SELECT 1 FROM {TABLE} WHERE matricule = ?", matricule).fetchone():
            raise ErreurBase("Ce matricule est déjà inscrit.")
        if cur.execute(f"SELECT 1 FROM {TABLE} WHERE username = ?", username).fetchone():
            raise ErreurBase("Ce nom d'utilisateur existe déjà, choisissez-en un autre.")
        cur.execute(
            f"INSERT INTO {TABLE} (matricule, nom, prenom, username, [password], [role], actif, created_at) "
            f"VALUES (?, ?, ?, ?, ?, ?, ?, SYSDATETIME())",
            matricule, nom, prenom, username, hasher_mot_de_passe(mot_de_passe), ROLE_PAR_DEFAUT, actif,
        )
        cn.commit()
    return bool(actif)


# ------------------------------------------------- administration des comptes
def lister_utilisateurs() -> list:
    sql = (f"SELECT id, matricule, nom, prenom, username, [role], actif, created_at "
           f"FROM {TABLE} ORDER BY actif ASC, created_at DESC, id DESC")
    with closing(connexion()) as cn:
        lignes = cn.cursor().execute(sql).fetchall()
    return [
        {"id": l.id, "matricule": l.matricule, "nom": l.nom, "prenom": l.prenom,
         "username": l.username, "role": l.role, "actif": bool(l.actif), "created_at": l.created_at}
        for l in lignes
    ]


def _maj(sql: str, *params) -> None:
    with closing(connexion()) as cn:
        cn.cursor().execute(sql, *params)
        cn.commit()


def definir_actif(user_id: int, actif: bool) -> None:
    _maj(f"UPDATE {TABLE} SET actif = ? WHERE id = ?", 1 if actif else 0, user_id)


def definir_role(user_id: int, role: str) -> None:
    _maj(f"UPDATE {TABLE} SET [role] = ? WHERE id = ?", role, user_id)


def supprimer_utilisateur(user_id: int) -> None:
    _maj(f"DELETE FROM {TABLE} WHERE id = ?", user_id)


def reinitialiser_mot_de_passe(user_id: int) -> str:
    """Génère un mot de passe temporaire, le hache et l'enregistre. Retourne le mot de passe
    EN CLAIR une seule fois : c'est à l'administrateur de le transmettre à l'utilisateur
    (de vive voix ou par un canal sûr), il n'est jamais stocké ni renvoyé par la suite."""
    temporaire = secrets.token_urlsafe(6)  # ex. "aZ3-Qs9Lk1" : 8 caractères lisibles
    _maj(f"UPDATE {TABLE} SET [password] = ? WHERE id = ?", hasher_mot_de_passe(temporaire), user_id)
    return temporaire


# --------------------------------------------------------------- statistiques
@st.cache_data(ttl=300, show_spinner=False)
def stats_accepte_refuse() -> dict:
    if SQL_STATS is None:
        return {**STATS_MANUELLES, "demo": False}
    try:
        with closing(connexion()) as cn:
            a, r = cn.cursor().execute(SQL_STATS).fetchone()
        return {"accepte": int(a or 0), "refuse": int(r or 0), "demo": False}
    except Exception:
        return {"accepte": 0, "refuse": 0, "demo": False}
