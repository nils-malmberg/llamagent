"""Tests des commandes /... (commands.py)."""

import pytest

from llamagent import llm
from llamagent.commands import COMMANDS, execute_command
from llamagent.config import Config
from llamagent.session import create_session


@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "list_models", lambda config: ["qwen3.5:4b", "qwen3.5:latest", "llama3.2:3b"])
    config = Config(ollama_url="http://ollama", model="qwen3.5:4b", workdir=tmp_path)
    return create_session(config, confirm=lambda question: True)


def test_help_liste_toutes_les_commandes(session):
    aide = execute_command(session, "/help")
    assert all(name in aide for name in COMMANDS)


def test_commande_inconnue(session):
    assert "Commande inconnue : /foo" in execute_command(session, "/foo")


def test_temperature(session):
    assert execute_command(session, "/temp 0.7") == "Température : 0.7"
    assert session.config.temperature == 0.7
    assert "entre 0 et 2" in execute_command(session, "/temp 5")
    assert "Usage" in execute_command(session, "/temp chaud")
    assert session.config.temperature == 0.7


def test_contexte(session):
    execute_command(session, "/ctx 16384")
    assert session.config.num_ctx == 16384
    assert "entre 2048" in execute_command(session, "/ctx 100")


def test_modeles_et_changement_de_modele(session):
    assert "* qwen3.5:4b" in execute_command(session, "/models")
    execute_command(session, "/model llama3.2:3b")
    assert session.config.model == "llama3.2:3b"
    execute_command(session, "/model qwen3.5")  # -> qwen3.5:latest
    assert session.config.model == "qwen3.5:latest"
    assert "Modèle inconnu" in execute_command(session, "/model gpt-5")
    assert session.config.model == "qwen3.5:latest"


def test_skill_chargee_dans_la_conversation(session):
    assert "corriger-un-bug" in execute_command(session, "/skills")
    execute_command(session, "/skill corriger-un-bug")
    assert "Corriger un bug" in session.messages[-1]["content"]
    assert "skill inconnue" in execute_command(session, "/skill inexistante")


def test_clear(session):
    session.messages.append({"role": "user", "content": "x"})
    execute_command(session, "/clear")
    assert [m["role"] for m in session.messages] == ["system"]


def test_allow(session):
    execute_command(session, "/allow python -m pytest")
    assert session.ctx.allowed_commands == ["python -m pytest"]
    assert execute_command(session, "/allow git status && del x").startswith("Refusé")
    assert session.ctx.allowed_commands == ["python -m pytest"]


def test_init_cree_les_fichiers_du_projet(session, tmp_path):
    from llamagent.config import read_toml
    from llamagent.tools import available_skills

    resultat = execute_command(session, "/init")
    assert resultat.startswith("Créé :")
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8").startswith("# Instructions du projet")
    assert read_toml(tmp_path / ".llamagent" / "config.toml") == {}  # tout est en commentaire
    assert (tmp_path / ".llamagent" / "skills" / "LISEZMOI.txt").exists()
    # Le LISEZMOI n'est pas une skill, et AGENTS.md est déjà dans le prompt système.
    assert "LISEZMOI" not in available_skills(session.ctx.skills_dirs)
    assert "## Instructions du projet (AGENTS.md)" in session.messages[0]["content"]
    assert execute_command(session, "/init") == "Ce projet est déjà initialisé : rien à créer."


def test_init_ne_remplace_pas_un_fichier_existant(session, tmp_path):
    (tmp_path / "AGENTS.md").write_text("Mes consignes.", encoding="utf-8")
    resultat = execute_command(session, "/init")
    assert "  AGENTS.md" not in resultat  # pas dans la liste des fichiers créés
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == "Mes consignes."


def test_init_refuse_par_l_utilisateur(session, tmp_path):
    session.ctx.confirm = lambda question: False
    assert execute_command(session, "/init") == "Rien n'a été créé."
    assert not (tmp_path / "AGENTS.md").exists()


def test_sessions_reprise_et_suppression(session, tmp_path):
    from llamagent.history import save_session

    assert execute_command(session, "/sessions") == "Aucune conversation sauvegardée dans ce projet."
    session.messages.append({"role": "user", "content": "Corrige le bug"})
    save_session(session)
    assert "Corrige le bug" in execute_command(session, "/sessions")

    execute_command(session, "/clear")
    assert execute_command(session, "/resume").startswith("Conversation reprise : Corrige le bug")
    assert session.messages[-1]["content"] == "Corrige le bug"
    assert "introuvable" in execute_command(session, "/resume 9")

    session.ctx.confirm = lambda question: False
    assert execute_command(session, "/delete 1") == "Rien n'a été supprimé."
    session.ctx.confirm = lambda question: True
    assert execute_command(session, "/delete 1").startswith("Conversation supprimée")
    assert session.session_id is None
    assert execute_command(session, "/sessions") == "Aucune conversation sauvegardée dans ce projet."


def test_context_et_compact(session, monkeypatch):
    assert "total estimé" in execute_command(session, "/context")
    assert execute_command(session, "/compact") == "Rien à compacter : la conversation est vide."
    monkeypatch.setattr(llm, "chat", lambda config, messages, tools=None: {"role": "assistant", "content": "Résumé."})
    session.messages.append({"role": "user", "content": "Bonjour"})
    assert execute_command(session, "/compact").endswith("Résumé.")
    # Le fichier sauvegardé contient la conversation compactée.
    from llamagent.history import find_session
    saved = find_session(session.config.workdir, "1")
    assert "Résumé." in saved["messages"][0]["content"]
    assert saved["title"] == "Bonjour"  # le titre ne change pas après un compactage


def test_init_cree_un_gitignore_pour_les_sessions(session, tmp_path):
    execute_command(session, "/init")
    assert (tmp_path / ".llamagent" / ".gitignore").read_text(encoding="utf-8") == "sessions/\n"