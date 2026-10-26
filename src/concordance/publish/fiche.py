"""Fiches de preuve HTML : une page par mesure et un index, en pages statiques (site/).

Règles d'affichage : docs/methodologie.md (Présentation, Explication de vote absente, Vérification des citations).
Aucune ressource externe, aucun script, aucun suivi. Lancer : python -m concordance.publish.fiche [--sortie site]
"""

import argparse
import html
import json
import re
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import urlsplit

import psycopg

from concordance import db
from concordance.ingest.an import group_periods
from concordance.ingest.raw import RAW
from concordance.ingest.senat import copy_rows, fold, memberships
from concordance.pipeline import judge
from concordance.pipeline.retrieve import search
from concordance.rules import Membership, group_at

LIMITE = 5  # scrutins par mesure : les mêmes que ceux jugés (judge.main, --limite par défaut)
APERCU = 160  # caractères de citation affichés dans l'index
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
        "décembre")
THEME = {"retraites": "les retraites"}
LIEU = {"an": "à l'Assemblée nationale", "senat": "au Sénat", "pe": "au Parlement européen"}
DONNEES = {"an": "de l'Assemblée nationale", "senat": "du Sénat"}
ELUS = {"an": "les députés", "senat": "les sénateurs", "pe": "les eurodéputés"}
NATURE = {"texte_entier": "vote sur l'ensemble du texte", "article": "article", "amendement": "amendement",
          "motion": "motion", "autre": "autre"}
RELATION = {"dans_le_sens": "dans le sens de la mesure", "contraire": "contraire à la mesure", "ambigu": "ambigu",
            "hors_sujet": "hors sujet"}
POSITION = {"pour": "pour", "contre": "contre", "abstention": "abstention", "non_votant": "non-vote"}
WAYBACK = re.compile(r"https?://web\.archive\.org/web/(\d{4})(\d{2})(\d{2})\d*/https?://([^/]+)")
LIEN_ALLIANCE = "Les liens d'alliance entre partis et groupes ne sont pas encore renseignés."
NON_COLLECTEE = "Explication de vote non collectée : le Parlement européen n'est pas encore couvert par les explications de vote."
VOIR_SCRUTIN = {"an": "Voir le scrutin sur le site officiel", "senat": "Voir le scrutin sur le site officiel",
                "pe": "Voir le scrutin sur HowTheyVote.eu"}
VOIR_AMENDEMENT = "Voir l'amendement sur le site officiel"
NV_VOLONTAIRES = ("Non-votants volontaires : dans les données de l'Assemblée, ce chiffre est égal à celui des abstentions "
                  "pour chaque groupe de ce scrutin. Sa définition n'est pas confirmée.")
LEGENDE = ("Barre de répartition : plein = pour ; hachures obliques = contre ; gris = abstention ; hachures "
           "horizontales = non-votants. Les chiffres sont donnés tels quels.")
LEGENDE_VERDICT = ("En attente : pas encore jugé. Relecture à venir : les deux juges ne sont pas d'accord, ou une "
                   "citation a été rejetée ; aucun verdict n'est publié. Non jugé : abstention, non-vote ou pas de "
                   "position majoritaire ; la fiche décrit les chiffres, sans interprétation.")
ETAT = {"en_cours": "Jugement en cours", "desaccord": "Désaccord des juges, relecture humaine à venir",
        "rejet": "Jugement rejeté (citation non vérifiée), relecture à venir"}
ETAT_COURT = {"en_cours": "En attente", "desaccord": "Relecture à venir", "rejet": "Relecture à venir"}
STATUT = {"accord des deux juges": "les deux juges sont d'accord", "relecture humaine": "relecture humaine"}

Cle = tuple[int, int, int]  # mesure, scrutin, groupe


class Mesure(NamedTuple):
    id: int
    cle: str
    theme: str
    citation: str
    source_url: str
    consultee: date
    candidat_id: int
    nom: str
    parti: str | None


class Candidat(NamedTuple):
    id: int
    nom: str
    parti: str | None


class NomGroupe(NamedTuple):
    chamber: str
    legislature: int | None
    nom: str  # sigle, ou libellé à défaut


class Amendement(NamedTuple):
    numero: str
    dispositif: str | None
    expose: str | None
    source_url: str


class Scrutin(NamedTuple):
    id: int
    chamber: str
    legislature: int | None
    jour: date
    intitule: str
    dossier: str | None
    nature: str | None
    sort: str | None
    source_url: str
    amendement: Amendement | None


class Groupe(NamedTuple):
    id: int
    external_id: str
    sigle: str | None
    libelle: str
    categorie: str
    membres: int | None
    pour: int
    contre: int
    abstention: int
    non_votants: int
    non_votants_volontaires: int | None
    position: str | None


class Explication(NamedTuple):
    orateur: str
    texte: str
    source_url: str


class ScrutinVue(NamedTuple):
    scrutin: Scrutin
    groupes: list[Groupe]
    explications: dict[int, list[Explication]]  # par groupe


class Donnees(NamedTuple):
    verdicts: dict[Cle, dict[str, Any]]  # judge.verdicts
    reviews: dict[Cle, tuple[str, str, str]]  # relation, justification, relecteur
    groupes: dict[int, NomGroupe]
    liens: dict[str, dict[str, list[Membership] | None]]  # candidat -> chambre -> appartenances (None : homonymes)


# --- Mise en forme de base -------------------------------------------------------------------------------------------

def esc(texte: str) -> str:
    return html.escape(texte, quote=True)


def jour(d: date) -> str:
    return f"{'1er' if d.day == 1 else d.day} {MOIS[d.month - 1]} {d.year}"


