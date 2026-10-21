from concordance.rules import majority, nature


def test_nature() -> None:
    assert nature("la motion de rejet préalable", "SPO") == "motion"
    assert nature("le texte", "MOC") == "motion"
    assert nature("l’amendement n° 12 de M. X", "SPO") == "amendement"
    assert nature("le sous-amendement n° 3", "SPO") == "amendement"
    assert nature("l'article premier du projet de loi", "SPO") == "article"
    assert nature("l'ensemble de la proposition de loi", "SPS") == "texte_entier"
    assert nature("la première partie du projet de loi de finances", "SPO") is None
    assert nature("sur l'ensemble du texte élaboré par la commission mixte paritaire") == "texte_entier"  # Sénat
    assert nature("sur l'amendement n° 18, présenté par M. X") == "amendement"


def test_majority() -> None:
    assert majority(119, 6, 19) == "pour"
    assert majority(0, 12, 3) == "contre"
    assert majority(5, 5, 0) is None  # égalité en tête
    assert majority(0, 0, 0) is None  # aucun vote exprimé
    assert majority(2, 2, 7) == "abstention"
