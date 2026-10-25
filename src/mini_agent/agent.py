"""La boucle agentique (version de l'étape 5)."""

from typing import Callable

from mini_agent.config import MAX_TOURS
from mini_agent.tools import ToolContext, execute_tool, tool_schemas

# Une fonction qui reçoit (messages, schémas des outils) et renvoie le message
# de l'assistant. En vrai : llm.chat. Dans les tests : un faux modèle.
ChatFunction = Callable[[list[dict], list[dict]], dict]


def run_turn(chat: ChatFunction, messages: list[dict], ctx: ToolContext, max_tours: int = MAX_TOURS) -> str:
    """Version simple de l'étape 5 (les étapes 6 et 8 l'enrichissent)."""
    for tour in range(1, max_tours + 1):
        reply = chat(messages, tool_schemas())
        messages.append(reply)

        tool_calls = reply.get("tool_calls") or []
        if not tool_calls:
            return reply.get("content", "")

        for call in tool_calls:
            name = call["function"]["name"]
            arguments = call["function"].get("arguments", {})
            result = execute_tool(name, arguments, ctx)
            messages.append({"role": "tool", "tool_name": name, "content": result})

    return f"Arrêt : limite de {max_tours} tours atteinte sans réponse finale."