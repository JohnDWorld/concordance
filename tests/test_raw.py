import io
import json
import time
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from concordance.ingest import raw


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, length: int, status: int = 200, start: int = 0) -> None:
        super().__init__(body)
        self.status = status
        self.headers = {"Content-Length": str(len(body) if status == 206 else length), "ETag": '"v1"'}
        if status == 206:
            self.headers["Content-Range"] = f"bytes {start}-{length - 1}/{length}"


def setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, responses: list[FakeResponse]) -> list[str | None]:
    """Réponses servies dans l'ordre ; renvoie l'en-tête Range de chaque requête reçue."""
    ranges: list[str | None] = []

    def urlopen(request: urllib.request.Request, **_: Any) -> FakeResponse:
        ranges.append(request.get_header("Range"))
        assert request.get_header("If-range") == ('"v1"' if request.get_header("Range") else None)
        return responses.pop(0)

    monkeypatch.setattr(raw, "RAW", tmp_path)
    monkeypatch.setattr(raw, "MANIFEST", tmp_path / "manifest.jsonl")
    monkeypatch.setattr(raw, "RETRY_DELAYS", (0,))
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return ranges


def test_truncated_download_is_resumed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ranges = setup(monkeypatch, tmp_path, [FakeResponse(b"abc", 10), FakeResponse(b"defghij", 10, status=206, start=3)])
    path = raw.download("https://example.org/f.zip", Path("f.zip"))
    assert path.read_bytes() == b"abcdefghij"
    assert ranges == [None, "bytes=3-"]
    entry: dict[str, Any] = json.loads((tmp_path / "manifest.jsonl").read_text())
    assert (entry["url"], entry["bytes"]) == ("https://example.org/f.zip", 10)


def test_server_ignoring_range_restarts_from_zero(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    setup(monkeypatch, tmp_path, [FakeResponse(b"abc", 10), FakeResponse(b"abcdefghij", 10)])
    assert raw.download("https://example.org/f.zip", Path("f.zip")).read_bytes() == b"abcdefghij"


def test_download_without_progress_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    setup(monkeypatch, tmp_path, [FakeResponse(b"abc", 10), FakeResponse(b"", 10, status=206, start=3)])
    with pytest.raises(OSError, match="tronqué"):
        raw.download("https://example.org/f.zip", Path("f.zip"))
    assert not (tmp_path / "f.zip").exists()


def test_resume_across_runs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Un fichier partiel d'une exécution précédente est repris, protégé par If-Range."""
    ranges = setup(monkeypatch, tmp_path, [FakeResponse(b"defghij", 10, status=206, start=3)])
    (tmp_path / "f.zip.part").write_bytes(b"abc")
    (tmp_path / "f.zip.part.etag").write_text('"v1"')
    assert raw.download("https://example.org/f.zip", Path("f.zip")).read_bytes() == b"abcdefghij"
    assert ranges == ["bytes=3-"]
    assert not (tmp_path / "f.zip.part.etag").exists()


def test_partial_without_etag_restarts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ranges = setup(monkeypatch, tmp_path, [FakeResponse(b"abcdefghij", 10)])
    (tmp_path / "f.zip.part").write_bytes(b"xyz")  # origine inconnue : jamais repris
    assert raw.download("https://example.org/f.zip", Path("f.zip")).read_bytes() == b"abcdefghij"
    assert ranges == [None]
