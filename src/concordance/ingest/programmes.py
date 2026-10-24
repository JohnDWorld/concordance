"""Candidats et mesures relus dans donnees/, chaque citation vérifiée mot pour mot sur sa source au chargement."""

import csv
import hashlib
import html
import re
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

import psycopg

from concordance import db
from concordance.ingest.raw import download
from concordance.models import CandidateEventRow, MeasureRow

CANDIDATS = Path("donnees/candidats.csv")
MESURES = Path("donnees/mesures_retraites.csv")
PAUSE = 1.0


def page_text(path: Path) -> str:
    """Texte affiché d'une page HTML ou d'un PDF."""
    data = path.read_bytes()
    if data.startswith(b"%PDF"):
        return subprocess.run(["pdftotext", str(path), "-"], capture_output=True, check=True, text=True).stdout
    raw = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", data.decode("utf-8", errors="replace"))
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


def compact(text: str) -> str:
    """Caractères exacts, espaces ignorés : la conversion d'une page en texte ajoute ou retire des espaces."""
    return "".join(text.split())


def found_in(citation: str, page: str) -> bool:
    return compact(citation) in compact(page)


def fetch(url: str) -> str | None:
    try:
        path = download(url, Path("programmes/pages") / hashlib.sha1(url.encode()).hexdigest()[:16])
    except OSError:
        return None
    finally:
        time.sleep(PAUSE)
    return page_text(path)


def measure_key(candidate_id: int, m: MeasureRow) -> str:
    """Même clé que la colonne générée measures.cle."""
    return hashlib.md5(f"{candidate_id}|{m.source_url}|{m.citation}".encode()).hexdigest()


def load(conn: psycopg.Connection[Any], events: list[CandidateEventRow], measures: list[MeasureRow]) -> None:
    names = {e.candidat: (e.nom, e.parti) for e in events}
    with conn.cursor() as cur:
        db.upsert(cur, "candidates", [{"full_name": n, "party": p} for n, p in names.values()], ("full_name",))
        cur.execute("select full_name, id from concordance.candidates where full_name = any(%s)", ([n for n, _ in names.values()],))
        by_name = dict(cur.fetchall())
        ids = {slug: by_name[name] for slug, (name, _) in names.items()}
        db.upsert(cur, "candidate_events", [
            {"candidate_id": ids[e.candidat], "event": e.evenement, "event_date": e.date, "source_url": e.source_url}
            for e in events], ("candidate_id", "event", "event_date"))
        db.upsert(cur, "measures", [
            {"candidate_id": ids[m.candidat], "theme": "retraites", "texte": m.citation, "citation": m.citation,
             "source_url": m.source_url, "retrieved_at": m.consulte_le}
            for m in measures], ("cle",))
        # Une mesure retirée du fichier relu disparaît de la base (refusé par la base si un jugement s'y rapporte).
        cur.execute("delete from concordance.measures where candidate_id = any(%s) and not (cle = any(%s))",
                    (list(ids.values()), [measure_key(ids[m.candidat], m) for m in measures]))


def main() -> None:
    with CANDIDATS.open(encoding="utf-8", newline="") as f:
        events = [CandidateEventRow.model_validate(r) for r in csv.DictReader(f)]
    with MESURES.open(encoding="utf-8", newline="") as f:
        rows = [MeasureRow.model_validate(r) for r in csv.DictReader(f)]
    unknown = {m.candidat for m in rows} - {e.candidat for e in events}
    if unknown:
        raise SystemExit(f"mesures de candidats absents de {CANDIDATS} : {sorted(unknown)}")
    stats: Counter[str] = Counter()
    pages: dict[str, str | None] = {}
    verified = []
    for m in rows:
        if m.source_url not in pages:
            pages[m.source_url] = fetch(m.source_url)
        page = pages[m.source_url]
        if page is None:
            stats["source inaccessible"] += 1
            print(f"REJETÉE (source inaccessible) {m.candidat} : {m.source_url}")
        elif not found_in(m.citation, page):
            stats["citation introuvable sur la source"] += 1
            print(f"REJETÉE (introuvable) {m.candidat} : {m.citation[:80]}")
        else:
            verified.append(m)
    with db.connect() as conn:
        load(conn, events, verified)
    print(f"{len({e.candidat for e in events})} candidats, {len(events)} événements, {len(verified)} mesures vérifiées", dict(stats))


if __name__ == "__main__":
    main()
