"""Register a locally supplied resource for the same onboarding and extraction pipeline."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from ..paths import DATA, ROOT
from .fetch import MAX_DOWNLOAD

REGISTRY = DATA / "registered"
SOURCE_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")


def local_sources() -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(REGISTRY.glob("*/source.json")) if not path.parent.name.startswith(".")]


def register(source_id: str, file: Path, *, title: str, publisher: str, licence: str) -> dict:
    from .select import load_manifest

    if not SOURCE_ID.fullmatch(source_id) or Path(source_id).is_reserved():
        raise ValueError("source ID must be a valid filename of up to 64 lowercase letters, digits, hyphens or underscores")
    if source_id in load_manifest():
        raise ValueError(f"source ID already registered: {source_id}")
    if not file.is_file():
        raise ValueError(f"source file not found: {file}")

    destination = REGISTRY / source_id
    snapshot_path = destination / "snapshot"
    REGISTRY.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=REGISTRY, prefix=".register-") as staging:
        source_dir = Path(staging) / source_id
        source_dir.mkdir()
        digest = hashlib.sha256()
        size = 0
        with file.open("rb") as raw, (source_dir / snapshot_path.name).open("wb") as snapshot:
            for chunk in iter(lambda: raw.read(1 << 20), b""):
                size += len(chunk)
                if size > MAX_DOWNLOAD:
                    raise ValueError(f"source exceeds the {MAX_DOWNLOAD:,}-byte limit")
                digest.update(chunk)
                snapshot.write(chunk)
        if not size:
            raise ValueError("source file is empty")
        source = {
            "source_id": source_id,
            "title": title,
            "publisher": publisher,
            "licence": licence,
            "resource_name": file.name,
            "advertised_format": file.suffix.lstrip(".").upper() or "unknown",
            "snapshot": {
                "path": snapshot_path.relative_to(ROOT).as_posix(),
                "sha256": digest.hexdigest(),
                "bytes": size,
                "downloaded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            },
        }
        (source_dir / "source.json").write_text(json.dumps(source, indent=2), encoding="utf-8")
        source_dir.rename(destination)
    return source
