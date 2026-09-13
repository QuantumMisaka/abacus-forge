"""Installability contract for the optional abacuslite parser dependency.

The canonical checkout is a Stage 0 oracle, not an installable dependency.
This test keeps the Stage 1 boundary executable without claiming that a
published abacuslite release exists.
"""

from __future__ import annotations

from pathlib import Path
import re
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def _project_metadata() -> dict[str, object]:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        return tomllib.load(stream)["project"]


def test_abacuslite_extra_is_exactly_pinned_if_declared() -> None:
    project = _project_metadata()
    dependencies = project.get("dependencies", [])
    optional = project.get("optional-dependencies", {})
    assert isinstance(dependencies, list)
    assert not any(str(item).lower().startswith("abacuslite") for item in dependencies)
    assert isinstance(optional, dict)

    declared = [
        str(item)
        for values in optional.values()
        if isinstance(values, list)
        for item in values
        if str(item).lower().startswith("abacuslite")
    ]
    if not declared:
        # No public exact release is currently available.  The optional
        # parser therefore remains deliberately blocked at the package layer.
        return
    assert len(declared) == 1
    assert re.fullmatch(r"abacuslite==[^;\s]+", declared[0], flags=re.IGNORECASE)

