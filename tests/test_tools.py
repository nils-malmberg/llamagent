"""Tests des outils et du registre (tools.py)."""

import pytest

from mini_agent.tools import TOOLS, ToolContext, available_skills, execute_tool, tool_schemas


@pytest.fixture
def ctx(tmp_path):
    """Un dossier de travail temporaire, où l'utilisateur répond toujours « oui »."""
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "demo.md").write_text(
        "---\ndescription: Une skill de test.\n---\n# Demo\nFais ceci.\n", encoding="utf-8"
    )
    return ToolContext(workdir=tmp_path, skills_dir=tmp_path / "skills", confirm=lambda question: True)


def test_cinq_outils_maximum():
    assert len(TOOLS) <= 5
    assert [s["function"]["name"] for s in tool_schemas()] == list(TOOLS)


def test_read_file(ctx):
    (ctx.workdir / "a.txt").write_text("contenu é", encoding="utf-8")
    assert execute_tool("read_file", {"path": "a.txt"}, ctx) == "contenu é"


def test_read_file_hors_du_dossier_refuse(ctx):
    assert execute_tool("read_file", {"path": "../x.txt"}, ctx).startswith("Refusé")


def test_list_files_ignore_dossiers_caches(ctx):
    (ctx.workdir / "src").mkdir()
    (ctx.workdir / "src" / "main.py").write_text("", encoding="utf-8")
    (ctx.workdir / ".venv").mkdir()
    (ctx.workdir / ".venv" / "lib.py").write_text("", encoding="utf-8")
    (ctx.workdir / "__pycache__").mkdir()
    (ctx.workdir / "__pycache__" / "x.pyc").write_text("", encoding="utf-8")
    resultat = execute_tool("list_files", {}, ctx)
    assert "src/main.py" in resultat.splitlines()  # toujours des "/"
    assert ".venv" not in resultat
    assert "__pycache__" not in resultat


def test_list_files_dossier_inexistant(ctx):
    # Un dossier absent ne doit pas passer pour un dossier vide.
    (ctx.workdir / "a.txt").write_text("", encoding="utf-8")
    for path in ("mini-agent", "a.txt"):
        assert "n'est pas un dossier existant" in execute_tool("list_files", {"path": path}, ctx)


def test_write_file_avec_confirmation(ctx):
    questions = []
    ctx.confirm = lambda question: questions.append(question) or True
    resultat = execute_tool("write_file", {"path": "dir/b.txt", "content": "ligne 1\nligne 2\n"}, ctx)
    assert resultat.startswith("Fichier dir/b.txt écrit")
    assert (ctx.workdir / "dir" / "b.txt").read_text(encoding="utf-8") == "ligne 1\nligne 2\n"
    assert "+ligne 1" in questions[0]  # l'utilisateur a vu le diff


def test_write_file_refuse_par_l_utilisateur(ctx):
    ctx.confirm = lambda question: False
    resultat = execute_tool("write_file", {"path": "b.txt", "content": "x"}, ctx)
    assert resultat.startswith("Refusé")
    assert not (ctx.workdir / "b.txt").exists()


def test_run_command(ctx):
    resultat = execute_tool("run_command", {"command": 'python -c "print(\'bonjour é\')"'}, ctx)
    assert "code de sortie : 0" in resultat
    assert "bonjour é" in resultat


def test_run_command_refusee(ctx):
    ctx.confirm = lambda question: False
    assert execute_tool("run_command", {"command": "echo x"}, ctx).startswith("Refusé")


def test_run_command_timeout(ctx):
    ctx.command_timeout = 1
    resultat = execute_tool("run_command", {"command": 'python -c "import time; time.sleep(5)"'}, ctx)
    assert "dépassé 1 s" in resultat


def test_run_command_sans_clavier(ctx):
    # Un programme qui attend une saisie reçoit « fin de fichier » au lieu de bloquer.
    resultat = execute_tool("run_command", {"command": 'python -c "input()"'}, ctx)
    assert "EOFError" in resultat


def test_load_skill(ctx):
    assert "Fais ceci." in execute_tool("load_skill", {"name": "demo"}, ctx)
    assert available_skills(ctx.skills_dir) == {"demo": "Une skill de test."}


def test_load_skill_inconnue(ctx):
    resultat = execute_tool("load_skill", {"name": "../secret"}, ctx)
    assert resultat.startswith("Refusé")
    assert "demo" in resultat  # la liste des skills valides est donnée


def test_outil_inconnu_donne_la_liste(ctx):
    resultat = execute_tool("delete_everything", {}, ctx)
    assert "outil inconnu" in resultat
    assert "read_file" in resultat


def test_argument_manquant(ctx):
    assert "argument manquant pour read_file : path" in execute_tool("read_file", {}, ctx)


def test_argument_inconnu(ctx):
    assert "argument inconnu" in execute_tool("read_file", {"path": "a", "encoding": "utf-8"}, ctx)


def test_arguments_en_texte_json(ctx):
    (ctx.workdir / "a.txt").write_text("ok", encoding="utf-8")
    assert execute_tool("read_file", '{"path": "a.txt"}', ctx) == "ok"


def test_arguments_json_invalide(ctx):
    assert "pas du JSON valide" in execute_tool("read_file", "{path: a.txt", ctx)


def test_exception_python_renvoyee_au_modele(ctx):
    resultat = execute_tool("read_file", {"path": "absent.txt"}, ctx)
    assert resultat.startswith("Erreur pendant read_file : FileNotFoundError")