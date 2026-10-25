"""Appel au LLM via l'API native d'Ollama (/api/chat).

C'est le seul module qui parle au réseau. Le reste du projet ne manipule
que des listes de messages (des dictionnaires Python).
"""

import requests

from mini_agent.config import REQUEST_TIMEOUT, Config


def chat(config: Config, messages: list[dict], tools: list[dict] | None = None) -> dict:
    """Envoie la conversation (et la liste des outils) à Ollama.

    Renvoie le message de l'assistant, par exemple :
        {"role": "assistant", "content": "Bonjour !"}
    ou, si le modèle veut utiliser un outil :
        {"role": "assistant", "content": "",
         "tool_calls": [{"function": {"name": "read_file",
                                      "arguments": {"path": "main.py"}}}]}
    """
    payload = {
        "model": config.model,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": config.options(),
    }
    if tools:
        payload["tools"] = tools
    response = requests.post(config.chat_url, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()["message"]