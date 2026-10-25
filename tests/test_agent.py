"""Tests de la boucle agentique (agent.py), avec un faux modèle."""

import pytest

from mini_agent.agent import run_turn
from mini_agent.tools import ToolContext


class FakeChat:
    """Faux client Ollama : renvoie des réponses écrites à l'avance."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []  # ce que la boucle a envoyé à chaque appel

    def __call__(self, messages, tools):
        self.calls.append(list(messages))
        return self.replies.pop(0)


def tool_call(name, **arguments):
    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": arguments}}]}


def answer(text):
    return {"role": "assistant", "content": text}


@pytest.fixture
def ctx(tmp_path):
    (tmp_path / "notes.txt").write_text("12, 15, 9", encoding="utf-8")
    return ToolContext(workdir=tmp_path, skills_dir=tmp_path / "skills", confirm=lambda question: True)


def test_reponse_directe_sans_outil(ctx):
    chat = FakeChat([answer("Bonjour !")])
    messages = [{"role": "user", "content": "Salut"}]
    assert run_turn(chat, messages, ctx) == "Bonjour !"
    assert len(chat.calls) == 1


def test_outil_execute_et_resultat_renvoye(ctx):
    chat = FakeChat([tool_call("read_file", path="notes.txt"), answer("Il y a 3 notes.")])
    messages = [{"role": "user", "content": "Combien de notes ?"}]

    assert run_turn(chat, messages, ctx) == "Il y a 3 notes."
    # La conversation contient : user, assistant (tool_calls), tool, assistant.
    assert [m["role"] for m in messages] == ["user", "assistant", "tool", "assistant"]
    assert messages[2] == {"role": "tool", "tool_name": "read_file", "content": "12, 15, 9"}
    # Au 2e appel, le modèle a bien reçu le résultat de l'outil.
    assert chat.calls[1][-1]["content"] == "12, 15, 9"