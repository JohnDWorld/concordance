"""Juge : la position d'un groupe sur un scrutin va-t-elle dans le sens d'une mesure ? (contrat dans CLAUDE.md)

Tout texte envoyé au juge passe par l'anonymiseur. Deux juges de familles différentes jugent chaque paire ; un
verdict n'est publié que s'ils sont d'accord, sinon la paire attend une relecture humaine (docs/methodologie.md).
"""

import argparse
import json
import os
import random
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

import psycopg
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from concordance import db
from concordance.models import Nature
from concordance.pipeline.anonymize import Dictionary, anonymize, build_dictionary
from concordance.pipeline.retrieve import perimeter, search

PROMPT_VERSION = "judge_v2"
SYSTEM, MESSAGE = re.sub(r"^<!--.*?-->\n", "", (Path(__file__).parents[3] / "prompts" / f"{PROMPT_VERSION}.md")
                         .read_text(encoding="utf-8"), flags=re.S).split("\n---MESSAGE---\n")
# Deux familles, Qwen (Alibaba) et Llama (Meta), chacune servie par llama.cpp (API compatible OpenAI) :
# variable d'environnement de l'adresse, adresse par défaut. Évaluation : docs/evaluation/juges_<consigne>.md.
JUDGES = {"qwen3-30b-a3b": ("LLM_URL", "http://localhost:8012"), "llama3.2": ("JUGE2_URL", "http://localhost:8013")}
Relation = Literal["dans_le_sens", "contraire", "ambigu", "hors_sujet"]
Effect = Literal["rapproche", "eloigne", "ambigu", "hors_sujet"]
AMENDMENT_MAX = 3000  # caractères du dispositif et de l'exposé envoyés au juge
CHAMBERS = {"an": "Assemblée nationale", "senat": "Sénat", "pe": "Parlement européen"}
# Les modèles recopient l'apostrophe typographique et les espaces insécables en caractères simples : le texte envoyé
# (contre lequel les citations sont vérifiées) les remplace avant l'anonymisation. La fiche publie le texte d'origine.
TYPOGRAPHY = str.maketrans({"’": "'", "\u00a0": " ", "\u202f": " "})


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["mesure", "scrutin", "explication"]
    extrait: str = Field(min_length=1)


class Verdict(BaseModel):
    """Sortie du juge. Ordre des champs : le modèle cite, établit l'effet du texte et justifie avant de conclure."""
    model_config = ConfigDict(extra="forbid")
    nature_du_vote: Nature
    citations: list[Citation] = Field(min_length=1)
    effet_du_texte: Effect
    justification: str = Field(max_length=520)  # borne la génération ; la règle du contrat reste 80 mots
    relation: Relation
    confiance: float = Field(ge=0, le=1)

    @field_validator("justification")
    @classmethod
    def at_most_80_words(cls, v: str) -> str:
        if len(v.split()) > 80:
            raise ValueError("justification de plus de 80 mots")
        return v


SCHEMA = Verdict.model_json_schema()


class Pair(BaseModel):
    """Données d'une paire avant anonymisation."""
    measure_id: int
    ballot_id: int
    group_id: int
    mesure: str
    scrutin: str
    position: str  # chiffres seuls, l'étiquette du groupe est ajoutée par render
    explication: str | None
    pour: int
    contre: int
    abstention: int
    majorite: Literal["pour", "contre"]


def expected(effect: str, pair: Pair) -> str:
    """Relation qui découle de l'effet du texte et du vote du groupe (consigne judge_v2, étape 2)."""
    if effect in ("ambigu", "hors_sujet"):
        return effect
    if max(pair.pour, pair.contre, pair.abstention) * 2 <= pair.pour + pair.contre + pair.abstention:
        return "ambigu"  # groupe partagé
    return "dans_le_sens" if (effect == "rapproche") == (pair.majorite == "pour") else "contraire"


def render(pair: Pair, dictionary: Dictionary, rng: random.Random) -> tuple[str, str, dict[str, list[int]]]:
    """Message anonymisé envoyé au juge, textes sources qu'il contient (sans titres ni phrases du gabarit, contre
    lesquels les citations sont vérifiées) et correspondance des étiquettes."""
    texts = [t.translate(TYPOGRAPHY) for t in (pair.mesure, pair.scrutin, pair.explication or "")]
    texts, mapping = anonymize(texts, pair.group_id, dictionary, rng)
    label = next(lab for lab, ids in mapping.items() if ids == [pair.group_id])
    mesure, scrutin, explication = texts
    position = f"{label} : {pair.position}"
    message = MESSAGE.format(mesure=mesure, scrutin=scrutin, groupe=label, position=position,
                             explication=explication or f"Aucune explication de vote disponible pour le {label}.")
    return message, "\n".join((mesure, scrutin, position, explication)), mapping


