import html
import re
from datetime import date
from typing import Any

from concordance.pipeline import judge
from concordance.publish.fiche import (
    Candidat, Donnees, Explication, Groupe, Mesure, NomGroupe, Scrutin, ScrutinVue, badge, detail_html, etiquettes,
    explications_html, fiche_scrutin, index_html, libelle_url, lien_scrutin, ligne_html, mesure_html,
    nv_volontaires_identiques, phrase_vote, sans_rapport,
)

QWEN, LLAMA = judge.JUDGES  # deux juges : clés dans le même ordre que judge.JUDGES
SCRUTIN = Scrutin(id=7, chamber="an", legislature=16, jour=date(2023, 2, 14),
                  intitule="l'amendement n° 12 de M. X à l'article 2 (première lecture).", dossier="Projet de loi",
                  nature="amendement", sort="rejeté", source_url="https://www.assemblee-nationale.fr/dyn/16/scrutins/965",
                  amendement=None)
SCRUTIN_PE = Scrutin(id=8, chamber="pe", legislature=10, jour=date(2024, 5, 14),
                     intitule="A European Strategy for Energy System Integration", dossier=None, nature=None,
                     sort="adopté", source_url="https://howtheyvote.eu/votes/1", amendement=None)
MESURE = Mesure(id=1, cle="0123456789abcdef", theme="retraites", citation="Retraite à 60 ans pour tous.",
                source_url="https://example.org/programme", consultee=date(2026, 10, 22), candidat_id=1,
                nom="Jean Dupont", parti="Parti Exemple")
MAPPING = {"Groupe A": [2], "Groupe B": [3]}  # étiquettes du juge -> identifiants de parl_groups
DONNEES = Donnees(verdicts={}, reviews={},
                  groupes={2: NomGroupe("an", 16, "LFI"), 3: NomGroupe("an", 16, "SOC")},
                  liens={"Jean Dupont": {"an": [], "senat": None}})


def groupe(id_: int, sigle: str, position: str | None = "pour", categorie: str = "groupe") -> Groupe:
    return Groupe(id=id_, external_id=f"PO{id_}", sigle=sigle, libelle=f"Libellé {sigle}", categorie=categorie,
                  membres=10, pour=6, contre=2, abstention=1, non_votants=1, non_votants_volontaires=0,
                  position=position)


def avis(relation: str | None, rejet: str | None = None) -> dict[str, Any]:
    return {"relation": relation, "rejet": rejet, "justification": "Le Groupe A a voté pour l'amendement.",
            "mapping": MAPPING}


def donnees(statut: str, relation: str | None, juges: dict[str, dict[str, Any]]) -> Donnees:
    verdict = {"relation": relation, "statut": statut, "juges": juges}
    return DONNEES._replace(verdicts={(1, 7, 2): verdict})


def rendu(d: Donnees, g: Groupe | None = None, s: Scrutin = SCRUTIN) -> str:
    """Ligne du tableau et détail d'un groupe : ce que le lecteur voit pour ce groupe."""
    g = g or groupe(2, "LFI")
    return ligne_html(1, s, g, "", d) + detail_html(1, s, g, [], d)


def test_badge_identique_pour_tous_les_groupes() -> None:
    a = badge("SOC", "Socialistes et apparentés")
    b = badge("LFI", "La France insoumise")
    assert re.sub(r">[^<]*<", "><", a) == re.sub(r">[^<]*<", "><", b)
    assert 'style="' not in a and "color" not in a


def test_explication_reproduite_mot_pour_mot_et_echappee() -> None:
    texte = 'Monsieur <b>X</b> & "Y" : l’égalité.\n\nSecond paragraphe.'
    out = explications_html([Explication("M. Dupont", texte, "https://example.org/cri#p1")], "an")
    assert html.escape(texte) in out
    assert "<b>X</b>" not in out


def test_explication_non_disponible_quand_il_n_y_en_a_pas() -> None:
    assert "Explication non disponible." in explications_html([], "an")
    assert "Explication non disponible." in detail_html(1, SCRUTIN, groupe(2, "LFI"), [], DONNEES)


def test_explication_pe_non_collectee_et_pas_de_faux_absent() -> None:
    out = explications_html([], "pe")
    assert "non collectée" in out and "Explication non disponible" not in out


def test_etiquettes_remplacees_par_le_sigle_de_la_bonne_legislature() -> None:
    groupes = {3: NomGroupe("an", 16, "SOC"), 9: NomGroupe("an", 17, "XX")}
    texte = "Le Groupe A a voté pour ; le Groupe B aussi ; le Groupe Z reste."
    assert etiquettes(texte, {"Groupe A": [3], "Groupe B": [9]}, SCRUTIN, groupes) == \
        "Le SOC a voté pour ; le XX aussi ; le Groupe Z reste."
    assert etiquettes("Le Groupe A", {"Groupe A": [3, 9]}, SCRUTIN, groupes) == "Le SOC"


