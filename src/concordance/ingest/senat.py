"""Ingestion Sénat : groupes politiques (export des sénateurs), scrutins et positions par groupe (pages HTML)."""

import argparse
import html
import re
import time
import zipfile
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from concordance import db
from concordance.ingest.raw import RAW, download
from concordance.models import Ballot, GroupPosition, ParlGroup
from concordance.rules import majority, nature

EXPORT = "https://data.senat.fr/data/senateurs/export_sens.zip"
SITE = "https://www.senat.fr"
PAUSE = 1.0  # secondes entre deux pages, par politesse envers senat.fr
MONTHS = {m: i for i, m in enumerate(
    ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"),
    start=1)}


def copy_rows(dump: str, table: str) -> Iterator[dict[str, Any]]:
    """Lignes du bloc COPY d'une table dans un dump PostgreSQL (valeurs str, ou None pour NULL)."""
    m = re.search(rf"^COPY (?:public\.)?{table} \((.*?)\) FROM stdin;\n(.*?)^\\\.$", dump, re.S | re.M)
    if m is None:
        raise ValueError(f"table {table} absente du dump")
    cols = m.group(1).split(", ")
    for line in m.group(2).splitlines():
        yield {c: None if v == r"\N" else v for c, v in zip(cols, line.split("\t"), strict=True)}


def day(value: str | None) -> date | None:
    d = date.fromisoformat(value[:10]) if value else None
    return None if d and d.year < 1900 else d  # 1899-12-31 : date inconnue dans la source


def parse_groups(dump: str) -> list[ParlGroup]:
    return [
        ParlGroup(
            chamber="senat",
            legislature=None,
            external_id=r["grppolcod"],
            sigle=r["grppolliccou"],
            libelle=r["grppollibcou"],
            start_date=day(r["grppoldatcre"]),
            end_date=day(r["grppoldatfin"]),
        )
        for r in copy_rows(dump, "grppol")
    ]


def clean(fragment: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", fragment).split())


def first(pattern: str, text: str) -> re.Match[str]:
    m = re.search(pattern, text, re.S)
    if m is None:
        raise ValueError(f"motif introuvable : {pattern}")
    return m


def count_field(label: str) -> str:
    label = " ".join(label.split()).lower().replace("’", "'")
    for prefix, field in (("pour", "pour"), ("contre", "contre"), ("abstention", "abstention"),
                          ("n'a pas pris part", "non_votants"), ("n'ont pas pris part", "non_votants")):
        if label.startswith(prefix):
            return field
    raise ValueError(f"décompte inconnu : {label}")


def parse_position(code: str, header: str) -> GroupPosition:
    counts = {"pour": 0, "contre": 0, "abstention": 0, "non_votants": 0}
    for label, n in re.findall(r'([^<>]+?)\xa0:\s*<span class="ms-1 fw-semibold">(\d+)</span>', header):
        counts[count_field(label)] += int(n)
    return GroupPosition(
        group_external_id=code,
        membres=int(first(r"<h3[^>]*>[^<]*?:\s*(\d+)", header).group(1)),
        non_votants_volontaires=None,
        position_majoritaire=majority(counts["pour"], counts["contre"], counts["abstention"]),
        **counts,
    )


def parse_ballot(page: str, session: int, number: int) -> Ballot:
    """Page d'un scrutin public. Lève ValueError si la page ne suit pas le gabarit attendu."""
    page = html.unescape(page)
    external_id = f"scr{session}-{number}"
    title = clean(first(r'<h1 class="page-title">(.*?)</h1>', page).group(1))
    d, month, year = first(r"séance du (\d+)(?:er)? (\S+) (\d{4})", title).groups()
    result = clean(first(r"Résultat du scrutin</h2>\s*<p>(.*?)</p>", page).group(1)).replace("’", "'")
    if "n'a pas adopté" in result:
        sort = "rejeté"
    elif "a adopté" in result:
        sort = "adopté"
    else:
        raise ValueError(f"{external_id} : résultat illisible ({result})")
    totals = {k: int(n) for n, k in re.findall(r"(\d+)</strong>\s*(pour|contre)\b", page)}
    positions = []
    for chunk in page.split('id="accordion-scrutin-')[1:]:
        code = chunk[: chunk.index('"')]
        positions.append(parse_position(code, chunk.split('<div id="accordion-collapse-', 1)[0]))
    # Contrôle : la somme des groupes doit retomber sur les totaux de la page.
    for k in ("pour", "contre"):
        if sum(getattr(p, k) for p in positions) != totals.get(k):
            raise ValueError(f"{external_id} : somme des groupes ({k}) différente du total {totals.get(k)}")
    lead = clean(first(r'<p class="page-lead">(.*?)</p>', page).group(1))
    dossier = re.search(r'href="(/dossier-legislatif/[^"]+)"', page)
    return Ballot(
        chamber="senat",
        legislature=None,
        external_id=external_id,
        ballot_date=date(int(year), MONTHS[month], int(d)),
        intitule=lead,
        objet=None,
        nature=nature(lead),
        sort=sort,
        dossier=SITE + dossier.group(1) if dossier else None,
        seance_ref=None,
        source_url=f"{SITE}/scrutin-public/{session}/{external_id}.html",
        positions=positions,
    )


def current_session(today: date) -> int:
    """Année de début de la session ordinaire en cours (elle s'ouvre en octobre)."""
    return today.year if today.month >= 10 else today.year - 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depuis", type=int, default=2022, help="première session (année de début)")
    first_session = parser.parse_args().depuis

    with zipfile.ZipFile(download(EXPORT, Path("senat/export_sens.zip"))) as zf:
        groups = parse_groups(zf.read("export_sens.sql").decode())
    ballots, errors = [], []
    for session in range(first_session, current_session(date.today()) + 1):
        index = download(f"{SITE}/scrutin-public/scr{session}.html", Path(f"senat/scrutins/scr{session}.html"))
        numbers = sorted({int(n) for n in re.findall(rf'href="{session}/scr{session}-(\d+)\.html"', index.read_text())})
        for n in numbers:
            dest = Path(f"senat/scrutins/{session}/scr{session}-{n}.html")
            # ponytail: une page déjà téléchargée n'est pas revérifiée ; relancer sans le fichier si le Sénat la corrige.
            if not (RAW / dest).exists():
                download(f"{SITE}/scrutin-public/{session}/scr{session}-{n}.html", dest)
                time.sleep(PAUSE)
            try:
                ballots.append(parse_ballot((RAW / dest).read_text(), session, n))
            except ValueError as e:
                errors.append(f"{dest.name} : {e}")

    with db.connect() as conn:
        db.load_votes(conn, "senat", groups, ballots)
    print(f"Sénat : {len(groups)} groupes, {len(ballots)} scrutins, {sum(len(b.positions) for b in ballots)} positions")
    for error in errors:
        print("Non chargé :", error)


if __name__ == "__main__":
    main()
