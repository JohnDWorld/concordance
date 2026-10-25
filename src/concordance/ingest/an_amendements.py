"""Amendements de l'Assemblée sur un dossier législatif, avec les mesures de docs/methodologie.md.

Les groupes de la législature doivent déjà être chargés (concordance.ingest.an).
"""

import argparse
import html
import json
import re
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import psycopg

from concordance import db
from concordance.ingest.an import AMO30, BASE, group_periods
from concordance.ingest.raw import RAW, download
from concordance.models import Amendment
from concordance.rules import Membership, amendment_scope, group_at, normalize, series_key

AMENDEMENTS = BASE + "/{leg}/loi/amendements_div_legis/Amendements.json.zip"


def value(v: Any) -> Any:
    """Valeur d'un champ de l'Assemblée, None pour xsi:nil."""
    return None if isinstance(v, dict) and v.get("@xsi:nil") == "true" else v


def as_list(v: Any) -> list[Any]:
    v = value(v)
    return [] if v is None else v if isinstance(v, list) else [v]


def plain(fragment: Any) -> str | None:
    if not isinstance(fragment, str):
        return None
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split()) or None


def parse_amendment(a: dict[str, Any], dossier_ref: str) -> Amendment:
    ident, signataires, cycle = a["identification"], a["signataires"], a["cycleDeVie"]
    auteur = signataires["auteur"]
    etats = value(cycle.get("etatDesTraitements")) or {}
    contenu = value(a.get("corps", {}).get("contenuAuteur")) or {}
    division = value(a.get("pointeurFragmentTexte", {}).get("division")) or {}
    return Amendment(
        chamber="an",
        legislature=a["legislature"],
        external_id=a["uid"],
        dossier_ref=dossier_ref,
        texte_ref=a["texteLegislatifRef"],
        numero=ident["numeroLong"],
        organe_examen=ident["prefixeOrganeExamen"],
        auteur_type=auteur["typeAuteur"],
        auteur_ref=value(auteur.get("acteurRef")),
        group_external_id=value(auteur.get("groupePolitiqueRef")),
        date_depot=value(cycle.get("dateDepot")),
        date_sort=date.fromisoformat(sort[:10]) if isinstance(sort := value(cycle.get("dateSort")), str) else None,
        etat=(value(etats.get("etat")) or {}).get("libelle"),
        sous_etat=(value(etats.get("sousEtat")) or {}).get("libelle"),
        sort=value(cycle.get("sort")),
        division=value(division.get("articleDesignationCourte")),
        dispositif=plain(value(contenu.get("dispositif"))),
        expose_sommaire=plain(value(contenu.get("exposeSommaire"))),
        cosignataires=as_list((value(signataires.get("cosignataires")) or {}).get("acteurRef")),
        source_url=f"https://www.assemblee-nationale.fr/dyn/{a['legislature']}/amendements/{a['uid']}",
    )


def measure(amendments: list[Amendment]) -> None:
    """Mesures de chaque amendement ; « identique » et « série » comparent les amendements d'un même texte."""
    published = [a for a in amendments if a.dispositif]
    copies = Counter((a.texte_ref, normalize(a.dispositif or "")) for a in published)
    variants: dict[tuple[str, str], set[str]] = defaultdict(set)
    for a in published:
        variants[(a.texte_ref, series_key(a.dispositif or ""))].add(normalize(a.dispositif or ""))
    for a in published:
        a.identique = copies[(a.texte_ref, normalize(a.dispositif or ""))] > 1
        a.serie = len(variants[(a.texte_ref, series_key(a.dispositif or ""))]) > 1
        a.suppression, a.forme, a.mots_ajoutes = amendment_scope(a.dispositif or "")



