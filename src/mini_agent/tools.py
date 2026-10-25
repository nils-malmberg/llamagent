"""Les outils mis à disposition du modèle, et leur registre.

Un outil = une fonction Python + un schéma JSON qui la décrit au modèle.
Le modèle ne voit que le schéma (nom, description, paramètres) ; c'est le
harness qui exécute la fonction quand le modèle la demande.

Pour ajouter un outil : écrire la fonction, écrire son schéma, ajouter une
ligne dans TOOLS. La boucle agentique (agent.py) n'a pas à être modifiée.
"""

import difflib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from mini_agent.config import COMMAND_TIMEOUT
from mini_agent.guards import GuardError, safe_path

# Dossiers jamais listés : sans intérêt pour le modèle et souvent énormes.
IGNORED_DIRS = {"__pycache__", "node_modules"}
MAX_LISTED_FILES = 200


@dataclass
class ToolContext:
    """Ce dont les outils ont besoin pour travailler, fourni par le harness."""

    workdir: Path  # dossier de travail : les outils ne sortent pas d'ici
    skills_dir: Path  # dossier des skills (fichiers Markdown)
    confirm: Callable[[str], bool]  # pose une question [o/N] à l'utilisateur
    command_timeout: int = COMMAND_TIMEOUT


def read_file(ctx: ToolContext, path: str) -> str:
    """Renvoie le contenu d'un fichier texte du dossier de travail."""
    return safe_path(ctx.workdir, path).read_text(encoding="utf-8")


def list_files(ctx: ToolContext, path: str = ".") -> str:
    """Liste les fichiers d'un dossier (et de ses sous-dossiers)."""
    root = safe_path(ctx.workdir, path)
    # Sans cette vérification, os.walk ignore en silence un dossier absent :
    # on répondrait « aucun fichier » et le modèle croirait le dossier vide.
    if not root.is_dir():
        return f"Erreur : '{path}' n'est pas un dossier existant. Utilise '.' pour le dossier de travail."
    workdir = ctx.workdir.resolve()
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # On modifie `dirnames` sur place pour qu'os.walk n'entre pas dans
        # les dossiers cachés (.git, .venv...) ni dans les dossiers ignorés.
        dirnames[:] = sorted(
            d for d in dirnames if not d.startswith(".") and d not in IGNORED_DIRS
        )
        for name in sorted(filenames):
            # as_posix() : toujours des "/" même sous Windows, pour le modèle.
            files.append((Path(dirpath) / name).relative_to(workdir).as_posix())
    if not files:
        return "(aucun fichier)"
    if len(files) > MAX_LISTED_FILES:
        hidden = len(files) - MAX_LISTED_FILES
        files = files[:MAX_LISTED_FILES] + [f"... et {hidden} autres fichiers"]
    return "\n".join(files)


def write_file(ctx: ToolContext, path: str, content: str) -> str:
    """Remplace (ou crée) un fichier, après confirmation de l'utilisateur."""
    target = safe_path(ctx.workdir, path)
    old = target.read_text(encoding="utf-8") if target.exists() else ""
    # On montre à l'utilisateur exactement ce qui va changer.
    diff = "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"{path} (avant)",
            tofile=f"{path} (après)",
        )
    )
    if not ctx.confirm(f"{diff or '(aucun changement)'}\nÉcrire {path} ?"):
        return "Refusé par l'utilisateur : le fichier n'a pas été modifié."
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Fichier {path} écrit ({len(content.splitlines())} lignes)."


def run_command(ctx: ToolContext, command: str) -> str:
    """Lance une commande shell dans le dossier de travail, après confirmation."""
    if not ctx.confirm(f"Exécuter : {command}"):
        return "Refusé par l'utilisateur : la commande n'a pas été exécutée."
    # Force Python (s'il est lancé par la commande) à écrire en UTF-8,
    # sinon Windows utilise cp1252 et les accents deviennent illisibles.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    try:
        result = subprocess.run(
            command,
            shell=True,  # cmd.exe sous Windows, /bin/sh sous macOS
            cwd=ctx.workdir,
            capture_output=True,
            stdin=subprocess.DEVNULL,  # une commande ne peut pas attendre une saisie au clavier
            encoding="utf-8",
            errors="replace",
            timeout=ctx.command_timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return f"Erreur : la commande a dépassé {ctx.command_timeout} s et a été arrêtée."
    return (
        f"code de sortie : {result.returncode}\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )


def schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
    """Construit le schéma d'un outil au format attendu par Ollama."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


PATH_PARAM = {"type": "string", "description": "Chemin relatif au dossier de travail, ex. 'src/main.py'."}


# nom de l'outil -> (fonction Python, schéma envoyé au modèle)
TOOLS: dict[str, tuple[Callable[..., str], dict]] = {
    "read_file": (
        read_file,
        schema("read_file", "Lit un fichier texte et renvoie tout son contenu.", {"path": PATH_PARAM}, ["path"]),
    ),
    "list_files": (
        list_files,
        schema(
            "list_files",
            "Liste les fichiers d'un dossier et de ses sous-dossiers. Utilise '.' pour le dossier de travail.",
            {"path": PATH_PARAM},
            [],
        ),
    ),
    "write_file": (
        write_file,
        schema(
            "write_file",
            "Écrit un fichier texte. Remplace TOUT le contenu : donne le fichier complet, pas seulement la partie modifiée.",
            {"path": PATH_PARAM, "content": {"type": "string", "description": "Contenu complet du fichier."}},
            ["path", "content"],
        ),
    ),
    "run_command": (
        run_command,
        schema(
            "run_command",
            "Exécute une commande shell dans le dossier de travail et renvoie sa sortie. Ex. 'python script.py'.",
            {"command": {"type": "string", "description": "La commande à exécuter."}},
            ["command"],
        ),
    ),
}


def tool_schemas() -> list[dict]:
    """Les schémas de tous les outils, à envoyer au modèle."""
    return [tool_schema for _, tool_schema in TOOLS.values()]


def execute_tool(name: str, arguments: dict, ctx: ToolContext) -> str:
    """Version simple de l'étape 5 (l'étape 8 y ajoute la gestion des erreurs)."""
    function, _ = TOOLS[name]
    return function(ctx, **arguments)