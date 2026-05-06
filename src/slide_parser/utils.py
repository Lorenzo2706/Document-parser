"""Shared helpers."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path


def slugify(value: str) -> str:
    """ASCII-safe slug suitable for filenames."""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    value = re.sub(r"[-\s]+", "-", value)
    return value or "document"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def doc_stem(input_path: Path) -> str:
    """Stable, slug-safe stem for output filenames."""
    return slugify(input_path.stem)
