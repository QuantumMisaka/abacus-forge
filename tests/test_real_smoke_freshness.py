from __future__ import annotations

from pathlib import Path

import pytest

from tests.real_smoke.test_abacus_smoke import _assert_no_preexisting_generated_outputs


@pytest.mark.parametrize(
    ("capability", "relative"),
    (
        ("scf", "reports/running_scf.log"),
        ("relax", "reports/running_relax.log"),
        ("relax", "outputs/OUT.ABACUS/STRU"),
    ),
)
def test_freshness_guard_rejects_collector_visible_generated_outputs(
    tmp_path: Path, capability: str, relative: str
) -> None:
    workspace = tmp_path / "workspace"
    path = workspace / relative
    path.parent.mkdir(parents=True)
    path.write_text("stale\n", encoding="utf-8")

    with pytest.raises(pytest.fail.Exception, match="pre-existing generated outputs"):
        _assert_no_preexisting_generated_outputs(workspace, capability=capability)


def test_freshness_guard_allows_input_handoff_and_non_domain_report_files(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "md-workspace"
    for relative in (
        "inputs/OUT.ABACUS/running_md.log",
        "inputs/OUT.ABACUS/MD_dump",
    ):
        path = workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("handoff\n", encoding="utf-8")

    _assert_no_preexisting_generated_outputs(workspace, capability="md")

    relax_workspace = tmp_path / "relax-workspace"
    for relative in ("reports/STRU", "reports/out.log"):
        path = relax_workspace / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("audit\n", encoding="utf-8")
    _assert_no_preexisting_generated_outputs(relax_workspace, capability="relax")
