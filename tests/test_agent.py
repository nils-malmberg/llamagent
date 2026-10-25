"""Tests de la boucle agentique (agent.py), avec un faux modèle."""

from pathlib import Path

import pytest

from llamagent.agent import build_system_prompt, describe_harness, run_turn
from llamagent.tools import ToolContext


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
    return ToolContext(workdir=tmp_path, skills_dirs=[tmp_path / "skills"], confirm=lambda question: True)


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


def test_max_tours(ctx):
    # Le modèle demande des outils sans jamais conclure.
    replies = [tool_call("read_file", path="notes.txt"), tool_call("list_files", path=".")] * 5
    chat = FakeChat(replies)
    resultat = run_turn(chat, [{"role": "user", "content": "?"}], ctx, max_tours=4)
    assert "limite de 4 tours" in resultat
    assert len(chat.calls) == 4


def test_appel_repete_detecte(ctx):
    chat = FakeChat([tool_call("read_file", path="notes.txt"), tool_call("read_file", path="notes.txt"), answer("fini")])
    messages = [{"role": "user", "content": "?"}]
    run_turn(chat, messages, ctx)
    tool_results = [m["content"] for m in messages if m["role"] == "tool"]
    assert tool_results[0] == "12, 15, 9"
    assert "déjà d'appeler read_file" in tool_results[1]


def test_outil_inconnu_ne_plante_pas(ctx):
    chat = FakeChat([tool_call("search_web", query="x"), answer("désolé")])
    messages = [{"role": "user", "content": "?"}]
    assert run_turn(chat, messages, ctx) == "désolé"
    assert "Outils valides" in messages[2]["content"]


def test_resultat_long_tronque(ctx):
    (ctx.workdir / "gros.txt").write_text("x" * 50_000, encoding="utf-8")
    chat = FakeChat([tool_call("read_file", path="gros.txt"), answer("ok")])
    messages = [{"role": "user", "content": "?"}]
    run_turn(chat, messages, ctx)
    assert len(messages[2]["content"]) < 5_000
    assert "tronqués" in messages[2]["content"]


def test_prompt_systeme_rempli():
    template = "OS={os} shell={shell} dossier={workdir}\n{skills}"
    prompt = build_system_prompt(template, Path("/projet"), {"corriger-un-bug": "Méthode."})
    assert "{" not in prompt
    assert "- corriger-un-bug : Méthode." in prompt


def test_prompt_systeme_avec_agents_md():
    prompt = build_system_prompt("{os}{shell}{workdir}{skills}", Path("/projet"), {}, "Utilise des tabulations.")
    assert prompt.endswith("## Instructions du projet (AGENTS.md)\nUtilise des tabulations.")


def test_vrai_prompt_et_vraies_skills():
    """Le fichier prompts/AGENT.md et les skills du dépôt se chargent bien."""
    from llamagent.config import PROMPTS_DIR, SKILLS_DIR
    from llamagent.tools import available_skills

    template = (PROMPTS_DIR / "AGENT.md").read_text(encoding="utf-8")
    skills = available_skills([SKILLS_DIR])
    assert set(skills) == {"corriger-un-bug", "ecrire-tests-pytest"}
    prompt = build_system_prompt(template, Path("/projet"), skills)
    assert "corriger-un-bug" in prompt and "{skills}" not in prompt


def test_ce_que_fait_le_harness(ctx):
    assert "confirmation" in describe_harness("edit_file", {"path": "a.py"}, ctx, repeated=False)
    assert "confirmation" in describe_harness("run_command", {"command": "python a.py"}, ctx, repeated=False)
    ctx.allowed_commands = ["python a.py"]
    assert "sans confirmation" in describe_harness("run_command", {"command": "python a.py"}, ctx, repeated=False)
    assert "inconnu" in describe_harness("search_web", {}, ctx, repeated=False)
    assert "pas exécuté" in describe_harness("read_file", {"path": "a.py"}, ctx, repeated=True)