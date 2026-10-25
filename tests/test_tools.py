"""Tests des outils et du registre (tools.py)."""

import time

import pytest

from llamagent.tools import TOOLS, ToolContext, available_skills, execute_tool, tool_schemas


@pytest.fixture
def ctx(tmp_path):
    """Un dossier de travail temporaire, où l'utilisateur répond toujours « oui »."""
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "demo.md").write_text(
        "---\ndescription: Une skill de test.\n---\n# Demo\nFais ceci.\n", encoding="utf-8"
    )
    return ToolContext(workdir=tmp_path, skills_dirs=[tmp_path / "skills"], confirm=lambda question: True)


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
    for path in ("llamagent", "a.txt"):
        assert "n'est pas un dossier existant" in execute_tool("list_files", {"path": path}, ctx)


def test_edit_file_cree_un_fichier(ctx):
    questions = []
    ctx.confirm = lambda question: questions.append(question) or True
    resultat = execute_tool("edit_file", {"path": "dir/b.txt", "old_text": "", "new_text": "ligne 1\nligne 2\n"}, ctx)
    assert resultat == "Fichier dir/b.txt créé."
    assert (ctx.workdir / "dir" / "b.txt").read_text(encoding="utf-8") == "ligne 1\nligne 2\n"
    assert "+ligne 1" in questions[0]  # l'utilisateur a vu le diff


def test_edit_file_remplace_un_passage(ctx):
    (ctx.workdir / "c.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
    resultat = execute_tool("edit_file", {"path": "c.py", "old_text": "b = 2", "new_text": "b = 20"}, ctx)
    assert resultat == "Fichier c.py modifié."
    assert (ctx.workdir / "c.py").read_text(encoding="utf-8") == "a = 1\nb = 20\nc = 3\n"


def test_edit_file_passage_introuvable(ctx):
    (ctx.workdir / "c.py").write_text("a = 1\n", encoding="utf-8")
    assert "old_text introuvable" in execute_tool("edit_file", {"path": "c.py", "old_text": "z = 9", "new_text": ""}, ctx)


def test_edit_file_passage_ambigu(ctx):
    (ctx.workdir / "c.py").write_text("x = 0\nx = 0\n", encoding="utf-8")
    assert "apparaît 2 fois" in execute_tool("edit_file", {"path": "c.py", "old_text": "x = 0", "new_text": "x = 1"}, ctx)


def test_edit_file_ne_recree_pas_un_fichier_existant(ctx):
    (ctx.workdir / "c.py").write_text("a = 1\n", encoding="utf-8")
    assert "existe déjà" in execute_tool("edit_file", {"path": "c.py", "old_text": "", "new_text": "b = 2"}, ctx)
    assert (ctx.workdir / "c.py").read_text(encoding="utf-8") == "a = 1\n"


def test_edit_file_refuse_par_l_utilisateur(ctx):
    ctx.confirm = lambda question: False
    resultat = execute_tool("edit_file", {"path": "b.txt", "old_text": "", "new_text": "x"}, ctx)
    assert resultat.startswith("Refusé")
    assert not (ctx.workdir / "b.txt").exists()


def test_run_command(ctx):
    resultat = execute_tool("run_command", {"command": 'python -c "print(\'bonjour é\')"'}, ctx)
    assert "code de sortie : 0" in resultat
    assert "bonjour é" in resultat


def test_run_command_autorisee_sans_confirmation(ctx):
    ctx.confirm = lambda question: pytest.fail("aucune question ne devait être posée")
    ctx.allowed_commands = ["python -c"]
    assert "code de sortie : 0" in execute_tool("run_command", {"command": 'python -c "print(1)"'}, ctx)


def test_run_command_refusee(ctx):
    ctx.confirm = lambda question: False
    assert execute_tool("run_command", {"command": "echo x"}, ctx).startswith("Refusé")


def test_run_command_timeout(ctx):
    ctx.command_timeout = 1
    resultat = execute_tool("run_command", {"command": 'python -c "import time; time.sleep(5)"'}, ctx)
    assert "dépassé 1 s" in resultat


def test_run_command_timeout_arrete_aussi_les_sous_processus(ctx):
    # parent.py lance enfant.py, qui écrit fini.txt au bout de 3 s. Tuer
    # seulement le shell ne suffit pas : l'enfant survivrait (et, sous
    # Windows, on attendrait sa fin car il garde la sortie ouverte).
    (ctx.workdir / "enfant.py").write_text(
        "import time, pathlib\ntime.sleep(3)\npathlib.Path('fini.txt').write_text('x')\n", encoding="utf-8"
    )
    (ctx.workdir / "parent.py").write_text(
        "import subprocess, sys\nsubprocess.run([sys.executable, 'enfant.py'])\n", encoding="utf-8"
    )
    ctx.command_timeout = 1
    debut = time.monotonic()
    resultat = execute_tool("run_command", {"command": "python parent.py"}, ctx)
    assert "dépassé 1 s" in resultat
    assert time.monotonic() - debut < 3  # pas d'attente de l'enfant
    time.sleep(4)
    assert not (ctx.workdir / "fini.txt").exists()  # l'enfant a bien été arrêté


def test_run_command_sans_clavier(ctx):
    # Un programme qui attend une saisie reçoit « fin de fichier » au lieu de bloquer.
    resultat = execute_tool("run_command", {"command": 'python -c "input()"'}, ctx)
    assert "EOFError" in resultat


def test_load_skill(ctx):
    assert "Fais ceci." in execute_tool("load_skill", {"name": "demo"}, ctx)
    assert available_skills(ctx.skills_dirs) == {"demo": "Une skill de test."}


def test_skill_du_projet_remplace_la_skill_globale(ctx):
    projet = ctx.workdir / ".llamagent" / "skills"
    projet.mkdir(parents=True)
    (projet / "demo.md").write_text("---\ndescription: Version du projet.\n---\nFais cela.\n", encoding="utf-8")
    ctx.skills_dirs = [ctx.workdir / "skills", projet]
    assert available_skills(ctx.skills_dirs) == {"demo": "Version du projet."}
    assert "Fais cela." in execute_tool("load_skill", {"name": "demo"}, ctx)


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