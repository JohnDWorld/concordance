from pathlib import Path

from concordance.ingest.programmes import found_in, page_text


def test_found_in_ignores_spacing_only(tmp_path: Path) -> None:
    page = tmp_path / "page.html"
    page.write_text("<html><script>var x = 'Retour à 60 ans.';</script><p>Retour de l’<em>âge</em> légal à 60\n ans.</p></html>",
                    encoding="utf-8")
    text = page_text(page)
    assert found_in("Retour de l’âge légal à 60 ans.", text)
    assert not found_in("Retour de l'âge légal à 60 ans.", text)  # apostrophe différente : pas la même citation
    assert not found_in("Retour à 60 ans.", text)  # présent seulement dans un script, pas dans la page affichée
