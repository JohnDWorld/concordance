import io
import json
import time
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from concordance.ingest import raw


class FakeResponse(io.BytesIO):
    def __init__(self, body: bytes, length: int) -> None:
        super().__init__(body)
        self.headers = {"Content-Length": str(length)}


def setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, responses: list[FakeResponse]) -> None:
    monkeypatch.setattr(raw, "RAW", tmp_path)
    monkeypatch.setattr(raw, "MANIFEST", tmp_path / "manifest.jsonl")
    monkeypatch.setattr(raw, "RETRY_DELAYS", (0,))
    monkeypatch.setattr(time, "sleep", lambda _: None)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: responses.pop(0))


def test_truncated_download_is_retried(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    setup(monkeypatch, tmp_path, [FakeResponse(b"abc", 10), FakeResponse(b"abcdefghij", 10)])
    path = raw.download("https://example.org/f.zip", Path("f.zip"))
    assert path.read_bytes() == b"abcdefghij"
    entry: dict[str, Any] = json.loads((tmp_path / "manifest.jsonl").read_text())
    assert (entry["url"], entry["bytes"]) == ("https://example.org/f.zip", 10)


def test_truncated_download_fails_after_retries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    setup(monkeypatch, tmp_path, [FakeResponse(b"abc", 10), FakeResponse(b"abc", 10)])
    with pytest.raises(OSError, match="tronqué"):
        raw.download("https://example.org/f.zip", Path("f.zip"))
    assert not (tmp_path / "f.zip").exists()
