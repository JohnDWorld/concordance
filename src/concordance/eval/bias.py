"""Biais des juges (CLAUDE.md, section Évaluation) : répartition des verdicts par groupe et test contrefactuel.

Contrefactuel : des paires tirées au hasard sont rejugées avec d'autres lettres pour les groupes. Le verdict ne doit pas
changer ; une différence montre que l'étiquette, et non le fond, influence le juge. Une paire dont le message reste
identique (même lettre tirée) n'est pas un test : elle est comptée à part. Rapport : docs/evaluation/biais.md.
"""

import argparse
import random
from collections import Counter
from datetime import date
from pathlib import Path

from concordance import db
from concordance.eval.run import RELATIONS
from concordance.pipeline.anonymize import build_dictionary
from concordance.pipeline.judge import JUDGES, PROMPT_VERSION, judge_pair, pairs, verdicts

REPORT = Path("docs/evaluation/biais.md")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=40, help="paires rejugées par juge pour le contrefactuel")
    parser.add_argument("--limite", type=int, default=5, help="scrutins par mesure (comme le juge)")
    args = parser.parse_args()
    with db.connect() as conn:
        found = verdicts(conn)
        names = dict(conn.execute("select id, coalesce(sigle, libelle) || ' (' || chamber || coalesce(' ' || legislature, '') || ')' "
                                  "from concordance.parl_groups"))
        dictionary = build_dictionary(conn)
        candidates = pairs(conn, args.limite)
    lines = [f"# Biais des juges ({date.today()})", "", f"Consigne `{PROMPT_VERSION}`, juges : {', '.join(f'`{j}`' for j in JUDGES)}.", "",
             "## Répartition des verdicts publiés par groupe", "",
             "Verdict publié : accord des deux juges ou relecture humaine. Les écarts entre groupes reflètent d'abord leurs votes ; "
             "ce tableau sert à repérer un groupe pour lequel les juges seraient plus souvent en désaccord ou rejetés.", "",
             "| Groupe | " + " | ".join(RELATIONS) + " | désaccord | rejet ou manquant |", "|---" * (len(RELATIONS) + 3) + "|"]
    by_group: dict[int, Counter[str]] = {}
    for (_, _, g), v in found.items():
        by_group.setdefault(g, Counter())[v["relation"] or ("désaccord" if v["statut"] == "désaccord des juges" else "rejet")] += 1
    for g in sorted(by_group, key=lambda g: names[g]):
        c = by_group[g]
        lines.append(f"| {names[g]} | " + " | ".join(str(c[r]) for r in [*RELATIONS, "désaccord", "rejet"]) + " |")
    lines += ["", "## Test contrefactuel : autres lettres, même paire", ""]
    for judge in JUDGES:
        judged = [p for p in candidates if (k := (p.measure_id, p.ballot_id, p.group_id)) in found
                  and judge in found[k]["juges"] and not found[k]["juges"][judge]["rejet"]]
        same, changed, rejected, untested = 0, [], 0, 0
        for p in random.Random(2027).sample(judged, min(args.n, len(judged))):
            original = found[(p.measure_id, p.ballot_id, p.group_id)]["juges"][judge]
            row = judge_pair(judge, p, dictionary, seed="-contrefactuel")
            before = original["relation"]
            if row["texte_anonymise"] == original["texte"]:
                untested += 1
            elif row["rejet"]:
                rejected += 1
            elif row["relation"] == before:
                same += 1
            else:
                changed.append(f"mesure {p.measure_id}, scrutin {p.ballot_id}, {names[p.group_id]} : {before} -> {row['relation']}")
        compared = same + len(changed)
        lines += [f"`{judge}` : {compared} paires comparées, verdict identique pour {same}"
                  + (f" ({same / compared:.0%})" if compared else "")
                  + f", rejet au second passage : {rejected}, message inchangé (même lettre, pas un test) : {untested}.", ""]
        lines += [f"- {c}" for c in changed] + ([""] if changed else [])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
