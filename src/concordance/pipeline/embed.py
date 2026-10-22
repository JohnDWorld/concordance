"""Embeddings des scrutins et des mesures (Ollama local), pour la recherche hybride."""

import argparse
import json
import os
import urllib.request
from typing import Any

import psycopg

from concordance import db

MODEL = "qwen3-embedding:0.6b"  # dimension 1024, cf. migration recherche_hybride
BATCH = 64
# Qwen3-Embedding : les requêtes portent une consigne, les documents non.
QUERY = "Instruct: Retrouver les scrutins parlementaires qui portent sur cette mesure de programme\nQuery: {}"
# Texte d'un scrutin : son intitulé ne dit souvent pas le sujet (« l'amendement n° 7 de M. X à l'article 2... »),
# les explications de vote et le débat, si. On ajoute le début de l'explication de chaque groupe et du débat.
BALLOT_TEXT = """concat_ws(' ', intitule, objet, dossier, (
    select left(string_agg(left(e.texte, 300), ' ' order by e.id), 1000)
    from concordance.vote_explanations e where e.ballot_id = ballots.id), left(debat, 1000))"""


def embed(texts: list[str]) -> list[list[float]]:
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/embed"
    request = urllib.request.Request(url, data=json.dumps({"model": MODEL, "input": texts}).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        vectors: list[list[float]] = json.load(response)["embeddings"]
    return vectors


def vector(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def fill(conn: psycopg.Connection[Any], table: str, text_sql: str, template: str = "{}") -> int:
    """Calcule les embeddings manquants d'une table. ponytail: un texte modifié garde son ancien embedding."""
    done = 0
    while True:
        rows = conn.execute(f"select id, {text_sql} from concordance.{table} where embedding is null order by id limit {BATCH}").fetchall()
        if not rows:
            return done
        vectors = embed([template.format(text) for _, text in rows])
        with conn.cursor() as cur:
            cur.executemany(f"update concordance.{table} set embedding = %s::vector where id = %s",
                            [(vector(v), id_) for (id_, _), v in zip(rows, vectors, strict=True)])
        conn.commit()
        done += len(rows)
        print(f"{table} : {done}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refaire", action="store_true", help="tout recalculer (après une nouvelle ingestion d'explications)")
    with db.connect() as conn:
        if parser.parse_args().refaire:
            conn.execute("update concordance.measures set embedding = null")
            conn.execute("update concordance.ballots set embedding = null")
            conn.commit()
        measures = fill(conn, "measures", "citation", QUERY)
        ballots = fill(conn, "ballots", BALLOT_TEXT)
    print(f"Embeddings calculés : {measures} mesures, {ballots} scrutins ({MODEL})")


if __name__ == "__main__":
    main()