def phrase_vote(s: Scrutin) -> str:
    """Une phrase simple par scrutin. L'intitulé d'un scrutin européen est en anglais : il est repris tel quel."""
    qui = f"Le {jour(s.jour)}, {LIEU[s.chamber]}, {ELUS[s.chamber]} ont voté"
    resultat = f"Résultat : {s.sort or 'non renseigné'}."
    if s.chamber == "pe":
        return f"{qui} : « {s.intitule} » (intitulé d'origine, en anglais). {resultat}"
    texte = re.sub(r"^sur ", "", s.intitule.strip(), flags=re.IGNORECASE).rstrip(".")
    verbe = f"sur {texte}" if texte[:1].islower() else f": {texte}"
    return f"{qui} {verbe}. {resultat}"


def libelle_url(url: str) -> str:
    """Adresse courte affichée : pour une archive Wayback, le site d'origine et la date de l'archive."""
    m = WAYBACK.match(url)
    if m:
        annee, mois, jour_, hote = m.groups()
        return f"{hote}, archive du {jour(date(int(annee), int(mois), int(jour_)))}"
    return urlsplit(url).netloc


def lien(url: str, texte: str | None = None) -> str:
    return f'<a href="{esc(url)}" title="{esc(url)}">{esc(texte or libelle_url(url))}</a>'


def badge(sigle: str | None, libelle: str) -> str:
    """Badge identique pour tous les groupes : sigle et nom complet, sans logo ni couleur."""
    return f'<span class="badge"><span class="sigle">{esc(sigle or libelle)}</span> <span class="nom">{esc(libelle)}</span></span>'


# ponytail: non appelée tant que la justification du juge n'est pas publiée (non relue) ;
# à rebrancher quand une relecture humaine l'autorisera.
def etiquettes(texte: str, mapping: dict[str, list[int]], s: Scrutin, groupes: dict[int, NomGroupe]) -> str:
    """Remplace « Groupe X » par le sigle du groupe réel : même chambre et législature que le scrutin, sinon le même
    sigle partout dans le mapping, sinon « un autre groupe »."""
    noms: dict[str, str] = {}
    for label, ids in mapping.items():
        reels = [groupes[i] for i in ids if i in groupes]
        memes = [g.nom for g in reels if (g.chamber, g.legislature) == (s.chamber, s.legislature)]
        if memes:
            noms[label] = memes[0]
        elif reels and len({g.nom for g in reels}) == 1:
            noms[label] = reels[0].nom
        else:
            noms[label] = "un autre groupe"
    if not noms:
        return texte
    motif = "|".join(re.escape(label) + r"(?!\w)" for label in sorted(noms, key=len, reverse=True))
    return re.sub(motif, lambda m: noms[m.group(0)], texte)


# --- Votes des groupes -----------------------------------------------------------------------------------------------

def position_texte(g: Groupe) -> str:
    if g.position:
        return POSITION.get(g.position, g.position)
    return "aucun vote exprimé" if g.pour + g.contre + g.abstention == 0 else "égalité en tête"


def barre_html(g: Groupe) -> str:
    """Répartition en motifs et niveaux de gris ; les nombres sont dans les colonnes du tableau (accessibilité)."""
    total = g.pour + g.contre + g.abstention + g.non_votants
    if not total:
        return ""
    parts = (("s-pour", g.pour), ("s-contre", g.contre), ("s-abst", g.abstention), ("s-nv", g.non_votants))
    segments = "".join(f'<span class="{cls}" style="width: {n * 100 / total:.2f}%"></span>' for cls, n in parts if n)
    return f'<div class="barre" aria-hidden="true">{segments}</div>'


def explications_html(liste: list[Explication], chambre: str) -> str:
    """Explications reproduites mot pour mot, jamais résumées (docs/methodologie.md)."""
    if not liste:
        if chambre == "pe":
            return f'<p class="absent">{NON_COLLECTEE}</p>'
        return '<p class="absent">Explication non disponible.</p>'
    return "".join(
        f'<blockquote class="explication"><p class="orateur">{esc(e.orateur)}</p><div class="texte">{esc(e.texte)}</div>'
        f'<p class="source">{lien(e.source_url, "Compte rendu intégral")}</p></blockquote>'
        for e in liste)


def categorie(g: Groupe, s: Scrutin) -> str:
    if g.categorie == "delegation_nationale":
        return "Délégation nationale française"
    return "Groupe du Parlement européen" if s.chamber == "pe" else ""


def hors_juge(g: Groupe, s: Scrutin) -> str | None:
    """Paire que le juge ne traite pas : décrite, jamais interprétée. None si elle est jugée."""
    if g.position in ("pour", "contre"):
        if s.chamber == "pe" and g.categorie == "groupe":
            return "Non jugé : au Parlement européen, seules les délégations nationales françaises sont jugées."
        return None
    if g.position:
        return "Non jugé : abstention ou non-vote, pas d'interprétation."
    if g.pour + g.contre + g.abstention == 0:
        return "Non jugé : aucun vote exprimé."
    return "Non jugé : égalité en tête, pas de position majoritaire, pas d'interprétation."


# --- Verdicts : jamais de verdict en cas de désaccord ----------------------------------------------------------------

def publiee(cle: Cle, d: Donnees) -> str | None:
    """Relation publiée : relecture humaine, sinon accord des deux juges. Jamais en cas de désaccord."""
    if cle in d.reviews:
        return d.reviews[cle][0]
    v = d.verdicts.get(cle)
    return str(v["relation"]) if v and v["statut"] == "accord des deux juges" else None


def relation_affichee(cle: Cle, s: Scrutin, d: Donnees) -> str | None:
    """Relation montrée : celle publiée, sans règle propre à l'affichage (les motions sont traitées par la consigne)."""
    return publiee(cle, d)


def etat_code(cle: Cle, d: Donnees) -> str:
    """Jugement sans verdict publié : en cours, désaccord, ou citation rejetée une fois tous les juges passés."""
    v = d.verdicts.get(cle)
    if v is None:
        return "en_cours"
    if v["statut"] == "désaccord des juges":
        return "desaccord"
    if len(v["juges"]) == len(judge.JUDGES) and any(j["rejet"] for j in v["juges"].values()):
        return "rejet"
    return "en_cours"


