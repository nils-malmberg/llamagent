"""Configuration de mini-agent.

Tout ce qui peut changer d'une machine à l'autre (adresse d'Ollama, modèle)
est lu dans les variables d'environnement, avec des valeurs par défaut
adaptées à mon NAS. Le reste (température, taille du contexte) est fixé ici
pour que tout le projet utilise les mêmes réglages.
"""

import os
from dataclasses import dataclass

# Valeurs par défaut : Ollama sur le NAS, modèle 4B qui tient dans 6 Go de VRAM.
DEFAULT_OLLAMA_URL = "http://192.168.1.76:11434"
DEFAULT_OLLAMA_MODEL = "qwen3.5:4b"

# Température basse : on veut un agent prévisible, pas créatif.
TEMPERATURE = 0.2
# Taille de la fenêtre de contexte (en tokens) demandée à Ollama.
# 8192 est un bon compromis pour un modèle 4B sur une carte de 6 Go.
NUM_CTX = 8192


@dataclass(frozen=True)
class Config:
    """Réglages de connexion à Ollama (immuables une fois chargés)."""

    ollama_url: str
    model: str
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
    # On retire un éventuel "/" final pour pouvoir écrire f"{url}/api/chat".
    return Config(ollama_url=url.rstrip("/"), model=model)