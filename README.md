# llamagent

Un agent de code minimal en Python, écrit à la main pour comprendre comment fonctionne un agent de code : boucle agentique, harness, outils, prompt système, skills et garde-fous.

Il pilote un LLM local servi par [Ollama](https://ollama.com) (par défaut `qwen3.5:4b`) via l'API native `/api/chat`. Aucun framework d'agent : une seule dépendance, `requests`.

![Interface de llamagent : la mascotte, puis chaque tour de la boucle avec le modèle, le harness et l'outil](https://raw.githubusercontent.com/nils-malmberg/llamagent/main/docs/interface.png)

📖 Tutoriel complet, étape par étape : [nils-malmberg.fr/project8.html](https://nils-malmberg.fr/project8.html)

## Installation

Prérequis : un serveur [Ollama](https://ollama.com) avec un modèle qui gère les outils (`ollama pull qwen3.5:4b`).

```bash
uv tool install llamagent      # ou : pipx install llamagent
```

Si Ollama ne tourne pas sur la même machine, indiquez son adresse dans `~/.llamagent/config.toml` (sous Windows : `C:\Users\<vous>\.llamagent\config.toml`) :

```toml
url = "http://192.168.1.76:11434"
```

## Utilisation

```bash
cd chemin/vers/mon-projet
llamagent                                   # mode conversation
llamagent "Trouve le bug dans @calc.py"     # une seule demande, puis on quitte
llamagent -c                                # reprendre la dernière conversation
llamagent -m qwen3.5:9b -t 0.5              # choisir le modèle et la température
llamagent --help
```

Le dossier depuis lequel on lance `llamagent` devient le dossier de travail : les outils de fichiers ne peuvent ni lire ni écrire ailleurs.

Chaque tour de la boucle est affiché avec ses trois acteurs : le **modèle** (ce qu'il demande), le **harness** (ce que les garde-fous en font) et l'**outil** (ce qu'il renvoie).

### Commandes

| Commande | Rôle |
|---|---|
| `/help` | liste des commandes |
| `/init` | préparer le projet : crée `AGENTS.md` et le dossier `.llamagent/` |
| `/config` | réglages actuels |
| `/models`, `/model qwen3.5:9b` | modèles installés, changer de modèle |
| `/temp 0.5`, `/ctx 16384` | changer la température, la taille du contexte |
| `/skills`, `/skill corriger-un-bug` | skills disponibles, charger une skill |
| `/context`, `/compact` | ce qui occupe le contexte, le compacter (automatique à 80 %) |
| `/sessions`, `/resume 2`, `/delete 2` | conversations sauvegardées |
| `/allow python -m pytest` | lancer une commande sans confirmation pour la session |
| `/clear`, `/quit` | effacer la conversation, quitter |

`@chemin` dans une demande joint le contenu du fichier.

## Configuration

Les réglages viennent de cinq sources ; chacune remplace la précédente :

1. les valeurs par défaut ;
2. le fichier global `~/.llamagent/config.toml` ;
3. le fichier du projet `.llamagent/config.toml` ;
4. les variables d'environnement `OLLAMA_URL` et `OLLAMA_MODEL` ;
5. les options de la ligne de commande.

```toml
url = "http://localhost:11434"
model = "qwen3.5:4b"
temperature = 0.2
num_ctx = 8192
allowed_commands = ["python -m pytest", "git status", "git diff"]
```

Autres variables : `LLAMAGENT_WORKDIR` (dossier de travail) et `NO_COLOR` (affichage sans couleurs).

## Personnaliser un projet

```
mon-projet/
├── AGENTS.md              # consignes du projet, ajoutées au prompt système
└── .llamagent/
    ├── .gitignore         # exclut sessions/ de git
    ├── config.toml        # réglages du projet
    ├── sessions/          # conversations sauvegardées
    └── skills/            # skills du projet (remplacent les globales de même nom)
```

`/init` crée ces fichiers. Une skill est un fichier Markdown avec un en-tête `description:` ; le modèle la charge avec l'outil `load_skill` quand la demande correspond.

```markdown
---
description: Écrire des tests pytest pour un module Python.
---
# Écrire des tests pytest

1. Lis le module à tester avec read_file.
2. ...
```

## Limites

- Seuls les outils de fichiers sont confinés au dossier de travail. Une commande lancée par `run_command` peut écrire ailleurs : la protection est la confirmation `[o/N]`. Les commandes autorisées sont un confort, pas une barrière de sécurité.
- Avec un modèle 4B et 8192 tokens, le contexte se remplit vite : `/compact` le résume.
- Un petit modèle peut inventer un outil, se tromper de chemin ou répéter un appel. Les erreurs lui sont renvoyées pour qu'il se corrige, mais il n'y arrive pas toujours.

## Développement

```bash
git clone https://github.com/nils-malmberg/llamagent.git
cd llamagent
uv sync
uv run pytest -q
uv tool install -e .     # la commande llamagent utilise ce dossier
```

Chaque push lance les tests sous Windows, macOS et Linux (Python 3.11 à 3.13). Pour publier une version : mettre à jour `version` dans `pyproject.toml`, puis créer et pousser l'étiquette correspondante (`git tag v0.1.0 && git push origin v0.1.0`) ; le paquet est publié sur TestPyPI, puis sur PyPI après validation.

## Licence

MIT, voir [LICENSE](https://github.com/nils-malmberg/llamagent/blob/main/LICENSE).