def juges_html(cle: Cle, v: dict[str, Any] | None, d: Donnees) -> str:
    """Un avis par juge, sans sa justification écrite : elle n'est pas encore relue par un humain."""
    items: list[str] = []
    for modele in judge.JUDGES:
        j = v["juges"].get(modele) if v else None
        if j is None:
            items.append(f'<li><span class="modele">{esc(modele)}</span> : pas encore jugé.</li>')
        elif j["rejet"]:
            items.append(f'<li><span class="modele">{esc(modele)}</span> : avis non retenu (citation non vérifiée).</li>')
        else:
            items.append(f'<li><span class="modele">{esc(modele)}</span> : <strong>{RELATION[j["relation"]]}</strong></li>')
    if cle in d.reviews:
        relation, justification, relecteur = d.reviews[cle]
        items.append(f'<li><span class="modele">Relecture humaine ({esc(relecteur)})</span> : '
                     f'<strong>{RELATION[relation]}</strong><p class="justif">{esc(justification)}</p></li>')
    return ('<h5 class="libelle">Avis des juges</h5>'
            '<p class="note">La justification écrite par chaque juge n\'est pas publiée : elle n\'a pas encore été relue.</p>'
            f'<ul class="juges">{"".join(items)}</ul>')


def verdict_html(cle: Cle, s: Scrutin, d: Donnees) -> str:
    v = d.verdicts.get(cle)
    relation = relation_affichee(cle, s, d)
    if relation:
        statut = STATUT.get(str(v["statut"]), "relecture humaine") if v else "relecture humaine"
        tete = (f'<p class="verdict v-{relation}"><span>Verdict publié :</span> <strong>{RELATION[relation]}</strong> '
                f'<span class="statut">({esc(statut)})</span></p>')
    elif v is None:
        return f'<p class="etat">{ETAT["en_cours"]} : aucun juge n\'a encore traité cette paire.</p>'
    else:
        tete = f'<p class="etat">{ETAT[etat_code(cle, d)]}.</p>'
    return tete + juges_html(cle, v, d)


def verdict_cellule(cle: Cle, s: Scrutin, g: Groupe, d: Donnees) -> str:
    """Case « Verdict » du tableau : version courte, expliquée une fois sous le tableau."""
    if hors_juge(g, s):
        return '<span class="etat">Non jugé</span>'
    relation = relation_affichee(cle, s, d)
    if relation:
        return f'<span class="verdict v-{relation}">{RELATION[relation]}</span>'
    return f'<span class="etat">{ETAT_COURT[etat_code(cle, d)]}</span>'


def ligne_html(mesure_id: int, s: Scrutin, g: Groupe, lien_candidat: str, d: Donnees) -> str:
    """Une ligne du tableau d'un scrutin : sigle, chiffres du groupe et verdict court (détails dans le bloc Détail)."""
    cle = (mesure_id, s.id, g.id)
    petits = [categorie(g, s), f"{g.membres} membres" if g.membres is not None else "",
              f"position majoritaire : {position_texte(g)}"]
    resume = " · ".join(p for p in petits if p)
    return ('<tr><th scope="row" class="groupe-cell">' + badge(g.sigle, g.libelle) + barre_html(g)
            + f'<span class="petit">{esc(resume)}</span>'
            + (f'<span class="petit">{esc(lien_candidat)}</span>' if lien_candidat else "")
            + f'</th><td data-label="Pour">{g.pour}</td><td data-label="Contre">{g.contre}</td>'
            + f'<td data-label="Abstentions">{g.abstention}</td><td data-label="Non-votants">{g.non_votants}</td>'
            + f'<td data-label="Verdict" class="verdict-cell">{verdict_cellule(cle, s, g, d)}</td></tr>')


def detail_html(mesure_id: int, s: Scrutin, g: Groupe, explications: list[Explication], d: Donnees) -> str:
    """Détail repliable d'un groupe : état complet du jugement, avis des juges, explication de vote."""
    hors = hors_juge(g, s)
    avis = f'<p class="etat">{esc(hors)}</p>' if hors else verdict_html((mesure_id, s.id, g.id), s, d)
    chiffres = (f"<div><dt>Non-votants volontaires</dt><dd>{g.non_votants_volontaires}</dd></div>"
                if g.non_votants_volontaires is not None else "")
    return (f'<details class="detail"><summary>Détail : {badge(g.sigle, g.libelle)}</summary>'
            + (f'<dl class="extras">{chiffres}</dl>' if chiffres else "")
            + avis
            + '<h5 class="libelle">Explication de vote</h5>' + explications_html(explications, s.chamber)
            + "</details>")


# --- Scrutins --------------------------------------------------------------------------------------------------------

def lien_scrutin(nom: str, s: Scrutin, periodes: list[Membership] | None,
                 groupes: list[Groupe]) -> tuple[list[str], dict[int, str]]:
    """Lien candidat-groupe dérivé des données : une ligne sur le bon groupe, sinon une note sur le scrutin.

    Trois cas distincts : homonymes, candidat absent des données, candidat sans groupe à la date.
    Une donnée absente n'est pas une preuve d'absence : la note le dit.
    """
    if s.chamber == "pe":
        return ["Lien avec les groupes européens : non établi, ces données ne sont pas rapprochées du candidat."], {}
    if periodes is None:
        return [f"Lien avec les groupes : non établi, plusieurs parlementaires portent le nom de {nom}."], {}
    if not periodes:  # absent des données, ou présent sans aucun mandat de groupe : les deux se disent ainsi
        return [f"Lien avec les groupes : les données {DONNEES[s.chamber]} n'indiquent aucun mandat de groupe pour {nom}."], {}
    code = group_at(periodes, s.jour)
    if code is None:
        return [f"Les données {DONNEES[s.chamber]} n'indiquent aucun mandat de groupe pour {nom} à cette date."], {}
    for g in groupes:
        if g.external_id == code:
            return [], {g.id: f"{nom} siégeait dans ce groupe à cette date."}
    return [f"{nom} siégeait {LIEU[s.chamber]}, dans un groupe qui n'a pas de position pour ce scrutin."], {}


