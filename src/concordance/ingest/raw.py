"""Téléchargement des données brutes dans data/raw/, avec date et URL consignées dans le manifeste."""

import hashlib
import http.client
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

RAW = Path("data/raw")
MANIFEST = RAW / "manifest.jsonl"
RETRY_DELAYS = (10, 30, 60, 120, 300)  # les serveurs de l'Assemblée répondent souvent 503 ou coupent la connexion
USER_AGENT = "Concordance (+https://github.com/JohnDWorld/concordance)"


def fetch_into(url: str, part: Path) -> None:
    """Complète `part` depuis l'octet déjà reçu (requête Range). Lève OSError si le fichier reste incomplet."""
    done = part.stat().st_size if part.exists() else 0
    headers = {"User-Agent": USER_AGENT} | ({"Range": f"bytes={done}-"} if done else {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as response:
        resumed = response.status == 206
        with part.open("ab" if resumed else "wb") as f:
            shutil.copyfileobj(response, f)
        expected = (response.headers.get("Content-Range") or "").rpartition("/")[2] if resumed else response.headers.get("Content-Length")
    # Un serveur qui coupe la connexion peut laisser un fichier tronqué sans lever d'erreur.
    if expected and part.stat().st_size != int(expected):
        raise OSError(f"téléchargement tronqué : {part.stat().st_size} octets sur {expected}")


def download(url: str, dest: Path) -> Path:
    path = RAW / dest
    part = path.with_name(path.name + ".part")
    path.parent.mkdir(parents=True, exist_ok=True)
    part.unlink(missing_ok=True)  # jamais de reprise d'un essai précédent : le fichier a pu changer depuis
    stalled = 0
    while True:
        before = part.stat().st_size if part.exists() else 0
        try:
            fetch_into(url, part)
            break
        except (OSError, http.client.HTTPException) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code < 500:
                raise
            progressed = part.exists() and part.stat().st_size > before
            stalled = 0 if progressed else stalled + 1
            if stalled >= len(RETRY_DELAYS):
                raise
            delay = 1 if progressed else RETRY_DELAYS[stalled]
            print(f"{url} : {e}, reprise dans {delay} s", file=sys.stderr)
            time.sleep(delay)
    part.replace(path)
    with path.open("rb") as f:
        sha256 = hashlib.file_digest(f, "sha256").hexdigest()
    entry = {
        "url": url,
        "path": str(path),
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "bytes": path.stat().st_size,
        "sha256": sha256,
    }
    with MANIFEST.open("a") as m:
        m.write(json.dumps(entry) + "\n")
    return path
