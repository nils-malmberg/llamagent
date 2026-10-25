"""Point d'entrée de la ligne de commande : `uv run mini-agent`.

À l'étape 0, il se contente d'afficher la configuration chargée.
La boucle agentique viendra se brancher ici dans les étapes suivantes.
"""

from mini_agent.config import load_config


def main() -> None:
    config = load_config()
    print("mini-agent — configuration chargée :")
    print(f"  OLLAMA_URL   = {config.ollama_url}")
    print(f"  OLLAMA_MODEL = {config.model}")
    print(f"  options      = {config.options()}")
    print(f"  endpoint     = {config.chat_url}")


if __name__ == "__main__":
    main()