def fiche_scrutin(s: Scrutin) -> str:
    rows: list[tuple[str, str]] = []
    if s.legislature:
        rows.append(("Législature", esc(f"{s.legislature}e législature")))
    if s.nature:
        rows.append(("Nature du vote", esc(NATURE.get(s.nature, s.nature))))
    if s.dossier:
        rows.append(("Dossier législatif", lien(s.dossier, f"Voir le dossier en ligne ({libelle_url(s.dossier)})")
                     if s.dossier.startswith("http") else esc(s.dossier)))
    rows.append(("Source du scrutin", lien(s.source_url, VOIR_SCRUTIN[s.chamber])))
    corps = "".join(f"<div><dt>{esc(k)}</dt><dd>{v}</dd></div>" for k, v in rows)
    return f'<dl class="meta">{corps}</dl>'


def amendement_html(a: Amendement | None) -> str:
    if a is None:
        return ""
    return (f'<details><summary>Texte de l\'amendement n° {esc(a.numero)}, voté</summary>'
            f'<h4>Dispositif</h4><p class="texte">{esc(a.dispositif or "non disponible dans les données")}</p>'
            f'<h4>Exposé sommaire</h4><p class="texte">{esc(a.expose or "non disponible dans les données")}</p>'
            f'<p>{lien(a.source_url, VOIR_AMENDEMENT)}</p></details>')


def nv_volontaires_identiques(s: Scrutin, groupes: list[Groupe]) -> bool:
    """Assemblée : le chiffre « non-votants volontaires » est-il égal aux abstentions pour tous les groupes ?"""
    return s.chamber == "an" and bool(groupes) and all(g.non_votants_volontaires == g.abstention for g in groupes)


def scrutin_html(m: Mesure, vue: ScrutinVue, d: Donnees) -> str:
    s = vue.scrutin
    entetes, liens = lien_scrutin(m.nom, s, d.liens[m.nom].get(s.chamber), vue.groupes)
    groupes = sorted(vue.groupes, key=lambda g: g.libelle.casefold())
    attente = sum(1 for g in groupes
                  if hors_juge(g, s) is None and relation_affichee((m.id, s.id, g.id), s, d) is None)
    notes = entetes + ([NV_VOLONTAIRES] if nv_volontaires_identiques(s, vue.groupes) else [])
    lignes = "".join(ligne_html(m.id, s, g, liens.get(g.id, ""), d) for g in groupes)
    details = "".join(f"<li>{detail_html(m.id, s, g, vue.explications.get(g.id, []), d)}</li>" for g in groupes)
    entete = ('<thead><tr><th scope="col">Groupe</th><th scope="col">Pour</th><th scope="col">Contre</th>'
              '<th scope="col">Abstentions</th><th scope="col">Non-votants</th><th scope="col">Verdict</th></tr></thead>')
    return (f'<article class="scrutin" id="scrutin-{s.id}"><h3>Scrutin du {jour(s.jour)}</h3>'
            f'<p class="phrase">{esc(phrase_vote(s))}</p>'
            + fiche_scrutin(s)
            + "".join(f'<p class="note">{esc(t)}</p>' for t in notes)
            + amendement_html(s.amendement)
            + f'<p>Groupes à relire ou pas encore jugés : {attente}.</p>'
            + '<div class="table-wrap"><table class="votes"><caption>Position de chaque groupe</caption>'
            + entete + f"<tbody>{lignes}</tbody></table></div>"
            + f'<p class="legende">{LEGENDE}</p><p class="legende">{LEGENDE_VERDICT}</p>'
            + '<h4>Avis des juges et explication de vote, groupe par groupe</h4>'
            + f'<ul class="details-groupes">{details}</ul>'
            + "</article>")


def sans_rapport(mesure_id: int, vue: ScrutinVue, d: Donnees) -> bool:
    """Replié seulement si tous les groupes jugés ont un verdict publié « hors sujet » (et qu'il y en a au moins un)."""
    relations = [relation_affichee((mesure_id, vue.scrutin.id, g.id), vue.scrutin, d)
                 for g in vue.groupes if hors_juge(g, vue.scrutin) is None]
    return bool(relations) and all(r == "hors_sujet" for r in relations)


# --- Pages -----------------------------------------------------------------------------------------------------------

