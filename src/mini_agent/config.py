"""Configuration de mini-agent.

Tout ce qui peut changer d'une machine à l'autre (adresse d'Ollama, modèle,
dossier de travail) est lu dans les variables d'environnement, avec des
valeurs par défaut adaptées à mon NAS. Le reste (réglages du modèle, limites
des garde-fous) est fixé ici pour que tout le projet utilise les mêmes valeurs.
"""

import os
from dataclasses import dataclass
from pathlib import Path

# Valeurs par défaut : Ollama sur le NAS, modèle 4B qui tient dans 6 Go de VRAM.
DEFAULT_OLLAMA_URL = "http://192.168.1.76:11434"
DEFAULT_OLLAMA_MODEL = "qwen3.5:4b"

# Température basse : on veut un agent prévisible, pas créatif.
TEMPERATURE = 0.2
# Taille de la fenêtre de contexte (en tokens) demandée à Ollama.
# 8192 est un bon compromis pour un modèle 4B sur une carte de 6 Go.
NUM_CTX = 8192
# Délai maximal d'une requête à Ollama, en secondes. Le premier appel est
# lent car Ollama doit charger le modèle en VRAM.
REQUEST_TIMEOUT = 120

# Garde-fous (étape 6).
MAX_TOURS = 15  # nombre maximal d'appels au LLM pour une même demande
COMMAND_TIMEOUT = 30  # durée maximale d'une commande lancée par run_command (s)
MAX_OUTPUT_CHARS = 4000  # taille maximale d'un résultat d'outil (~1000 tokens)

# Dossiers du projet : prompts/ et skills/ sont à la racine du dépôt,
# deux niveaux au-dessus de ce fichier (src/mini_agent/config.py).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = PROJECT_ROOT / "prompts"
SKILLS_DIR = PROJECT_ROOT / "skills"


@dataclass(frozen=True)
class Config:
    """Réglages chargés au démarrage (immuables ensuite)."""

    ollama_url: str
    model: str
    workdir: Path  # le seul dossier où l'agent a le droit de lire et d'écrire
    temperature: float = TEMPERATURE
    num_ctx: int = NUM_CTX

    @property
    def chat_url(self) -> str:
        """URL de l'API native d'Ollama (et non la couche /v1 compatible OpenAI)."""
        return f"{self.ollama_url}/api/chat"

    def options(self) -> dict:
        """Bloc `options` envoyé à Ollama à chaque appel."""
        return {"temperature": self.temperature, "num_ctx": self.num_ctx}


def load_config() -> Config:
    """Construit la configuration à partir des variables d'environnement."""
    url = os.environ.get("OLLAMA_URL", DEFAULT_OLLAMA_URL)
    model = os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    # Par défaut, l'agent travaille dans le dossier où on le lance.
    workdir = Path(os.environ.get("MINI_AGENT_WORKDIR", Path.cwd())).resolve()
    # On retire un éventuel "/" final pour pouvoir écrire f"{url}/api/chat".
    return Config(ollama_url=url.rstrip("/"), model=model, workdir=workdir)