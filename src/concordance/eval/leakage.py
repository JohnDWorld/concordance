"""Test de fuite (docs/methodologie.md) : un modèle devine le groupe de l'orateur d'un texte anonymisé.

Les mêmes textes sont anonymisés deux fois : à la main (référence : ce que le fond trahit à lui seul) et par
l'anonymiseur. L'anonymiseur est accepté si son taux ne dépasse pas celui de la référence de plus de MARGIN.
"""

import json
import os
import random
import re
import urllib.request
from collections import Counter
from datetime import date
from pathlib import Path

from concordance import db
from concordance.pipeline.anonymize import anonymize, build_dictionary

SAMPLE = Path("eval/fuite_echantillon.jsonl")
REFERENCE = Path("eval/fuite_reference.jsonl")
REPORT = Path("docs/evaluation/fuite.md")
MODEL = "qwen3-30b-a3b"  # servi par llama.cpp (llama-village), compatible OpenAI
MARGIN = 0.05  # fixée avant le test
PLACEHOLDER = re.compile(r"Groupe [A-Z]|\[(?:parti|personne|terme partisan)\]")
PROMPT = """Voici l'extrait d'une explication de vote prononcée à l'Assemblée nationale (17e législature) par l'orateur \
d'un groupe parlementaire. Les noms de groupes, de partis et de personnes ont été masqués.

Groupes possibles : {options}

Extrait :
{text}

Quel groupe a prononcé cette explication ? Réponds uniquement par un sigle de la liste."""


def only_masked(original: str, masked: str, longest: int = 90) -> bool:
    """Vrai si le texte masqué ne diffère de l'original que par des étiquettes : chaque morceau de texte entre deux
    étiquettes se retrouve tel quel et dans l'ordre, et un écart n'est permis qu'à la place d'une étiquette."""
    pos, after_label = 0, False
    for i, part in enumerate(re.split(f"({PLACEHOLDER.pattern})", masked)):
        if i % 2:  # étiquette
            after_label = True
            continue
        if not part:
            continue
        found = original.find(part, pos)
        gap = found - pos
        if found < 0 or (gap and (not after_label or gap > longest)):
            return False
        pos, after_label = found + len(part), False
    tail = len(original) - pos
    return tail == 0 or (after_label and tail <= longest)


def guess(text: str, options: list[str]) -> str:
    url = os.environ.get("LLM_URL", "http://localhost:8012") + "/v1/chat/completions"
    body = {"model": MODEL, "temperature": 0, "max_tokens": 12,
            "messages": [{"role": "user", "content": PROMPT.format(options=", ".join(options), text=text)}]}
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        answer: str = json.load(response)["choices"][0]["message"]["content"].strip()
    return next((o for o in sorted(options, key=len, reverse=True) if o.lower() in answer.lower()), answer)


def main() -> None:
    sample = [json.loads(line) for line in SAMPLE.open(encoding="utf-8")]
    reference = {r["id"]: r["reference"] for r in map(json.loads, REFERENCE.open(encoding="utf-8"))}
    # Même mise en forme que l'anonymiseur, pour que seul le masquage diffère entre les deux versions.
    same_form = {k: re.sub(r"\b[Gg]roupe (Groupe [A-Z])\b", r"\1", v) for k, v in reference.items()}
    options = sorted({s["sigle"] for s in sample})
    with db.connect() as conn:
        dictionary = build_dictionary(conn)
        groups = dict(conn.execute("select id, group_id from concordance.vote_explanations where id = any(%s)",
                                   ([s["id"] for s in sample],)).fetchall())
    rejected = [s["id"] for s in sample if not only_masked(s["texte"], reference[s["id"]])]
    kept = [s for s in sample if s["id"] not in rejected]
    hits: Counter[str] = Counter()
    for s in kept:
        [automatic], _ = anonymize([s["texte"]], groups[s["id"]], dictionary, random.Random(s["id"]))
        for name, text in (("reference", same_form[s["id"]]), ("anonymiseur", automatic), ("brut", s["texte"])):
            hits[name] += guess(text, options) == s["sigle"]
    n = len(kept)
    rate = {k: hits[k] / n for k in ("brut", "reference", "anonymiseur")}
    accepted = rate["anonymiseur"] <= rate["reference"] + MARGIN
    lines = [f"# Test de fuite ({date.today()})", "",
             f"Modèle devineur : `{MODEL}`. {n} explications de vote (Assemblée, 17e législature), {len(options)} groupes "
             f"possibles, hasard : {1 / len(options):.0%}. Références écartées (modifiées au-delà des étiquettes) : {len(rejected)}.", "",
             "| Version du texte | Groupe deviné |", "|---|---|",
             f"| Brut, non anonymisé | {rate['brut']:.0%} |",
             f"| Anonymisé à la main (référence) | {rate['reference']:.0%} |",
             f"| Anonymiseur automatique | {rate['anonymiseur']:.0%} |", "",
             f"Marge tolérée : {MARGIN:.0%}. Verdict : **{'accepté' if accepted else 'refusé, l’anonymiseur fuit'}**."]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