LIRE = (
    "Un scrutin est un vote de l'Assemblée nationale, du Sénat ou du Parlement européen. Les chiffres par groupe "
    "viennent des scrutins publics, où chaque parlementaire est recensé nominativement : pour, contre, abstentions, "
    "non-votants.",
    "« Dans le sens de la mesure » signifie que le texte voté allait dans le sens de la promesse ; « contraire à la "
    "mesure » qu'il allait dans le sens opposé. « Ambigu » ou « hors sujet » indique que le lien n'est pas net.",
    "Deux modèles d'intelligence artificielle installés sur un ordinateur jugent chaque paire à l'aveugle : les noms "
    "des groupes et des personnes sont masqués. Un verdict n'est publié que si les deux sont d'accord, ou après "
    "relecture humaine.",
    "Un jugement qui cite un passage introuvable dans le texte envoyé est rejeté. Cette fiche ne donne aucun score et "
    "n'indique pas comment voter.",
)
GLOSSAIRE = (
    ("Abstention", "Vote exprimé ni pour ni contre."),
    ("Amendement", "Proposition de modification d'un texte, déposée avant le vote par un parlementaire ou le Gouvernement."),
    ("Amendement identique", "Amendement dont le texte est identique à celui d'un autre amendement examiné sur le même passage du texte."),
    ("Article", "Subdivision d'un projet ou d'une proposition de loi. Le vote « sur l'article » porte sur sa rédaction."),
    ("Article 47-1 de la Constitution", "Article qui fixe les délais d'examen du projet de loi de financement de la sécurité sociale."),
    ("Article 49, alinéa 3, de la Constitution", "Procédure par laquelle le Gouvernement engage sa responsabilité sur un texte. Une motion de censure déposée sur ce fondement porte sur le Gouvernement."),
    ("Citation", "Passage recopié mot pour mot d'une source officielle."),
    ("Compte rendu intégral", "Transcription mot à mot des débats, publiée par l'Assemblée nationale ou le Sénat."),
    ("Délégation nationale française", "Élus français d'un même parti, au sein d'un groupe du Parlement européen. Présentée à côté du groupe, jamais à sa place."),
    ("Désaccord des juges", "Les deux juges ne donnent pas la même réponse. Aucun verdict n'est publié sans relecture humaine."),
    ("Dispositif", "Partie d'un amendement qui indique précisément ce qui est modifié dans le texte."),
    ("Dossier législatif", "Projet ou proposition de loi auquel le scrutin se rattache."),
    ("Exposé sommaire", "Explication écrite jointe à un amendement par son auteur."),
    ("Explication de vote", "Intervention d'un parlementaire, au nom de son groupe, avant ou après un vote. Reproduite mot pour mot."),
    ("Groupe parlementaire", "Parlementaires qui siègent ensemble à l'Assemblée, au Sénat ou au Parlement européen. Un groupe n'est pas un parti."),
    ("Intitulé", "Titre donné au scrutin par la source officielle."),
    ("Juge", "Modèle d'intelligence artificielle qui compare le texte de la mesure et celui du scrutin."),
    ("Lien avec le candidat", "Appartenance à un groupe, à la date du scrutin, d'un parlementaire qui porte le nom du candidat, d'après les données officielles. Ce n'est pas un lien d'alliance entre un parti et un groupe."),
    ("Législature", "Période entre deux élections générales des députés. La 17e a commencé en 2024."),
    ("Membres du groupe", "Nombre de parlementaires du groupe à la date du scrutin, selon la source officielle."),
    ("Motion de censure", "Vote qui peut renverser le Gouvernement. Il porte sur le Gouvernement, pas sur le fond d'un texte."),
    ("Motion de rejet préalable", "Vote qui demande de ne pas examiner un texte. Il porte sur la suite donnée au texte."),
    ("Non jugé", "Groupe dont la position n'est pas jugée : abstention, non-vote, égalité ou aucun vote. La fiche décrit les chiffres, sans interprétation."),
    ("Non-votant", "Parlementaire qui n'a pris part au vote ni pour, ni contre, ni en s'abstenant."),
    ("Non-votants volontaires", "Chiffre publié par l'Assemblée nationale. Dans ses données, il est égal au nombre d'abstentions : sa définition n'est pas confirmée."),
    ("Position majoritaire", "Position qui réunit le plus de voix dans le groupe. Un groupe qui n'a exprimé aucun vote n'a pas de position."),
    ("Première lecture", "Premier examen d'un texte par une assemblée, avant l'autre."),
    ("Proximité", "Mesure du rapprochement de sens entre la mesure et le scrutin, de 0 à 1. Elle sert à classer les scrutins, pas à juger le vote."),
    ("Relecture humaine", "Vérification d'un désaccord entre juges, ou d'un cas douteux, par une personne."),
    ("Scrutin", "Vote sur un texte ou un amendement, dont la source officielle publie le résultat."),
    ("Scrutin public", "Vote où la position de chaque parlementaire est recensée nominativement ; les chiffres par groupe sont publiés."),
    ("Sort du scrutin", "Résultat officiel du vote : adopté ou rejeté."),
    ("Sous-amendement", "Modification d'un amendement, déposée avant le vote sur cet amendement."),
    ("Verdict", "Relation entre le vote et la mesure : dans le sens, contraire, ambigu ou hors sujet. Publié seulement si les deux juges sont d'accord, ou après relecture humaine."),
    ("Vote sur l'ensemble", "Vote final sur l'ensemble du texte."),
    ("Commission mixte paritaire", "Réunion de sept députés et sept sénateurs chargée de proposer un texte commun quand les "
     "deux assemblées ne sont pas d'accord."),
    ("Nouvelle lecture", "Nouvel examen d'un texte par chaque assemblée après l'échec d'une commission mixte paritaire."),
    ("Lecture définitive", "Dernier vote de l'Assemblée nationale, qui tranche quand les deux assemblées restent en désaccord."),
    ("Question préalable", "Au Sénat, vote qui demande de ne pas examiner un texte, l'équivalent de la motion de rejet préalable."),
    ("Projet de loi, proposition de loi", "Texte déposé par le Gouvernement (projet) ou par des parlementaires (proposition)."),
    ("Loi de financement de la sécurité sociale", "Loi votée chaque année qui fixe les recettes et les dépenses de la "
     "sécurité sociale, dont les retraites."),
)
PROTOTYPE = ("<strong>Prototype : verdicts pas encore fiables.</strong> Les verdicts sont produits par des modèles "
             "d'intelligence artificielle et n'ont pas été relus par une personne. Évalués sur un jeu de référence, ils "
             "se trompent encore trop souvent (docs/evaluation dans le dépôt). Fiez-vous aux chiffres des votes et aux "
             "explications citées, pas aux verdicts.")
