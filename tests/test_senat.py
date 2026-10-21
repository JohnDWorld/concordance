from datetime import date

import pytest

from concordance.ingest.senat import Membership, copy_rows, current_session, parse_ballot, parse_explanations

# Gabarit réel d'une page de scrutin (senat.fr), réduit à deux groupes.
GROUP = """<div id="accordion-scrutin-{code}" class="accordion-header"><div role="button" data-bs-target="#accordion-collapse-scrutin-{code}">
<h3 class="accordion-title fs-5">Groupe {code}&nbsp;: {membres}<span class="visually-hidden">s&eacute;nateurs</span></h3>
<ul class="list-inline mb-0">
<li class="list-inline-item"><svg></svg>Pour&nbsp;: <span class="ms-1 fw-semibold">{pour}</span></li>
<li class="list-inline-item"><svg></svg>Contre&nbsp;: <span class="ms-1 fw-semibold">{contre}</span></li>
<li class="list-inline-item"><svg></svg>N'a
pas pris part au vote&nbsp;: <span class="ms-1 fw-semibold">1</span></li>
</ul></div></div>
<div id="accordion-collapse-scrutin-{code}"><ul><li><b>Pour</b>&nbsp;: MM. Untel</li></ul></div>"""
PAGE = """<h1 class="page-title"> Scrutin n&deg;251 - s&eacute;ance du 16 mars 2023 </h1>
<p class="page-lead">sur l'ensemble du texte &eacute;labor&eacute; par la commission mixte paritaire</p>
<a href="/dossier-legislatif/pjl22-368.html">Le dossier l&eacute;gislatif</a>
<h2 class="card-title">R&eacute;sultat du scrutin</h2> <p>Le S&eacute;nat a adopt&eacute;</p>
<strong class="display-4 ff-alt">{total_pour}</strong> pour <strong class="display-4 ff-alt">6</strong> contre
""" + GROUP.format(code="UMP", membres=145, pour=119, contre=6) + GROUP.format(code="SOC", membres=64, pour=0, contre=0)


def test_parse_ballot() -> None:
    b = parse_ballot(PAGE.format(total_pour=119), 2022, 251)
    assert (b.external_id, b.ballot_date, b.sort, b.nature) == ("scr2022-251", date(2023, 3, 16), "adopté", "texte_entier")
    assert b.dossier == "https://www.senat.fr/dossier-legislatif/pjl22-368.html"
    ump, soc = b.positions
    assert (ump.group_external_id, ump.membres, ump.pour, ump.contre, ump.non_votants, ump.position_majoritaire) == ("UMP", 145, 119, 6, 1, "pour")
    assert soc.position_majoritaire is None  # aucun vote exprimé


def test_totals_mismatch_rejected() -> None:
    with pytest.raises(ValueError, match="somme des groupes"):
        parse_ballot(PAGE.format(total_pour=120), 2022, 251)


def test_copy_rows() -> None:
    dump = "COPY public.grppol (grppolcod, grppoldatfin) FROM stdin;\nUC\t\\N\nUMP\t2020-01-01 00:00:00\n\\.\n"
    assert list(copy_rows(dump, "grppol")) == [
        {"grppolcod": "UC", "grppoldatfin": None},
        {"grppolcod": "UMP", "grppoldatfin": "2020-01-01 00:00:00"},
    ]


def test_current_session() -> None:
    assert current_session(date(2026, 10, 21)) == 2026
    assert current_session(date(2027, 3, 1)) == 2026


def turn(par: int, mat: str, nom: str, text: str, qua: str = "") -> str:
    return (f'<div id="intv_par_{par}" class="intervenant"><a name="int{par}"> </a>\n'
            f'<!--cri:intervenant mat="{mat}" nom="{nom}" qua="{qua}" type="1" -->\n'
            f'<p id="par_{par}"><span class="orateur_nom"><!--cri:orateurnom --><a class="lien_senfic" href="/senateur/x.html">'
            f'<span class="orateur_nom">M. </span><span class="orateur_nom">X.</span></a><!--/cri:orateurnom --></span> {text}</p>\n'
            '<!--/cri:intervenant --></div>\n')


PRESIDENT = ("86034E", "Gérard LARCHER")
CRI = (
    turn(1, *PRESIDENT, "La parole est à Mme Colette Mélot, pour le groupe Les Indépendants.", "président de séance")
    + turn(2, "11045K", "Laurence ROSSIGNOL", "Très bien !")  # interruption avant l'orateur annoncé
    + turn(3, "04057K", "Colette MÉLOT", "Monsieur le président, nous voterons ce texte.")
    + turn(4, "11045K", "Laurence ROSSIGNOL", "C’est faux !")
    + '<div id="intv_par_9" class="intervenant">\n<p id="par_9"><span class="orateur_nom"><!--cri:orateurnom -->'
      '<span class="orateur_nom">Mme Y et M. Z. </span><!--/cri:orateurnom --></span>C’est la dette !</p>\n</div>\n'  # interruption collective, sans commentaire cri
    + turn(5, "04057K", "Colette MÉLOT", "Je le maintiens. Comme le disait la séance du scrutin n° 12.")
    + turn(6, *PRESIDENT, "Voici le résultat du scrutin n° 251. La parole est à M. Paul Dupont, pour explication de vote.", "président de séance")
    + turn(7, "99999Z", "Paul DUPONT", "Je ne voterai pas cet amendement.")
    + turn(8, *PRESIDENT, "Je le mets aux voix. (L’amendement n’est pas adopté.) Il va être procédé au scrutin n° 252.", "président de séance")
)
MEMBERS: dict[str, list[Membership]] = {"04057K": [("RTLI", date(2020, 10, 5), None)], "99999Z": [("UC", None, None)]}


def test_parse_explanations() -> None:
    out, stats = parse_explanations(CRI, date(2023, 3, 16), "https://www.senat.fr/cri.html", MEMBERS)
    [e] = out
    assert (e.ballot_external_id, e.group_external_id, e.orateur_external_id) == ("scr2022-251", "RTLI", "04057K")
    assert e.texte == "Monsieur le président, nous voterons ce texte. […] Je le maintiens. Comme le disait la séance du scrutin n° 12."  # interruptions exclues
    assert e.source_url == "https://www.senat.fr/cri.html#par_3"
    assert stats["vote à main levée ou sans scrutin public"] == 1  # Paul Dupont : vote à main levée avant le scrutin 252
