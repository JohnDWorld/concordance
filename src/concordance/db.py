import os
from typing import Any

import psycopg
from psycopg import sql

from concordance.models import Ballot, Chamber, ParlGroup


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


def load_votes(conn: psycopg.Connection[Any], chamber: Chamber, groups: list[ParlGroup], ballots: list[Ballot]) -> None:
    """Charge groupes, scrutins et positions d'une chambre. Un groupe inconnu fait échouer le chargement."""
    with conn.cursor() as cur:
        upsert(cur, "parl_groups", [g.model_dump() for g in groups], ("chamber", "legislature", "external_id"))
        upsert(cur, "ballots", [b.model_dump(exclude={"positions"}) for b in ballots], ("chamber", "external_id"))
        cur.execute("select legislature, external_id, id from concordance.parl_groups where chamber = %s", (chamber,))
        group_ids = {(leg, ext): id_ for leg, ext, id_ in cur}
        cur.execute("select external_id, id from concordance.ballots where chamber = %s", (chamber,))
        ballot_ids = dict(cur.fetchall())
        rows = [
            {
                **p.model_dump(exclude={"group_external_id"}),
                "ballot_id": ballot_ids[b.external_id],
                "group_id": group_ids[(b.legislature, p.group_external_id)],
            }
            for b in ballots
            for p in b.positions
        ]
        upsert(cur, "group_positions", rows, ("ballot_id", "group_id"))
