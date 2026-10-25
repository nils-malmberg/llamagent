"""Vérifie le paquet construit avant de le publier (étape 18).

    python scripts/check_package.py            # le contenu du paquet (dist/)
    python scripts/check_package.py v0.1.0     # et l'étiquette correspond à la version
"""

import sys
import tomllib
import zipfile
from pathlib import Path

# Fichiers sans lesquels llamagent ne démarre pas : s'ils manquent dans le
# paquet, il s'installe sans erreur mais plante au premier lancement.
REQUIRED = [
    "llamagent/cli.py",
    "llamagent/prompts/AGENT.md",
    "llamagent/prompts/COMPACT.md",
    "llamagent/skills/corriger-un-bug.md",
    "llamagent/skills/ecrire-tests-pytest.md",
]


def main() -> None:
    version = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if len(sys.argv) > 1 and sys.argv[1] != f"v{version}":
        sys.exit(f"L'étiquette {sys.argv[1]} ne correspond pas à la version v{version} de pyproject.toml.")
    wheels = list(Path("dist").glob(f"llamagent-{version}-*.whl"))
    if len(wheels) != 1:
        sys.exit(f"Un seul paquet llamagent-{version} attendu dans dist/, trouvé : {[w.name for w in wheels]}")
    names = zipfile.ZipFile(wheels[0]).namelist()
    missing = [name for name in REQUIRED if name not in names]
    if missing:
        sys.exit(f"Fichiers absents du paquet : {', '.join(missing)}")
    print(f"{wheels[0].name} : {len(names)} fichiers, prompts et skills présents.")


if __name__ == "__main__":
    main()