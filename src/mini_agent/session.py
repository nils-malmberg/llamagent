"""La session : tout l'état d'une conversation avec l'agent.

Jusqu'à l'étape 8, cli.py gardait la configuration et les messages dans des
variables locales. Pour pouvoir changer de modèle ou de température en cours
de route (/model, /temp...), on les regroupe dans un objet Session que les
commandes peuvent modifier.
"""

import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable

from mini_agent import llm
from mini_agent.agent import build_system_prompt, run_turn
from mini_agent.config import MAX_OUTPUT_CHARS, PROJECT_DIR_NAME, PROJECT_INSTRUCTIONS, PROMPTS_DIR, SKILLS_DIR, Config
from mini_agent.guards import GuardError, safe_path, truncate
from mini_agent.tools import ToolContext, available_skills

# ─────────────────────────── Projet (étape 9) ───────────────────────────


def project_skills_dirs(workdir: Path) -> list[Path]:
    """Skills globales (dépôt mini-agent), puis skills du projet, qui l'emportent."""
    return [SKILLS_DIR, workdir / PROJECT_DIR_NAME / "skills"]


def load_project_instructions(workdir: Path) -> str:
    """Contenu du fichier AGENTS.md du projet, ou "" s'il n'y en a pas."""
    path = workdir / PROJECT_INSTRUCTIONS
    if not path.is_file():
        return ""
    # Tronqué : le prompt système est renvoyé à chaque appel, il doit rester court.
    return truncate(path.read_text(encoding="utf-8"), MAX_OUTPUT_CHARS)


# ─────────────────────────── Fichiers tagués (étape 11) ───────────────────────────

# « @chemin » en début de texte ou après un espace : une adresse e-mail
# comme nils@exemple.fr n'est donc pas prise pour un fichier.
MENTION = re.compile(r"(?<!\S)@([\w./\\-]+)")


def find_mentions(text: str) -> list[str]:
    """Chemins tagués avec @ dans la demande, sans doublon, dans l'ordre."""
    # rstrip : dans « regarde @main.py. » le point final n'est pas au fichier.
    paths = [match.rstrip(".,;:") for match in MENTION.findall(text)]
    return list(dict.fromkeys(path for path in paths if path))


def expand_mentions(text: str, workdir: Path) -> str:
    """Ajoute à la demande le contenu des fichiers tagués avec @chemin.

    Le modèle reçoit directement le contenu : pas besoin d'un appel à
    read_file, donc un tour de boucle en moins.
    """
    blocks = []
    for path in find_mentions(text):
        try:
            content = truncate(safe_path(workdir, path).read_text(encoding="utf-8"), MAX_OUTPUT_CHARS)
        except (GuardError, OSError, UnicodeDecodeError) as error:
            content = f"(fichier illisible : {error})"
        blocks.append(f"--- {path} ---\n{content}")
    if not blocks:
        return text
    return text + "\n\nFichiers mentionnés :\n\n" + "\n\n".join(blocks)


# ─────────────────────────── La session ───────────────────────────


@dataclass
class Session:
    """L'état d'une conversation : réglages, outils, messages."""

    config: Config
    template: str  # contenu de prompts/AGENT.md
    ctx: ToolContext
    messages: list[dict] = field(default_factory=list)
    context_tokens: int = 0  # taille du dernier échange, d'après Ollama

    def __post_init__(self) -> None:
        self.reset()

    def system_prompt(self) -> str:
        skills = available_skills(self.ctx.skills_dirs)
        instructions = load_project_instructions(self.config.workdir)
        return build_system_prompt(self.template, self.config.workdir, skills, instructions)

    def reset(self) -> None:
        """Repart d'une conversation vide. Le prompt système est relu :
        une skill ou un AGENTS.md modifié est pris en compte."""
        self.messages = [{"role": "system", "content": self.system_prompt()}]
        self.context_tokens = 0

    def update(self, **changes) -> None:
        """Change un réglage (modèle, température...) en gardant la conversation."""
        self.config = replace(self.config, **changes)

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        """La fonction `chat` donnée à la boucle. Elle lit self.config à chaque
        appel : un /model ou un /temp s'applique dès l'appel suivant."""
        data = llm.chat_full(self.config, messages, tools)
        # Tokens lus + tokens générés : la place occupée dans le contexte.
        self.context_tokens = data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
        return data["message"]

    def ask(self, text: str) -> str:
        """Traite une demande de l'utilisateur et renvoie la réponse finale."""
        self.messages.append({"role": "user", "content": expand_mentions(text, self.config.workdir)})
        return run_turn(self.chat, self.messages, self.ctx)


def create_session(config: Config, confirm: Callable[[str], bool]) -> Session:
    """Assemble une session : prompt système, outils, skills du projet."""
    ctx = ToolContext(
        workdir=config.workdir,
        skills_dirs=project_skills_dirs(config.workdir),
        confirm=confirm,
        allowed_commands=list(config.allowed_commands),
    )
    template = (PROMPTS_DIR / "AGENT.md").read_text(encoding="utf-8")
    return Session(config=config, template=template, ctx=ctx)