"""Anonymiseur : tout texte envoyé au juge passe par ici (CLAUDE.md, règle 2 ; docs/methodologie.md).

Le groupe jugé devient « Groupe X » (lettre tirée au hasard à chaque jugement), les autres groupes cités d'autres
lettres, les partis « [parti] », les personnes « [personne] », les termes partisans « [terme partisan] ».
Le dictionnaire vient des données (organes, sénateurs, eurodéputés, candidats), jamais d'une liste par parti.
"""

import csv
import gzip
import json
import random
import re
import unicodedata
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import psycopg

from concordance.ingest.raw import RAW
from concordance.ingest.senat import copy_rows

PERSON, PARTY, TERM = "[personne]", "[parti]", "[terme partisan]"
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CIVILITY = r"(?:M\.|Mme|Mmes|MM\.|Monsieur|Madame)"
# Désignations d'un camp qui ne sont ni un nom de groupe ni un nom de parti des données.
PARTISAN_TERMS = ("insoumis", "insoumise", "insoumises", "lepéniste", "lepénistes", "macroniste", "macronistes",
                  "mélenchoniste", "mélenchonistes", "frontiste", "frontistes", "zemmouriste", "zemmouristes",
                  "NUPES", "Nupes", "NFP", "Nouveau Front populaire", "Nouveau Front Populaire")


def variants(name: str) -> set[str]:
    """Écritures d'un même nom : espaces autour des tirets, apostrophes (les accents sont gérés par le motif)."""
    name = " ".join(name.split())
    out = {name, re.sub(r"\s*-\s*", "-", name), re.sub(r"\s*-\s*", " - ", name), name.replace("’", "'")}
    return {v for v in out if len(v) >= 2}


def unaccented(c: str) -> str:
    return "".join(x for x in unicodedata.normalize("NFD", c) if not unicodedata.combining(x))


ACCENTED: dict[str, set[str]] = {}
for _c in "àâäáãåçéèêëíìîïñóòôöõúùûüýÿÀÂÄÁÃÅÇÉÈÊËÍÌÎÏÑÓÒÔÖÕÚÙÛÜÝ":
    ACCENTED.setdefault(unaccented(_c), set()).add(_c)


def pattern(name: str) -> str:
    """Motif qui accepte le nom avec ou sans accents (« Ecolo » trouve « Écolo »), casse conservée."""
    out = []
    for c in name:
        base = unaccented(c)
        forms = {c, base} | ACCENTED.get(base, set())
        out.append("[" + "".join(sorted(re.escape(f) for f in forms)) + "]" if len(forms) > 1 else re.escape(c))
    return "".join(out)


def alternation(names: Iterable[str]) -> str:
    return "|".join(pattern(n) for n in sorted(set(names), key=len, reverse=True))


@dataclass
class Dictionary:
    persons: re.Pattern[str]  # noms complets ou noms après une civilité
    groups: list[tuple[re.Pattern[str], frozenset[int]]]  # nom -> tous les groupes qui le portent (législatures, chambres)
    parties: re.Pattern[str]
    terms: re.Pattern[str]


def compile_dictionary(full_names: Iterable[str], surnames: Iterable[str], groups: Iterable[tuple[str, int]],
                       parties: Iterable[str]) -> Dictionary:
    full = alternation(v for n in full_names for v in variants(n))
    last = alternation(v for n in surnames for v in variants(n))
    # Après une civilité, le nom complet d'abord : « M. Bertrand Pancher », pas « M. Bertrand » + « Pancher ».
    persons = re.compile(rf"\b(?:{CIVILITY}\s+(?:{full}|{last})|{full})\b", re.IGNORECASE)
    by_name: dict[str, set[int]] = {}
    for name, group_id in groups:
        for v in variants(name):
            by_name.setdefault(v, set()).add(group_id)
    # Sigles et noms de groupe : sensibles à la casse (« NI », « RE » ne sont pas « ni », « re »).
    group_patterns = [(re.compile(rf"(?<![\w-]){pattern(n)}(?![\w-])"), frozenset(ids)) for n, ids in
                      sorted(by_name.items(), key=lambda kv: len(kv[0]), reverse=True)]
    party_names = {v for p in parties for v in variants(p)} - set(by_name)
    return Dictionary(
        persons=persons,
        groups=group_patterns,
        parties=re.compile(rf"(?<![\w-])(?:{alternation(party_names)})(?![\w-])") if party_names else re.compile(r"(?!)"),
        terms=re.compile(rf"(?<![\w-])(?:{alternation(v for t in PARTISAN_TERMS for v in variants(t))})(?![\w-])", re.IGNORECASE),
    )