CSS = """
:root{--ink:#1c1c1a;--muted:#5a5a55;--paper:#fbfaf6;--line:#cfcdc6;--soft:#ecebe6;--gris:#8a8a85;--hatch:#6b6b66}
@media (prefers-color-scheme: dark){:root{--ink:#eeede8;--muted:#b4b3ad;--paper:#1a1a18;--line:#4a4a46;--soft:#2a2a27;--gris:#7d7d78;--hatch:#9a9a94}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
.page{max-width:780px;margin:0 auto;padding:24px 16px 64px;overflow-wrap:anywhere}
h1{font-size:1.9rem;line-height:1.2;margin:.3em 0}
h2{font-size:1.3rem;margin:2.2em 0 .6em;padding-top:.7em;border-top:1px solid var(--line)}
h3{font-size:1.1rem;margin:0 0 .4em}
h4{font-size:1rem;margin:1.1em 0 .3em}
p{margin:.5em 0}
a{color:var(--ink);text-decoration-thickness:1px;text-underline-offset:3px}
a:focus-visible,summary:focus-visible{outline:3px solid var(--ink);outline-offset:3px}
.evitement{position:absolute;left:-9999px}
.evitement:focus{left:16px;top:8px;background:var(--paper);padding:4px 8px}
.fil,.parti,.note,.source,.statut,.sous,.petit,.legende{color:var(--muted);font-size:.93rem}
.sous{font-size:1.1rem;margin:0 0 .8em}
.lire,.prototype,.vide{border:1px solid var(--ink);padding:12px 16px;margin:1.2em 0;background:var(--soft)}
.prototype{border-style:dashed}
.lire h2{margin:0 0 .4em;padding:0;border:0;font-size:1.15rem}
blockquote{margin:.8em 0;padding:0 0 0 1rem;border-left:3px solid var(--ink)}
.promesse blockquote p{font-size:1.12rem;margin:0}
.scrutin{border-top:1px solid var(--line);padding:1.2em 0 .4em}
.phrase{font-size:1.02rem}
dl.meta{display:grid;grid-template-columns:max-content 1fr;gap:.2em 1em;font-size:.95rem;margin:.6em 0}
dl.meta>div{display:contents}
dl.meta dt{color:var(--muted)}
dl.meta dd{margin:0}
.table-wrap{margin:.8em 0}
table.votes{width:100%;border-collapse:collapse;font-size:.95rem}
.votes caption{text-align:left;font-weight:700;font-size:1rem;padding:.2em 0 .5em}
.votes thead th{font-size:.85rem;color:var(--muted);font-weight:600;text-align:right;white-space:nowrap;border-bottom:1px solid var(--ink);padding:.3em .5em}
.votes thead th:first-child,.votes thead th:last-child{text-align:left}
.votes td,.votes tbody th{border-top:1px solid var(--line);padding:.6em .5em;vertical-align:top;text-align:right;font-variant-numeric:tabular-nums}
.votes tbody th{text-align:left;font-weight:400}
.votes td{white-space:nowrap}
.votes td.verdict-cell{text-align:left;white-space:normal}
.groupe-cell .petit{display:block;margin-top:.25em}
.barre{display:flex;height:12px;max-width:12rem;border:1px solid var(--ink);margin:.5em 0 0;background:var(--paper)}
.barre span{display:block;height:100%}
.s-pour{background:var(--ink)}
.s-contre{background:repeating-linear-gradient(45deg,var(--ink) 0 2px,transparent 2px 6px)}
.s-abst{background:var(--gris)}
.s-nv{background:repeating-linear-gradient(0deg,var(--hatch) 0 2px,transparent 2px 5px)}
.badge{display:inline-block;border:1px solid var(--ink);padding:2px 8px;border-radius:3px;font-size:.95rem;line-height:1.5}
.badge .sigle{font-weight:700}
.verdict{display:inline-block;padding:2px 10px;border:2px solid var(--ink);font-weight:600}
.v-dans_le_sens{border-style:solid}
.v-contraire{border-style:double;border-width:4px}
.v-ambigu{border-style:dashed}
.v-hors_sujet{border-style:dotted;font-weight:400}
.etat{color:var(--muted)}
h5.libelle{font-size:.85rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:1em 0 .2em}
.justif{margin:.2em 0 .4em 0}
.juges{padding-left:1.1rem;margin:.2em 0}
.modele{font-weight:700}
.extras{display:grid;grid-template-columns:repeat(auto-fit,minmax(9rem,1fr));gap:6px 12px;margin:.6em 0;font-size:.95rem}
.extras div{border-top:1px solid var(--line);padding-top:4px}
.extras dt{color:var(--muted);font-size:.85rem}
.extras dd{margin:0;font-size:1.2rem;font-weight:600;font-variant-numeric:tabular-nums}
.explication{border-left:2px solid var(--line);padding-left:12px;margin:.4em 0}
.texte{white-space:pre-line}
.explication .texte{margin:.3em 0}
.orateur{font-weight:600;margin:0}
.absent{font-style:italic;color:var(--muted)}
details{margin:.6em 0}
summary{cursor:pointer;font-weight:600}
details.detail{margin:0;border:1px solid var(--line);padding:6px 12px}
details.detail[open]{padding-bottom:12px}
.details-groupes{list-style:none;padding:0;margin:0}
.details-groupes>li+li{margin-top:.5em}
.glossaire dt{font-weight:700;margin-top:.7em}
.glossaire dd{margin:0}
.candidats{list-style:none;padding:0;margin:0}
.candidats>li{border-top:1px solid var(--line);padding:14px 0}
.candidats h3{margin:0 0 .1em}
.mesures{list-style:none;padding:0;margin:.4em 0}
.mesures li{margin:.5em 0}
footer{margin-top:3em;border-top:1px solid var(--line);padding-top:1em;font-size:.92rem;color:var(--muted)}
footer p{margin:.4em 0}
@media (max-width:640px){
.votes caption{display:block}
.votes thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.votes,.votes tbody{display:block;width:100%}
.votes tr{display:flex;flex-wrap:wrap;gap:4px 18px;align-items:baseline;border:1px solid var(--line);margin:0 0 12px;padding:10px}
.votes tbody th{flex:1 1 100%;padding:0 0 4px;border:0}
.votes td{display:block;border:0;padding:0;text-align:left;white-space:nowrap}
.votes td::before{content:attr(data-label) " ";color:var(--muted)}
.votes td.verdict-cell{flex:1 1 100%;white-space:normal;margin-top:4px}
}
"""


