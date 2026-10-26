"""Évaluation des juges sur le jeu de référence eval/gold_retraites.csv (CLAUDE.md, section Évaluation).

--echantillon N : tire N paires parmi celles à juger, équilibrées entre groupes, et écrit le fichier à annoter
(colonnes relation et justification vides) avec, à côté, le contexte anonymisé de chaque paire pour l'annotation.
--juger JUGE : fait juger les paires de référence. Sans option : accord de chaque juge avec l'annotation, kappa entre
les deux juges, rapport docs/evaluation/juges_<consigne>.md.
"""

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import psycopg

from concordance import db
from concordance.pipeline.anonymize import anonymize, build_dictionary
from concordance.pipeline.judge import JUDGES, PROMPT_VERSION, TYPOGRAPHY, Pair, pairs, render, run, verdicts

GOLD = Path("eval/gold_retraites.csv")
REPORT = Path(f"docs/evaluation/juges_{PROMPT_VERSION}.md")
FIELDS = ["mesure_cle", "candidat", "chambre", "scrutin", "intitule", "groupe", "sigle", "relation", "nature_du_vote", "justification",
          "annotation"]
RELATIONS = ["dans_le_sens", "contraire", "ambigu", "hors_sujet"]
CONTEXT_MAX = 4000  # fin du débat qui précède le scrutin, pour comprendre ce qui est voté


def balanced(candidates: list[Pair], n: int, seed: int = 0) -> list[Pair]:
    """Tirage tour à tour dans chaque groupe : aucun groupe n'est sur-représenté tant que les autres ont des paires."""
    rng = random.Random(seed)
    by_group: dict[int, list[Pair]] = defaultdict(list)
    for p in candidates:
        by_group[p.group_id].append(p)
    for v in by_group.values():
        rng.shuffle(v)
    out: list[Pair] = []
    while len(out) < n and any(by_group.values()):
        for g in sorted(by_group):
            if by_group[g] and len(out) < n:
                out.append(by_group[g].pop())
    return out


def kappa(a: list[str], b: list[str]) -> float | None:
    """Kappa de Cohen entre deux séries d'étiquettes."""
    n = len(a)
    if n == 0:
        return None
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in ca) / n**2
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def write_sample(n: int, limit: int, contexts: Path, overwrite: bool) -> None:
    if GOLD.exists() and any(r["relation"] for r in csv.DictReader(GOLD.open(encoding="utf-8"))) and not overwrite:
        raise SystemExit(f"{GOLD} contient déjà des annotations : --ecraser pour le remplacer")
    with db.connect() as conn:
        dictionary = build_dictionary(conn)
        chosen = balanced(pairs(conn, limit), n)
        rows, out = [], []
        for i, p in enumerate(chosen):
            cle, candidat = conn.execute("select m.cle, c.full_name from concordance.measures m join concordance.candidates c "
                                         "on c.id = m.candidate_id where m.id = %s", (p.measure_id,)).fetchone() or ("", "")
            chambre, scrutin, intitule, debat = conn.execute("select chamber, external_id, intitule, debat from concordance.ballots "
                                                             "where id = %s", (p.ballot_id,)).fetchone() or ("", "", "", "")
            groupe, sigle = conn.execute("select external_id, coalesce(sigle, libelle) from concordance.parl_groups where id = %s",
                                         (p.group_id,)).fetchone() or ("", "")
            rows.append({"mesure_cle": cle, "candidat": candidat, "chambre": chambre, "scrutin": scrutin, "intitule": intitule[:160],
                         "groupe": groupe, "sigle": sigle, "relation": "", "nature_du_vote": "", "justification": "", "annotation": ""})
            # Annotation à l'aveugle : même anonymisation que le juge, avec la fin du débat pour comprendre le texte voté.
            # ponytail: le débat est anonymisé à part, les autres groupes peuvent y recevoir d'autres lettres que dans
            # le message (seule celle du groupe jugé coïncide) ; un seul appel à anonymize si l'on réannote.
            rng = random.Random(f"annotation-{i}")
            message, _, mapping = render(p, dictionary, rng)
            [context], _ = anonymize([(debat or "")[-CONTEXT_MAX:].translate(TYPOGRAPHY)], p.group_id, dictionary,
                                     random.Random(f"annotation-{i}"))
            label = next(lab for lab, ids in mapping.items() if ids == [p.group_id])
            out.append({"id": i, "groupe": label, "message": message, "debat": context})
    with GOLD.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    contexts.write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out), encoding="utf-8")
    print(f"{len(rows)} paires dans {GOLD}, contextes dans {contexts}")


def reference(conn: psycopg.Connection[Any], gold: list[dict[str, str]]) -> dict[tuple[int, int, int], dict[str, str]]:
    """Paires du jeu de référence -> (mesure, scrutin, groupe) en base."""
    keys: dict[tuple[int, int, int], dict[str, str]] = {}
    for r in gold:
        row = conn.execute("""
            select m.id, b.id, g.id from concordance.measures m, concordance.ballots b, concordance.parl_groups g
            where m.cle = %s and b.chamber = %s and b.external_id = %s and g.chamber = b.chamber
              and g.legislature is not distinct from b.legislature and g.external_id = %s""",
                           (r["mesure_cle"], r["chambre"], r["scrutin"], r["groupe"])).fetchone()
        if row:
            keys[(row[0], row[1], row[2])] = r
    return keys