def check(raw: str, sources: str, pair: Pair) -> tuple[Verdict | None, str | None]:
    """Verdict validé et motif de rejet : réponse hors contrat, citation absente des textes envoyés au juge, ou relation
    qui ne découle pas de l'effet du texte et du vote. La section indiquée par « source » n'est pas contrôlée : seule
    compte la présence mot pour mot (CLAUDE.md, règle 4)."""
    try:
        verdict = Verdict.model_validate_json(raw)
    except ValidationError as e:
        return None, f"réponse hors contrat : {e.errors()[0]['msg']} ({raw[:300]})"
    for c in verdict.citations:
        if c.extrait not in sources:
            return verdict, f"citation introuvable dans le texte envoyé : {c.extrait[:300]}"
    if verdict.relation != (want := expected(verdict.effet_du_texte, pair)):
        return verdict, f"relation incohérente : effet « {verdict.effet_du_texte} » et vote du groupe donnent « {want} »"
    return verdict, None


def post(url: str, body: dict[str, Any]) -> Any:
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.load(response)


def ask(judge: str, message: str) -> str:
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": message}]
    return str(post(os.environ.get(*JUDGES[judge]) + "/v1/chat/completions", {
        "model": judge, "messages": messages, "temperature": 0, "seed": 0, "max_tokens": 800,
        "response_format": {"type": "json_schema", "json_schema": {"name": "verdict", "schema": SCHEMA}}})
        ["choices"][0]["message"]["content"])


def judge_pair(judge: str, pair: Pair, dictionary: Dictionary, seed: str = "") -> dict[str, Any]:
    """Un jugement, prêt à être inséré dans concordance.judgments. Étiquettes tirées par paire, juge et graine."""
    rng = random.Random(f"{pair.measure_id}-{pair.ballot_id}-{pair.group_id}-{judge}{seed}")
    message, sources, mapping = render(pair, dictionary, rng)
    verdict, rejet = check(ask(judge, message), sources, pair)
    fields = verdict.model_dump() if verdict else {}
    if verdict:
        fields["citations"] = Jsonb(fields["citations"])
    return {"measure_id": pair.measure_id, "ballot_id": pair.ballot_id, "group_id": pair.group_id, "model": judge,
            "prompt_version": PROMPT_VERSION, "texte_anonymise": message, "mapping_anonymisation": Jsonb(mapping),
            "rejet": rejet, **fields}


def figures(pour: int, contre: int, abstention: int, non_votants: int, membres: int | None, majority: str) -> str:
    total = f", sur {membres} membres" if membres else ""
    return (f"{pour} pour, {contre} contre, {abstention} abstentions, {non_votants} non-votants{total}. "
            f"Position majoritaire : {majority}.")


def ballot_text(conn: psycopg.Connection[Any], ballot_id: int) -> str:
    row = conn.execute("""
        select b.chamber, b.legislature, b.ballot_date, b.intitule, b.objet, b.nature, b.sort, b.dossier,
               a.dispositif, a.expose_sommaire
        from concordance.ballots b left join concordance.amendments a on a.id = b.amendment_id where b.id = %s""",
                       (ballot_id,)).fetchone()
    assert row is not None
    chamber, leg, day, intitule, objet, nature, sort, dossier, dispositif, expose = row
    lines = [f"{CHAMBERS[chamber]}{f', {leg}e législature' if leg else ''}, {day}.", f"Intitulé : {intitule}"]
    lines += [f"{label} : {v}" for label, v in (("Nature", nature), ("Objet", objet), ("Dossier", dossier),
                                                 ("Résultat", sort)) if v and v != intitule]
    lines += [f"{label} : {v[:AMENDMENT_MAX]}{' [texte tronqué]' if len(v) > AMENDMENT_MAX else ''}" for label, v in (("Amendement voté, dispositif", dispositif),
                                                                 ("Amendement voté, exposé sommaire", expose)) if v]
    return "\n".join(lines)


# Seules les positions majoritaires pour ou contre sont jugées : l'abstention, le non-vote et le partage à égalité
# sont décrits sur la fiche sans interprétation. Au Parlement européen, les délégations nationales françaises.
POSITIONS = """
select gp.group_id, gp.pour, gp.contre, gp.abstention, gp.non_votants, gp.membres, gp.position_majoritaire
from concordance.group_positions gp join concordance.parl_groups g on g.id = gp.group_id
where gp.ballot_id = %s and gp.position_majoritaire in ('pour', 'contre')
  and (g.chamber <> 'pe' or g.categorie = 'delegation_nationale')
order by gp.group_id
"""


