"""La boucle agentique : le cœur de mini-agent.

    tant que le modèle demande des outils :
        exécuter chaque outil demandé
        ajouter le résultat à la conversation
        rappeler le modèle
    sinon : renvoyer sa réponse finale

La boucle ne connaît aucun outil en particulier : elle passe par le registre
de tools.py. Elle ne parle pas non plus directement à Ollama : on lui donne
une fonction `chat`, ce qui permet de la tester avec un faux modèle.
"""

import json
import os
import platform
from pathlib import Path
from typing import Callable

from mini_agent.config import MAX_OUTPUT_CHARS, MAX_TOURS
from mini_agent.guards import truncate
from mini_agent.tools import ToolContext, execute_tool, tool_schemas

# Une fonction qui reçoit (messages, schémas des outils) et renvoie le message
# de l'assistant. En vrai : llm.chat. Dans les tests : un faux modèle.
ChatFunction = Callable[[list[dict], list[dict]], dict]


# ─────────────────────────── Affichage ───────────────────────────

# Codes couleur ANSI. NO_COLOR=1 les désactive (convention https://no-color.org).
USE_COLOR = "NO_COLOR" not in os.environ
GREY, RED, YELLOW, CYAN = "90", "31", "33", "36"


def color(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text


def log_tool_call(tour: int, name: str, arguments) -> None:
    args = json.dumps(arguments, ensure_ascii=False)
    if len(args) > 120:
        args = args[:120] + "…"
    print(color(f"[tour {tour}] ", GREY) + color(f"{name}", CYAN) + color(f" {args}", GREY))


def log_tool_result(result: str) -> None:
    is_error = result.startswith(("Erreur", "Refusé"))
    lines = result.splitlines() or [""]
    preview = lines[0][:100] + (f"  (+{len(lines) - 1} lignes)" if len(lines) > 1 else "")
    print(color(f"   → {preview}", RED if is_error else GREY))


# ─────────────────────────── Prompt système ───────────────────────────


def build_system_prompt(template: str, workdir: Path, skills: dict[str, str], project_instructions: str = "") -> str:
    """Remplit le modèle de prompt (prompts/AGENT.md) avec l'environnement réel.

    Si le projet a un fichier AGENTS.md (étape 9), son contenu est ajouté à la fin.
    """
    shell = "cmd.exe" if os.name == "nt" else "/bin/sh"
    skills_text = "\n".join(f"- {name} : {description}" for name, description in skills.items())
    # str.replace plutôt que str.format : le Markdown peut contenir des { }.
    prompt = (
        template.replace("{os}", platform.system())
        .replace("{shell}", shell)
        .replace("{workdir}", str(workdir))
        .replace("{skills}", skills_text or "(aucune)")
    )
    if project_instructions:
        prompt += f"\n\n## Instructions du projet (AGENTS.md)\n{project_instructions}"
    return prompt


# ─────────────────────────── La boucle ───────────────────────────


def run_turn(chat: ChatFunction, messages: list[dict], ctx: ToolContext, max_tours: int = MAX_TOURS) -> str:
    """Traite le dernier message utilisateur et renvoie la réponse finale.

    `messages` est modifiée sur place : on y ajoute les messages de
    l'assistant et les résultats des outils, pour garder tout l'historique.
    """
    previous_call = None
    for tour in range(1, max_tours + 1):
        reply = chat(messages, tool_schemas())
        # 1) On garde le message de l'assistant TEL QUEL, avec ses tool_calls :
        #    au prochain appel, le modèle doit voir ce qu'il a demandé.
        messages.append(reply)

        tool_calls = reply.get("tool_calls") or []
        if not tool_calls:
            return reply.get("content", "")

        for call in tool_calls:
            name = call["function"]["name"]
            arguments = call["function"].get("arguments", {})
            log_tool_call(tour, name, arguments)

            # Détection de boucle : le même appel deux fois de suite ne
            # donnera pas un résultat différent, on le signale au modèle.
            signature = (name, json.dumps(arguments, sort_keys=True, ensure_ascii=False))
            if signature == previous_call:
                result = (
                    f"Erreur : tu viens déjà d'appeler {name} avec exactement ces arguments. "
                    "Le résultat sera le même : change d'approche ou donne ta réponse finale."
                )
            else:
                result = execute_tool(name, arguments, ctx)
            previous_call = signature

            result = truncate(result, MAX_OUTPUT_CHARS)
            log_tool_result(result)
            # 2) Puis le résultat de l'outil, avec le rôle "tool".
            messages.append({"role": "tool", "tool_name": name, "content": result})

    return f"Arrêt : limite de {max_tours} tours atteinte sans réponse finale."