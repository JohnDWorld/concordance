"""Ingestion Parlement européen : groupes, votes et positions par groupe, depuis HowTheyVote.eu (ODbL)."""

import csv
import gzip
import json
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from datetime import date, datetime
from pathlib import Path

from concordance import db
from concordance.ingest.raw import USER_AGENT, download
from concordance.models import Ballot, GroupPosition, ParlGroup
from concordance.rules import majority

RELEASES = "https://github.com/HowTheyVote/data/releases"
LATEST = "https://api.github.com/repos/HowTheyVote/data/releases/latest"
FILES = ("votes", "member_votes", "groups", "group_memberships", "national_parties")
COUNTRY = "FRA"  # délégations nationales suivies : celles des partis français
POSITIONS = {"FOR": "pour", "AGAINST": "contre", "ABSTENTION": "abstention", "DID_NOT_VOTE": "non_votants"}
Row = dict[str, str]


def latest_tag() -> str:
    request = urllib.request.Request(LATEST, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        tag: str = json.load(response)["tag_name"]
    return tag


def rows(path: Path) -> Iterator[Row]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def term_starts(memberships: Iterable[Row]) -> dict[int, date]:
    """Début de chaque législature, déduit des appartenances aux groupes (aucune date codée en dur)."""
    starts: dict[int, date] = {}
    for r in memberships:
        term, start = int(r["term"]), date.fromisoformat(r["start_date"])
        starts[term] = min(start, starts.get(term, start))
    return starts


def term_of(when: date, starts: dict[int, date]) -> int:
    return max(term for term, start in starts.items() if start <= when)


def parse_groups(groups: Iterable[Row], memberships: Iterable[Row]) -> list[ParlGroup]:
    """Un groupe par législature où il a des membres, avec la période couverte par ces membres."""
    labels = {g["code"]: g for g in groups}
    spans: dict[tuple[int, str], tuple[date, date | None]] = {}
    for r in memberships:
        key = (int(r["term"]), r["group_code"])
        start, end = date.fromisoformat(r["start_date"]), date.fromisoformat(r["end_date"]) if r["end_date"] else None
        if key in spans:
            old_start, old_end = spans[key]
            start = min(start, old_start)
            end = None if end is None or old_end is None else max(end, old_end)
        spans[key] = (start, end)
    return [
        ParlGroup(
            chamber="pe",
            legislature=term,
            external_id=code,
            sigle=labels[code]["short_label"],
            libelle=labels[code]["official_label"] or labels[code]["label"],
            start_date=start,
            end_date=end,
        )
        for (term, code), (start, end) in spans.items()
    ]


def delegation_id(party_id: str) -> str:
    return f"{COUNTRY}-{party_id}"


def parse_ballots(
    votes: Iterable[Row], member_votes: Iterable[Row], parties: Iterable[Row], starts: dict[int, date]
) -> tuple[list[Ballot], list[ParlGroup], int]:
    """Votes, positions par groupe et par délégation nationale française, et nombre de votes individuels sans groupe.

    Une délégation existe pour une législature dès qu'un eurodéputé du parti y vote ; sa période va de son
    premier à son dernier vote.
    """
    votes = list(votes)  # parcourus deux fois
    days = {v["id"]: datetime.fromisoformat(v["timestamp"]).date() for v in votes}
    counts: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    seen: dict[tuple[int, str], tuple[date, date]] = {}
    without_group = 0
    for r in member_votes:
        position = POSITIONS[r["position"]]
        if r["group_code"]:
            counts[r["vote_id"]][r["group_code"]][position] += 1
        else:
            without_group += 1
        if r["country_code"] == COUNTRY and r["national_party_id"]:
            counts[r["vote_id"]][delegation_id(r["national_party_id"])][position] += 1
            when = days[r["vote_id"]]
            key = (term_of(when, starts), r["national_party_id"])
            first, last = seen.get(key, (when, when))
            seen[key] = (min(first, when), max(last, when))
    labels = {p["id"]: p for p in parties}
    delegations = [
        ParlGroup(
            chamber="pe",
            legislature=term,
            external_id=delegation_id(party),
            sigle=labels[party]["short_label"],
            libelle=labels[party]["label"],
            start_date=first,
            end_date=last,
            categorie="delegation_nationale",
        )
        for (term, party), (first, last) in seen.items()
    ]
    ballots = []
    for v in votes:
        when = days[v["id"]]
        positions = [
            GroupPosition(
                group_external_id=group,
                membres=sum(c.values()),
                pour=c["pour"],
                contre=c["contre"],
                abstention=c["abstention"],
                non_votants=c["non_votants"],
                non_votants_volontaires=None,
                position_majoritaire=majority(c["pour"], c["contre"], c["abstention"]),
            )
            for group, c in counts[v["id"]].items()
        ]
        ballots.append(Ballot(
            chamber="pe",
            legislature=term_of(when, starts),
            external_id=v["id"],
            ballot_date=when,
            intitule=v["display_title"],
            objet=v["description"] or v["amendment_subject"] or None,
            nature="amendement" if v["amendment_number"] else "texte_entier" if v["is_main"] == "True" else None,
            sort={"ADOPTED": "adopté", "REJECTED": "rejeté"}.get(v["result"]),  # vide dans la source pour une majorité de votes
            dossier=v["procedure_title"] or v["procedure_reference"] or None,
            seance_ref=None,
            source_url=f"https://howtheyvote.eu/votes/{v['id']}",
            positions=positions,
        ))
    return ballots, delegations, without_group


def main() -> None:
    tag = latest_tag()
    paths = {name: download(f"{RELEASES}/download/{tag}/{name}.csv.gz", Path(f"pe/{tag}/{name}.csv.gz")) for name in FILES}
    starts = term_starts(rows(paths["group_memberships"]))
    groups = parse_groups(rows(paths["groups"]), rows(paths["group_memberships"]))
    ballots, delegations, without_group = parse_ballots(
        rows(paths["votes"]), rows(paths["member_votes"]), rows(paths["national_parties"]), starts)
    with db.connect() as conn:
        db.load_votes(conn, "pe", groups + delegations, ballots)
    print(f"PE ({tag}) : {len(groups)} groupes, {len(delegations)} délégations françaises, {len(ballots)} votes, "
          f"{sum(len(b.positions) for b in ballots)} positions")
    print(f"Législatures : {', '.join(f'{t} depuis le {d}' for t, d in sorted(starts.items()))} ; votes individuels sans groupe : {without_group}")


if __name__ == "__main__":
    main()
