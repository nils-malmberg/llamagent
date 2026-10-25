"""Garde-fous : ce qui protège l'utilisateur contre les erreurs du modèle.

Le modèle peut se tromper de chemin, vouloir écrire n'importe où ou lancer
une commande qui ne s'arrête jamais. Ces vérifications sont faites par le
harness, en Python : on ne compte pas sur le modèle pour les respecter.
"""

from pathlib import Path


class GuardError(Exception):
    """Action refusée par un garde-fou. Le message est renvoyé au modèle."""


def safe_path(workdir: Path, path: str) -> Path:
    """Transforme un chemin donné par le modèle en chemin sûr.

    Refuse tout chemin qui contient ".." ou qui sort du dossier de travail
    (par exemple un chemin absolu comme /etc/passwd ou C:\\Windows).
    """
    if ".." in Path(path).parts:
        raise GuardError(f"chemin refusé ({path}) : '..' est interdit.")
    root = workdir.resolve()
    # Si `path` est absolu, `root / path` vaut `path` : d'où la vérification.
    full = (root / path).resolve()
    if not full.is_relative_to(root):
        raise GuardError(f"chemin refusé ({path}) : il sort du dossier de travail {root}.")
    return full


def ask_confirmation(question: str) -> bool:
    """Demande une confirmation à l'utilisateur. Par défaut (Entrée) : non."""
    answer = input(f"{question} [o/N] ").strip().lower()
    return answer in ("o", "oui")


def truncate(text: str, max_chars: int) -> str:
    """Raccourcit un texte trop long en gardant le début et la fin.

    La fin est souvent la partie utile (message d'erreur, traceback).
    """
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    removed = len(text) - 2 * half
    return f"{text[:half]}\n[... {removed} caractères tronqués ...]\n{text[-half:]}"