def test_etiquettes_hors_chambre_sigle_commun_ou_un_autre_groupe() -> None:
    groupes = {9: NomGroupe("senat", None, "SOC"), 10: NomGroupe("pe", 10, "LFI")}
    mapping = {"Groupe A": [9], "Groupe B": [9, 10]}
    assert etiquettes("Groupe A ; Groupe B.", mapping, SCRUTIN, groupes) == "SOC ; un autre groupe."


def test_justification_du_juge_non_publiee() -> None:
    d = donnees("accord des deux juges", "dans_le_sens", {QWEN: avis("dans_le_sens"), LLAMA: avis("dans_le_sens")})
    out = mesure_html(MESURE, [ScrutinVue(SCRUTIN, [groupe(2, "LFI")], {})], d)
    assert "a voté pour l'amendement" not in out and "Groupe A" not in out
    assert "n'est pas publiée" in out


def test_pas_de_verdict_en_cas_de_desaccord() -> None:
    d = donnees("désaccord des juges", None, {QWEN: avis("contraire"), LLAMA: avis("ambigu")})
    out = rendu(d)
    assert "verdict v-" not in out and "Verdict publié" not in out
    assert "Désaccord des juges, relecture humaine à venir" in out
    assert "contraire à la mesure" in out and "ambigu" in out  # les deux avis sont montrés


def test_verdict_publie_seulement_avec_accord_des_deux_juges() -> None:
    d = donnees("accord des deux juges", "dans_le_sens", {QWEN: avis("dans_le_sens"), LLAMA: avis("dans_le_sens")})
    out = rendu(d)
    assert 'class="verdict v-dans_le_sens"' in out and "Verdict publié" in out
    rejete = donnees("jugement manquant ou rejeté", None,
                     {QWEN: avis(None, "citation introuvable"), LLAMA: avis("contraire")})
    out = rendu(rejete)
    assert "verdict v-" not in out
    assert "Jugement rejeté (citation non vérifiée), relecture à venir" in out
    assert "avis non retenu" in out


def test_verdict_relecture_humaine_sans_jugement() -> None:
    d = DONNEES._replace(reviews={(1, 7, 2): ("ambigu", "Relu à la main.", "Relecteur")})
    out = ligne_html(1, SCRUTIN, groupe(2, "LFI"), "", d)
    assert 'class="verdict v-ambigu"' in out


def test_jugement_en_cours_sans_ligne_dans_judgments() -> None:
    out = ligne_html(1, SCRUTIN, groupe(2, "LFI"), "", DONNEES)
    assert "En attente" in out and "verdict v-" not in out
    detail = detail_html(1, SCRUTIN, groupe(2, "LFI"), [], DONNEES)
    assert "Jugement en cours : aucun juge n'a encore traité cette paire." in detail
    assert "Qwen" not in detail and QWEN not in detail and LLAMA not in detail  # une seule phrase, sans liste des juges


def test_abstention_decrite_sans_interpretation() -> None:
    out = detail_html(1, SCRUTIN, groupe(2, "LFI", position="abstention"), [], DONNEES)
    assert html.escape("Non jugé : abstention ou non-vote, pas d'interprétation.") in out
    assert ">Non jugé<" in ligne_html(1, SCRUTIN, groupe(2, "LFI", position="abstention"), "", DONNEES)


def test_egalite_et_aucun_vote_ne_sont_pas_confondus() -> None:
    egalite = groupe(2, "LFI", position=None)._replace(pour=3, contre=3, abstention=0)
    assert "Non jugé : égalité en tête" in detail_html(1, SCRUTIN, egalite, [], DONNEES)
    vide = groupe(2, "LFI", position=None)._replace(pour=0, contre=0, abstention=0)
    assert "Non jugé : aucun vote exprimé." in detail_html(1, SCRUTIN, vide, [], DONNEES)


def test_groupe_europeen_non_juge_hors_delegations() -> None:
    out = detail_html(1, SCRUTIN_PE, groupe(2, "S&D", categorie="groupe"), [], DONNEES)
    assert "seules les délégations nationales françaises sont jugées" in out


def test_motion_suit_le_verdict_publie() -> None:
    motion = SCRUTIN._replace(intitule="Motion de censure", nature="motion", sort="rejeté")
    d = donnees("accord des deux juges", "ambigu", {QWEN: avis("ambigu"), LLAMA: avis("ambigu")})
    assert 'class="verdict v-ambigu"' in rendu(d, s=motion)  # aucune règle propre à l'affichage
    assert "En attente" in ligne_html(1, motion, groupe(2, "LFI"), "", DONNEES)  # pas de jugement : pas de verdict

def test_lien_candidat_sur_le_groupe_ou_en_en_tete() -> None:
    lignes, par_groupe = lien_scrutin("Jean Dupont", SCRUTIN, [("PO2", date(2020, 1, 1), None)], [groupe(2, "LFI")])
    assert lignes == [] and par_groupe == {2: "Jean Dupont siégeait dans ce groupe à cette date."}


