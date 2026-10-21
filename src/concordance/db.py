import os
from typing import Any

import psycopg
from psycopg import sql


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(os.environ["DATABASE_URL"])


def upsert(cur: psycopg.Cursor[Any], table: str, rows: list[dict[str, Any]], conflict: tuple[str, ...]) -> None:
    """Insère ou met à jour des lignes de concordance.<table>, clé = colonnes `conflict`."""
    if not rows:
        return
    cols = list(rows[0])
    query = sql.SQL("insert into concordance.{t} ({c}) values ({v}) on conflict ({k}) do update set {u}").format(
        t=sql.Identifier(table),
        c=sql.SQL(", ").join(map(sql.Identifier, cols)),
        v=sql.SQL(", ").join(map(sql.Placeholder, cols)),
        k=sql.SQL(", ").join(map(sql.Identifier, conflict)),
        u=sql.SQL(", ").join(sql.SQL("{0} = excluded.{0}").format(sql.Identifier(c)) for c in cols if c not in conflict),
    )
    cur.executemany(query, rows)
