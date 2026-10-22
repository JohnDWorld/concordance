"""Lignes chargées en base, communes aux trois chambres."""

from datetime import date
from typing import Literal

from pydantic import BaseModel

Chamber = Literal["an", "senat", "pe"]
Nature = Literal["texte_entier", "article", "amendement", "motion", "autre"]
Position = Literal["pour", "contre", "abstention", "non_votant"]
Category = Literal["groupe", "delegation_nationale"]


class ParlGroup(BaseModel):
    chamber: Chamber
    legislature: int | None
    external_id: str
    sigle: str | None
    libelle: str
    start_date: date | None
    end_date: date | None
    categorie: Category = "groupe"


class GroupPosition(BaseModel):
    group_external_id: str
    membres: int | None
    pour: int
    contre: int
    abstention: int
    non_votants: int
    non_votants_volontaires: int | None
    position_majoritaire: Position | None


class VoteExplanation(BaseModel):
    ballot_external_id: str
    ballot_date: date  # contrôle : le scrutin relié doit dater du jour de la séance
    group_external_id: str
    orateur: str
    orateur_external_id: str | None
    texte: str
    source_url: str


class Ballot(BaseModel):
    chamber: Chamber
    legislature: int | None
    external_id: str
    ballot_date: date
    intitule: str
    objet: str | None
    nature: Nature | None
    sort: str | None
    dossier: str | None
    seance_ref: str | None
    source_url: str
    positions: list[GroupPosition]


CandidateEventKind = Literal["declaration", "retrait", "battu_primaire", "liste_officielle", "absent_liste_officielle"]


class CandidateEventRow(BaseModel):
    """Ligne de donnees/candidats.csv : une entrée ou sortie de la liste, datée et sourcée."""
    candidat: str
    nom: str
    parti: str
    evenement: CandidateEventKind
    date: date
    source_url: str
    note: str = ""


class MeasureRow(BaseModel):
    """Ligne de donnees/mesures_retraites.csv : citation exacte d'une source officielle du candidat."""
    candidat: str
    sujet: str
    citation: str
    source_url: str
    consulte_le: date
