"""Étape 1 — Premier appel à Ollama.

Objectif : envoyer UNE question au modèle via l'API native /api/chat et
afficher sa réponse. Pas d'historique, pas d'outil : juste une requête HTTP.

Lancer :
    uv run python steps/step1_hello.py
    uv run python steps/step1_hello.py "Ta question ici"
"""

import json
import os
import sys

import requests

# Même configuration que src/llamagent/config.py, recopiée ici pour que
# le script reste autonome (un seul fichier à lire pour comprendre l'étape).
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://192.168.1.76:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:4b")


def chat(messages: list[dict]) -> dict:
    """Envoie la conversation à Ollama et renvoie la réponse JSON complète."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,  # toute la conversation, à chaque appel
        "stream": False,  # une seule réponse complète, pas de flux token par token
        "think": False,  # pas de « réflexion » cachée avant la réponse
        "options": {"temperature": 0.2, "num_ctx": 8192},
    }
    # Le premier appel peut être lent : Ollama charge le modèle en VRAM.
    response = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
    response.raise_for_status()  # lève une exception si HTTP 4xx / 5xx
    return response.json()


def main() -> None:
    question = " ".join(sys.argv[1:]) or "Explique en une phrase ce qu'est un agent de code."
    messages = [{"role": "user", "content": question}]

    print(f"POST {OLLAMA_URL}/api/chat  (modèle : {OLLAMA_MODEL})")
    print(f"Question : {question}\n")
    try:
        data = chat(messages)
    except requests.ConnectionError:
        print(f"Impossible de joindre Ollama sur {OLLAMA_URL}. Vérifie OLLAMA_URL.")
        sys.exit(1)

    # On affiche la réponse brute une fois : c'est utile de voir ce que
    # renvoie vraiment l'API avant de n'en garder qu'un champ.
    print("Réponse brute d'Ollama :")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    # Ce qui nous intéresse : le message de l'assistant.
    print("\nRéponse du modèle :")
    print(data["message"]["content"])

    # Les durées sont en nanosecondes.
    tokens = data.get("eval_count", 0)
    seconds = data.get("eval_duration", 0) / 1e9
    if seconds:
        print(f"\n{tokens} tokens générés en {seconds:.1f} s ({tokens / seconds:.1f} tokens/s)")


if __name__ == "__main__":
    main()