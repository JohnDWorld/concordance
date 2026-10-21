"""Règles générales de docs/methodologie.md, appliquées de la même façon à toutes les chambres."""

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


def majority(pour: int, contre: int, abstention: int) -> Position | None:
    """Position qui a le plus de voix. None en cas d'égalité en tête ou sans aucun vote exprimé."""
    counts: dict[Position, int] = {"pour": pour, "contre": contre, "abstention": abstention}
    top = max(counts.values())
    leaders = [p for p, n in counts.items() if n == top]
    return leaders[0] if top and len(leaders) == 1 else None
