"""Étape 2 — Chat avec mémoire.

La « mémoire » du modèle n'est qu'une liste Python : `messages`.
À chaque tour, on y ajoute la question, on envoie TOUTE la liste à Ollama,
puis on y ajoute la réponse. Le modèle lui-même ne retient rien entre
deux appels : si on vide la liste, il a tout « oublié ».

Commandes : /messages (voir la liste envoyée), /oublie (la vider), /quit

Lancer :
    uv run python steps/step2_chat.py
"""

import json
import os

import requests

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://192.168.1.76:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:4b")


def chat(messages: list[dict]) -> dict:
    """Envoie toute la conversation et renvoie le message de l'assistant."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "num_ctx": 8192},
    }
    response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
    response.raise_for_status()
    return response.json()["message"]


def main() -> None:
    messages: list[dict] = []  # toute la mémoire de la conversation est ici
    print(f"Chat avec {OLLAMA_MODEL}. Commandes : /messages, /oublie, /quit")

    while True:
        try:
            text = input("\nvous > ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text == "/quit":
            break
        if text == "/messages":
            print(json.dumps(messages, indent=2, ensure_ascii=False))
            continue
        if text == "/oublie":
            messages.clear()
            print("(liste vidée : le modèle a tout « oublié »)")
            continue

        messages.append({"role": "user", "content": text})
        reply = chat(messages)  # on envoie TOUT l'historique
        messages.append(reply)  # et on garde la réponse pour le prochain tour
        print(f"\nmodèle > {reply['content']}")
        print(f"(historique : {len(messages)} messages)")


if __name__ == "__main__":
    main()