from datetime import date

import pytest

from concordance.ingest.senat import copy_rows, current_session, parse_ballot

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
