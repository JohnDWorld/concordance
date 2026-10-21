from concordance.rules import amendment_scope, majority, nature, series_key


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


def test_series_key() -> None:
    a = series_key('Remplacer les mots : "le lendemain de" par les mots : "quatre-vingt-trois jours après"')
    b = series_key('Remplacer les mots : "le lendemain de" par les mots : "soixante-et-un jour après"')
    c = series_key('Remplacer les mots : "le lendemain de" par les mots : "cent trente-quatre jours après"')
    assert a == b == c
    assert series_key("Remplacer l’âge de 64 ans par 63 ans.") == series_key("Remplacer l'âge de 64 ans par 62 ans.")
    assert series_key("Supprimer cet article.") != series_key("Supprimer l’alinéa 3.")


def test_amendment_scope() -> None:
    assert amendment_scope("Supprimer cet article.") == (True, False, 0)
    assert amendment_scope("Supprimer les deuxième et troisième phrases de l’alinéa 3.") == (True, False, 0)
    assert amendment_scope("À l’alinéa 17, substituer au mot : « et », le mot : « ou ».") == (False, False, 1)
    assert amendment_scope("À l’alinéa 2, remplacer le mot : « etat » par le mot : « État ».") == (False, True, 1)
    assert amendment_scope("À l’alinéa 4, après le mot : « salariés », insérer le signe : « , ».") == (False, True, 0)
    assert amendment_scope("À la fin de l’alinéa 6, supprimer le mot : « élective ».") == (False, False, 0)
    assert amendment_scope("À l’alinéa 12, après le mot : « absence », insérer les mots : « de conclusion, ».") == (False, False, 2)
    assert amendment_scope('Remplacer les mots : "le lendemain de" par les mots : "soixante-et-un jour après"') == (False, False, 3)
    nested = "Après l'alinéa 4, insérer l'alinéa suivant : « 3° Est ajoutée une phrase ainsi rédigée : « Ne peuvent être réputés usuels. » »"
    assert amendment_scope(nested) == (False, False, 12)
    assert amendment_scope("Dans un délai d’un mois, le Gouvernement remet au Parlement un rapport.") == (False, False, 12)