def judge_reference(judge: str, parallel: int) -> None:
    """Fait juger par `judge` les paires du jeu de référence pas encore jugées avec la consigne en cours."""
    with db.connect() as conn:
        keys = reference(conn, list(csv.DictReader(GOLD.open(encoding="utf-8"))))
        done = set(conn.execute("select measure_id, ballot_id, group_id from concordance.judgments "
                                "where model = %s and prompt_version = %s", (judge, PROMPT_VERSION)).fetchall())
        todo = [p for p in pairs(conn, 5) if (k := (p.measure_id, p.ballot_id, p.group_id)) in keys and k not in done]
        run(conn, judge, todo, build_dictionary(conn), parallel)


def evaluate() -> str:
    gold = list(csv.DictReader(GOLD.open(encoding="utf-8")))
    with db.connect() as conn:
        keys = reference(conn, gold)
        found = verdicts(conn)
    lines = [f"# Évaluation des juges ({date.today()})", "",
             f"Consigne `{PROMPT_VERSION}`. Jeu de référence : {len(gold)} paires ({GOLD}), "
             f"annotation : {', '.join(f'{k} ({v})' for k, v in Counter(r['annotation'] for r in gold).items())}.", ""]
    lines += ["| Juge | Paires jugées | Rejetées | Accord avec l'annotation |", "|---|---|---|---|"]
    per_judge: dict[str, dict[tuple[int, int, int], str]] = {}
    for judge in JUDGES:
        judged = {k: v["juges"][judge] for k, v in found.items() if k in keys and judge in v["juges"]}
        valid: dict[tuple[int, int, int], str] = {k: j["relation"] for k, j in judged.items() if not j["rejet"]}
        per_judge[judge] = valid
        hits = sum(valid[k] == keys[k]["relation"] for k in valid)
        lines.append(f"| `{judge}` | {len(judged)} | {len(judged) - len(valid)} | "
                     f"{hits}/{len(valid)} ({hits / len(valid):.0%}) |" if valid else f"| `{judge}` | {len(judged)} | - | - |")
    both = [k for k in per_judge[next(iter(JUDGES))] if all(k in v for v in per_judge.values())]
    a, b = ([per_judge[j][k] for k in both] for j in JUDGES)
    k_value = kappa(a, b)
    published = {k: v["relation"] for k, v in found.items() if k in keys and v["relation"]}
    hits = sum(published[k] == keys[k]["relation"] for k in published)
    lines += ["", f"Kappa entre les deux juges : {k_value:.2f} sur {len(both)} paires jugées par les deux." if k_value is not None
              else "Kappa entre les deux juges : pas encore de paire jugée par les deux.",
              f"Verdict publié (accord des deux juges ou relecture) : {len(published)} paires, "
              + (f"dont {hits} conformes à l'annotation ({hits / len(published):.0%})." if published else "aucune."), ""]
    lines += ["## Matrice de confusion (lignes : annotation, colonnes : juge)", ""]
    for judge, by_pair in per_judge.items():
        lines += [f"`{judge}`", "", "| | " + " | ".join(RELATIONS) + " |", "|---" * (len(RELATIONS) + 1) + "|"]
        for gold_rel in RELATIONS:
            counts = Counter(by_pair[k] for k in by_pair if keys[k]["relation"] == gold_rel)
            lines.append(f"| {gold_rel} | " + " | ".join(str(counts[r]) for r in RELATIONS) + " |")
        lines.append("")
    lines += ["## Accord par groupe", "", "Un juge biaisé se tromperait plus souvent pour certains groupes.", "",
              "| Groupe | Paires | " + " | ".join(f"`{j}`" for j in JUDGES) + " |", "|---|---" + "|---" * len(JUDGES) + "|"]
    for sigle in sorted({r["sigle"] for r in keys.values()}):
        ks = [k for k, r in keys.items() if r["sigle"] == sigle]
        cells = []
        for by_pair in per_judge.values():
            v = [k for k in ks if k in by_pair]
            cells.append(f"{sum(by_pair[k] == keys[k]['relation'] for k in v)}/{len(v)}" if v else "-")
        lines.append(f"| {sigle} | {len(ks)} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--echantillon", type=int, help="tirer N paires à annoter")
    parser.add_argument("--limite", type=int, default=2, help="scrutins par mesure parmi lesquels tirer l'échantillon")
    parser.add_argument("--ecraser", action="store_true", help="remplacer un jeu de référence déjà annoté")
    parser.add_argument("--contextes", type=Path, help="fichier JSONL des contextes anonymisés à annoter")
    parser.add_argument("--juger", choices=JUDGES, help="faire d'abord juger les paires de référence par ce juge")
    parser.add_argument("--paralleles", type=int, default=1, help="requêtes envoyées en même temps au juge")
    args = parser.parse_args()
    if args.juger:
        judge_reference(args.juger, args.paralleles)
    if args.echantillon:
        write_sample(args.echantillon, args.limite, args.contextes or Path("eval/gold_contextes.jsonl"), args.ecraser)
        return
    report = evaluate()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
