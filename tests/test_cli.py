"""Tests de la ligne de commande (cli.py)."""

from importlib.metadata import version

import pytest

from llamagent.cli import parse_args


def test_version(capsys):
    with pytest.raises(SystemExit):
        parse_args(["--version"])
    assert capsys.readouterr().out.strip() == f"llamagent {version('llamagent')}"


def test_options():
    args = parse_args(["-m", "qwen3.5:9b", "-t", "0.5", "-c", "Corrige", "le", "bug"])
    assert (args.model, args.temperature, args.resume) == ("qwen3.5:9b", 0.5, True)
    assert args.demande == ["Corrige", "le", "bug"]


def test_prompts_et_skills_dans_le_paquet():
    from llamagent.config import PACKAGE_DIR, PROMPTS_DIR, SKILLS_DIR

    assert PROMPTS_DIR.parent == SKILLS_DIR.parent == PACKAGE_DIR  # installés avec le code
    assert (PROMPTS_DIR / "AGENT.md").is_file() and (PROMPTS_DIR / "COMPACT.md").is_file()