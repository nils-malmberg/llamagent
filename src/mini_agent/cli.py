"""Point d'entrée de la ligne de commande : `mini-agent`.

    mini-agent                          # mode conversation dans le dossier courant
    mini-agent "corrige le bug..."      # une seule demande, puis on quitte
    mini-agent -m qwen3.5:9b -t 0.5     # options : voir mini-agent --help

C'est ici qu'on assemble le harness : configuration, session (prompt
système, outils, garde-fous), commandes /..., puis la boucle agentique.
"""

import argparse
import os

import requests

from mini_agent.agent import GREY, RED, YELLOW, color
from mini_agent.commands import execute_command
from mini_agent.config import load_config
from mini_agent.context import compact, needs_compaction
from mini_agent.guards import ask_confirmation
from mini_agent.history import find_session, resume_session, save_session
from mini_agent.session import Session, create_session, find_mentions, load_project_instructions


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="mini-agent", description="Un agent de code minimal autour d'Ollama.")
    parser.add_argument("demande", nargs="*", help="demande à traiter avant de quitter (sinon : mode conversation)")
    parser.add_argument("-m", "--model", help="modèle Ollama, ex. qwen3.5:4b")
    parser.add_argument("-t", "--temperature", type=float, help="température, ex. 0.2")
    parser.add_argument("--num-ctx", type=int, help="taille du contexte en tokens, ex. 8192")
    parser.add_argument("--url", help="adresse du serveur Ollama")
    parser.add_argument("-c", "--continue", dest="resume", action="store_true", help="reprendre la dernière conversation du projet")
    return parser.parse_args(argv)


def context_status(session: Session) -> str:
    """Une ligne qui montre la place occupée dans le contexte du modèle."""
    used, size = session.context_tokens, session.config.num_ctx
    text = f"[contexte : {'≈ ' if session.context_estimated else ''}{used} / {size} tokens]"
    if used >= size:
        return color(text + " plein : Ollama a coupé le début de la conversation", RED)
    if used >= 0.75 * size:
        return color(text + " presque plein", YELLOW)
    return color(text, GREY)


def handle_request(session: Session, text: str) -> None:
    """Envoie une demande à l'agent et affiche sa réponse."""
    for path in find_mentions(text):
        print(color(f"   + fichier joint : {path}", GREY))
    try:
        answer = session.ask(text)
    except requests.RequestException as error:
        print(f"Erreur de communication avec Ollama : {error}")
        return
    print(f"\nagent > {answer}")
    print(context_status(session))
    # Étape 16 : entre deux demandes, on compacte si le contexte est presque plein.
    if needs_compaction(session):
        print(color("Contexte presque plein : compactage automatique de la conversation...", YELLOW))
        try:
            compact(session)
            print(context_status(session))
        except requests.RequestException as error:
            print(f"Compactage impossible : {error}")
    # Étape 15 : la conversation est sauvegardée après chaque demande.
    save_session(session)


def main() -> None:
    if os.name == "nt":
        os.system("")  # active les couleurs ANSI dans les anciennes consoles Windows

    args = parse_args()
    config = load_config({"model": args.model, "temperature": args.temperature, "num_ctx": args.num_ctx, "url": args.url})
    session = create_session(config, confirm=ask_confirmation)

    print(f"mini-agent — modèle {config.model} sur {config.ollama_url}")
    print(f"Dossier de travail : {config.workdir}")
    if load_project_instructions(config.workdir):
        print("Instructions du projet : AGENTS.md")
    if args.resume:
        data = find_session(config.workdir, "1")
        if data is None:
            print("Aucune conversation à reprendre dans ce projet : nouvelle conversation.")
        else:
            resume_session(session, data)
            print(f"Conversation reprise : {data.get('title', '')} ({len(data['messages'])} messages)")

    try:
        # Mode « une seule demande » : la demande est passée en argument.
        if args.demande:
            handle_request(session, " ".join(args.demande))
            return

        print("Tape ta demande, ou /help pour les commandes.")
        while True:
            text = input("\nvous > ").strip()
            if text in ("/quit", "/exit"):
                break
            if text.startswith("/"):
                print(execute_command(session, text))
            elif text:
                handle_request(session, text)
    except (KeyboardInterrupt, EOFError):
        print("\nAu revoir.")


if __name__ == "__main__":
    main()