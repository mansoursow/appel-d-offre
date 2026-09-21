# -*- coding: utf-8 -*-
"""Historique des prix : chargement en base, filtrage et statistiques.

But metier : pour un futur marche du meme type, savoir ce que le cabinet a
propose par le passe et ce que les concurrents proposent d'habitude.

Deux sources alimentent la base :
  - app/data/prix_reference.json, produit par tools/import_prix_reference.py
    et committe avec le code : c'est l'amorce, chargee a chaque demarrage ;
  - un classeur envoye par l'administrateur depuis l'application, qui remplace
    integralement le contenu (voir replace_from_workbook).
"""
from __future__ import annotations

import json
import statistics
import unicodedata
from pathlib import Path

from sqlalchemy.orm import Session

from . import config
from .models import PriceMarket, PriceOffer
from .price_import import canonical, read_workbook
from .workflow_schemas import (
    CompetitorStatOut,
    NatureBenchmarkOut,
    NatureOptionOut,
    PriceHistoryOut,
    PriceMarketOut,
    PriceOfferOut,
)

SEED_FILE = Path(__file__).resolve().parent / "data" / "prix_reference.json"


# --------------------------------------------------------------------------
# Chargement
# --------------------------------------------------------------------------
def _add_marche(db: Session, data: dict) -> PriceMarket:
    marche = PriceMarket(
        cle=data["cle"],
        annee=data["annee"],
        date=data.get("date"),
        objet=data["objet"],
        structure=data.get("structure"),
        methode=data.get("methode"),
        attributaire=data.get("attributaire"),
        observations=data.get("observations"),
        participants_bruts=data.get("participants_bruts"),
    )
    for offre in data.get("offres", []):
        marche.offres.append(PriceOffer(
            nom=offre["nom"],
            cle=offre.get("cle") or canonical(offre["nom"]),
            montant=offre.get("montant"),
            montant_texte=offre.get("montant_texte"),
            note=offre.get("note"),
            est_adoc=bool(offre.get("est_adoc")),
            est_attributaire=bool(offre.get("est_attributaire")),
        ))
    db.add(marche)
    return marche


def seed_price_references(db: Session) -> int:
    """Charge le JSON committe, sans jamais toucher a ce qui est deja en base.

    Idempotent : seuls les marches dont la cle est absente sont ajoutes. Un
    classeur plus recent envoye par l'administrateur n'est donc pas ecrase au
    redeploiement suivant.
    """
    if not SEED_FILE.exists():
        return 0
    try:
        payload = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0

    existantes = {cle for (cle,) in db.query(PriceMarket.cle).all()}
    ajoutes = 0
    for data in payload.get("marches", []):
        if data.get("cle") in existantes:
            continue
        _add_marche(db, data)
        ajoutes += 1
    if ajoutes:
        db.commit()
    return ajoutes


def replace_from_workbook(db: Session, source) -> int:
    """Remplace tout l'historique par le contenu d'un classeur envoye.

    Remplacement complet et non fusion : le classeur est la reference unique,
    une ligne corrigee ou supprimee dans Excel doit se refleter a l'identique.
    """
    marches = read_workbook(source)
    if not marches:
        return 0
    db.query(PriceOffer).delete(synchronize_session=False)
    db.query(PriceMarket).delete(synchronize_session=False)
    for data in marches:
        _add_marche(db, data)
    db.commit()
    return len(marches)


