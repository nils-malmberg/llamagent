"""Appel au LLM via l'API native d'Ollama.

C'est le seul module qui parle au réseau. Le reste du projet ne manipule
que des listes de messages (des dictionnaires Python).
"""

import requests

from llamagent.config import REQUEST_TIMEOUT, Config


def chat_full(config: Config, messages: list[dict], tools: list[dict] | None = None) -> dict:
    """Envoie la conversation à /api/chat et renvoie la réponse JSON complète.

    En plus du message, la réponse contient des compteurs utiles, comme
    prompt_eval_count (tokens lus) et eval_count (tokens générés).
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
    return response.json()


def chat(config: Config, messages: list[dict], tools: list[dict] | None = None) -> dict:
    """Envoie la conversation (et la liste des outils) à Ollama.

    Renvoie le message de l'assistant, par exemple :
        {"role": "assistant", "content": "Bonjour !"}
    ou, si le modèle veut utiliser un outil :
        {"role": "assistant", "content": "",
         "tool_calls": [{"function": {"name": "read_file",
                                      "arguments": {"path": "main.py"}}}]}
    """
    return chat_full(config, messages, tools)["message"]


def list_models(config: Config) -> list[str]:
    """Noms des modèles installés sur le serveur Ollama (GET /api/tags)."""
    response = requests.get(f"{config.ollama_url}/api/tags", timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return sorted(model["name"] for model in response.json()["models"])