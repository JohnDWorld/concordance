from datetime import date

from concordance.ingest.an import parse_ballot, parse_group

# Extrait réduit de VTANR5L16V1240 (structure réelle de Scrutins.json, nombres en chaînes).
SCRUTIN = {
    "uid": "VTANR5L16V1240",
    "numero": "1240",
    "legislature": "16",
    "seanceRef": "RUANR5L16S2023IDS26958",
    "dateScrutin": "2023-03-20",
    "typeVote": {"codeTypeVote": "MOC", "libelleTypeVote": "scrutin public solennel"},
    "sort": {"code": "rejeté"},
    "titre": "la motion de censure déposée en application de l'article 49, alinéa 3, de la Constitution",
    "objet": {"libelle": "la motion de censure déposée en application de l'article 49, alinéa 3, de la Constitution",
              "dossierLegislatif": None},
    "ventilationVotes": {"organe": {"groupes": {"groupe": [
        {"organeRef": "PO800538", "nombreMembresGroupe": "170",
         "vote": {"positionMajoritaire": "pour",
                  "decompteVoix": {"nonVotants": "1", "pour": "0", "contre": "0", "abstentions": "0",
                                   "nonVotantsVolontaires": "2"}}},
        {"organeRef": "PO800520", "nombreMembresGroupe": "88",
         "vote": {"positionMajoritaire": "pour",
                  "decompteVoix": {"nonVotants": "0", "pour": "88", "contre": "0", "abstentions": "0",
                                   "nonVotantsVolontaires": "0"}}},
    ]}}},
}


def test_parse_ballot() -> None:
    b = parse_ballot(SCRUTIN)
    assert (b.external_id, b.legislature, b.ballot_date, b.nature, b.sort) == ("VTANR5L16V1240", 16, date(2023, 3, 20), "motion", "rejeté")
    assert b.objet is None  # identique au titre
    assert b.source_url == "https://www.assemblee-nationale.fr/dyn/16/scrutins/1240"
    silent, voting = b.positions
    assert (silent.group_external_id, silent.membres, silent.pour, silent.non_votants, silent.non_votants_volontaires) == ("PO800538", 170, 0, 1, 2)
    assert silent.position_majoritaire is None  # aucun vote exprimé : la position de la source n'a pas de sens
    assert (voting.pour, voting.position_majoritaire) == (88, "pour")


def test_parse_group() -> None:
    organe = {"uid": "PO830170", "codeType": "GP", "libelle": "Socialistes et apparentés", "libelleAbrege": "SOC",
              "legislature": "16", "viMoDe": {"dateDebut": "2023-10-19", "dateFin": "2024-06-09"}}
    g = parse_group(organe, {16, 17})
    assert g is not None and (g.sigle, g.legislature, g.end_date) == ("SOC", 16, date(2024, 6, 9))
    assert parse_group(organe, {17}) is None
    assert parse_group({**organe, "codeType": "COMPER"}, {16}) is None