def page(titre: str, corps: str) -> str:
    return ('<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{esc(titre)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n'
            '<a class="evitement" href="#contenu">Aller au contenu</a>\n'
            f'<div class="page" id="contenu">{corps}</div>\n</body>\n</html>\n')


def pied(pe: bool) -> str:
    lignes = [
        f"Méthode : consigne donnée aux juges, version {judge.PROMPT_VERSION}. Deux juges de familles différentes "
        f"({esc(', '.join(judge.JUDGES))}) jugent chaque paire à l'aveugle. Un verdict n'est publié que si les deux sont "
        "d'accord, ou après relecture humaine.",
        "Données de vote : Assemblée nationale et Sénat, Licence Ouverte (Etalab).",
    ]
    if pe:
        lignes.append("Données HowTheyVote.eu : base sous licence ODbL 1.0, contenus sous licence DbCL 1.0. Au Parlement européen, les noms des groupes et les intitulés "
                      "des scrutins sont repris tels quels de la source, en anglais.")
    lignes += [f"Page générée le {jour(date.today())}.",
               'Code, prompts et méthodologie (fichier docs/methodologie.md) : '
               '<a href="https://github.com/JohnDWorld/concordance">dépôt Concordance</a>.']
    return "<footer>" + "".join(f"<p>{ligne}</p>" for ligne in lignes) + "</footer>"


def glossaire_html() -> str:
    return ('<details class="glossaire-bloc"><summary>Glossaire : les termes techniques</summary><dl class="glossaire">'
            + "".join(f"<div><dt>{esc(t)}</dt><dd>{esc(df)}</dd></div>" for t, df in sorted(GLOSSAIRE)) + "</dl></details>")


def mesure_html(m: Mesure, vues: list[ScrutinVue], d: Donnees) -> str:
    principaux: list[str] = []
    ecartes: list[str] = []
    for vue in sorted(vues, key=lambda v: (v.scrutin.jour, v.scrutin.id)):
        (ecartes if sans_rapport(m.id, vue, d) else principaux).append(scrutin_html(m, vue, d))
    parti = f" ({esc(m.parti)})" if m.parti else ""
    ecartes_html = (f'<details><summary>Votes examinés mais jugés sans rapport avec la mesure ({len(ecartes)})</summary>'
                    + "".join(ecartes) + "</details>") if ecartes else ""
    corps = (
        '<p class="fil"><a href="../index.html">Concordance</a>, retour à l\'index</p>'
        f'<h1>{esc(m.nom)} : mesure sur {THEME.get(m.theme, m.theme)}</h1>'
        '<section class="promesse"><h2>La promesse, citée mot pour mot</h2>'
        f'<blockquote><p>« {esc(m.citation)} »</p></blockquote>'
        f'<p class="source">Candidat : {esc(m.nom)}{parti}. Source : {lien(m.source_url)}, '
        f'consultée le {jour(m.consultee)}.</p></section>'
        '<aside class="lire"><h2>Comment lire cette fiche</h2>' + "".join(f"<p>{t}</p>" for t in LIRE)
        + glossaire_html() + '</aside>'
        f'<p class="prototype">{PROTOTYPE}</p>'
        '<h2>Votes liés à cette mesure</h2>'
        f'<p>Nombre de scrutins retenus : {len(vues)}. Les scrutins sont classés par proximité de sens avec la mesure '
        '(voir « Proximité » dans le glossaire), puis affichés par date. Un vote lié n\'est pas un vote pour ou contre la '
        'mesure : les juges disent ensuite si le texte voté va dans son sens.</p>'
        '<p class="note">Lien avec le candidat : appartenance au groupe à la date du scrutin, d\'après les données officielles '
        f"de l'Assemblée nationale et du Sénat. {LIEN_ALLIANCE}</p>"
        + ("".join(principaux) or '<p class="vide">Aucun scrutin retenu pour cette mesure.</p>')
        + ecartes_html
        + pied(any(v.scrutin.chamber == "pe" for v in vues))
    )
    return page(f"Fiche : {m.nom}, les retraites", corps)


def nom_famille(nom: str) -> str:
    """Tout ce qui suit le premier mot (prénom simple dans les données) : « Marine Le Pen » -> « Le Pen »."""
    # ponytail: un prénom composé trierait mal ; stocker le nom de famille à la saisie quand il y en aura un.
    return nom.split(" ", 1)[1] if " " in nom else nom


def debut(texte: str) -> str:
    if len(texte) <= APERCU:
        return texte
    return texte[:APERCU].rsplit(" ", 1)[0] + " …"


def index_html(candidats: list[Candidat], mesures: list[Mesure]) -> str:
    items: list[str] = []
    for c in sorted(candidats, key=lambda c: (fold(nom_famille(c.nom)), fold(c.nom))):
        liste = [m for m in mesures if m.candidat_id == c.id]
        parti = f'<p class="parti">{esc(c.parti)}</p>' if c.parti else ""
        if liste:
            corps = '<ul class="mesures">' + "".join(
                f'<li><span>« {esc(debut(m.citation))} »</span> <a href="mesures/{m.cle[:12]}.html">Voir la fiche</a></li>'
                for m in liste) + "</ul>"
        else:
            corps = '<p class="note">Aucune mesure retraites saisie à ce jour.</p>'
        items.append(f'<li><h3>{esc(c.nom)}</h3>{parti}{corps}</li>')
    corps = (
        '<header><h1>Concordance</h1><p class="sous">Les promesses des candidats face aux votes du Parlement.</p></header>'
        f'<p class="prototype">{PROTOTYPE} Seules les mesures sur les retraites sont saisies pour l\'instant. Pour un '
        'candidat sans mesure saisie, la saisie n\'est pas encore faite : cela ne signifie pas qu\'il n\'a rien proposé '
        'sur les retraites.</p>'
        '<p>Chaque fiche relie une mesure citée mot pour mot à des votes réels, et montre la position de chaque groupe '
        'avec son explication de vote. Aucun score, aucun classement, aucune consigne de vote.</p>'
        '<h2>Candidats</h2><p class="note">Classés par nom de famille. Tous les candidats sont affichés.</p>'
        f'<ul class="candidats">{"".join(items)}</ul>'
        + pied(False)
    )
    return page("Concordance : promesses et votes", corps)


