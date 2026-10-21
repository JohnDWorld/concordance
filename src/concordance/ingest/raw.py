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
RETRY_DELAYS = (10, 30, 60, 120, 300)  # les serveurs de l'Assemblée répondent souvent 503
USER_AGENT = "Concordance (+https://github.com/JohnDWorld/concordance)"


def download(url: str, dest: Path) -> Path:
    path = RAW / dest
    part = path.with_name(path.name + ".part")
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for delay in (*RETRY_DELAYS, None):
        try:
            with urllib.request.urlopen(request, timeout=120) as response, part.open("wb") as f:
                shutil.copyfileobj(response, f)
                expected = response.headers.get("Content-Length")
            # Un serveur qui coupe la connexion peut laisser un fichier tronqué sans lever d'erreur.
            if expected is not None and part.stat().st_size != int(expected):
                raise OSError(f"téléchargement tronqué : {part.stat().st_size} octets sur {expected}")
            break
        except (OSError, http.client.HTTPException) as e:
            client_error = isinstance(e, urllib.error.HTTPError) and e.code < 500
            if delay is None or client_error:
                raise
            print(f"{url} : {e}, nouvel essai dans {delay} s", file=sys.stderr)
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
