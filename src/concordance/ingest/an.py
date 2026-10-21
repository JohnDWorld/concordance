"""Ingestion Assemblée nationale : groupes politiques (AMO30), scrutins et positions par groupe."""

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any

import psycopg

from concordance import db
from concordance.ingest.raw import download
from concordance.models import Ballot, GroupPosition, Nature, ParlGroup

BASE = "https://data.assemblee-nationale.fr/static/openData/repository"
SCRUTINS = BASE + "/{leg}/loi/scrutins/Scrutins.json.zip"
AMO30 = BASE + "/17/amo/tous_acteurs_mandats_organes_xi_legislature/AMO30_tous_acteurs_tous_mandats_tous_organes_historique.json.zip"
CONGRES = "SSG"  # séance commune aux deux chambres, groupes du Sénat inclus : hors périmètre AN
MISSING_GROUP = "PO0"  # défaut de la source (docs/sources.md) : position sans groupe identifiable


def nature(titre: str, code_type_vote: str) -> Nature | None:
    """Nature du scrutin déduite du début de l'intitulé (docs/methodologie.md). None si rien ne correspond."""
    t = titre.replace("’", "'").lower()
    if code_type_vote == "MOC" or t.startswith("la motion"):
        return "motion"
    if t.startswith(("l'amendement", "le sous-amendement", "les amendements")):
        return "amendement"
    if t.startswith("l'article"):
        return "article"
    if t.startswith("l'ensemble"):
        return "texte_entier"
    return None


def parse_group(organe: dict[str, Any], legislatures: set[int]) -> ParlGroup | None:
    if organe.get("codeType") != "GP" or int(organe.get("legislature") or 0) not in legislatures:
        return None
    return ParlGroup(
        chamber="an",
        legislature=organe["legislature"],
        external_id=organe["uid"],
        sigle=organe.get("libelleAbrege"),
        libelle=organe["libelle"],
        start_date=organe["viMoDe"]["dateDebut"],
        end_date=organe["viMoDe"]["dateFin"],
    )


def parse_ballot(s: dict[str, Any]) -> Ballot:
    positions = []
    for g in s["ventilationVotes"]["organe"]["groupes"]["groupe"]:
        v = g["vote"]["decompteVoix"]
        expressed = int(v["pour"]) + int(v["contre"]) + int(v["abstentions"])
        positions.append(GroupPosition(
            group_external_id=g["organeRef"],
            membres=g["nombreMembresGroupe"],
            pour=v["pour"],
            contre=v["contre"],
            abstention=v["abstentions"],
            non_votants=v["nonVotants"],
            non_votants_volontaires=v.get("nonVotantsVolontaires"),
            # La source renseigne une position même sans aucun vote exprimé (motion de censure : seuls
            # les « pour » sont décomptés). Rapporter ce champ ferait dire au groupe ce qu'il n'a pas voté.
            position_majoritaire=g["vote"]["positionMajoritaire"] if expressed else None,
        ))
    objet = s["objet"]["libelle"]
    return Ballot(
        chamber="an",
        legislature=s["legislature"],
        external_id=s["uid"],
        ballot_date=s["dateScrutin"],
        intitule=s["titre"],
        objet=objet if objet != s["titre"] else None,
        nature=nature(s["titre"], s["typeVote"]["codeTypeVote"]),
        sort=s["sort"]["code"],
        dossier=(s["objet"].get("dossierLegislatif") or {}).get("libelle"),
        seance_ref=s["seanceRef"],
        source_url=f"https://www.assemblee-nationale.fr/dyn/{s['legislature']}/scrutins/{s['numero']}",
        positions=positions,
    )


def load(conn: psycopg.Connection[Any], groups: list[ParlGroup], ballots: list[Ballot]) -> int:
    """Charge le tout et renvoie le nombre de positions ignorées faute de groupe identifiable."""
    with conn.cursor() as cur:
        db.upsert(cur, "parl_groups", [g.model_dump() for g in groups], ("chamber", "legislature", "external_id"))
        db.upsert(cur, "ballots", [b.model_dump(exclude={"positions"}) for b in ballots], ("chamber", "external_id"))
        cur.execute("select legislature, external_id, id from concordance.parl_groups where chamber = 'an'")
        group_ids = {(leg, ext): id_ for leg, ext, id_ in cur}
        cur.execute("select external_id, id from concordance.ballots where chamber = 'an'")
        ballot_ids = dict(cur.fetchall())
        rows = [
            {
                **p.model_dump(exclude={"group_external_id"}),
                "ballot_id": ballot_ids[b.external_id],
                "group_id": group_ids[(b.legislature, p.group_external_id)],
            }
            for b in ballots
            for p in b.positions
            if p.group_external_id != MISSING_GROUP
        ]
        db.upsert(cur, "group_positions", rows, ("ballot_id", "group_id"))
    return sum(len(b.positions) for b in ballots) - len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legislatures", type=int, nargs="+", required=True)
    legislatures = set(parser.parse_args().legislatures)

    with zipfile.ZipFile(download(AMO30, Path("an/AMO30.json.zip"))) as zf:
        organes = (json.loads(zf.read(n))["organe"] for n in zf.namelist() if "/organe/" in n)
        groups = [g for o in organes if (g := parse_group(o, legislatures))]
    ballots, congres = [], 0
    for leg in sorted(legislatures):
        with zipfile.ZipFile(download(SCRUTINS.format(leg=leg), Path(f"an/{leg}/Scrutins.json.zip"))) as zf:
            for name in zf.namelist():
                if not name.endswith(".json"):
                    continue
                s = json.loads(zf.read(name))["scrutin"]
                if s["typeVote"]["codeTypeVote"] == CONGRES:
                    congres += 1
                else:
                    ballots.append(parse_ballot(s))

    with db.connect() as conn:
        skipped = load(conn, groups, ballots)
    positions = sum(len(b.positions) for b in ballots) - skipped
    print(f"AN : {len(groups)} groupes, {len(ballots)} scrutins, {positions} positions")
    print(f"Ignorés : {congres} scrutin(s) du Congrès, {skipped} position(s) sans groupe ({MISSING_GROUP})")


if __name__ == "__main__":
    main()
