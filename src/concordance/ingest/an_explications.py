"""Explications de vote de l'Assemblée, depuis les comptes rendus intégraux (Syceron), selon docs/methodologie.md.

Les scrutins et groupes doivent déjà être chargés (concordance.ingest.an).
"""

import argparse
import html
import json
import re
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from concordance import db
from concordance.ingest.an import AMO30, BASE, SCRUTINS, group_periods
from concordance.ingest.raw import RAW, download
from concordance.models import VoteExplanation
from concordance.rules import Membership, group_at

COMPTES_RENDUS = BASE + "/{leg}/vp/syceronbrut/syseron.xml.zip"  # la page affiche « /VP/ », qui renvoie 404
# Sections du sommaire dont les orateurs prennent position avant un vote.
SECTIONS = re.compile(r"(?i)^(?:explications? de vote|motions? de censure|motion de rejet préalable|vote sur l[’']ensemble)")
# Les entrées vides du sommaire sont auto-fermantes (<para .../>) : sans les traiter, une section avalerait la suivante.
TOC_SECTION = re.compile(r"<titreStruct[^>]*>\s*<intitule>(.*?)</intitule>.*?</titreStruct>((?:\s*<para[^>]*?(?:/>|>.*?</para>))*)", re.S)
PARAGRAPH = re.compile(r"<paragraphe ([^>]*)>(.*?)</paragraphe>", re.S)
ATTRIBUTE = re.compile(r'(\w+)="([^"]*)"')
RESULT = "Voici le résultat du scrutin"
HAND_VOTE = re.compile(r"\((?:L[’']|La |Le |Les )[^()]*\badopté(?:e|s|es)?\.\)")
PRESIDENCY = re.compile(r"^(?:M\. le président|Mme la présidente)")
Ballots = dict[str, list[tuple[str, int, int]]]  # séance -> (scrutin, pour, contre)


@dataclass
class Para:
    order: int
    anchor: str
    acteur: str
    grammar: str
    speaker: str
    text: str


