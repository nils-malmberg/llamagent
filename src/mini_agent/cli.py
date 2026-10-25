"""Point d'entrée de la ligne de commande : `uv run mini-agent`.

    uv run mini-agent                      # mode conversation
    uv run mini-agent "corrige le bug..."  # une seule demande, puis on quitte

C'est ici qu'on assemble le harness : configuration, prompt système,
outils, garde-fous, puis la boucle agentique.
"""

import os
import sys

import requests

from mini_agent import llm
from mini_agent.agent import build_system_prompt, run_turn
from mini_agent.config import PROMPTS_DIR, SKILLS_DIR, load_config
from mini_agent.guards import ask_confirmation
from mini_agent.tools import ToolContext, available_skills


def ask_agent(chat, messages: list[dict], ctx: ToolContext, text: str) -> None:
    """Ajoute une demande à la conversation, lance la boucle, affiche la réponse."""
    messages.append({"role": "user", "content": text})
    try:
        answer = run_turn(chat, messages, ctx)
    except requests.RequestException as error:
        print(f"Erreur de communication avec Ollama : {error}")
        return
    print(f"\nagent > {answer}")


def main() -> None:
    if os.name == "nt":
        os.system("")  # active les couleurs ANSI dans les anciennes consoles Windows

    config = load_config()
    template = (PROMPTS_DIR / "AGENT.md").read_text(encoding="utf-8")
    skills = available_skills(SKILLS_DIR)
    ctx = ToolContext(workdir=config.workdir, skills_dir=SKILLS_DIR, confirm=ask_confirmation)

    # La conversation commence toujours par le prompt système.
    messages = [{"role": "system", "content": build_system_prompt(template, config.workdir, skills)}]

    def chat(msgs: list[dict], tools: list[dict]) -> dict:
        return llm.chat(config, msgs, tools)

    print(f"mini-agent — modèle {config.model} sur {config.ollama_url}")
    print(f"Dossier de travail : {config.workdir}")

    try:
        # Mode « une seule demande » : la demande est passée en argument.
        if len(sys.argv) > 1:
            ask_agent(chat, messages, ctx, " ".join(sys.argv[1:]))
            return

        print("Tape ta demande (/quit pour sortir).")
        while True:
            text = input("\nvous > ").strip()
            if text in ("/quit", "/exit"):
                break
            if text:
                ask_agent(chat, messages, ctx, text)
    except (KeyboardInterrupt, EOFError):
        print("\nAu revoir.")


if __name__ == "__main__":
    main()