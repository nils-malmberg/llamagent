# mini-agent

Un agent de code minimal en Python, écrit à la main pour comprendre comment fonctionne un agent comme opencode ou Claude Code : boucle agentique, harness, outils, prompt système, skills et garde-fous.

Il pilote un LLM local servi par [Ollama](https://ollama.com) (par défaut `qwen3.5:4b`) via l'API native `/api/chat`. Aucun framework d'agent : une seule dépendance, `requests`.

📖 Tutoriel complet, étape par étape : [nils-malmberg.fr/project8.html](https://nils-malmberg.fr/project8.html)

## Fonctionnalités

- **Boucle agentique** : le modèle demande des outils, le harness les exécute et lui renvoie les résultats, jusqu'à une réponse finale.
- **5 outils** : `read_file`, `list_files`, `edit_file`, `run_command`, `load_skill`.
- **Confiné au dossier de travail** : les outils de fichiers ne peuvent ni lire ni écrire en dehors du dossier où l'on lance l'agent.
- **Garde-fous** : confirmation `[o/N]` avant chaque écriture (avec le diff) et chaque commande, nombre maximal de tours, timeout des commandes, sorties tronquées, détection des appels répétés.
- **Robuste** : outil inconnu, argument manquant, JSON invalide ou exception Python sont renvoyés au modèle sous forme de texte, sans faire planter l'agent.
- **Par projet** : consignes dans `AGENTS.md`, skills dans `.mini-agent/skills/`, réglages dans `.mini-agent/config.toml`.
- **Commandes `/…`** pour changer de modèle, de température ou de taille de contexte en cours de conversation.
- **Fichiers tagués** : `@chemin` dans une demande joint le contenu du fichier.
- **Compteur de contexte** affiché après chaque réponse.

## Installation

Prérequis : [uv](https://docs.astral.sh/uv/), Python ≥ 3.11 (uv l'installe si besoin), et un serveur Ollama avec un modèle qui gère les outils.

```bash
git clone https://github.com/nils-malmberg/mini-agent.git
cd mini-agent
uv tool install -e .
uv tool update-shell   # une seule fois, puis rouvrir le terminal
```

L'option `-e` (installation éditable) est nécessaire : `prompts/` et `skills/` sont lus depuis le dépôt.

## Utilisation

```bash
cd chemin/vers/mon-projet
mini-agent                                   # mode conversation
mini-agent "Trouve le bug dans @calc.py"     # une seule demande, puis on quitte
mini-agent -m qwen3.5:9b -t 0.5              # choisir le modèle et la température
mini-agent --help
```

Le dossier depuis lequel on lance `mini-agent` devient le dossier de travail.

### Commandes

| Commande | Rôle |
|---|---|
| `/help` | liste des commandes |
| `/init` | préparer le projet AGENTS.md et dossier .mini-agent |
| `/config` | réglages actuels |
| `/models` | modèles installés sur le serveur Ollama |
| `/model qwen3.5:9b` | changer de modèle (la conversation continue) |
| `/temp 0.5` | changer la température |
| `/ctx 16384` | changer la taille du contexte |
| `/skills` | skills disponibles |
| `/skill corriger-un-bug` | charger une skill dans la conversation |
| `/allow python -m pytest` | lancer une commande sans confirmation pour la session |
| `/clear` | effacer la conversation |
| `/quit` | quitter |

## Configuration

Les réglages viennent de cinq sources ; chacune remplace la précédente :

1. les valeurs par défaut (`src/mini_agent/config.py`) ;
2. le fichier global `~/.mini-agent/config.toml` (Windows : `C:\Users\<vous>\.mini-agent\config.toml`) ;
3. le fichier du projet `.mini-agent/config.toml` ;
4. les variables d'environnement `OLLAMA_URL` et `OLLAMA_MODEL` ;
5. les options de la ligne de commande.

```toml
# ~/.mini-agent/config.toml
url = "http://192.168.1.76:11434"
model = "qwen3.5:4b"
temperature = 0.2
num_ctx = 8192
```

```toml
# mon-projet/.mini-agent/config.toml
temperature = 0.1
allowed_commands = ["python -m pytest", "git status", "git diff"]
```

Autres variables : `MINI_AGENT_WORKDIR` (dossier de travail, facultatif) et `NO_COLOR` (désactive les couleurs).

## Personnaliser un projet

```
mon-projet/
├── AGENTS.md              # consignes du projet, ajoutées au prompt système
└── .mini-agent/
    ├── config.toml        # réglages du projet
    └── skills/            # skills du projet (remplacent les globales de même nom)
        └── ma-skill.md
```

Une skill est un fichier Markdown avec un en-tête `description:`. Le prompt système ne contient que son nom et sa description ; le modèle charge le contenu avec `load_skill` quand il en a besoin.

```markdown
---
description: Écrire des tests pytest pour un module Python.
---
# Écrire des tests pytest

1. Lis le module à tester avec read_file.
2. ...
```

## Structure

```
mini-agent/
├── src/mini_agent/
│   ├── config.py      # configuration et limites des garde-fous
│   ├── llm.py         # appels à Ollama (/api/chat, /api/tags)
│   ├── tools.py       # outils et registre
│   ├── guards.py      # garde-fous
│   ├── agent.py       # boucle agentique et prompt système
│   ├── session.py     # état de la conversation, fichiers tagués
│   ├── commands.py    # commandes /...
│   └── cli.py         # point d'entrée `mini-agent`
├── prompts/AGENT.md   # prompt système
├── skills/            # skills globales
├── demo/stats.py      # script buggé pour la démo
└── tests/             # pytest, Ollama remplacé par un faux modèle
```

## Tests

```bash
uv run pytest -q
```

## Limites

- **Confinement** : seuls les outils de fichiers sont confinés au dossier de travail. Une commande lancée par `run_command` peut écrire ailleurs : la protection est la confirmation `[o/N]`. Les commandes autorisées (`allowed_commands`, `/allow`) sont un confort, pas une barrière de sécurité. N'y mettez que des commandes sans danger.
- **Contexte** : avec un modèle 4B et 8192 tokens, le contexte se remplit vite. Au-delà, Ollama coupe le début de la conversation : utilisez `/clear`.
- **Petits modèles** : un modèle 4B peut inventer un outil, se tromper de chemin ou répéter un appel. Les erreurs lui sont renvoyées pour qu'il se corrige, mais il n'y arrive pas toujours.

## Licence

Voir [LICENSE](LICENSE).