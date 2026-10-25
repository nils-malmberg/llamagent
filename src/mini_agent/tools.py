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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from mini_agent.config import COMMAND_TIMEOUT
from mini_agent.guards import GuardError, is_allowed_command, safe_path

# Dossiers jamais listés : sans intérêt pour le modèle et souvent énormes.
IGNORED_DIRS = {"__pycache__", "node_modules"}
MAX_LISTED_FILES = 200


@dataclass
class ToolContext:
    """Ce dont les outils ont besoin pour travailler, fourni par le harness."""

    workdir: Path  # dossier de travail : les outils ne sortent pas d'ici
    skills_dirs: list[Path]  # dossiers des skills, du plus général au plus précis
    confirm: Callable[[str], bool]  # pose une question [o/N] à l'utilisateur
    command_timeout: int = COMMAND_TIMEOUT
    # Commandes lancées sans confirmation (étape 14), modifiable avec /allow.
    allowed_commands: list[str] = field(default_factory=list)


# ─────────────────────────── Les outils ───────────────────────────


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


def edit_file(ctx: ToolContext, path: str, old_text: str, new_text: str) -> str:
    """Remplace un passage exact d'un fichier, ou crée un fichier si old_text est vide.

    Le modèle n'envoie que le passage modifié, pas tout le fichier : c'est
    beaucoup moins de contexte consommé, et le reste du fichier est intact.
    """
    target = safe_path(ctx.workdir, path)
    if old_text == "":
        if target.exists():
            return f"Erreur : {path} existe déjà. Pour le modifier, donne dans old_text le passage exact à remplacer."
        old, content = "", new_text
    else:
        if not target.is_file():
            return f"Erreur : fichier introuvable : {path}. Pour créer un fichier, laisse old_text vide."
        old = target.read_text(encoding="utf-8")
        count = old.count(old_text)
        if count == 0:
            return f"Erreur : old_text introuvable dans {path}. Relis le fichier avec read_file et copie le passage exactement."
        if count > 1:
            return f"Erreur : old_text apparaît {count} fois dans {path}. Ajoute des lignes autour pour qu'il soit unique."
        content = old.replace(old_text, new_text, 1)

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
    return f"Fichier {path} {'créé' if old_text == '' else 'modifié'}."


def run_command(ctx: ToolContext, command: str) -> str:
    """Lance une commande shell dans le dossier de travail, après confirmation."""
    # Les commandes de la liste autorisée passent sans question (étape 14).
    if not is_allowed_command(command, ctx.allowed_commands) and not ctx.confirm(f"Exécuter : {command}"):
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


def load_skill(ctx: ToolContext, name: str) -> str:
    """Renvoie le contenu d'une skill (fichier Markdown d'un dossier de skills)."""
    skills = find_skills(ctx.skills_dirs)
    # On vérifie le nom dans la liste : impossible de lire un autre fichier.
    if name not in skills:
        raise GuardError(f"skill inconnue '{name}'. Skills disponibles : {', '.join(skills) or 'aucune'}.")
    return skills[name].read_text(encoding="utf-8")


# ─────────────────────────── Skills ───────────────────────────


def read_skill_description(path: Path) -> str:
    """Lit la ligne `description:` de l'en-tête d'une skill.

    Une skill commence par un petit en-tête entre deux lignes "---" :
        ---
        description: Écrire des tests pytest pour du code Python.
        ---
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            key, _, value = line.partition(":")
            if key.strip() == "description":
                return value.strip()
    return "(pas de description)"


def find_skills(skills_dirs: list[Path]) -> dict[str, Path]:
    """Renvoie {nom de la skill: fichier} pour les fichiers .md de chaque dossier.

    Les dossiers sont lus dans l'ordre : une skill du projet (dernier dossier)
    remplace une skill globale du même nom.
    """
    skills = {}
    for skills_dir in skills_dirs:
        if skills_dir.is_dir():
            skills.update({p.stem: p for p in sorted(skills_dir.glob("*.md"))})
    return skills


def available_skills(skills_dirs: list[Path]) -> dict[str, str]:
    """Renvoie {nom de la skill: description}, pour le prompt système."""
    return {name: read_skill_description(path) for name, path in find_skills(skills_dirs).items()}


# ─────────────────────────── Le registre ───────────────────────────


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
    "edit_file": (
        edit_file,
        schema(
            "edit_file",
            "Modifie un fichier : remplace old_text (copié exactement depuis read_file, présent une seule fois) par new_text. "
            "Pour créer un nouveau fichier, laisse old_text vide.",
            {
                "path": PATH_PARAM,
                "old_text": {"type": "string", "description": "Passage exact à remplacer, ou '' pour créer le fichier."},
                "new_text": {"type": "string", "description": "Nouveau texte."},
            },
            ["path", "old_text", "new_text"],
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
    "load_skill": (
        load_skill,
        schema(
            "load_skill",
            "Charge les instructions d'une skill listée dans le prompt système.",
            {"name": {"type": "string", "description": "Nom exact de la skill, ex. 'corriger-un-bug'."}},
            ["name"],
        ),
    ),
}


def tool_schemas() -> list[dict]:
    """Les schémas de tous les outils, à envoyer au modèle."""
    return [tool_schema for _, tool_schema in TOOLS.values()]


def execute_tool(name: str, arguments, ctx: ToolContext) -> str:
    """Exécute un outil demandé par le modèle et renvoie toujours un texte.

    Aucune erreur ne doit faire planter l'agent : chaque problème est
    décrit dans le texte renvoyé, pour que le modèle puisse se corriger.
    """
    if name not in TOOLS:
        return f"Erreur : outil inconnu '{name}'. Outils valides : {', '.join(TOOLS)}."
    function, tool_schema = TOOLS[name]

    # Certains modèles renvoient les arguments sous forme de texte JSON.
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            return f"Erreur : les arguments de {name} ne sont pas du JSON valide : {arguments}"
    if not isinstance(arguments, dict):
        return f"Erreur : les arguments de {name} doivent être un objet JSON."

    parameters = tool_schema["function"]["parameters"]
    expected = ", ".join(parameters["properties"])
    missing = [p for p in parameters["required"] if p not in arguments]
    if missing:
        return f"Erreur : argument manquant pour {name} : {', '.join(missing)}. Paramètres attendus : {expected}."
    unknown = [p for p in arguments if p not in parameters["properties"]]
    if unknown:
        return f"Erreur : argument inconnu pour {name} : {', '.join(unknown)}. Paramètres attendus : {expected}."

    try:
        return function(ctx, **arguments)
    except GuardError as error:
        return f"Refusé : {error}"
    except Exception as error:  # toute autre exception Python
        return f"Erreur pendant {name} : {type(error).__name__}: {error}"