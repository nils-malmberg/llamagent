"""Tests de la session (session.py) : projet, fichiers tagués, réglages."""

from pathlib import Path

import pytest

from mini_agent import llm
from mini_agent.config import Config
from mini_agent.session import create_session, expand_mentions, find_mentions


@pytest.fixture
def session(tmp_path):
    config = Config(ollama_url="http://ollama", model="qwen3.5:4b", workdir=tmp_path)
    return create_session(config, confirm=lambda question: True)


def test_mentions():
    texte = "Regarde @src/app.py et @README.md. Écris à nils@exemple.fr, puis relis @src/app.py"
    assert find_mentions(texte) == ["src/app.py", "README.md"]


def test_contenu_des_fichiers_mentionnes(tmp_path):
    (tmp_path / "app.py").write_text("print('ok')\n", encoding="utf-8")
    texte = expand_mentions("Explique @app.py", tmp_path)
    assert texte.startswith("Explique @app.py\n\nFichiers mentionnés :")
    assert "--- app.py ---\nprint('ok')" in texte


def test_mention_hors_du_dossier_ou_absente(tmp_path):
    texte = expand_mentions("Lis @../secret.txt et @absent.py", tmp_path)
    assert "--- ../secret.txt ---\n(fichier illisible : chemin refusé" in texte
    assert "--- absent.py ---\n(fichier illisible :" in texte


def test_sans_mention_le_texte_ne_change_pas(tmp_path):
    assert expand_mentions("Bonjour", tmp_path) == "Bonjour"


def test_agents_md_dans_le_prompt_systeme(tmp_path, session):
    assert "AGENTS.md" not in session.messages[0]["content"]
    (tmp_path / "AGENTS.md").write_text("Les tests sont dans tests/.", encoding="utf-8")
    session.reset()  # /clear relit le fichier
    assert session.messages[0]["content"].endswith("Les tests sont dans tests/.")


def test_changer_de_modele_garde_la_conversation(monkeypatch, session):
    vus = []

    def faux_chat_full(config, messages, tools):
        vus.append((config.model, config.temperature, len(messages)))
        return {"message": {"role": "assistant", "content": "ok"}, "prompt_eval_count": 1200, "eval_count": 30}

    monkeypatch.setattr(llm, "chat_full", faux_chat_full)
    session.ask("Bonjour")
    session.update(model="qwen3.5:9b", temperature=0.6)
    session.ask("Et maintenant ?")
    assert vus == [("qwen3.5:4b", 0.2, 2), ("qwen3.5:9b", 0.6, 4)]
    assert session.context_tokens == 1230


def test_skills_du_projet(tmp_path, session):
    assert session.ctx.skills_dirs[-1] == tmp_path / ".mini-agent" / "skills"
    assert session.ctx.skills_dirs[0].name == "skills"