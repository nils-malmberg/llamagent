"""Sauvegarde des conversations, pour les reprendre plus tard (étape 15).

Chaque conversation est un fichier JSON dans .mini-agent/sessions/ du
projet. Il est réécrit après chaque demande : en cas d'arrêt brutal, on
perd au plus la demande en cours.
"""

import json
from datetime import datetime
from pathlib import Path

from mini_agent.config import PROJECT_DIR_NAME
from mini_agent.context import estimate_messages
from mini_agent.session import Session

def sessions_dir(workdir: Path) -> Path:
    return workdir / PROJECT_DIR_NAME / "sessions"


def save_session(session: Session) -> None:
    """Enregistre la conversation, sans le prompt système (reconstruit à la reprise)."""
    conversation = session.messages[1:]
    if not any(m["role"] == "user" for m in conversation):
        return  # conversation vide : rien à sauvegarder
    now = datetime.now()
    if session.session_id is None:
        session.session_id = now.strftime("%Y-%m-%d_%H-%M-%S")
    session.remember_title()
    data = {
        "id": session.session_id,
        "title": session.title,
        "updated": now.isoformat(timespec="seconds"),
        "model": session.config.model,
        "messages": conversation,
    }
    folder = sessions_dir(session.config.workdir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{session.session_id}.json"
    # On écrit dans un fichier temporaire, puis on le renomme : un Ctrl+C
    # pendant l'écriture ne laisse jamais un fichier à moitié écrit.
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    temporary.replace(path)


def list_sessions(workdir: Path) -> list[dict]:
    """Les conversations sauvegardées, de la plus récente à la plus ancienne."""
    folder = sessions_dir(workdir)
    if not folder.is_dir():
        return []
    sessions = []
    for path in folder.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue  # fichier abîmé : on l'ignore plutôt que de planter
        data["path"] = path  # pour /delete : on supprime ce fichier-là, rien d'autre
        sessions.append(data)
    return sorted(sessions, key=lambda data: data.get("updated", ""), reverse=True)


def find_session(workdir: Path, ref: str) -> dict | None:
    """ref : numéro affiché par /sessions (1 = la plus récente) ou identifiant."""
    sessions = list_sessions(workdir)
    if ref.isdigit() and 1 <= int(ref) <= len(sessions):
        return sessions[int(ref) - 1]
    return next((data for data in sessions if data.get("id") == ref), None)


def resume_session(session: Session, data: dict) -> None:
    """Remplace la conversation en cours par une conversation sauvegardée."""
    session.reset()  # prompt système relu : AGENTS.md et skills à jour
    session.messages += data["messages"]
    session.session_id = data["id"]
    session.title = data.get("title", "")
    # Ollama ne mesurera le contexte qu'au prochain appel : en attendant, une estimation.
    session.context_tokens = estimate_messages(session.messages)
    session.context_estimated = True


def delete_session(data: dict) -> None:
    data["path"].unlink(missing_ok=True)