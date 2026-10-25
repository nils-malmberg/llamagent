"""Tests de la mesure et du compactage du contexte (context.py)."""

import pytest

from llamagent import llm
from llamagent.config import Config
from llamagent.context import compact, context_report, estimate_tokens, needs_compaction, transcript
from llamagent.session import create_session


@pytest.fixture
def session(tmp_path):
    config = Config(ollama_url="http://ollama", model="qwen3.5:4b", workdir=tmp_path)
    session = create_session(config, confirm=lambda question: True)
    session.messages += [
        {"role": "user", "content": "Corrige le bug de calc.py"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "calc.py"}}}]},
        {"role": "tool", "tool_name": "read_file", "content": "x" * 5000},
        {"role": "assistant", "content": "C'est corrigé."},
    ]
    return session


def test_estimation():
    assert estimate_tokens("a" * 400) == 100


def test_rapport_par_categorie(session):
    rapport = context_report(session)
    for categorie in ("prompt système", "schémas des outils", "vos messages", "réponses du modèle", "résultats d'outils", "total estimé"):
        assert categorie in rapport
    ligne = next(l for l in rapport.splitlines() if l.startswith("résultats d'outils"))
    assert ligne.endswith("≈   1250 tokens")  # 5000 caractères / 4


def test_transcription_raccourcit_les_resultats(session):
    texte = transcript(session.messages)
    assert "UTILISATEUR : Corrige le bug de calc.py" in texte
    assert 'AGENT appelle read_file {"path": "calc.py"}' in texte
    assert "RÉSULTAT de read_file :" in texte
    assert len(texte) < 1000  # le résultat de 5000 caractères est tronqué
    assert "prompt" not in texte.lower()  # le prompt système n'est pas résumé


def test_compactage(monkeypatch, session):
    envoyes = []

    def faux_chat(config, messages, tools=None):
        envoyes.append((messages, tools))
        return {"role": "assistant", "content": "  calc.py : add corrigée (a + b).  "}

    monkeypatch.setattr(llm, "chat", faux_chat)
    system_prompt = session.messages[0]
    resume = compact(session)

    assert resume == "calc.py : add corrigée (a + b)."
    messages, tools = envoyes[0]
    assert tools is None  # le résumé est demandé sans outils
    assert "Tu résumes une conversation" in messages[0]["content"]  # prompts/COMPACT.md
    assert "UTILISATEUR : Corrige le bug de calc.py" in messages[1]["content"]
    assert session.messages[0] is system_prompt
    assert [m["role"] for m in session.messages] == ["system", "user", "assistant"]
    assert "calc.py : add corrigée" in session.messages[1]["content"]
    assert 0 < session.context_tokens < 2000
    assert session.context_estimated
    assert "(estimation)" in context_report(session)


def test_seuil_de_compactage(session):
    session.context_tokens = 6000
    assert not needs_compaction(session)  # 6000 / 8192 = 73 %
    session.context_tokens = 6600
    assert needs_compaction(session)  # 80 %