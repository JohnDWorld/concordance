import json
import random

from concordance.pipeline.anonymize import PERSON, compile_dictionary
from concordance.pipeline.judge import Pair, check, consensus, render

DICTIONARY = compile_dictionary(full_names=["Mathilde Panot"], surnames=["Panot"],
                                groups=[("Horizons et apparentés", 1), ("HOR", 1), ("LIOT", 2)], parties=[])
PAIR = Pair(measure_id=1, ballot_id=2, group_id=1, mesure="Retraite à 60 ans.",
            scrutin="Intitulé : l'amendement n° 12 de Mme Mathilde Panot (LIOT)",
            position="3 pour, 1 contre, 0 abstentions, 0 non-votants. Position majoritaire : pour.",
            explication="Le groupe Horizons et apparentés votera pour.")


def verdict(**over: object) -> str:
    return json.dumps({"nature_du_vote": "amendement", "citations": [{"source": "mesure", "extrait": "Retraite à 60 ans"}],
                       "justification": "Le texte rapproche de la mesure.", "relation": "dans_le_sens", "confiance": 0.8} | over)


def test_render_sends_only_anonymized_text() -> None:
    message, sections, mapping = render(PAIR, DICTIONARY, random.Random(0))
    judged = next(lab for lab, ids in mapping.items() if ids == [1])
    other = next(lab for lab, ids in mapping.items() if ids == [2])
    assert "Panot" not in message and "Horizons" not in message and "LIOT" not in message
    assert f"## Position du {judged}\n\n{judged} : 3 pour" in message
    assert sections["scrutin"] == f"Intitulé : l'amendement n° 12 de {PERSON} ({other})\n{judged} : 3 pour, 1 contre, " \
                                  "0 abstentions, 0 non-votants. Position majoritaire : pour."
    assert sections["explication"] == f"Le {judged} votera pour."


def test_missing_explanation_is_stated() -> None:
    message, sections, mapping = render(PAIR.model_copy(update={"explication": None}), DICTIONARY, random.Random(0))
    assert f"Aucune explication de vote disponible pour le {next(iter(mapping))}." in message
    assert sections["explication"] == ""


def test_citations_must_match_the_text_sent() -> None:
    _, sections, _ = render(PAIR, DICTIONARY, random.Random(0))
    assert check(verdict(), sections) == (check(verdict(), sections)[0], None)
    _, rejet = check(verdict(citations=[{"source": "explication", "extrait": "Horizons et apparentés"}]), sections)
    assert rejet and rejet.startswith("citation introuvable")  # vrai nom absent du texte anonymisé
    _, rejet = check(verdict(citations=[{"source": "scrutin", "extrait": "Retraite à 60 ans"}]), sections)
    assert rejet  # présent dans la mesure, pas dans le scrutin


def test_contract_violations_are_rejected() -> None:
    _, sections, _ = render(PAIR, DICTIONARY, random.Random(0))
    for bad in (verdict(citations=[]), verdict(relation="favorable"), verdict(confiance=2),
                verdict(justification="mot " * 81), "pas du JSON"):
        v, rejet = check(bad, sections)
        assert v is None and rejet and rejet.startswith("réponse hors contrat")


def test_published_verdict_needs_both_judges_or_a_review() -> None:
    assert consensus({"qwen3-30b-a3b": "contraire", "llama3.2": "contraire"}, None) == ("contraire", "accord des deux juges")
    assert consensus({"qwen3-30b-a3b": "contraire", "llama3.2": "ambigu"}, None) == (None, "désaccord des juges")
    assert consensus({"qwen3-30b-a3b": "contraire", "llama3.2": None}, None)[0] is None
    assert consensus({"qwen3-30b-a3b": "contraire"}, None)[0] is None
    assert consensus({"qwen3-30b-a3b": "contraire", "llama3.2": "ambigu"}, "ambigu") == ("ambigu", "relecture humaine")
