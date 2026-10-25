"""Tests de la sauvegarde des conversations (history.py)."""

import json

import pytest

from llamagent.config import Config
from llamagent.history import delete_session, find_session, list_sessions, resume_session, save_session, sessions_dir
from llamagent.session import create_session


@pytest.fixture
def session(tmp_path):
    config = Config(ollama_url="http://ollama", model="qwen3.5:4b", workdir=tmp_path)
    return create_session(config, confirm=lambda question: True)


def converse(session, *texts):
    for text in texts:
        session.messages.append({"role": "user", "content": text})
        session.messages.append({"role": "assistant", "content": f"réponse à {text}"})


def test_conversation_vide_pas_sauvegardee(session, tmp_path):
    save_session(session)
    assert list_sessions(tmp_path) == []


def test_sauvegarde_et_liste(session, tmp_path):
    converse(session, "Corrige le bug de calc.py\nmerci", "Et ajoute un test")
    save_session(session)
    sessions = list_sessions(tmp_path)
    assert len(sessions) == 1
    data = sessions[0]
    assert data["id"] == session.session_id
    assert data["title"] == "Corrige le bug de calc.py"  # première ligne de la première demande
    assert data["model"] == "qwen3.5:4b"
    assert [m["role"] for m in data["messages"]] == ["user", "assistant", "user", "assistant"]  # sans le prompt système


def test_meme_fichier_tant_que_la_conversation_continue(session, tmp_path):
    converse(session, "Première demande")
    save_session(session)
    converse(session, "Deuxième demande")
    save_session(session)
    assert len(list(sessions_dir(tmp_path).glob("*.json"))) == 1
    assert len(list_sessions(tmp_path)[0]["messages"]) == 4


def test_clear_commence_un_nouveau_fichier(session, tmp_path):
    converse(session, "Première conversation")
    save_session(session)
    session.reset()
    assert session.session_id is None


def test_reprise(session, tmp_path):
    converse(session, "Corrige le bug")
    save_session(session)
    saved_id = session.session_id
    session.reset()
    (tmp_path / "AGENTS.md").write_text("Nouvelle consigne.", encoding="utf-8")

    resume_session(session, find_session(tmp_path, "1"))
    assert session.session_id == saved_id
    assert [m["role"] for m in session.messages] == ["system", "user", "assistant"]
    assert session.messages[0]["content"].endswith("Nouvelle consigne.")  # prompt système relu
    assert session.context_tokens > 0  # estimation en attendant Ollama


def test_recherche_par_numero_ou_identifiant(tmp_path):
    folder = sessions_dir(tmp_path)
    folder.mkdir(parents=True)
    for name, updated in (("ancienne", "2026-10-01T10:00:00"), ("recente", "2026-10-25T10:00:00")):
        data = {"id": name, "title": name, "updated": updated, "model": "m", "messages": []}
        (folder / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
    assert find_session(tmp_path, "1")["id"] == "recente"
    assert find_session(tmp_path, "2")["id"] == "ancienne"
    assert find_session(tmp_path, "ancienne")["id"] == "ancienne"
    assert find_session(tmp_path, "3") is None


def test_fichier_abime_ignore(session, tmp_path):
    converse(session, "Demande")
    save_session(session)
    (sessions_dir(tmp_path) / "abime.json").write_text("{pas du json", encoding="utf-8")
    assert len(list_sessions(tmp_path)) == 1


def test_suppression(session, tmp_path):
    converse(session, "Demande")
    save_session(session)
    delete_session(find_session(tmp_path, "1"))
    assert list_sessions(tmp_path) == []