# --------------------------------------------------------------------------
# Lecture
# --------------------------------------------------------------------------
def _sans_accent(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _serialize(marche: PriceMarket) -> PriceMarketOut:
    montant_adoc = next(
        (o.montant for o in marche.offres if o.est_adoc and o.montant is not None), None
    )
    montant_gagnant = next(
        (o.montant for o in marche.offres if o.est_attributaire and o.montant is not None), None
    )

    offres = []
    for offre in marche.offres:
        ecart = None
        if montant_adoc and offre.montant is not None and not offre.est_adoc:
            ecart = round(100.0 * (offre.montant - montant_adoc) / montant_adoc, 1)
        offres.append(PriceOfferOut(
            nom=offre.nom,
            montant=offre.montant,
            montant_texte=offre.montant_texte,
            note=offre.note,
            est_adoc=offre.est_adoc,
            est_attributaire=offre.est_attributaire,
            ecart_adoc_pct=ecart,
        ))
    # Le moins cher d'abord : c'est l'ordre dans lequel on lit un depouillement.
    offres.sort(key=lambda o: (o.montant is None, o.montant or 0))

    chiffrees = sorted(o.montant for o in marche.offres if o.montant is not None)
    rang = chiffrees.index(montant_adoc) + 1 if montant_adoc in chiffrees else None
    moins_disant = chiffrees[0] if chiffrees else None

    # La nature est deduite de l'objet a chaque lecture plutot que stockee :
    # affiner la liste de mots-cles dans config.py reclasse aussitot tout
    # l'historique, sans reimport ni migration de base.
    nature = config.market_nature(marche.objet, marche.structure or "")

    return PriceMarketOut(
        id=marche.id,
        annee=marche.annee,
        date=marche.date,
        objet=marche.objet,
        structure=marche.structure,
        methode=marche.methode,
        nature=nature,
        nature_label=config.market_nature_label(nature),
        attributaire=marche.attributaire,
        observations=marche.observations,
        participants_bruts=marche.participants_bruts,
        offres=offres,
        montant_adoc=montant_adoc,
        montant_gagnant=montant_gagnant,
        adoc_gagnant=any(o.est_adoc and o.est_attributaire for o in marche.offres),
        rang_adoc=rang,
        nb_offres_chiffrees=len(chiffrees),
        montant_moins_disant=moins_disant,
        # "Moins-disant" n'a de sens que face a au moins un concurrent chiffre.
        adoc_moins_disant=len(chiffrees) > 1 and montant_adoc == moins_disant,
    )


def _competitor_stats(marches: list[PriceMarketOut]) -> list[CompetitorStatOut]:
    """Ce que chaque concurrent a propose, et comment il se situe face a ADOC."""
    agrege: dict[str, dict] = {}

    for marche in marches:
        for offre in marche.offres:
            if offre.est_adoc or offre.montant is None:
                continue
            cle = canonical(offre.nom)
            entree = agrege.setdefault(cle, {
                "nom": offre.nom, "montants": [], "victoires": 0, "ecarts": [], "moins_cher": 0,
            })
            entree["montants"].append(offre.montant)
            if offre.est_attributaire:
                entree["victoires"] += 1
            if offre.ecart_adoc_pct is not None:
                entree["ecarts"].append(offre.ecart_adoc_pct)
                if offre.ecart_adoc_pct < 0:
                    entree["moins_cher"] += 1

    stats = [
        CompetitorStatOut(
            nom=e["nom"],
            marches=len(e["montants"]),
            victoires=e["victoires"],
            montant_min=min(e["montants"]),
            montant_max=max(e["montants"]),
            montant_median=int(statistics.median(e["montants"])),
            comparaisons=len(e["ecarts"]),
            ecart_moyen_pct=round(sum(e["ecarts"]) / len(e["ecarts"]), 1) if e["ecarts"] else None,
            moins_cher_que_adoc=e["moins_cher"],
        )
        for e in agrege.values()
    ]
    # Les concurrents les plus souvent rencontres en premier : ce sont eux
    # dont le comportement de prix est le plus instructif.
    stats.sort(key=lambda s: (-s.marches, -s.victoires, s.nom))
    return stats


def _nature_benchmarks(marches: list[PriceMarketOut]) -> list[NatureBenchmarkOut]:
    """Niveau de prix a battre, nature par nature.

    Les montants ne sont comparables qu'a l'interieur d'une meme nature : un
    commissariat aux comptes et un plan strategique n'ont pas la meme echelle.
    Le "moins-disant" n'est calcule que sur les marches ou au moins deux prix
    sont connus -- sur un marche ou nous sommes seuls chiffres, etre le plus
    bas ne veut rien dire.
    """
    par_nature: dict[str, dict] = {}

    for marche in marches:
        entree = par_nature.setdefault(marche.nature, {
            "label": marche.nature_label, "marches": 0, "compares": 0,
            "adoc": [], "concurrents": [], "moins_disants": [],
            "fois_moins_disant": 0, "victoires": 0,
        })
        entree["marches"] += 1
        if marche.adoc_gagnant:
            entree["victoires"] += 1
        if marche.montant_adoc is not None:
            entree["adoc"].append(marche.montant_adoc)
        entree["concurrents"].extend(
            o.montant for o in marche.offres if not o.est_adoc and o.montant is not None
        )
        if marche.nb_offres_chiffrees > 1 and marche.montant_moins_disant is not None:
            entree["compares"] += 1
            entree["moins_disants"].append(marche.montant_moins_disant)
            if marche.adoc_moins_disant:
                entree["fois_moins_disant"] += 1

    def mediane(valeurs):
        return int(statistics.median(valeurs)) if valeurs else None

    reperes = [
        NatureBenchmarkOut(
            code=code,
            label=e["label"],
            marches=e["marches"],
            marches_compares=e["compares"],
            adoc_median=mediane(e["adoc"]),
            concurrent_min=min(e["concurrents"]) if e["concurrents"] else None,
            concurrent_median=mediane(e["concurrents"]),
            moins_disant_median=mediane(e["moins_disants"]),
            fois_moins_disant=e["fois_moins_disant"],
            victoires=e["victoires"],
        )
        for code, e in par_nature.items()
    ]
    # Les natures les plus documentees d'abord : ce sont celles sur lesquelles
    # le repere de prix a le plus de valeur.
    reperes.sort(key=lambda r: (-r.marches_compares, -r.marches, r.label))
    return reperes


def build_price_history(
    db: Session,
    *,
    search: str | None = None,
    annee: int | None = None,
    methode: str | None = None,
    nature: str | None = None,
    issue: str | None = None,
) -> PriceHistoryOut:
    """Historique filtre + statistiques calculees sur le sous-ensemble affiche."""
    tous = [_serialize(m) for m in db.query(PriceMarket).all()]
    tous.sort(key=lambda m: (m.date or "%d-00-00" % m.annee, m.objet), reverse=True)

    annees = sorted({m.annee for m in tous}, reverse=True)
    methodes = sorted({m.methode for m in tous if m.methode})

    effectifs: dict[str, dict] = {}
    for m in tous:
        entree = effectifs.setdefault(m.nature, {"label": m.nature_label, "n": 0})
        entree["n"] += 1
    natures = sorted(
        (NatureOptionOut(code=code, label=e["label"], marches=e["n"])
         for code, e in effectifs.items()),
        key=lambda n: (-n.marches, n.label),
    )

    retenus = tous
    if annee:
        retenus = [m for m in retenus if m.annee == annee]
    if methode:
        retenus = [m for m in retenus if m.methode == methode]
    if nature:
        retenus = [m for m in retenus if m.nature == nature]
    if issue == "gagnes":
        retenus = [m for m in retenus if m.adoc_gagnant]
    elif issue == "perdus":
        retenus = [m for m in retenus if not m.adoc_gagnant]
    if search:
        # La recherche porte aussi sur les noms des participants : "combien
        # propose Mazars d'habitude ?" doit ramener les marches ou il figure.
        besoin = _sans_accent(search).split()
        def correspond(m: PriceMarketOut) -> bool:
            foin = _sans_accent(" ".join(filter(None, [
                m.objet, m.structure, m.attributaire, m.methode,
                " ".join(o.nom for o in m.offres),
            ])))
            return all(mot in foin for mot in besoin)
        retenus = [m for m in retenus if correspond(m)]

    return PriceHistoryOut(
        marches=retenus,
        concurrents=_competitor_stats(retenus),
        reperes=_nature_benchmarks(retenus),
        annees=annees,
        methodes=methodes,
        natures=natures,
        total_marches=len(tous),
        marches_gagnes=sum(1 for m in retenus if m.adoc_gagnant),
    )