def clean(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def paragraphs(body: str) -> list[Para]:
    out = []
    for attributes, inner in PARAGRAPH.findall(body):
        a = dict(ATTRIBUTE.findall(attributes))
        name = re.search(r"<nom>(.*?)</nom>", inner, re.S)
        text = re.search(r"<texte[^>]*>(.*?)</texte>", inner, re.S)
        out.append(Para(int(a.get("ordre_absolu_seance") or 0), a.get("id_syceron", ""), a.get("id_acteur", ""),
                        a.get("code_grammaire", ""), clean(name.group(1)) if name else "", clean(text.group(1)) if text else ""))
    return sorted(out, key=lambda p: p.order)


def listed_orators(toc: str) -> list[str]:
    """Ancres des orateurs listés au sommaire sous une section de prise de position avant un vote."""
    anchors = []
    for m in TOC_SECTION.finditer(toc):
        if SECTIONS.match(clean(m.group(1))):
            for anchor, label in re.findall(r'<para id_syceron="(\d+)">(.*?)</para>', m.group(2), re.S):
                if "," not in clean(label):  # « M. X, rapporteur » ou « ..., ministre » : parole au titre d'une fonction
                    anchors.append(anchor)
    return anchors


def match_ballot(result: str, candidates: list[tuple[str, int, int]]) -> str | None:
    """Scrutin de la séance dont les chiffres sont ceux annoncés (le numéro n'est pas lu en séance)."""
    pour = re.search(r"Pour l[’'](?:adoption|approbation)\s*:?\s*(\d+)", result)  # « Pour l’adoption : 145 »
    contre = re.search(r"Contre\s*:?\s*(\d+)", result)
    if pour is None:
        return None
    found = [uid for uid, p, c in candidates if p == int(pour.group(1)) and (contre is None or c == int(contre.group(1)))]
    return found[0] if len(found) == 1 else None


def parse_explanations(raw: str, ballots: Ballots, periods: dict[str, list[Membership]]
                       ) -> tuple[list[VoteExplanation], Counter[str]]:
    stats: Counter[str] = Counter()
    uid = re.search(r"<uid>(.*?)</uid>", raw)
    seance = re.search(r"<seanceRef>(.*?)</seanceRef>", raw)
    day_text = re.search(r"<dateSeance>(\d{8})", raw)
    legislature = re.search(r"<legislature>(\d+)</legislature>", raw)
    if not (uid and seance and day_text and legislature):
        stats["compte rendu sans métadonnées"] += 1
        return [], stats
    day = date(int(day_text.group(1)[:4]), int(day_text.group(1)[4:6]), int(day_text.group(1)[6:]))
    url = f"https://www.assemblee-nationale.fr/dyn/{legislature.group(1)}/comptes-rendus/seance/{uid.group(1)}"
    start = raw.find("<contenu>")
    paras = paragraphs(raw[start:])
    position = {p.anchor: i for i, p in enumerate(paras)}
    out = []
    for anchor in listed_orators(raw[:start]):
        i = position.get(anchor)
        if i is None:
            stats["ancre du sommaire introuvable"] += 1
            continue
        orator = paras[i]
        turns: list[list[str]] = [[]]
        end = i
        for j in range(i, len(paras)):
            p = paras[j]
            if p.acteur == orator.acteur and not PRESIDENCY.match(p.speaker):
                if not turns[-1] or j == end + 1:
                    turns[-1].append(p.text)
                else:
                    turns.append([p.text])  # reprise après une interruption
                end = j
            elif p.grammar.startswith("INTERRUPTION"):
                continue  # les interruptions des autres orateurs sont exclues
            else:
                break  # la présidence ou un autre orateur reprend la parole
        # Scrutins rattachés : le premier résultat annoncé ensuite, puis les suivants tant qu'aucun débat ne reprend.
        linked: list[str] = []
        for p in paras[end + 1:]:
            if RESULT in p.text:
                ballot = match_ballot(p.text, ballots.get(seance.group(1), []))
                if ballot is None:
                    stats["résultat sans scrutin correspondant"] += 1
                    break
                linked.append(ballot)
            elif not linked and HAND_VOTE.search(p.text):
                break  # vote à main levée avant tout scrutin : explication non rattachée
            elif linked and p.grammar == "PAROLE_GENERIQUE" and not PRESIDENCY.match(p.speaker):
                break
        if not linked:
            stats["vote à main levée ou sans scrutin public"] += 1
            continue
        group = group_at(periods.get(orator.acteur, []), day)
        if group is None:
            stats["orateur sans groupe à la date (ministre, non-député...)"] += 1
            continue
        texte = " […] ".join(" ".join(turn) for turn in turns)
        for ballot in linked:
            out.append(VoteExplanation(
                ballot_external_id=ballot,
                ballot_date=day,
                group_external_id=group,
                orateur=orator.speaker,
                orateur_external_id=orator.acteur,
                texte=texte,
                source_url=f"{url}#{orator.anchor}",
            ))
    stats["explications"] += len(out)
    return out, stats


def parse_debates(raw: str, ballots: Ballots) -> dict[str, tuple[date, str]]:
    """Débat qui précède chaque scrutin de la séance : paragraphes depuis le résultat précédent."""
    seance = re.search(r"<seanceRef>(.*?)</seanceRef>", raw)
    day_text = re.search(r"<dateSeance>(\d{8})", raw)
    if not (seance and day_text):
        return {}
    day = date(int(day_text.group(1)[:4]), int(day_text.group(1)[4:6]), int(day_text.group(1)[6:]))
    debates: dict[str, tuple[date, str]] = {}
    spoken: list[str] = []  # paragraphes de la séance, hors annonces de résultat
    start = 0  # début du débat depuis le résultat précédent
    for p in paragraphs(raw[raw.find("<contenu>"):]):
        if RESULT in p.text:
            first = start
            while first > 0 and sum(len(t) for t in spoken[first:]) < db.DEBATE_MIN:
                first -= 1
            ballot = match_ballot(p.text, ballots.get(seance.group(1), []))
            if ballot is not None:
                debates[ballot] = (day, " ".join(spoken[first:]))
            start = len(spoken)
        else:
            spoken.append(p.text)
    return debates


def ballots_by_seance(zf: zipfile.ZipFile) -> Ballots:
    out: Ballots = {}
    for name in zf.namelist():
        if name.endswith(".json"):
            s = json.loads(zf.read(name))["scrutin"]
            d = s["syntheseVote"]["decompte"]
            out.setdefault(s["seanceRef"], []).append((s["uid"], int(d["pour"]), int(d["contre"])))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legislatures", type=int, nargs="+", required=True)
    legislatures = sorted(set(parser.parse_args().legislatures))

    with zipfile.ZipFile(download(AMO30, Path("an/AMO30.json.zip"))) as zf:
        periods = group_periods(zf)
    explanations: list[VoteExplanation] = []
    debates: dict[str, tuple[date, str]] = {}
    stats: Counter[str] = Counter()
    for leg in legislatures:
        cached = {name: RAW / f"an/{leg}/{name}" for name in ("Scrutins.json.zip", "syseron.xml.zip")}
        # ponytail: archives gardées si déjà présentes ; les supprimer pour les rafraîchir.
        scrutins = cached["Scrutins.json.zip"] if cached["Scrutins.json.zip"].exists() else download(
            SCRUTINS.format(leg=leg), Path(f"an/{leg}/Scrutins.json.zip"))
        reports = cached["syseron.xml.zip"] if cached["syseron.xml.zip"].exists() else download(
            COMPTES_RENDUS.format(leg=leg), Path(f"an/{leg}/syseron.xml.zip"))
        with zipfile.ZipFile(scrutins) as zf:
            ballots = ballots_by_seance(zf)
        with zipfile.ZipFile(reports) as zf:
            for name in zf.namelist():
                if name.endswith(".xml"):
                    raw = zf.read(name).decode("utf-8")
                    found, page_stats = parse_explanations(raw, ballots, periods)
                    debates |= parse_debates(raw, ballots)
                    explanations += found
                    stats += page_stats
    with db.connect() as conn:
        stats["explication sans scrutin du même jour"] = db.load_explanations(conn, "an", explanations)
        stats["scrutins avec débat"] = db.load_debates(conn, "an", debates)
    print("Explications de vote (AN) :", dict(stats))


if __name__ == "__main__":
    main()
