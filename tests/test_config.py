"""Tests de la configuration (config.py)."""

import pytest

from mini_agent import config as config_module
from mini_agent.config import DEFAULT_OLLAMA_MODEL, load_config


@pytest.fixture(autouse=True)
def environnement_propre(monkeypatch, tmp_path):
    """Chaque test part sans variables d'environnement ni fichier global."""
    for name in ("OLLAMA_URL", "OLLAMA_MODEL", "MINI_AGENT_WORKDIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config_module, "USER_CONFIG", tmp_path / "global" / "config.toml")
    monkeypatch.chdir(tmp_path)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_valeurs_par_defaut(monkeypatch, tmp_path):
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434/")
    config = load_config()
    assert config.model == DEFAULT_OLLAMA_MODEL
    assert config.chat_url == "http://localhost:11434/api/chat"  # "/" final retiré
    assert config.workdir == tmp_path.resolve()


def test_dossier_de_travail_inexistant(monkeypatch, tmp_path):
    monkeypatch.setenv("MINI_AGENT_WORKDIR", str(tmp_path / "absent"))
    with pytest.raises(SystemExit, match="Dossier de travail introuvable"):
        load_config()


def test_ordre_des_sources(monkeypatch, tmp_path):
    write(config_module.USER_CONFIG, 'model = "global"\ntemperature = 0.5\nnum_ctx = 4096\n')
    write(tmp_path / ".mini-agent" / "config.toml", 'model = "projet"\ntemperature = 0.7\n')
    monkeypatch.setenv("OLLAMA_MODEL", "variable")
    config = load_config({"temperature": 0.9, "model": None})  # option non donnée : None
    assert config.num_ctx == 4096  # fichier global
    assert config.model == "variable"  # la variable d'environnement bat les fichiers
    assert config.temperature == 0.9  # l'option de ligne de commande bat tout


def test_commandes_autorisees_depuis_le_fichier(tmp_path):
    write(tmp_path / ".mini-agent" / "config.toml", 'allowed_commands = ["python -m pytest", "git status"]\n')
    assert load_config().allowed_commands == ("python -m pytest", "git status")


def test_reglage_inconnu(tmp_path):
    write(tmp_path / ".mini-agent" / "config.toml", "temperatur = 0.5\n")
    with pytest.raises(SystemExit, match="Réglage inconnu.*temperatur"):
        load_config()


def test_fichier_toml_invalide(tmp_path):
    write(tmp_path / ".mini-agent" / "config.toml", "model = \n")
    with pytest.raises(SystemExit, match="Fichier de réglages invalide"):
        load_config()


def test_valeur_invalide(tmp_path):
    write(tmp_path / ".mini-agent" / "config.toml", 'temperature = "chaud"\n')
    with pytest.raises(SystemExit, match="Réglage invalide"):
        load_config()