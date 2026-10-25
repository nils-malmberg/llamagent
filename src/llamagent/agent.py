"""La boucle agentique : le cœur de llamagent.

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

from llamagent import ui
from llamagent.config import MAX_OUTPUT_CHARS, MAX_TOURS
from llamagent.guards import is_allowed_command, truncate
from llamagent.tools import TOOLS, ToolContext, execute_tool, tool_schemas

# Une fonction qui reçoit (messages, schémas des outils) et renvoie le message
# de l'assistant. En vrai : llm.chat. Dans les tests : un faux modèle.
ChatFunction = Callable[[list[dict], list[dict]], dict]


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


def describe_harness(name: str, arguments, ctx: ToolContext, repeated: bool) -> str:
    """Ce que le harness fait de la demande du modèle, en une phrase (étape 17).

    Seulement pour l'affichage : on rend visible le rôle du harness entre
    le modèle, qui demande, et l'outil, qui exécute.
    """
    if repeated:
        return "appel identique au précédent : pas exécuté, le modèle est prévenu"
    if name not in TOOLS:
        return "outil inconnu : l'erreur est renvoyée au modèle"
    if name == "edit_file":
        return "vérifie le chemin, montre le diff et demande ta confirmation"
    if name == "run_command":
        command = arguments.get("command", "") if isinstance(arguments, dict) else ""
        if is_allowed_command(command, ctx.allowed_commands):
            return "commande autorisée : lancée sans confirmation"
        return "demande ta confirmation avant de lancer la commande"
    if name == "load_skill":
        return "vérifie que la skill existe et la charge"
    return f"vérifie le chemin et exécute {name}"


def run_turn(chat: ChatFunction, messages: list[dict], ctx: ToolContext, max_tours: int = MAX_TOURS) -> str:
    """Traite le dernier message utilisateur et renvoie la réponse finale.

    `messages` est modifiée sur place : on y ajoute les messages de
    l'assistant et les résultats des outils, pour garder tout l'historique.
    L'affichage montre chaque tour : le modèle demande, le harness décide,
    l'outil répond.
    """
    previous_call = None
    for tour in range(1, max_tours + 1):
        print(ui.tour_header(tour))
        reply = chat(messages, tool_schemas())
        # 1) On garde le message de l'assistant TEL QUEL, avec ses tool_calls :
        #    au prochain appel, le modèle doit voir ce qu'il a demandé.
        messages.append(reply)

        tool_calls = reply.get("tool_calls") or []
        if not tool_calls:
            print(ui.role_line("modèle", "répond sans demander d'outil : fin de la boucle"))
            print(ui.answer_header(tour))
            return reply.get("content", "")

        for call in tool_calls:
            name = call["function"]["name"]
            arguments = call["function"].get("arguments", {})
            print(ui.model_asks(name, arguments))

            # Détection de boucle : le même appel deux fois de suite ne
            # donnera pas un résultat différent, on le signale au modèle.
            signature = (name, json.dumps(arguments, sort_keys=True, ensure_ascii=False))
            repeated = signature == previous_call
            print(ui.role_line("harness", describe_harness(name, arguments, ctx, repeated)))
            if repeated:
                result = (
                    f"Erreur : tu viens déjà d'appeler {name} avec exactement ces arguments. "
                    "Le résultat sera le même : change d'approche ou donne ta réponse finale."
                )
            else:
                result = execute_tool(name, arguments, ctx)
            previous_call = signature

            shortened = truncate(result, MAX_OUTPUT_CHARS)
            print(ui.tool_result(shortened, truncated=len(shortened) < len(result)))
            # 2) Puis le résultat de l'outil, avec le rôle "tool".
            messages.append({"role": "tool", "tool_name": name, "content": shortened})

    print(ui.role_line("harness", f"limite de {max_tours} tours atteinte : la boucle s'arrête", ui.RED))
    return f"Arrêt : limite de {max_tours} tours atteinte sans réponse finale."