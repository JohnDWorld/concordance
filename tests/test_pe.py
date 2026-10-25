from datetime import date

from concordance.ingest.pe import parse_ballots, parse_groups, term_of, term_starts

MEMBERSHIPS = [
    {"member_id": "1", "group_code": "EPP", "term": "9", "start_date": "2019-07-02", "end_date": "2024-07-15"},
    {"member_id": "2", "group_code": "EPP", "term": "10", "start_date": "2024-07-16", "end_date": ""},
    {"member_id": "3", "group_code": "PFE", "term": "10", "start_date": "2024-07-16", "end_date": "2025-01-01"},
]
GROUPS = [{"code": "EPP", "official_label": "Groupe du Parti populaire européen", "label": "EPP", "short_label": "EPP"},
          {"code": "PFE", "official_label": "", "label": "Patriots for Europe", "short_label": "PfE"}]
VOTE = {"id": "198261", "timestamp": "2026-10-08 12:06:35", "display_title": "Human rights situation in Iran",
        "description": "", "amendment_subject": "", "amendment_number": "", "is_main": "True", "result": "",
        "procedure_title": "", "procedure_reference": "2026/2912(RSP)"}


def test_terms() -> None:
    starts = term_starts(MEMBERSHIPS)
    assert starts == {9: date(2019, 7, 2), 10: date(2024, 7, 16)}
    assert term_of(date(2024, 7, 15), starts) == 9
    assert term_of(date(2024, 7, 16), starts) == 10


def test_parse_groups() -> None:
    groups = {(g.legislature, g.external_id): g for g in parse_groups(GROUPS, MEMBERSHIPS)}
    assert groups[(10, "EPP")].end_date is None  # un membre encore en fonction
    assert groups[(10, "PFE")].libelle == "Patriots for Europe"  # libellé officiel absent : libellé courant
    assert (9, "PFE") not in groups


def test_parse_ballots() -> None:
    member_votes = [
        {"vote_id": "198261", "group_code": "EPP", "position": "FOR", "country_code": "FRA", "national_party_id": "5441"},
        {"vote_id": "198261", "group_code": "EPP", "position": "FOR", "country_code": "DEU", "national_party_id": "1"},
        {"vote_id": "198261", "group_code": "EPP", "position": "DID_NOT_VOTE", "country_code": "FRA", "national_party_id": "5441"},
        {"vote_id": "198261", "group_code": "PFE", "position": "AGAINST", "country_code": "FRA", "national_party_id": "5494"},
        {"vote_id": "198261", "group_code": "", "position": "FOR", "country_code": "ITA", "national_party_id": "2"},
    ]
    parties = [{"id": "5441", "label": "Les Républicains", "short_label": "LR"}, {"id": "5494", "label": "Rassemblement national", "short_label": "RN"}]
    [b], delegations, without_group = parse_ballots([VOTE], member_votes, parties, term_starts(MEMBERSHIPS))
    assert (b.legislature, b.nature, b.sort, b.dossier) == (10, "texte_entier", None, "2026/2912(RSP)")
    assert b.source_url == "https://howtheyvote.eu/votes/198261"
    positions = {p.group_external_id: p for p in b.positions}
    epp, pfe, lr = positions["EPP"], positions["PFE"], positions["FRA-5441"]
    assert (epp.membres, epp.pour, epp.non_votants, epp.position_majoritaire) == (3, 2, 1, "pour")
    assert (pfe.contre, pfe.position_majoritaire) == (1, "contre")
    assert (lr.membres, lr.pour, lr.non_votants) == (2, 1, 1)  # seuls les élus français du parti
    assert "FRA-1" not in positions  # délégations étrangères non suivies
    assert {(d.external_id, d.sigle, d.categorie, d.legislature) for d in delegations} == {
        ("FRA-5441", "LR", "delegation_nationale", 10), ("FRA-5494", "RN", "delegation_nationale", 10)}
    assert without_group == 1
