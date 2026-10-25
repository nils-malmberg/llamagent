---
description: Écrire des tests pytest pour un module Python.
---
# Écrire des tests pytest

1. Lis le module à tester avec read_file.
2. Crée un fichier `test_<module>.py` à côté du module avec edit_file (old_text vide).
3. Écris une fonction `test_...` par comportement : un cas normal,
   un cas limite (liste vide, zéro...), un cas d'erreur avec `pytest.raises`.
4. Importe le module avec `from <module> import <fonction>`.
5. Lance `python -m pytest -q` avec run_command.
6. Si un test échoue, vérifie d'abord si c'est le test ou le code qui est faux.
   Ne modifie pas le code testé sans le dire.
7. Réponds avec la liste des tests écrits et le résultat de pytest.