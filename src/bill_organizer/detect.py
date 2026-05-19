"""Step 1 -- find new bills in the drop folder, skipping duplicates.

Duplicate detection uses a content hash so the same bill is never processed
twice even if it is re-dropped under a different filename.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

SUPPORTED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png"}

# Files matching these are work-in-progress / OS noise, never bills.
_TEMP_PREFIXES = ("~$", ".")
_TEMP_SUFFIXES = (".crdownload", ".part", ".tmp")

# A file whose size is still changing is probably mid-copy; require it to be
# at least this old before touching it.
_MIN_AGE_SECONDS = 2.0


def file_hash(path: Path) -> str:
    """SHA-256 of a file's bytes, used as the dedup key."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_processed_index(index_path: Path) -> dict[str, str]:
    """Load the hash -> filename map of bills already handled."""
    if not index_path.exists():
        return {}
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_processed_index(index_path: Path, index: dict[str, str]) -> None:
    """Persist the dedup index."""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")


def _is_temp_file(path: Path) -> bool:
    name = path.name
    return name.startswith(_TEMP_PREFIXES) or path.suffix.lower() in _TEMP_SUFFIXES


def _is_stable(path: Path) -> bool:
    """True if the file is old enough to be done copying."""
    try:
        return (time.time() - path.stat().st_mtime) >= _MIN_AGE_SECONDS
    except OSError:
        return False


def find_new_bills(drop_dir: Path, index_path: Path) -> list[Path]:
    """Return supported, non-duplicate, fully-written files from ``drop_dir``.

    Already-processed files are matched by content hash against ``index_path``.
    """
    if not drop_dir.exists():
        return []

    known_hashes = set(load_processed_index(index_path).keys())
    new_bills: list[Path] = []

    for entry in sorted(drop_dir.iterdir()):
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if _is_temp_file(entry):
            continue
        if not _is_stable(entry):
            continue
        try:
            digest = file_hash(entry)
        except OSError:
            continue
        if digest in known_hashes:
            continue
        new_bills.append(entry)

    return new_bills
