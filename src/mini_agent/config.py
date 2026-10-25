"""Configuration de mini-agent.

Les réglages viennent de plusieurs sources. Chacune remplace la précédente :
    1. les valeurs par défaut ci-dessous (adaptées à mon NAS) ;
    2. le fichier global   ~/.mini-agent/config.toml ;
    3. le fichier du projet .mini-agent/config.toml (dans le dossier de travail) ;
    4. les variables d'environnement OLLAMA_URL et OLLAMA_MODEL ;
    5. les options de la ligne de commande (--model, --temperature...).
Les limites des garde-fous, elles, sont fixées ici.
"""

import os
import tomllib
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

# Dossiers du projet mini-agent : prompts/ et skills/ sont à la racine du
# dépôt, deux niveaux au-dessus de ce fichier (src/mini_agent/config.py).
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = PROJECT_ROOT / "prompts"
SKILLS_DIR = PROJECT_ROOT / "skills"

# Réglages propres à chaque projet (étape 9) : un dossier .mini-agent/ dans
# le dossier de travail, et un fichier AGENTS.md à sa racine.
PROJECT_DIR_NAME = ".mini-agent"
PROJECT_INSTRUCTIONS = "AGENTS.md"
# Fichier de réglages global de l'utilisateur (étape 12).
USER_CONFIG = Path.home() / PROJECT_DIR_NAME / "config.toml"
# Les seules clés acceptées dans un fichier config.toml.
SETTINGS_KEYS = {"url", "model", "temperature", "num_ctx", "allowed_commands"}


@dataclass(frozen=True)
class Config:
    """Réglages de la session. Pour en changer un : dataclasses.replace()."""

    ollama_url: str
    model: str
    workdir: Path  # le seul dossier où l'agent a le droit de lire et d'écrire
    temperature: float = TEMPERATURE
    num_ctx: int = NUM_CTX
    # Commandes que run_command lance sans demander confirmation (étape 14).
    allowed_commands: tuple[str, ...] = ()

    @property
    def chat_url(self) -> str:
        """URL de l'API native d'Ollama (et non la couche /v1 compatible OpenAI)."""
        return f"{self.ollama_url}/api/chat"

    def options(self) -> dict:
        """Bloc `options` envoyé à Ollama à chaque appel."""
        return {"temperature": self.temperature, "num_ctx": self.num_ctx}


def read_toml(path: Path) -> dict:
    """Lit un fichier de réglages TOML. Renvoie {} s'il n'existe pas."""
    if not path.is_file():
        return {}
    try:
        settings = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise SystemExit(f"Fichier de réglages invalide : {path}\n{error}")
    # Une faute de frappe (« temperatur ») serait sinon ignorée sans prévenir.
    unknown = set(settings) - SETTINGS_KEYS
    if unknown:
        raise SystemExit(f"Réglage inconnu dans {path} : {', '.join(sorted(unknown))}")
    return settings


def load_config(cli_options: dict | None = None) -> Config:
    """Construit la configuration à partir de toutes les sources, dans l'ordre."""
    # Par défaut, l'agent travaille dans le dossier où on le lance.
    workdir = Path(os.environ.get("MINI_AGENT_WORKDIR", Path.cwd())).resolve()
    # Un dossier de travail absent ferait échouer tous les outils plus tard,
    # avec des erreurs obscures (WinError 267 sous Windows) : on s'arrête net.
    if not workdir.is_dir():
        raise SystemExit(f"Dossier de travail introuvable : {workdir} (vérifie MINI_AGENT_WORKDIR).")

    settings = {"url": DEFAULT_OLLAMA_URL, "model": DEFAULT_OLLAMA_MODEL, "temperature": TEMPERATURE, "num_ctx": NUM_CTX}
    settings.update(read_toml(USER_CONFIG))
    settings.update(read_toml(workdir / PROJECT_DIR_NAME / "config.toml"))
    if "OLLAMA_URL" in os.environ:
        settings["url"] = os.environ["OLLAMA_URL"]
    if "OLLAMA_MODEL" in os.environ:
        settings["model"] = os.environ["OLLAMA_MODEL"]
    # Options de la ligne de commande : seulement celles qui ont été données.
    settings.update({key: value for key, value in (cli_options or {}).items() if value is not None})

    try:
        return Config(
            # On retire un éventuel "/" final pour pouvoir écrire f"{url}/api/chat".
            ollama_url=str(settings["url"]).rstrip("/"),
            model=str(settings["model"]),
            workdir=workdir,
            temperature=float(settings["temperature"]),
            num_ctx=int(settings["num_ctx"]),
            allowed_commands=tuple(str(command) for command in settings.get("allowed_commands", ())),
        )
    except (TypeError, ValueError) as error:  # ex. temperature = "chaud"
        raise SystemExit(f"Réglage invalide : {error}")