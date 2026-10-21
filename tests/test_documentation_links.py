from __future__ import annotations

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRECTORIES = {".git", ".worktrees", ".venv", "node_modules"}
_MARKDOWN_LINK = re.compile(
    r"\[[^\]\n]+\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)"
)


def _iter_markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if not any(
            part in SKIP_DIRECTORIES for part in path.relative_to(ROOT).parts
        )
    )


def _broken_relative_markdown_links() -> list[str]:
    broken: list[str] = []
    for path in _iter_markdown_files():
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for match in _MARKDOWN_LINK.finditer(line):
                target = match.group(1)
                target_path = target.split("#", 1)[0]
                if not target_path:
                    continue
                if target_path.startswith(
                    ("http://", "https://", "mailto:", "file:")
                ):
                    continue
                resolved = (path.parent / target_path).resolve()
                if not resolved.is_relative_to(ROOT):
                    # AGENTS.md deliberately links to the workspace-level
                    # governance file, which is outside this repository.
                    continue
                if not resolved.exists():
                    relative_source = path.relative_to(ROOT).as_posix()
                    broken.append(
                        f"{relative_source}:{line_number}: {target} -> {resolved}"
                    )
    return broken


@pytest.mark.core
def test_markdown_relative_link_targets_exist() -> None:
    files = _iter_markdown_files()
    assert files, "expected repository Markdown documentation to be present"

    broken = _broken_relative_markdown_links()
    assert not broken, (
        "Markdown links point to missing repository targets:\n" + "\n".join(broken)
    )


@pytest.mark.core
def test_markdown_link_guard_has_repository_coverage() -> None:
    files = _iter_markdown_files()
    readme = ROOT / "README.md"
    candidate_evidence = (
        ROOT
        / "docs/superpowers/evidence/2026-10-21-forge-main-4106f33-candidate.md"
    )
    assert readme in files
    assert candidate_evidence in files
    assert len(files) >= 100
