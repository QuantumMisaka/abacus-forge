from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from abacus_forge import collect
from abacus_forge.contracts import OperationOutcome, ScfCollectRequest
from abacus_forge.services import ScfServiceSet
from tests.support.reference_workspaces import FIXTURE_ROOT, copy_abacustest_scf_workspace


def _assert_factual_projection(actual: Any, expected: Any) -> None:
    """Compare parser facts without requiring byte-identical numeric output."""
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        assert actual == expected
        return
    if isinstance(expected, (int, float)):
        assert actual == pytest.approx(expected)
        return
    if isinstance(expected, list):
        assert isinstance(actual, list)
        assert len(actual) == len(expected)
        for actual_item, expected_item in zip(actual, expected):
            _assert_factual_projection(actual_item, expected_item)
        return
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        assert set(actual) == set(expected)
        for key, expected_item in expected.items():
            _assert_factual_projection(actual[key], expected_item)
        return
    raise AssertionError(f"unexpected fixture value type: {type(expected).__name__}")


@pytest.mark.benchmark
def test_abacustest_scf_projection_preserves_migration_metrics(tmp_path: Path) -> None:
    result = collect(copy_abacustest_scf_workspace(tmp_path / "benchmark"))
    assert result.status == "completed"
    assert len(result.metrics["force"]) == 81
    expected_stress_rows = [
        [-52.80278090212644, -0.20034687716893254, -0.16869734918889936],
        [-0.20034687716893204, -52.87869324794468, -0.45515956333833435],
        [-0.16869734918889878, -0.45515956333833385, -39.96544028144169],
    ]
    # The public collector contract stores the latest 3x3 stress tensor as a
    # flat list, while the ABACUSTest reference records rows.
    expected_stress = [value for row in expected_stress_rows for value in row]
    assert result.metrics["stress"] == pytest.approx(
        expected_stress
    )
    assert result.metrics["pressure"] == pytest.approx(-48.548971477133335)
    assert result.metrics["total_time"] == pytest.approx(932.927)


@pytest.mark.benchmark
def test_typed_scf_collection_preserves_abacustest_observations(tmp_path: Path) -> None:
    """The typed migration surface keeps the legacy parser's factual metrics."""
    typed_workspace = copy_abacustest_scf_workspace(tmp_path / "typed" / "scf")
    typed = ScfServiceSet.default(workspace_root=typed_workspace.root.parent).collect.collect(
        ScfCollectRequest(
            operation_id="123e4567-e89b-42d3-a456-426614174500",
            workspace_rel="scf",
        )
    )

    assert isinstance(typed, OperationOutcome)
    assert typed.status.execution == "not_run"
    assert typed.status.scientific == "unassessed"

    reference = json.loads((FIXTURE_ROOT / "abacus.json").read_text(encoding="utf-8"))["output"][0]
    expected_force = [value for row in reference["force"] for value in row]
    expected_stress = [value for row in reference["stress"] for value in row]
    volume = 8.3004 * 8.3004 * 25.362243471279523
    kbar_to_ev_per_angstrom3 = 3.398927420868445e-6 * 27.211396132 / 0.52917721092**3
    expected_virial = [value * volume * kbar_to_ev_per_angstrom3 for value in expected_stress]
    expected = {
        "natom": 27,
        "converged": True,
        "converge": True,
        "normal_end": True,
        "force": expected_force,
        "forces": [expected_force],
        "stress": expected_stress,
        "stresses": [expected_stress],
        "pressure": -48.548971477133335,
        "pressures": [-48.548971477133335],
        "virial": expected_virial,
        "virials": [expected_virial],
        "total_time": 932.927,
    }
    observations = {
        observation.name: observation.to_dict()["value"]
        for observation in typed.observations
    }
    for name, expected_value in expected.items():
        assert name in observations
        _assert_factual_projection(observations[name], expected_value)

    # The typed collector preserves the legacy artifact inventory while
    # returning paths relative to the portable Forge workspace.
    assert {artifact.path_rel for artifact in typed.envelope.artifacts} == {
        "inputs/INPUT",
        "inputs/KPT",
        "inputs/STRU",
        "outputs/OUT.ABACUS/INPUT",
        "outputs/OUT.ABACUS/running_scf.log",
        "outputs/OUT.ABACUS/time.json",
        "outputs/out.log",
        "outputs/stderr.log",
    }
    references = typed.envelope.diagnostics["artifact_refs"]
    assert {reference["artifact_id"] for reference in references} == {
        artifact.id for artifact in typed.envelope.artifacts
    }
    assert all(reference["operation_id"] == typed.operation_id for reference in references)
