from datetime import date

from concordance.ingest.an_explications import match_ballot, parse_explanations


def para(order: int, anchor: str, acteur: str, nom: str, text: str, grammar: str = "PAROLE_GENERIQUE") -> str:
    return (f'<paragraphe ordre_absolu_seance="{order}" id_acteur="{acteur}" code_grammaire="{grammar}" id_syceron="{anchor}">'
            f"<orateurs><orateur><nom>{nom}</nom></orateur></orateurs><texte>{text}</texte></paragraphe>")


# Gabarit réel d'un compte rendu Syceron, réduit : sommaire puis corps.
REPORT = (
    "<compteRendu><uid>CRSANR5L16S2023O1N182</uid><seanceRef>S1</seanceRef>"
    "<metadonnees><dateSeance>20230320160000000</dateSeance><legislature>16</legislature></metadonnees>"
    '<sommaire><titreStruct id_syceron="9"><intitule>Texte</intitule></titreStruct><para id_syceron="10"/>'
    '<titreStruct id_syceron="11"><intitule>Explications de vote</intitule></titreStruct>'
    '<para id_syceron="101">Mme Alice A (AA)</para><para id_syceron="201">M. Bruno B, ministre</para>'
    '<para id_syceron="301">M. Carl C (CC)</para></sommaire>'
    "<contenu>"
    + para(1, "100", "PA9", "Mme la présidente", "La parole est à Mme Alice A.")
    + para(2, "101", "PA1", "Mme Alice A", "Nous voterons ce texte.")
    + para(3, "102", "PA2", "M. Zoé Z", "Très bien !", "INTERRUPTION_1_10")
    + para(4, "103", "PA1", "Mme Alice A", "Il est juste.")
    + para(5, "200", "PA9", "Mme la présidente", "La parole est à M. le ministre.")
    + para(6, "201", "PA5", "M. Bruno B", "Le Gouvernement est favorable.")
    + para(7, "202", "PA9", "Mme la présidente", "Voici le résultat du scrutin : Pour l’adoption 120 Contre 30")
    + para(8, "300", "PA9", "Mme la présidente", "La parole est à M. Carl C.")
    + para(9, "301", "PA3", "M. Carl C", "Nous voterons contre l’amendement.")
    + para(10, "302", "PA9", "Mme la présidente", "(L’amendement n’est pas adopté.)")
    + para(11, "303", "PA9", "Mme la présidente", "Voici le résultat du scrutin : Pour l’adoption 12 Contre 99")
    + "</contenu></compteRendu>"
)
BALLOTS = {"S1": [("V1", 120, 30), ("V2", 12, 99)]}
PERIODS: dict[str, list[tuple[str, date | None, date | None]]] = {"PA1": [("PO-AA", date(2022, 6, 28), None)], "PA3": [("PO-CC", date(2022, 6, 28), None)]}


def test_parse_explanations() -> None:
    out, stats = parse_explanations(REPORT, BALLOTS, PERIODS)
    [e] = out  # le ministre (fonction) est exclu ; Carl C. s'exprime avant un vote à main levée
    assert (e.ballot_external_id, e.group_external_id, e.orateur_external_id, e.ballot_date) == ("V1", "PO-AA", "PA1", date(2023, 3, 20))
    assert e.texte == "Nous voterons ce texte. […] Il est juste."  # interruption exclue
    assert e.source_url == "https://www.assemblee-nationale.fr/dyn/16/comptes-rendus/seance/CRSANR5L16S2023O1N182#101"
    assert stats["vote à main levée ou sans scrutin public"] == 1


def test_match_ballot() -> None:
    candidates = [("V1240", 278, 0), ("V1241", 94, 0)]
    assert match_ballot("Voici le résultat du scrutin : Pour l’adoption 278. La majorité requise...", candidates) == "V1240"
    assert match_ballot("Voici le résultat du scrutin : Pour l’adoption 50 Contre 3", candidates) is None
    assert match_ballot("Majorité requise ... : 289 Pour l’adoption : 94 La majorité requise", candidates) == "V1241"
    assert match_ballot("Pour l’approbation 278 Contre 0 L’Assemblée nationale a approuvé", candidates) == "V1240"