def test_lien_candidat_trois_cas_distincts() -> None:
    absent, _ = lien_scrutin("Jean Dupont", SCRUTIN, [], [groupe(2, "LFI")])
    assert "les données de l'Assemblée nationale n'indiquent aucun mandat de groupe pour Jean Dupont." in absent[0]
    sans_groupe, _ = lien_scrutin("Jean Dupont", SCRUTIN, [("PO9", date(2010, 1, 1), date(2011, 1, 1))],
                                  [groupe(2, "LFI")])
    assert "n'indiquent aucun mandat de groupe pour Jean Dupont à cette date" in sans_groupe[0]
    homonymes, _ = lien_scrutin("Jean Dupont", SCRUTIN, None, [groupe(2, "LFI")])
    assert "plusieurs parlementaires" in homonymes[0]


def test_non_votants_volontaires_identiques_aux_abstentions() -> None:
    assert nv_volontaires_identiques(SCRUTIN, [groupe(2, "LFI")._replace(non_votants_volontaires=1, abstention=1)])
    assert not nv_volontaires_identiques(SCRUTIN, [groupe(2, "LFI")])


def test_dossier_senat_affiche_un_lien_et_pas_une_url_brute() -> None:
    url = "https://www.senat.fr/dossier-legislatif/pjl22-368.html"
    out = fiche_scrutin(SCRUTIN._replace(chamber="senat", dossier=url))
    assert f'href="{url}"' in out and f">{url}<" not in out and "Voir le dossier en ligne (www.senat.fr)" in out


def test_phrase_de_vote() -> None:
    assert "les eurodéputés ont voté" in phrase_vote(SCRUTIN_PE)
    assert "(intitulé d'origine, en anglais)" in phrase_vote(SCRUTIN_PE)
    assert "ont voté sur l'amendement n° 12" in phrase_vote(SCRUTIN)
    motion = SCRUTIN._replace(intitule="Motion de censure", sort="rejeté")
    assert "ont voté : Motion de censure. Résultat : rejeté." in phrase_vote(motion)


def test_libelle_url_archive_et_site() -> None:
    archive = "https://web.archive.org/web/20260829200732/https://melenchon2027.fr/programme2025/livre/chapitre8/s8/"
    assert libelle_url(archive) == "melenchon2027.fr, archive du 29 août 2026"
    assert libelle_url("https://www.unenouvelleenergie.fr/notre-programme/") == "www.unenouvelleenergie.fr"


def test_scrutin_replie_seulement_si_tous_les_groupes_juges_sont_hors_sujet() -> None:
    hors = {"relation": "hors_sujet", "statut": "accord des deux juges", "juges": {}}
    d = DONNEES._replace(verdicts={(1, 7, 2): hors})
    deux_groupes = ScrutinVue(SCRUTIN, [groupe(2, "LFI"), groupe(3, "SOC", position="contre")], {})
    assert not sans_rapport(1, deux_groupes, d)  # SOC attend encore son jugement : le scrutin reste visible
    assert sans_rapport(1, ScrutinVue(SCRUTIN, [groupe(2, "LFI")], {}), d)


def test_page_complete_sans_script_ni_ressource_externe() -> None:
    d = donnees("accord des deux juges", "hors_sujet", {QWEN: avis("hors_sujet"), LLAMA: avis("hors_sujet")})
    vue = ScrutinVue(SCRUTIN, [groupe(2, "LFI"), groupe(3, "SOC", position="contre")],
                     {2: [Explication("M. Dupont", "Texte exact.", "https://example.org/cri")]})
    d = d._replace(verdicts={**d.verdicts, (1, 7, 3): {"relation": "hors_sujet", "statut": "accord des deux juges",
                                                       "juges": {}}})
    out = mesure_html(MESURE, [vue], d)
    assert out.startswith("<!doctype html>") and 'lang="fr"' in out
    assert "Comment lire cette fiche" in out and "Retraite à 60 ans pour tous." in out
    assert "Votes examinés mais jugés sans rapport avec la mesure (1)" in out  # tous les verdicts publiés hors sujet
    assert "Texte exact." in out
    assert not re.search(r"<script|<link|@import|\bsrc=", out)
    assert "\u2014" not in out and "\u2013" not in out  # tirets longs interdits (CLAUDE.md)
    assert not re.search("[✓✗✔✘]", out)  # pas de coches ni croix : aucun jugement bien ou mal


def test_page_sans_scrutin_et_compte_exact() -> None:
    out = mesure_html(MESURE, [], DONNEES)
    assert "Nombre de scrutins retenus : 0" in out and "Aucun scrutin retenu" in out


def test_index_trie_par_nom_de_famille_sans_repli() -> None:
    out = index_html([Candidat(1, "Jean-Luc Mélenchon", None), Candidat(2, "Marine Le Pen", None)], [])
    assert out.index("Marine Le Pen") < out.index("Jean-Luc Mélenchon")
    assert out.count("Aucune mesure retraites saisie à ce jour.") == 2
    assert "<details" not in out  # liste complète, jamais repliée
    assert "Prototype : verdicts pas encore fiables." in out and "Seules les mesures sur les retraites" in out
