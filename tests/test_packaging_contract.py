"""Packaging contract tests for PEP 517 build configuration."""

try:
    import tomllib as _toml_reader
except ImportError:  # Python < 3.11
    import tomli as _toml_reader
import pytest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_pyproject() -> dict:
    with open(PROJECT_ROOT / "pyproject.toml", "rb") as handle:
        return _toml_reader.load(handle)


@pytest.mark.core
def test_wheel_contains_only_runtime_package() -> None:
    config = _load_pyproject()["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert config["packages"] == ["src/abacus_forge"]


@pytest.mark.core
def test_sdist_includes_source_tests_examples_and_provenance() -> None:
    config = _load_pyproject()["tool"]["hatch"]["build"]["targets"]["sdist"]
    assert set(config["include"]) == {
        "src",
        "tests",
        "examples",
        "scripts/release_validate.py",
        "docs",
        "pyproject.toml",
        "README.md",
        "LICENSE",
    }
    force_includes = set(config["force-include"])
    assert {
        "docs/superpowers/evidence/2026-10-21-forge-abacuslite-1.2.2-package-provenance.json",
        "docs/superpowers/evidence/2026-10-19-forge-abacuslite-1.2.0-package-provenance.json",
        "docs/superpowers/evidence/2026-09-14-forge-stage1-package-provenance.json",
    } <= force_includes


@pytest.mark.core
def test_sdist_excludes_evidence_and_internal_docs() -> None:
    config = _load_pyproject()["tool"]["hatch"]["build"]["targets"]["sdist"]
    assert set(config["exclude"]) >= {
        "docs/archive",
        "docs/superpowers/evidence",
        "docs/superpowers/plans",
        "docs/superpowers/specs",
        ".scratch",
    }


def test_sdist_preserves_workflow_and_repository_entry_documents() -> None:
    config = _load_pyproject()["tool"]["hatch"]["build"]["targets"]["sdist"]
    force_includes = set(config["force-include"])
    assert {".github/workflows/ci.yml", "AGENTS.md", "ROADMAP.md"} <= force_includes

def test_sdist_includes_required_engine_log_fixtures() -> None:
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "!tests/fixtures/**/*.log" in gitignore
