"""Petit script de statistiques sur des notes.

Il contient un bug volontaire : c'est la démo de mini-agent.
"""


def moyenne(notes: list[float]) -> float:
    total = 0
    for i in range(1, len(notes)):
        total += notes[i]
    return total / len(notes)


if __name__ == "__main__":
    notes = [12, 15, 9, 18]
    resultat = moyenne(notes)
    print(f"Moyenne des notes {notes} : {resultat}")
    assert resultat == 13.5, f"moyenne attendue : 13.5, obtenue : {resultat}"
    print("OK")