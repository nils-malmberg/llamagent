"""Tests de l'interface (ui.py)."""

from collections import namedtuple

import pytest

from mini_agent import ui

Size = namedtuple("Size", "columns lines")


def plain(text):
    return ui.ANSI_CODE.sub("", text)


@pytest.fixture
def couleurs(monkeypatch):
    """Comme dans un vrai terminal : couleurs et caractères Unicode."""
    monkeypatch.setattr(ui, "STYLE", True)
    monkeypatch.setattr(ui, "UNICODE", True)
    monkeypatch.setattr(ui.shutil, "get_terminal_size", lambda fallback=None: Size(100, 40))


@pytest.fixture
def texte_simple(monkeypatch):
    """Comme une sortie redirigée vers un fichier : ni couleurs, ni Unicode."""
    monkeypatch.setattr(ui, "STYLE", False)
    monkeypatch.setattr(ui, "UNICODE", False)
    monkeypatch.setattr(ui.shutil, "get_terminal_size", lambda fallback=None: Size(100, 40))


def test_style_et_longueur_visible(couleurs):
    texte = ui.style("bonjour", ui.BOLD, ui.TEAL)
    assert texte == "\033[1;38;5;38mbonjour\033[0m"
    assert ui.visible_len(texte) == 7


def test_mascotte(couleurs):
    lignes = [plain(ligne) for ligne in ui.mascot()]
    assert lignes == ui.MASCOT
    assert ui.ORANGE in ui.mascot()[0]  # l'antenne est orange


def test_banniere(couleurs):
    banniere = plain(ui.banner([("modèle", "qwen3.5:4b"), ("dossier", "/home/nils/projets/calc")]))
    assert "│o o│   un agent de code minimal autour d’Ollama" in banniere
    assert "┌─┴─┐   mini-agent" in banniere
    assert "  modèle   qwen3.5:4b" in banniere


def test_banniere_raccourcit_les_chemins_longs(couleurs, monkeypatch):
    monkeypatch.setattr(ui.shutil, "get_terminal_size", lambda fallback=None: Size(40, 40))
    banniere = plain(ui.banner([("dossier", "/home/nils/" + "x" * 100 + "/calc")]))
    ligne = banniere.splitlines()[-1]
    assert ligne.endswith("/calc") and "…" in ligne


def test_sans_couleurs_ni_unicode(texte_simple):
    banniere = ui.banner([("modèle", "qwen3.5:4b")])
    assert "\033" not in banniere
    assert "|o o|" in banniere  # la mascotte en ASCII
    assert ui.render_markdown("**gras** et `code`") == "**gras** et `code`"  # Markdown laissé tel quel


def test_les_acteurs_sont_alignes(couleurs):
    lignes = [plain(ui.role_line(nom, "texte")) for nom in ("vous", "modèle", "harness", "outil")]
    assert {ligne.index("texte") for ligne in lignes} == {len(ui.INDENT)}


def test_le_modele_demande(couleurs):
    assert plain(ui.model_asks("edit_file", {"path": "calc.py", "old_text": "a", "new_text": "b"})) == "  modèle   demande edit_file(calc.py, …)"
    assert plain(ui.model_asks("list_files", {})) == "  modèle   demande list_files()"


def test_resultat_de_l_outil(couleurs):
    assert ui.RED in ui.tool_result("Refusé : chemin refusé")
    assert ui.RED not in ui.tool_result("Fichier calc.py modifié.")
    assert plain(ui.tool_result("a\nb\nc", truncated=True)) == "  outil    a  (+2 lignes)  [tronqué]"


def test_traits_de_separation(couleurs):
    assert plain(ui.tour_header(2)).strip().startswith("── tour 2 ──")
    assert "réponse · 3 appels au modèle" in plain(ui.answer_header(3))
    assert "1 appel au modèle" in plain(ui.answer_header(1))


def test_markdown(couleurs):
    lignes = ui.render_markdown("# Titre\n- **gras** et `code`\n```\nprint(1)\n```").splitlines()
    assert plain(lignes[0]) == "Titre"
    assert plain(lignes[1]) == "► gras et code"
    assert plain(lignes[2]) == "│ print(1)"  # les ``` ne sont pas affichés
    assert len(lignes) == 3


def test_jauge_de_contexte(couleurs):
    assert "█████░░░░░" in ui.context_gauge("qwen3.5:4b", 4096, 8192, False)
    assert ui.YELLOW in ui.context_gauge("qwen3.5:4b", 7000, 8192, False)
    plein = ui.context_gauge("qwen3.5:4b", 9000, 8192, False)
    assert ui.RED in plein and "plein" in plein
    assert "≈882 / 2048" in plain(ui.context_gauge("qwen3.5:4b", 882, 2048, True))


def test_confirmation_avec_diff_en_couleurs(couleurs, monkeypatch, capsys):
    questions = []
    monkeypatch.setattr("builtins.input", lambda question: questions.append(question) or "o")
    assert ui.confirm("--- a.py (avant)\n+++ a.py (après)\n-x = 1\n+x = 2\nÉcrire a.py ?") is True
    sortie = capsys.readouterr().out
    assert ui.INDENT + ui.style("-x = 1", ui.RED) in sortie  # aligné sous le texte du harness
    assert ui.style("+x = 2", ui.GREEN) in sortie
    assert "Écrire a.py ?" in questions[0] and "[o/N]" in questions[0]


def test_animation_sans_terminal(texte_simple):
    with ui.thinking():
        pass  # ne fait rien, et surtout ne bloque pas