"""Essai rapide de l'étape 5, à lancer depuis la racine du projet :
    uv run python try_step5.py
"""
from mini_agent import llm
from mini_agent.agent import run_turn
from mini_agent.config import SKILLS_DIR, load_config
from mini_agent.guards import ask_confirmation
from mini_agent.tools import ToolContext

config = load_config()
ctx = ToolContext(
    workdir=config.workdir, 
    skills_dir=SKILLS_DIR, 
    confirm=ask_confirmation
)
messages = [{"role": "user", "content": "Liste les fichiers du projet, puis lis pyproject.toml et donne ses dépendances."}]
answer = run_turn(lambda msgs, tools: llm.chat(config, msgs, tools), messages, ctx)

# La boucle de l'étape 5 n'affiche rien : on relit la conversation pour voir
# quels outils le modèle a appelés et ce qu'il a reçu en retour.
print(f"Dossier de travail : {config.workdir}\n")
for message in messages:
    for call in message.get("tool_calls") or []:
        print(f"appel    : {call['function']['name']} {call['function']['arguments']}")
    if message["role"] == "tool":
        print(f"résultat : {message['content'][:300]}\n")
print(f"Réponse  : {answer}")