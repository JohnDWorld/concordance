from concordance.eval.leakage import only_masked

ORIGINAL = "Le groupe Horizons et apparentés, avec M. Marcangeli, votera contre. (Applaudissements sur les bancs du groupe RN.)"


def test_only_masked_accepts_label_replacements() -> None:
    assert only_masked(ORIGINAL, "Le Groupe A, avec [personne], votera contre. (Applaudissements sur les bancs du Groupe B.)")


def test_only_masked_rejects_rewording() -> None:
    assert not only_masked(ORIGINAL, "Le Groupe A, avec [personne], s'opposera. (Applaudissements sur les bancs du Groupe B.)")
    assert not only_masked(ORIGINAL, "Le Groupe A votera contre.")  # passage supprimé