def pairs(conn: psycopg.Connection[Any], limit: int, measure: int | None = None) -> list[Pair]:
    """Paires à juger : pour chaque mesure, les `limit` scrutins les plus proches, chaque groupe qui a voté.
    Rang par rang (le plus proche de chaque mesure d'abord) : un passage interrompu couvre déjà toutes les mesures."""
    measures = conn.execute("select id, theme, citation from concordance.measures where %(m)s::bigint is null or id = %(m)s "
                            "order by id", {"m": measure}).fetchall()
    scope = {theme: perimeter(conn, theme) for _, theme, _ in measures}
    ranked = sorted((rank, measure_id, citation, ballot_id) for measure_id, theme, citation in measures
                    for rank, (ballot_id, *_) in enumerate(search(conn, measure_id, theme, limit, scope[theme])))
    out: list[Pair] = []
    ballots: dict[int, str] = {}
    for _, measure_id, citation, ballot_id in ranked:
        scrutin = ballots.setdefault(ballot_id, ballot_text(conn, ballot_id))
        for group_id, pour, contre, abst, nv, membres, majority in conn.execute(POSITIONS, (ballot_id,)).fetchall():
            texts = [t for (t,) in conn.execute("select texte from concordance.vote_explanations "
                                                "where ballot_id = %s and group_id = %s order by id", (ballot_id, group_id))]
            out.append(Pair(measure_id=measure_id, ballot_id=ballot_id, group_id=group_id, mesure=citation,
                            scrutin=scrutin, position=figures(pour, contre, abst, nv, membres, majority),
                            explication="\n\n".join(texts) or None, pour=pour, contre=contre, abstention=abst,
                            majorite=majority))
    return out


LATEST = """
select distinct on (measure_id, ballot_id, group_id, model) measure_id, ballot_id, group_id, model, relation, rejet,
       justification, mapping_anonymisation, texte_anonymise
from concordance.judgments where prompt_version = %s
order by measure_id, ballot_id, group_id, model, id desc
"""


def verdicts(conn: psycopg.Connection[Any]) -> dict[tuple[int, int, int], dict[str, Any]]:
    """Dernier jugement de chaque juge par paire, et verdict publié : relecture humaine, sinon accord des deux juges."""
    out: dict[tuple[int, int, int], dict[str, Any]] = {}
    for m, b, g, model, relation, rejet, justification, mapping, sent in conn.execute(LATEST, (PROMPT_VERSION,)):
        out.setdefault((m, b, g), {"juges": {}})["juges"][model] = {
            "relation": relation, "rejet": rejet, "justification": justification, "mapping": mapping, "texte": sent}
    reviews = {(m, b, g): (r, j) for m, b, g, r, j in conn.execute(
        "select measure_id, ballot_id, group_id, relation, justification from concordance.reviews")}
    for key, v in out.items():
        v["relation"], v["statut"] = consensus({j: x["relation"] if not x["rejet"] else None for j, x in v["juges"].items()},
                                              reviews.get(key, (None, None))[0])
    return out


def consensus(relations: dict[str, str | None], review: str | None) -> tuple[str | None, str]:
    if review:
        return review, "relecture humaine"
    found = [relations.get(j) for j in JUDGES]
    if None in found:
        return None, "jugement manquant ou rejeté"
    if len(set(found)) > 1:
        return None, "désaccord des juges"
    return found[0], "accord des deux juges"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--juge", choices=JUDGES, required=True)
    parser.add_argument("--limite", type=int, default=5, help="scrutins par mesure")
    parser.add_argument("--mesure", type=int, help="une seule mesure")
    parser.add_argument("--refaire", action="store_true", help="rejuger les paires déjà jugées par ce juge")
    parser.add_argument("--paralleles", type=int, default=1, help="requêtes envoyées en même temps au serveur du juge")
    args = parser.parse_args()
    with db.connect() as conn:
        dictionary = build_dictionary(conn)
        done = set() if args.refaire else set(conn.execute(
            "select measure_id, ballot_id, group_id from concordance.judgments where model = %s and prompt_version = %s",
            (args.juge, PROMPT_VERSION)).fetchall())
        todo = [p for p in pairs(conn, args.limite, args.mesure) if (p.measure_id, p.ballot_id, p.group_id) not in done]
        run(conn, args.juge, todo, dictionary, args.paralleles)


def run(conn: psycopg.Connection[Any], judge: str, todo: list[Pair], dictionary: Dictionary, parallel: int) -> None:
    print(f"{len(todo)} paires à juger par {judge}", flush=True)
    # Plusieurs requêtes en file : le serveur les traite une à une, mais n'attend plus entre deux paires.
    with ThreadPoolExecutor(parallel) as pool:
        for i, row in enumerate(pool.map(lambda p: attempt(judge, p, dictionary), todo), 1):
            if row:
                save(conn, row, i, len(todo))


def attempt(judge: str, pair: Pair, dictionary: Dictionary) -> dict[str, Any] | None:
    """Un serveur indisponible n'est pas un jugement : la paire n'est pas enregistrée et sera rejugée au passage suivant."""
    try:
        return judge_pair(judge, pair, dictionary)
    except OSError as e:  # URLError, HTTPError, délai dépassé
        print(f"paire {pair.measure_id}-{pair.ballot_id}-{pair.group_id} non jugée : {e}", flush=True)
        return None


def save(conn: psycopg.Connection[Any], row: dict[str, Any], i: int, total: int) -> None:
    with conn.cursor() as cur:
        db.upsert(cur, "judgments", [row], ("id",))  # id généré : toujours une insertion
    conn.commit()
    if i % 20 == 0 or row["rejet"]:
        print(f"{i}/{total}", row.get("relation"), (row["rejet"] or "")[:160], flush=True)


if __name__ == "__main__":
    main()