# --- Chargement ------------------------------------------------------------------------------------------------------

SCRUTIN = """
select b.id, b.chamber, b.legislature, b.ballot_date, b.intitule, b.dossier, b.nature, b.sort, b.source_url,
       a.numero, a.dispositif, a.expose_sommaire, a.source_url
from concordance.ballots b left join concordance.amendments a on a.id = b.amendment_id where b.id = %s
"""
GROUPES = """
select g.id, g.external_id, g.sigle, g.libelle, g.categorie, gp.membres, gp.pour, gp.contre, gp.abstention,
       gp.non_votants, gp.non_votants_volontaires, gp.position_majoritaire
from concordance.group_positions gp join concordance.parl_groups g on g.id = gp.group_id where gp.ballot_id = %s
"""
EXPLICATIONS = "select group_id, orateur, texte, source_url from concordance.vote_explanations where ballot_id = %s order by id"


def personnes_an() -> dict[str, list[list[Membership]]]:
    """Nom complet (sans accents ni casse) -> appartenances de chaque parlementaire de ce nom (AMO30)."""
    index: dict[str, list[list[Membership]]] = defaultdict(list)
    with zipfile.ZipFile(RAW / "an" / "AMO30.json.zip") as zf:
        periodes = group_periods(zf)
        for name in zf.namelist():
            if "/acteur/" in name:
                acteur = json.loads(zf.read(name))["acteur"]
                ident = acteur["etatCivil"]["ident"]
                index[fold(f"{ident.get('prenom') or ''} {ident.get('nom') or ''}")].append(
                    periodes.get(acteur["uid"]["#text"], []))
    return index


def personnes_senat() -> dict[str, list[list[Membership]]]:
    index: dict[str, list[list[Membership]]] = defaultdict(list)
    with zipfile.ZipFile(RAW / "senat" / "export_sens.zip") as zf:
        dump = zf.read("export_sens.sql").decode()
    periodes = memberships(dump)
    for r in copy_rows(dump, "sen"):
        index[fold(f"{r['senprenomuse'] or ''} {r['sennomuse'] or ''}")].append(periodes.get(r["senmat"], []))
    return index


def appartenances(candidats: list[str]) -> dict[str, dict[str, list[Membership] | None]]:
    """Par candidat : appartenances du parlementaire de même nom. Pas de devinette : homonymes = pas de lien."""
    an, senat = personnes_an(), personnes_senat()

    def trouve(index: dict[str, list[list[Membership]]], nom: str) -> list[Membership] | None:
        found = index.get(fold(nom), [])
        if len(found) > 1:
            return None
        return found[0] if found else []

    return {nom: {"an": trouve(an, nom), "senat": trouve(senat, nom)} for nom in candidats}


def charger(conn: psycopg.Connection[Any]) -> Donnees:
    reviews = {(m, b, g): (r, j, who) for m, b, g, r, j, who in conn.execute(
        "select measure_id, ballot_id, group_id, relation, justification, reviewer from concordance.reviews")}
    groupes = {i: NomGroupe(ch, leg, sigle or libelle) for i, ch, leg, sigle, libelle in conn.execute(
        "select id, chamber, legislature, sigle, libelle from concordance.parl_groups")}
    noms = [nom for (nom,) in conn.execute("select full_name from concordance.candidates")]
    return Donnees(judge.verdicts(conn), reviews, groupes, appartenances(noms))


def scrutin_vue(conn: psycopg.Connection[Any], ballot_id: int) -> ScrutinVue:
    row = conn.execute(SCRUTIN, (ballot_id,)).fetchone()
    assert row is not None
    bid, chamber, leg, day, intitule, dossier, nature, sort, source, numero, dispositif, expose, source_am = row
    amendement = Amendement(numero, dispositif, expose, source_am) if numero else None
    scrutin = Scrutin(bid, chamber, leg, day, intitule, dossier, nature, sort, source, amendement)
    groupes = [Groupe(*r) for r in conn.execute(GROUPES, (ballot_id,)).fetchall()]
    explications: dict[int, list[Explication]] = {}
    for gid, orateur, texte, url in conn.execute(EXPLICATIONS, (ballot_id,)).fetchall():
        explications.setdefault(gid, []).append(Explication(orateur, texte, url))
    return ScrutinVue(scrutin, groupes, explications)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sortie", type=Path, default=Path("site"), help="dossier des pages générées")
    sortie = parser.parse_args().sortie
    with db.connect() as conn:
        d = charger(conn)
        candidats = [Candidat(*r) for r in conn.execute("select id, full_name, party from concordance.candidates")]
        mesures = [Mesure(i, cle, theme, citation, url, retrieved.date(), cand, nom, parti) for
                   i, cle, theme, citation, url, retrieved, cand, nom, parti in conn.execute(
                       "select m.id, m.cle, m.theme, m.citation, m.source_url, m.retrieved_at, c.id, c.full_name, c.party "
                       "from concordance.measures m join concordance.candidates c on c.id = m.candidate_id order by m.id")]
        (sortie / "mesures").mkdir(parents=True, exist_ok=True)
        for m in mesures:
            vues = [scrutin_vue(conn, row[0]) for row in search(conn, m.id, m.theme, LIMITE)]
            (sortie / "mesures" / f"{m.cle[:12]}.html").write_text(mesure_html(m, vues, d), encoding="utf-8")
        (sortie / "index.html").write_text(index_html(candidats, mesures), encoding="utf-8")
    print(f"{len(mesures)} fiches de mesure et l'index écrits dans {sortie}")


if __name__ == "__main__":
    main()
