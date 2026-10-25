"""Étape 4 — La boucle agentique.

Cette fois, on exécute les outils demandés et on renvoie leur résultat :
  1. on appelle le modèle avec la conversation et les outils ;
  2. s'il demande des outils : on ajoute SON message à la conversation,
     on exécute chaque outil, on ajoute chaque résultat (rôle "tool"),
     et on recommence en 1 ;
  3. sinon, sa réponse est la réponse finale.

Lancer (depuis la racine du projet) :
    uv run python steps/step4_loop.py
    uv run python steps/step4_loop.py "Lis le pyproject.toml et donne les dépendances."
"""

import os
import sys
from pathlib import Path

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://192.168.1.76:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:4b")
MAX_TOURS = 10  # garde-fou minimal contre une boucle infinie (voir étape 6)


def read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


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
        "tools": tools,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "num_ctx": 8192},
    }
    response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
    response.raise_for_status()
    return response.json()["message"]


def run_tool(name: str, arguments: dict) -> str:
    """Exécute l'outil demandé. Une erreur devient un texte pour le modèle."""
    if name != "read_file":
        return f"Erreur : outil inconnu '{name}'."
    try:
        return read_file(**arguments)
    except Exception as error:
        return f"Erreur : {type(error).__name__}: {error}"


def main() -> None:
    question = " ".join(sys.argv[1:]) or "Lis pyproject.toml et dis-moi quelles sont les dépendances du projet."
    messages = [{"role": "user", "content": question}]

    for tour in range(1, MAX_TOURS + 1):
        message = chat(messages, [READ_FILE_SCHEMA])
        messages.append(message)  # 1) le message de l'assistant, avec ses tool_calls

        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            print(f"\nRéponse finale (tour {tour}) :\n{message['content']}")
            return

        for call in tool_calls:
            name = call["function"]["name"]
            arguments = call["function"]["arguments"]
            print(f"[tour {tour}] le modèle appelle {name}({arguments})")
            result = run_tool(name, arguments)
            print(f"         -> {len(result)} caractères renvoyés au modèle")
            # 2) le résultat, avec le rôle "tool" et le nom de l'outil
            messages.append({"role": "tool", "tool_name": name, "content": result})

    print(f"Arrêt : {MAX_TOURS} tours sans réponse finale.")


if __name__ == "__main__":
    main()