def anonymize(texts: list[str], judged_group: int, dictionary: Dictionary, rng: random.Random
              ) -> tuple[list[str], dict[str, list[int]]]:
    """Textes anonymisés et correspondance étiquette -> groupes (stockée avec le jugement).

    Un nom porté par plusieurs groupes (« LIOT » en 16e et en 17e législature) prend la lettre du groupe jugé
    s'il le désigne : sinon le juge croirait lire l'avis d'un autre groupe.
    """
    letters = list(LETTERS)
    rng.shuffle(letters)
    judged = f"Groupe {letters.pop()}"
    labels: dict[frozenset[int], str] = {}

    def label(ids: frozenset[int]) -> str:
        if judged_group in ids:
            return judged
        if ids not in labels:
            labels[ids] = f"Groupe {letters.pop()}"
        return labels[ids]

    out = []
    for text in texts:
        text = dictionary.persons.sub(PERSON, text)
        for regex, ids in dictionary.groups:
            if regex.search(text):  # une lettre n'est attribuée qu'à un groupe réellement cité
                text = regex.sub(label(ids), text)
        text = re.sub(r"\b[Gg]roupe (Groupe [A-Z])\b", r"\1", text)  # « le groupe Groupe C » -> « le Groupe C »
        text = dictionary.parties.sub(PARTY, text)
        out.append(dictionary.terms.sub(TERM, text))
    return out, {judged: [judged_group]} | {lab: sorted(ids) for ids, lab in labels.items()}


def build_dictionary(conn: psycopg.Connection[Any]) -> Dictionary:
    """Dictionnaire construit depuis les données brutes et la base (organes, sénateurs, eurodéputés, candidats)."""
    full_names: set[str] = set()
    surnames: set[str] = set()
    with zipfile.ZipFile(RAW / "an/AMO30.json.zip") as zf:
        for name in zf.namelist():
            if "/acteur/" in name:
                ident = json.loads(zf.read(name))["acteur"]["etatCivil"]["ident"]
                full_names.add(f"{ident['prenom']} {ident['nom']}")
                surnames.add(ident["nom"])
    with zipfile.ZipFile(RAW / "senat/export_sens.zip") as zf:
        for r in copy_rows(zf.read("export_sens.sql").decode(), "sen"):
            full_names.add(f"{r['senprenomuse']} {r['sennomuse']}")
            surnames.add(r["sennomuse"])
    members = sorted((RAW / "pe").glob("*/members.csv.gz"))[-1:]
    for path in members:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                last = r["last_name"].title()
                full_names.add(f"{r['first_name']} {last}")
                surnames.add(last)
    candidates = [n for (n,) in conn.execute("select full_name from concordance.candidates")]
    full_names |= set(candidates)
    surnames |= {n.split(" ", 1)[1] for n in candidates if " " in n}
    groups = [(n, gid) for gid, libelle, sigle in conn.execute("select id, libelle, sigle from concordance.parl_groups")
              for n in (libelle, sigle) if n]
    parties = [p for (p,) in conn.execute("select distinct party from concordance.candidates where party is not null")]
    parties += [r["label"] for path in sorted((RAW / "pe").glob("*/national_parties.csv.gz"))[-1:]
                for r in csv.DictReader(gzip.open(path, "rt", encoding="utf-8")) if r["country_code"] == "FRA"]
    return compile_dictionary(full_names, surnames, groups, parties)
