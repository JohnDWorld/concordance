"""Ingestion Sénat : groupes politiques (export des sénateurs), scrutins et positions par groupe (pages HTML)."""

import argparse
import html
import re
import time
import unicodedata
import urllib.error
import zipfile
from collections import Counter
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from concordance import db
from concordance.ingest.raw import RAW, download
from concordance.models import Ballot, GroupPosition, ParlGroup, VoteExplanation
from concordance.rules import majority, nature

EXPORT = "https://data.senat.fr/data/senateurs/export_sens.zip"
SITE = "https://www.senat.fr"
# Compte rendu intégral (mot à mot). Jamais /cra/ : le compte rendu analytique résume les interventions.
CRI = SITE + "/seances/s{day:%Y%m}/s{day:%Y%m%d}/s{day:%Y%m%d}_mono.html"
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


Membership = tuple[str, date | None, date | None]
BLOCK_START = re.compile(r'<div id="intv_par_\d+" class="intervenant">')
BLOCK_END = "<!--/cri:intervenant -->"  # absent des interruptions collectives
SPEAKER = re.compile(r'<!--cri:intervenant mat="([^"]*)" nom="([^"]*)" qua="([^"]*)"')
PARAGRAPH = re.compile(r'<p id="(par_\d+)"[^>]*>(.*?)</p>', re.S)
GIVES_FLOOR = re.compile(r"La parole est à .*?, pour (?:explication de vote|le groupe|la réunion administrative)")
SCRUTIN = re.compile(r"résultat du scrutin(?: public)? n°\s*(\d+)")  # formule officielle, pas une simple mention
HAND_VOTE = re.compile(r"\((?:L[’']amendement|Les amendements|Le sous-amendement|L[’']article|La motion|L[’']ensemble"
                       r"|La proposition|Le projet)[^()]*adopté[es]{0,2}\.\)")


def memberships(dump: str) -> dict[str, list[Membership]]:
    """Matricule du sénateur vers ses appartenances à des groupes politiques."""
    out: dict[str, list[Membership]] = {}
    for r in copy_rows(dump, "memgrppol"):
        out.setdefault(r["senmat"], []).append((r["grppolcod"], day(r["memgrppoldatdeb"]), day(r["memgrppoldatfin"])))
    return out


def group_at(periods: list[Membership], when: date) -> str | None:
    codes = {code for code, start, end in periods if (start is None or start <= when) and (end is None or when <= end)}
    return codes.pop() if len(codes) == 1 else None


def fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold()) if not unicodedata.combining(c))


def speech(block: str) -> list[tuple[str, str]]:
    """Paragraphes (ancre, texte exact) d'un tour de parole, sans le nom ni la qualité de l'orateur."""
    block = re.sub(r'<span class="orateur_nom"><!--cri:orateurnom -->.*?<!--/cri:orateurnom --></span>', "", block, flags=re.S)
    block = re.sub(r'<span class="orateur_qualite">.*?</span>', "", block, flags=re.S)
    return [(anchor, re.sub(r"^[.,\s]+", "", clean(p))) for anchor, p in PARAGRAPH.findall(block)]


def turns_of(page: str) -> list[tuple[int, str, re.Match[str] | None]]:
    """Tours de parole (position de fin, contenu, orateur). Un tour va jusqu'au suivant, coupé à son commentaire de fin."""
    starts = [m.end() for m in BLOCK_START.finditer(page)]
    out = []
    for start, nxt in zip(starts, [*starts[1:], len(page)], strict=True):
        cut = page.find(BLOCK_END, start, nxt)
        end = cut if cut >= 0 else nxt
        out.append((end, page[start:end], SPEAKER.search(page, start, end)))
    return out


