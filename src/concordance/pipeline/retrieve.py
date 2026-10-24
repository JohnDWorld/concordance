"""Scrutins liés à chaque mesure : périmètre du thème (mots), puis classement par proximité de sens (embeddings).

Règle documentée dans docs/methodologie.md, section « Recherche des scrutins liés à une mesure ».
"""

import argparse
from datetime import date
from pathlib import Path
from typing import Any

import psycopg

from concordance import db

# Périmètre d'un thème : mots de l'intitulé ou du dossier (plein texte français, anglais pour le PE),
# ou au moins MIN_MENTIONS mentions du thème dans les explications de vote, ou dans le débat qui précède le scrutin.
THEMES = {
    "retraites": {
        "titre": "retraite | pension | vieillesse | (âge <-> légal) | (âge <-> de <-> départ) | retirement | old-age",
        "explications": r"\m(retraite|pension)",  # début de mot : « suspension » ne compte pas
    },
}
MIN_MENTIONS = 3

PERIMETER = """
select b.id from concordance.ballots b where b.recherche @@ to_tsquery('french', %(titre)s)
union
select e.ballot_id from concordance.vote_explanations e
group by e.ballot_id having sum(regexp_count(lower(e.texte), %(explications)s)) >= %(min)s
union
select b.id from concordance.ballots b where regexp_count(lower(b.debat), %(explications)s) >= %(min)s
"""

SEARCH = f"""
select b.id, b.chamber, b.ballot_date, b.external_id, b.intitule, b.source_url,
       1 - (b.embedding <=> m.embedding) as proximite
from concordance.ballots b, concordance.measures m
where m.id = %(measure)s and b.id in ({PERIMETER})
order by b.embedding <=> m.embedding limit %(limit)s
"""


def perimeter_size(conn: psycopg.Connection[Any], theme: str) -> int:
    row = conn.execute(f"select count(*) from ({PERIMETER}) p", THEMES[theme] | {"min": MIN_MENTIONS}).fetchone()
    return int(row[0]) if row else 0


def search(conn: psycopg.Connection[Any], measure_id: int, theme: str, limit: int) -> list[tuple[Any, ...]]:
    return conn.execute(SEARCH, THEMES[theme] | {"min": MIN_MENTIONS, "measure": measure_id, "limit": limit}).fetchall()


CHAMBERS = {"an": "Assemblée", "senat": "Sénat", "pe": "Parlement européen"}


def review(conn: psycopg.Connection[Any], limit: int) -> str:
    """Document de relecture : pour chaque mesure, les scrutins candidats avec leur lien officiel."""
    lines = [f"# Relecture : scrutins candidats par mesure ({date.today()})", "",
             f"Périmètre « retraites » : {perimeter_size(conn, 'retraites')} scrutins. "
             f"Pour chaque mesure, les {limit} plus proches par le sens. Règle : docs/methodologie.md.", ""]
    measures = conn.execute("""select m.id, c.full_name, m.theme, m.citation, m.source_url from concordance.measures m
                               join concordance.candidates c on c.id = m.candidate_id order by c.full_name, m.id""").fetchall()
    for measure_id, name, theme, citation, source in measures:
        lines += [f"## {name}", "", f"> {citation}", "", f"[Source]({source})", "",
                  "| # | Chambre | Date | Scrutin | Proximité |", "|---|---|---|---|---|"]
        for rank, (_, chamber, day, _, title, url, score) in enumerate(search(conn, measure_id, theme, limit), 1):
            lines.append(f"| {rank} | {CHAMBERS[chamber]} | {day} | [{title[:120]}]({url}) | {score:.2f} |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10, help="scrutins par mesure")
    parser.add_argument("--revue", type=Path, help="écrire le document de relecture (Markdown) dans ce fichier")
    args = parser.parse_args()
    with db.connect() as conn:
        if args.revue:
            args.revue.write_text(review(conn, args.limit), encoding="utf-8")
            return
        print("Périmètre « retraites » :", perimeter_size(conn, "retraites"), "scrutins")
        measures = conn.execute("""select m.id, c.full_name, m.theme, m.citation from concordance.measures m
                                   join concordance.candidates c on c.id = m.candidate_id order by c.full_name, m.id""").fetchall()
        for measure_id, name, theme, citation in measures:
            print(f"\n== {name} : {citation[:110]}")
            for _, chamber, day, ext, title, _, score in search(conn, measure_id, theme, args.limit):
                print(f"   {score:.3f} {chamber:5} {day} {ext:16} {title[:95]}")


if __name__ == "__main__":
    main()
