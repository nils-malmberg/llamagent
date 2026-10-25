"""Point d'entrée de la ligne de commande : `llamagent`.

    llamagent                          # mode conversation dans le dossier courant
    llamagent "corrige le bug..."      # une seule demande, puis on quitte
    llamagent -m qwen3.5:9b -t 0.5     # options : voir llamagent --help

C'est ici qu'on assemble le harness : configuration, session (prompt
système, outils, garde-fous), commandes /..., puis la boucle agentique.
Tout l'affichage passe par ui.py (étape 17).
"""

import argparse
import os
from importlib.metadata import version

import requests

from llamagent import ui
from llamagent.commands import execute_command
from llamagent.config import PROJECT_DIR_NAME, load_config
from llamagent.context import compact, needs_compaction
from llamagent.history import find_session, resume_session, save_session
from llamagent.session import Session, create_session, find_mentions, load_project_instructions
from llamagent.tools import available_skills


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="llamagent", description="Un agent de code minimal autour d'Ollama.")
    parser.add_argument("demande", nargs="*", help="demande à traiter avant de quitter (sinon : mode conversation)")
    parser.add_argument("-m", "--model", help="modèle Ollama, ex. qwen3.5:4b")
    parser.add_argument("-t", "--temperature", type=float, help="température, ex. 0.2")
    parser.add_argument("--num-ctx", type=int, help="taille du contexte en tokens, ex. 8192")
    parser.add_argument("--url", help="adresse du serveur Ollama")
    parser.add_argument("-c", "--continue", dest="resume", action="store_true", help="reprendre la dernière conversation du projet")
    parser.add_argument("--version", action="version", version=f"llamagent {version('llamagent')}")
    return parser.parse_args(argv)


def context_status(session: Session) -> str:
    """La jauge de contexte affichée sous chaque réponse."""
    c = session.config
    return ui.context_gauge(c.model, session.context_tokens, c.num_ctx, session.context_estimated)


def handle_request(session: Session, text: str) -> None:
    """Envoie une demande à l'agent et affiche sa réponse."""
    for path in find_mentions(text):
        print(ui.info(f"@{path} joint au message"))
    try:
        answer = session.ask(text)
    except requests.RequestException as error:
        print(ui.error(f"Erreur de communication avec Ollama : {error}"))
        return
    print(ui.answer(answer))
    print("\n" + context_status(session))
    # Étape 16 : entre deux demandes, on compacte si le contexte est presque plein.
    if needs_compaction(session):
        print(ui.warning("Contexte presque plein : compactage automatique de la conversation..."))
        try:
            compact(session)
            print(context_status(session))
        except requests.RequestException as error:
            print(ui.error(f"Compactage impossible : {error}"))
    # Étape 15 : la conversation est sauvegardée après chaque demande.
    save_session(session)


def project_summary(session: Session) -> str:
    """Une ligne qui résume ce que le projet apporte : AGENTS.md, skills, réglages."""
    workdir = session.config.workdir
    has_instructions = bool(load_project_instructions(workdir))
    parts = ["AGENTS.md"] if has_instructions else []
    parts.append(f"{len(available_skills(session.ctx.skills_dirs))} skills")
    if (workdir / PROJECT_DIR_NAME / "config.toml").is_file():
        parts.append("config.toml")
    if not has_instructions:
        parts.append("/init pour préparer le projet")
    return ui.symbol(" · ", " - ").join(parts)


def main() -> None:
    if os.name == "nt":
        os.system("")  # active les codes ANSI (couleurs) dans les consoles Windows

    args = parse_args()
    config = load_config({"model": args.model, "temperature": args.temperature, "num_ctx": args.num_ctx, "url": args.url})
    session = create_session(config, confirm=ui.confirm)
    session.waiting = ui.thinking  # animation pendant l'attente du modèle

    rows = [("modèle", config.model), ("serveur", config.ollama_url), ("dossier", str(config.workdir)), ("projet", project_summary(session))]
    if args.resume:
        data = find_session(config.workdir, "1")
        if data is None:
            rows.append(("reprise", "aucune conversation sauvegardée : nouvelle conversation"))
        else:
            resume_session(session, data)
            rows.append(("reprise", f"{data.get('title', '')} ({len(data['messages'])} messages)"))
    print(ui.banner(rows))

    try:
        # Mode « une seule demande » : la demande est passée en argument.
        if args.demande:
            handle_request(session, " ".join(args.demande))
            return

        while True:
            text = input(ui.prompt()).strip()
            if text in ("/quit", "/exit"):
                break
            if text.startswith("/"):
                print(ui.indent(execute_command(session, text)))
            elif text:
                handle_request(session, text)
    except (KeyboardInterrupt, EOFError):
        print("\n" + ui.style("  Au revoir.", ui.GREY))


if __name__ == "__main__":
    main()