def parse_explanations(page: str, when: date, url: str, members: dict[str, list[Membership]]) -> tuple[list[VoteExplanation], Counter[str]]:
    """Explications de vote d'un compte rendu intégral, selon la règle de docs/methodologie.md."""
    page = html.unescape(page)
    stats: Counter[str] = Counter()
    flat = clean(page)
    blocks = turns_of(page)
    out = []
    i = 0
    while i < len(blocks):
        _, body, who = blocks[i]
        i += 1
        if not (who and who.group(3) == "président de séance" and GIVES_FLOOR.search(clean(body))):
            continue
        announced = fold(clean(body))
        orator = None  # premier intervenant qui porte le nom annoncé (une interruption peut le précéder)
        for _, _, speaker in blocks[i:]:
            if speaker and speaker.group(3) == "président de séance":
                break
            if speaker and all(w in announced for w in fold(speaker.group(2)).split()):
                orator = speaker
                break
        if orator is None:
            stats["orateur annoncé introuvable"] += 1
            continue
        mat, name = orator.group(1), orator.group(2)
        turns, end = [], blocks[i][0]
        while i < len(blocks):
            block_end, block, speaker = blocks[i]
            if speaker and speaker.group(3) == "président de séance":
                break
            if speaker and speaker.group(1) == mat:  # les interruptions des autres orateurs sont exclues
                turns.append(speech(block))
                end = block_end
            i += 1
        rest = page[end:]
        scrutin, hand = SCRUTIN.search(rest), HAND_VOTE.search(rest)
        if scrutin is None or (hand is not None and hand.start() < scrutin.start()):
            stats["vote à main levée ou sans scrutin public"] += 1
            continue
        group = group_at(members.get(mat, []), when)
        if group is None:
            stats["groupe introuvable à la date"] += 1
            continue
        paragraphs = [p for turn in turns for p in turn]
        texte = " […] ".join(" ".join(text for _, text in turn) for turn in turns)
        if any(part not in flat for part in texte.split(" […] ")):  # pas de source exacte, pas d'explication
            stats["texte non retrouvé mot pour mot"] += 1
            continue
        out.append(VoteExplanation(
            ballot_external_id=f"scr{current_session(when)}-{scrutin.group(1)}",
            ballot_date=when,
            group_external_id=group,
            orateur=name,
            orateur_external_id=mat,
            texte=texte,
            source_url=f"{url}#{paragraphs[0][0]}",
        ))
    stats["explications"] = len(out)
    return out, stats


def current_session(today: date) -> int:
    """Année de début de la session ordinaire en cours (elle s'ouvre en octobre)."""
    return today.year if today.month >= 10 else today.year - 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depuis", type=int, default=2022, help="première session (année de début)")
    first_session = parser.parse_args().depuis

    with zipfile.ZipFile(download(EXPORT, Path("senat/export_sens.zip"))) as zf:
        dump = zf.read("export_sens.sql").decode()
    groups, members = parse_groups(dump), memberships(dump)
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

    explanations: list[VoteExplanation] = []
    stats: Counter[str] = Counter()
    for when in sorted({b.ballot_date for b in ballots}):
        url = CRI.format(day=when)
        dest = Path(f"senat/cri/s{when:%Y%m%d}_mono.html")
        if not (RAW / dest).exists():
            try:
                download(url, dest)
            except urllib.error.HTTPError as e:  # le compte rendu intégral paraît avec quelques semaines de délai
                stats[f"compte rendu intégral absent (HTTP {e.code})"] += 1
                continue
            finally:
                time.sleep(PAUSE)
        found, page_stats = parse_explanations((RAW / dest).read_text(), when, url, members)
        explanations += found
        stats += page_stats

    with db.connect() as conn:
        db.load_votes(conn, "senat", groups, ballots)
        stats["explication sans scrutin du même jour"] = db.load_explanations(conn, "senat", explanations)
    print(f"Sénat : {len(groups)} groupes, {len(ballots)} scrutins, {sum(len(b.positions) for b in ballots)} positions")
    print("Explications de vote :", dict(stats))
    for error in errors:
        print("Non chargé :", error)


if __name__ == "__main__":
    main()
