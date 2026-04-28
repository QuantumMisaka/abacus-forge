"""Input validation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def validate_inputs(path: str | Path) -> dict[str, Any]:
    base = Path(path)
    missing = [name for name in ("INPUT", "STRU", "KPT") if not (base / name).exists()]
    return {
        "valid": not missing,
        "missing": missing,
    }
