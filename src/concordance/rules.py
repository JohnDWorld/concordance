"""Règles générales de docs/methodologie.md, appliquées de la même façon à toutes les chambres."""

import re
import unicodedata
from datetime import date

from concordance.models import Nature, Position


def nature(intitule: str, code_type_vote: str = "") -> Nature | None:
    """Nature du scrutin déduite du début de l'intitulé. None si rien ne correspond."""
    t = intitule.replace("’", "'").lower().removeprefix("sur ")
    if code_type_vote == "MOC" or t.startswith("la motion"):
        return "motion"
    if t.startswith(("l'amendement", "le sous-amendement", "les amendements")):
        return "amendement"
    if t.startswith("l'article"):
        return "article"
    if t.startswith("l'ensemble"):
        return "texte_entier"
    return None


Membership = tuple[str, date | None, date | None]  # (groupe, début, fin)


def group_at(periods: list[Membership], when: date | None) -> str | None:
    """Groupe d'un parlementaire à une date (appartenance officielle). None si inconnu ou ambigu."""
    if when is None:
        return None
    codes = {g for g, start, end in periods if (start is None or start <= when) and (end is None or when <= end)}
    return codes.pop() if len(codes) == 1 else None


def majority(pour: int, contre: int, abstention: int) -> Position | None:
    """Position qui a le plus de voix. None en cas d'égalité en tête ou sans aucun vote exprimé."""
    counts: dict[Position, int] = {"pour": pour, "contre": contre, "abstention": abstention}
    top = max(counts.values())
    leaders = [p for p, n in counts.items() if n == top]
    return leaders[0] if top and len(leaders) == 1 else None


# --- Amendements (docs/methodologie.md, section Amendements) ---------------------------------------------

NUMBER = (r"(?:z[ée]ro|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize"
          r"|vingts?|trente|quarante|cinquante|soixante|cents?|mille|premi[eè]re?|\w+i[eè]me|\d+(?:[.,]\d+)?)")
NUMBERS = re.compile(rf"\b{NUMBER}(?:[- ](?:et[- ])?(?:{NUMBER}|une?))*\b", re.I)
NEW_TEXT = re.compile(r"(?i)\b(?:insérer|ajouter|compléter|complété|rédiger|rédigée?s?|suivante?s?|par)\b")
OLD_TEXT = re.compile(r"(?i)\b(?:remplacer|supprimer|substituer|après|avant|au mot|aux mots|du mot|des mots)\b")
OPENING, CLOSING = "«“", "»”"


def normalize(text: str) -> str:
    """Texte comparable : espaces réduits, apostrophes et guillemets unifiés."""
    return " ".join(text.replace("’", "'").replace("“", "«").replace("”", "»").split())


def series_key(text: str) -> str:
    """Texte avec tous les nombres masqués (chiffres ou lettres) : deux amendements en série ont la même clé."""
    masked = NUMBERS.sub("#", normalize(text).lower())
    return re.sub(r"#(\s+\w+?)s\b", r"#\1", masked)  # « 61 jour » / « 83 jours »


def quotes(text: str) -> list[tuple[str, str]]:
    """Segments cités de premier niveau, avec le texte qui les précède depuis le segment précédent."""
    out, depth, start, last = [], 0, 0, 0
    straight = '"' in text and not any(c in text for c in OPENING)
    for i, c in enumerate(text):
        if straight and c == '"':
            c = "«" if depth == 0 else "»"
        if c in "«" + OPENING:
            if depth == 0:
                start = i
            depth += 1
        elif c in "»" + CLOSING and depth:
            depth -= 1
            if depth == 0:
                out.append((text[last:start], text[start + 1:i].strip()))
                last = i + 1
    return out


def bare(text: str) -> str:
    """Texte sans ponctuation, casse ni accents : deux textes de forme seulement différente sont égaux."""
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold()) if c.isalnum())


def amendment_scope(dispositif: str) -> tuple[bool, bool, int]:
    """(suppression, forme seulement, mots ajoutés ou réécrits) d'un dispositif. Approximation documentée."""
    text = normalize(dispositif)
    segments = quotes(text)
    if not segments:
        suppression = bool(re.match(r"(?i)supprimer\b", text))  # article, alinéa, phrase... sans texte cité
        return suppression, False, 0 if suppression else len(text.split())
    words, form_only, previous_old = 0, True, None
    for before, quoted in segments:
        new_kw = [m.end() for m in NEW_TEXT.finditer(before)]
        old_kw = [m.end() for m in OLD_TEXT.finditer(before)]
        is_new = bool(new_kw) and (not old_kw or new_kw[-1] > old_kw[-1])
        if not new_kw and not old_kw:
            is_new = previous_old is not None  # « substituer au mot : « a », le mot : « b » »
        if is_new:
            words += sum(1 for w in quoted.split() if any(c.isalnum() for c in w))  # la ponctuation n'est pas un mot
            if bare(quoted) and bare(quoted) != bare(previous_old or ""):
                form_only = False
            previous_old = None
        else:
            if previous_old is not None and bare(previous_old):
                form_only = False  # suppression de mots, sans remplacement
            previous_old = quoted
    if previous_old is not None and bare(previous_old):
        form_only = False
    return False, form_only, words