def load(conn: psycopg.Connection[Any], amendments: list[Amendment], periods: dict[str, list[Membership]]) -> Counter[str]:
    stats: Counter[str] = Counter()
    with conn.cursor() as cur:
        cur.execute("select legislature, external_id, id from concordance.parl_groups where chamber = 'an'")
        group_ids = {(leg, ext): id_ for leg, ext, id_ in cur}
        rows = []
        for a in amendments:
            group_id = group_ids.get((a.legislature, a.group_external_id)) if a.group_external_id else None
            if a.group_external_id and group_id is None:
                stats["groupe de l'auteur inconnu"] += 1
            rows.append({**a.model_dump(exclude={"group_external_id", "cosignataires"}), "group_id": group_id})
        db.upsert(cur, "amendments", rows, ("external_id",))
        cur.execute("select external_id, id from concordance.amendments where external_id = any(%s)",
                    ([a.external_id for a in amendments],))
        ids = dict(cur.fetchall())
        # Les cosignatures sont recalculées en entier pour ces amendements.
        cur.execute("delete from concordance.amendment_cosignatures where amendment_id = any(%s)", (list(ids.values()),))
        cosignatures = []
        for a in amendments:
            counts = Counter(group_at(periods.get(ref, []), a.date_depot) for ref in a.cosignataires)
            stats["cosignataire sans groupe à la date"] += counts.pop(None, 0)
            cosignatures += [
                {"amendment_id": ids[a.external_id], "group_id": group_ids[(a.legislature, g)], "cosignataires": n}
                for g, n in counts.items()
                if g is not None
            ]
        db.upsert(cur, "amendment_cosignatures", cosignatures, ("amendment_id", "group_id"))
    return stats


LINK = """
update concordance.ballots b set amendment_id = m.amendment_id
from (
    select s.id as ballot_id, min(a.id) as amendment_id
    from concordance.ballots s
    join concordance.amendments a
      on a.legislature = s.legislature and a.organe_examen = 'AN' and a.date_sort = s.ballot_date
     and regexp_replace(a.numero, '^[A-Z]+-', '') = substring(s.intitule from 'n° ?([0-9]+)')
    where s.chamber = 'an' and s.legislature = %(leg)s and s.nature = 'amendement'
    group by s.id having count(*) = 1
) m
where b.id = m.ballot_id
"""


def link_ballots(conn: psycopg.Connection[Any], legislature: int) -> int:
    """Relie chaque scrutin sur un amendement à cet amendement : même numéro (sans le préfixe « I- » des lois de
    finances), examiné en séance, sort daté du jour du scrutin. Seules les correspondances uniques sont gardées."""
    return conn.execute(LINK, {"leg": legislature}).rowcount


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legislature", type=int, required=True)
    parser.add_argument("--dossier", help="référence du dossier législatif (DLR5L...) ; tous les dossiers sinon")
    args = parser.parse_args()

    with zipfile.ZipFile(download(AMO30, Path("an/AMO30.json.zip"))) as zf:
        periods = group_periods(zf)
    dest = Path(f"an/{args.legislature}/Amendements.json.zip")
    # ponytail: archive gardée si déjà présente (plusieurs centaines de Mo) ; la supprimer pour la rafraîchir.
    path = RAW / dest if (RAW / dest).exists() else download(AMENDEMENTS.format(leg=args.legislature), dest)
    stats: Counter[str] = Counter()
    with zipfile.ZipFile(path) as zf, db.connect() as conn:
        by_dossier: dict[str, list[str]] = defaultdict(list)
        for n in zf.namelist():
            if n.endswith(".json") and (args.dossier is None or n.startswith(f"json/{args.dossier}/")):
                by_dossier[n.split("/")[1]].append(n)
        if not by_dossier:
            raise SystemExit(f"aucun amendement pour le dossier {args.dossier}")
        for dossier, names in sorted(by_dossier.items()):  # un dossier à la fois : la mémoire reste bornée
            amendments = [parse_amendment(json.loads(zf.read(n))["amendement"], dossier) for n in names]
            measure(amendments)
            stats += load(conn, amendments, periods)
            conn.commit()
            stats["amendements"] += len(amendments)
        stats["scrutins reliés à leur amendement"] = link_ballots(conn, args.legislature)
    print(f"{len(by_dossier)} dossiers :", dict(stats))


if __name__ == "__main__":
    main()
