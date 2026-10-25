"""Les commandes /... tapées par l'utilisateur (et non par le modèle).

Même principe que le registre d'outils : un dictionnaire
nom -> (fonction, aide). Ajouter une commande ne touche ni à la boucle
ni à cli.py. Chaque fonction reçoit la session et le texte tapé après la
commande, et renvoie le texte à afficher.
"""

from typing import Callable

import requests

from llamagent import llm
from llamagent.context import compact, context_report
from llamagent.config import PROJECT_DIR_NAME, PROJECT_INSTRUCTIONS
from llamagent.guards import SHELL_OPERATORS, GuardError
from llamagent.history import delete_session, find_session, list_sessions, resume_session, save_session
from llamagent.session import Session
from llamagent.tools import available_skills, load_skill


def cmd_help(session: Session, arg: str) -> str:
    lines = [f"{name:<9} {description}" for name, (_, description) in COMMANDS.items()]
    return "\n".join(lines + [f"{'/quit':<9} quitter", "", "@chemin dans une demande : joint le contenu du fichier."])


# Fichiers créés par /init dans le projet : chemin relatif -> contenu.
INIT_FILES = {
    PROJECT_INSTRUCTIONS: """# Instructions du projet

- But du projet : ...
- Lancer le projet : ...
- Lancer les tests : python -m pytest -q
- Conventions de code : ...
- Fichiers ou dossiers à ne jamais modifier : ...
""",
    f"{PROJECT_DIR_NAME}/config.toml": """# Réglages de llamagent pour ce projet (ils remplacent ~/.llamagent/config.toml).
# Retire le # devant une ligne pour l'activer.
# model = "qwen3.5:4b"
# temperature = 0.2
# num_ctx = 8192
# allowed_commands = ["python -m pytest", "git status", "git diff"]
""",
    # Les conversations sauvegardées contiennent le contenu des fichiers lus :
    # elles ne doivent pas finir dans le dépôt git du projet.
    f"{PROJECT_DIR_NAME}/.gitignore": "sessions/\n",
    f"{PROJECT_DIR_NAME}/skills/LISEZMOI.txt": """Skills de ce projet : un fichier .md par skill, par exemple deployer.md.

Format :

---
description: Une ligne qui dit quand utiliser cette skill.
---
# Titre

1. Première étape de la méthode.
2. ...

Le prompt système ne contient que le nom et la description de chaque skill.
Le modèle charge le contenu avec load_skill quand la demande correspond.
Une skill de ce dossier remplace une skill globale du même nom.
Ce fichier .txt n'est pas une skill : il est ignoré.
""",
}


def cmd_init(session: Session, arg: str) -> str:
    workdir = session.config.workdir
    # On ne remplace jamais un fichier existant : seuls les manquants sont créés.
    missing = [rel for rel in INIT_FILES if not (workdir / rel).exists()]
    if not missing:
        return "Ce projet est déjà initialisé : rien à créer."
    listing = "\n".join(f"  {rel}" for rel in missing)
    if not session.ctx.confirm(f"Fichiers à créer :\n{listing}\nLes créer dans {workdir} ?"):
        return "Rien n'a été créé."
    for rel in missing:
        path = workdir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(INIT_FILES[rel], encoding="utf-8")
    # Le prompt système est reconstruit pour tenir compte d'AGENTS.md,
    # sans effacer la conversation en cours.
    session.messages[0] = {"role": "system", "content": session.system_prompt()}
    return f"Créé :\n{listing}\nComplète AGENTS.md, puis ajoute tes skills dans {PROJECT_DIR_NAME}/skills/."


def cmd_config(session: Session, arg: str) -> str:
    c = session.config
    return (
        f"modèle         : {c.model}\n"
        f"serveur        : {c.ollama_url}\n"
        f"température    : {c.temperature}\n"
        f"contexte       : {c.num_ctx} tokens\n"
        f"dossier        : {c.workdir}\n"
        f"sans confirmer : {', '.join(session.ctx.allowed_commands) or 'aucune commande'}"
    )


def cmd_models(session: Session, arg: str) -> str:
    models = llm.list_models(session.config)
    return "\n".join(("* " if name == session.config.model else "  ") + name for name in models) or "(aucun modèle)"


def cmd_model(session: Session, arg: str) -> str:
    if not arg:
        return f"Modèle actuel : {session.config.model}"
    models = llm.list_models(session.config)
    # « qwen3.5 » désigne « qwen3.5:latest » pour Ollama.
    name = arg if arg in models else f"{arg}:latest"
    if name not in models:
        return f"Modèle inconnu : {arg}. Tape /models pour voir les modèles installés."
    session.update(model=name)
    return f"Modèle : {name} (la conversation continue avec ce modèle)"


def cmd_temp(session: Session, arg: str) -> str:
    if not arg:
        return f"Température actuelle : {session.config.temperature}"
    try:
        value = float(arg)
    except ValueError:
        return "Usage : /temp 0.2"
    if not 0 <= value <= 2:
        return "La température doit être comprise entre 0 et 2."
    session.update(temperature=value)
    return f"Température : {value}"


def cmd_ctx(session: Session, arg: str) -> str:
    if not arg:
        return f"Contexte : {session.config.num_ctx} tokens"
    try:
        value = int(arg)
    except ValueError:
        return "Usage : /ctx 8192"
    if not 2048 <= value <= 131072:
        return "Le contexte doit être compris entre 2048 et 131072 tokens."
    session.update(num_ctx=value)
    return f"Contexte : {value} tokens (plus de contexte = plus de VRAM utilisée)"


