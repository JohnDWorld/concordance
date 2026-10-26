import random

from concordance.pipeline.anonymize import PERSON, PARTY, TERM, anonymize, compile_dictionary

DICTIONARY = compile_dictionary(
    full_names=["Laurent Marcangeli", "Mathilde Panot", "Bertrand Pancher", "Xavier Bertrand"],
    surnames=["Marcangeli", "Panot", "Petit", "Pancher", "Bertrand"],
    groups=[("Horizons et apparentés", 1), ("HOR", 1), ("La France insoumise - Nouvelle Union Populaire écologique et sociale", 2),
            ("LFI - NUPES", 2), ("Non inscrit", 3), ("NI", 3), ("Ecolo - NUPES", 4), ("LIOT", 5), ("LIOT", 6), ("À Droite", 7), ("Droite Républicaine", 8)],
    parties=["Rassemblement national", "Horizons et apparentés"],
)


def test_judged_group_and_others_get_distinct_labels() -> None:
    text = ("C’est pourquoi les députés du groupe Horizons et apparentés ne voteront pas. "
            "(Applaudissements sur les bancs des groupes HOR et LFI-NUPES.)")
    [out], mapping = anonymize([text], judged_group=1, dictionary=DICTIONARY, rng=random.Random(0))
    judged = next(label for label, gids in mapping.items() if gids == [1])
    other = next(label for label, gids in mapping.items() if gids == [2])
    assert judged != other
    assert out == (f"C’est pourquoi les députés du {judged} ne voteront pas. "
                   f"(Applaudissements sur les bancs des groupes {judged} et {other}.)")


def test_persons_parties_and_terms() -> None:
    text = "M. Marcangeli répond à Mathilde Panot sur le Rassemblement national et les macronistes, ni plus ni moins, en petit comité."
    [out], _ = anonymize([text], judged_group=3, dictionary=DICTIONARY, rng=random.Random(0))
    assert out == f"{PERSON} répond à {PERSON} sur le {PARTY} et les {TERM}, ni plus ni moins, en petit comité."
    # « ni » et « petit » restent : sigles sensibles à la casse, nom seul remplacé seulement après une civilité


def test_label_is_drawn_at_random() -> None:
    labels = {next(iter(anonymize(["HOR"], 1, DICTIONARY, random.Random(seed))[1])) for seed in range(20)}
    assert len(labels) > 1


def test_accents_and_civility_with_full_name() -> None:
    [out], mapping = anonymize(["La motion de M. Bertrand Pancher, soutenue par Écolo-NUPES."], 1, DICTIONARY, random.Random(0))
    assert out == f"La motion de {PERSON}, soutenue par {next(lab for lab, g in mapping.items() if g == [4])}."


def test_shared_name_takes_judged_label() -> None:
    """« LIOT » désigne deux groupes (deux législatures) : jugé ou non, le nom doit rester cohérent."""
    [out], mapping = anonymize(["Le groupe LIOT votera la motion."], 6, DICTIONARY, random.Random(0))
    assert out == f"Le {next(lab for lab, g in mapping.items() if g == [6])} votera la motion."
    [out], mapping = anonymize(["Le groupe LIOT votera la motion."], 1, DICTIONARY, random.Random(0))
    assert mapping[out.split()[1] + " " + out.split()[2]] == [5, 6]


def test_names_in_context_and_group_variants() -> None:
    text = ("La loi Pancher, votée sous le gouvernement Bertrand, et M. le député Marcangeli : les écolos "
            "et les Horizons et Apparentés en parlent ; un petit Bertrand de village reste un mot.")
    [out], mapping = anonymize([text], 1, DICTIONARY, random.Random(0))
    judged = next(lab for lab, g in mapping.items() if g == [1])
    assert out == (f"La loi {PERSON}, votée sous le gouvernement {PERSON}, et {PERSON} : les {TERM} "
                   f"et les {judged} en parlent ; un petit Bertrand de village reste un mot.")


def test_short_group_names_do_not_swallow_common_words() -> None:
    text = "Le groupe Droite républicaine, assis à droite, et le groupe À Droite."
    [out], mapping = anonymize([text], 8, DICTIONARY, random.Random(0))
    dr, ad = (next(lab for lab, g in mapping.items() if g == [i]) for i in (8, 7))
    assert out == f"Le {dr}, assis à droite, et le {ad}."
