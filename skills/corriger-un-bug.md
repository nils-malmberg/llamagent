---
description: Méthode pour trouver et corriger un bug dans un script Python.
---
# Corriger un bug

1. Lance le script avec run_command pour voir l'erreur ou le résultat faux.
2. Lis le fichier concerné avec read_file.
3. Trouve la cause exacte : la ligne fautive et pourquoi elle est fausse.
4. Corrige avec edit_file en changeant le moins de choses possible :
   old_text = les lignes fautives copiées exactement, new_text = les lignes corrigées.
5. Relance le script avec run_command pour vérifier que le bug a disparu.
6. Réponds en expliquant : la cause du bug, la correction, la vérification.