def cmd_skills(session: Session, arg: str) -> str:
    skills = available_skills(session.ctx.skills_dirs)
    return "\n".join(f"{name} : {description}" for name, description in skills.items()) or "(aucune skill)"


def cmd_skill(session: Session, arg: str) -> str:
    if not arg:
        return "Usage : /skill nom (voir /skills)"
    try:
        content = load_skill(session.ctx, arg)
    except GuardError as error:
        return str(error)
    # Ajoutée à la conversation : le modèle la verra dès la prochaine demande.
    session.messages.append({"role": "user", "content": f"Pour la suite, suis les instructions de la skill « {arg} » :\n\n{content}"})
    return f"Skill {arg} chargée dans la conversation."


def cmd_clear(session: Session, arg: str) -> str:
    session.reset()
    return "Conversation effacée. Prompt système, skills et AGENTS.md relus."


def cmd_sessions(session: Session, arg: str) -> str:
    sessions = list_sessions(session.config.workdir)
    if not sessions:
        return "Aucune conversation sauvegardée dans ce projet."
    lines = []
    for number, data in enumerate(sessions, start=1):
        current = "*" if data["id"] == session.session_id else " "
        date = data.get("updated", "?").replace("T", " ")[:16]
        lines.append(f"{current}{number:>3}. {date}  {len(data.get('messages', [])):>3} messages  {data.get('title', '')}")
    return "\n".join(lines + ["", "/resume <numéro> pour reprendre, /delete <numéro> pour supprimer."])


def cmd_resume(session: Session, arg: str) -> str:
    # Sans argument : la conversation la plus récente.
    data = find_session(session.config.workdir, arg or "1")
    if data is None:
        return f"Conversation introuvable : {arg}. Tape /sessions pour la liste."
    resume_session(session, data)
    return f"Conversation reprise : {data.get('title', '')} ({len(data['messages'])} messages)."


def cmd_delete(session: Session, arg: str) -> str:
    if not arg:
        return "Usage : /delete <numéro> (voir /sessions)"
    data = find_session(session.config.workdir, arg)
    if data is None:
        return f"Conversation introuvable : {arg}. Tape /sessions pour la liste."
    if not session.ctx.confirm(f"Supprimer la conversation « {data.get('title', '')} » ?"):
        return "Rien n'a été supprimé."
    delete_session(data)
    if data["id"] == session.session_id:
        session.session_id = None  # la conversation en cours sera sauvegardée dans un nouveau fichier
    return f"Conversation supprimée : {data.get('title', '')}"


def cmd_context(session: Session, arg: str) -> str:
    return context_report(session)


def cmd_compact(session: Session, arg: str) -> str:
    if len(session.messages) <= 1:
        return "Rien à compacter : la conversation est vide."
    summary = compact(session)
    save_session(session)  # le fichier sauvegardé contient désormais le résumé
    return f"Conversation compactée. Le modèle repart de ce résumé :\n\n{summary}"


def cmd_allow(session: Session, arg: str) -> str:
    allowed = session.ctx.allowed_commands
    if not arg:
        return "Commandes lancées sans confirmation : " + (", ".join(allowed) or "aucune")
    if any(operator in arg for operator in SHELL_OPERATORS):
        return "Refusé : une commande autorisée ne doit contenir aucun opérateur shell (& | ; > < ...)."
    allowed.append(arg)
    return f"« {arg} » sera lancée sans confirmation jusqu'à la fin de la session."


# nom de la commande -> (fonction, aide affichée par /help)
COMMANDS: dict[str, tuple[Callable[[Session, str], str], str]] = {
    "/help": (cmd_help, "liste des commandes"),
    "/init": (cmd_init, "préparer le projet : AGENTS.md et dossier .llamagent/"),
    "/config": (cmd_config, "réglages actuels"),
    "/models": (cmd_models, "modèles installés sur le serveur Ollama"),
    "/model": (cmd_model, "changer de modèle : /model qwen3.5:4b"),
    "/temp": (cmd_temp, "changer la température : /temp 0.5"),
    "/ctx": (cmd_ctx, "changer la taille du contexte : /ctx 16384"),
    "/skills": (cmd_skills, "skills disponibles"),
    "/skill": (cmd_skill, "charger une skill : /skill corriger-un-bug"),
    "/clear": (cmd_clear, "effacer la conversation"),
    "/context": (cmd_context, "ce qui occupe le contexte"),
    "/compact": (cmd_compact, "résumer la conversation pour libérer du contexte"),
    "/sessions": (cmd_sessions, "conversations sauvegardées dans ce projet"),
    "/resume": (cmd_resume, "reprendre une conversation : /resume 2 (sans numéro : la dernière)"),
    "/delete": (cmd_delete, "supprimer une conversation : /delete 2"),
    "/allow": (cmd_allow, "lancer une commande sans confirmation : /allow python -m pytest"),
}


def execute_command(session: Session, line: str) -> str:
    """Exécute une ligne comme « /temp 0.5 » et renvoie le texte à afficher."""
    name, _, arg = line.strip().partition(" ")
    if name not in COMMANDS:
        return f"Commande inconnue : {name}. Tape /help."
    function, _ = COMMANDS[name]
    try:
        return function(session, arg.strip())
    except requests.RequestException as error:
        return f"Erreur de communication avec Ollama : {error}"