# -*- coding: utf-8 -*-
"""Regenere app/data/prix_reference.json a partir du classeur des MI et PTF.

Ce fichier JSON est le point de depart de la page "Historique des prix" : il
est charge en base au demarrage de l'application. A relancer apres chaque mise
a jour du classeur, puis committer le JSON produit :

    cd app/backend
    python tools/import_prix_reference.py "C:/chemin/Tableau des MI ET PTF- ADOC.xlsx"

L'administrateur peut aussi envoyer directement le classeur depuis l'onglet
Administration de l'application, ce qui evite ce script au quotidien.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.price_import import read_workbook  # noqa: E402

DEST = Path(__file__).resolve().parent.parent / "app" / "data" / "prix_reference.json"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    source = Path(sys.argv[1])
    if not source.exists():
        print("Classeur introuvable : %s" % source)
        return 1

    marches = read_workbook(source)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(
        json.dumps({"source": source.name, "marches": marches}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    offres = sum(len(m["offres"]) for m in marches)
    print("%d marches, %d offres chiffrees -> %s" % (len(marches), offres, DEST))

    suspects = [
        (m["objet"][:60], o["nom"], o["montant_texte"])
        for m in marches for o in m["offres"] if o["montant_incertain"]
    ]
    if suspects:
        print("\n%d montant(s) illisibles, a corriger dans le classeur :" % len(suspects))
        for objet, nom, texte in suspects:
            print("  - %s... | %s : %r" % (objet, nom, texte))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
