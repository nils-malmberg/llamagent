"""Tests des garde-fous (guards.py)."""

import pytest

from llamagent.guards import GuardError, ask_confirmation, is_allowed_command, safe_path, truncate


def test_chemin_relatif_accepte(tmp_path):
    assert safe_path(tmp_path, "src/main.py") == (tmp_path / "src" / "main.py").resolve()


def test_point_point_refuse(tmp_path):
    with pytest.raises(GuardError, match=r"\.\."):
        safe_path(tmp_path, "../secret.txt")


def test_point_point_refuse_meme_s_il_reste_dedans(tmp_path):
    with pytest.raises(GuardError):
        safe_path(tmp_path, "src/../main.py")


def test_chemin_absolu_hors_du_dossier_refuse(tmp_path):
    dehors = tmp_path.parent / "ailleurs.txt"
    with pytest.raises(GuardError, match="sort du dossier"):
        safe_path(tmp_path, str(dehors))


def test_chemin_absolu_dans_le_dossier_accepte(tmp_path):
    dedans = tmp_path / "main.py"
    assert safe_path(tmp_path, str(dedans)) == dedans.resolve()


def test_truncate_texte_court_inchange():
    assert truncate("bonjour", 100) == "bonjour"


def test_truncate_garde_debut_et_fin():
    texte = "A" * 50 + "B" * 50 + "C" * 50
    resultat = truncate(texte, 40)
    assert resultat.startswith("A" * 20)
    assert resultat.endswith("C" * 20)
    assert "110 caractères tronqués" in resultat


@pytest.mark.parametrize(
    ("reponse", "attendu"),
    [("o", True), ("oui", True), ("O", True), ("", False), ("n", False), ("non", False), ("y", False)],
)
def test_confirmation(monkeypatch, reponse, attendu):
    monkeypatch.setattr("builtins.input", lambda question: reponse)
    assert ask_confirmation("Continuer ?") is attendu


@pytest.mark.parametrize(
    ("commande", "attendu"),
    [
        ("python -m pytest", True),
        ("python -m pytest -q tests", True),
        ("python -m pytestx", False),  # préfixe d'un autre mot
        ("git status", True),
        ("git push", False),
        ("git status && del *.py", False),  # enchaînement
        ("git status; rm -rf /", False),
        ("python -m pytest > sortie.txt", False),  # redirection
        ("git status | more", False),
    ],
)
def test_commandes_autorisees(commande, attendu):
    assert is_allowed_command(commande, ["python -m pytest", "git status"]) is attendu