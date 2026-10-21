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
FILES = ("votes", "member_votes", "groups", "group_memberships")
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


def parse_ballots(votes: Iterable[Row], member_votes: Iterable[Row], starts: dict[int, date]) -> tuple[list[Ballot], int]:
    """Votes et positions agrégées par groupe. Renvoie aussi le nombre de votes individuels sans groupe."""
    counts: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    without_group = 0
    for r in member_votes:
        if not r["group_code"]:
            without_group += 1
            continue
        counts[r["vote_id"]][r["group_code"]][POSITIONS[r["position"]]] += 1
    ballots = []
    for v in votes:
        when = datetime.fromisoformat(v["timestamp"]).date()
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
    return ballots, without_group


def main() -> None:
    tag = latest_tag()
    paths = {name: download(f"{RELEASES}/download/{tag}/{name}.csv.gz", Path(f"pe/{tag}/{name}.csv.gz")) for name in FILES}
    starts = term_starts(rows(paths["group_memberships"]))
    groups = parse_groups(rows(paths["groups"]), rows(paths["group_memberships"]))
    ballots, without_group = parse_ballots(rows(paths["votes"]), rows(paths["member_votes"]), starts)
    with db.connect() as conn:
        db.load_votes(conn, "pe", groups, ballots)
    print(f"PE ({tag}) : {len(groups)} groupes, {len(ballots)} votes, {sum(len(b.positions) for b in ballots)} positions")
    print(f"Législatures : {', '.join(f'{t} depuis le {d}' for t, d in sorted(starts.items()))} ; votes individuels sans groupe : {without_group}")


if __name__ == "__main__":
    main()
