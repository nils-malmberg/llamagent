"""Étape 3 — Premier outil (sans l'exécuter).

On décrit une fonction Python au modèle grâce à un schéma JSON envoyé dans
le champ `tools`. Le modèle ne peut pas l'exécuter : il peut seulement
répondre « je voudrais appeler read_file avec path=... ». C'est un tool call.
Ici, on se contente d'afficher cette demande brute.

Lancer (depuis la racine du projet) :
    uv run python steps/step3_tool.py
    uv run python steps/step3_tool.py "Que contient README.md ?"
"""

import json
import os
import sys
from pathlib import Path

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://192.168.1.76:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:4b")


def read_file(path: str) -> str:
    """La vraie fonction Python. À cette étape, personne ne l'appelle encore."""
    return Path(path).read_text(encoding="utf-8")


# Ce que le modèle voit de l'outil : un nom, une description, des paramètres.
READ_FILE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Lit un fichier texte et renvoie tout son contenu.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Chemin du fichier, ex. 'pyproject.toml'."}
            },
            "required": ["path"],
        },
    },
}


def chat(messages: list[dict], tools: list[dict]) -> dict:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "tools": tools,  # la liste des outils que le modèle peut demander
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "num_ctx": 8192},
    }
    response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
    response.raise_for_status()
    return response.json()["message"]


def main() -> None:
    question = " ".join(sys.argv[1:]) or "Que contient le fichier pyproject.toml ?"
    message = chat([{"role": "user", "content": question}], [READ_FILE_SCHEMA])

    print("Message brut renvoyé par le modèle :")
    print(json.dumps(message, indent=2, ensure_ascii=False))

    tool_calls = message.get("tool_calls") or []
    if not tool_calls:
        print("\nPas d'appel d'outil : le modèle a répondu directement.")
        return
    for call in tool_calls:
        function = call["function"]
        print(f"\nLe modèle demande : {function['name']}({function['arguments']})")
    print("(À cette étape, on n'exécute rien : le modèle ne peut pas agir seul.)")


if __name__ == "__main__":
    main()