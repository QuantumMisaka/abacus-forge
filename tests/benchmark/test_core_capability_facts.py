from __future__ import annotations

import math
import uuid
from pathlib import Path
from typing import Any

import pytest

from abacus_forge import (
    MdCollectRequest,
    MdServiceSet,
    OperationOutcome,
    RelaxCollectRequest,
    RelaxServiceSet,
    ScfCollectRequest,
    ScfServiceSet,
    collect,
)
from tests.support.reference_workspaces import (
    copy_abacustest_scf_workspace,
    copy_native_md_workspace,
    copy_native_relax_workspace,
)


@pytest.mark.benchmark
@pytest.mark.parametrize("capability", ["scf", "relax", "cell-relax", "md"])
def test_core_capability_typed_projection_matches_legacy_facts(
    tmp_path: Path, capability: str
) -> None:
    workspace = _copy_workspace(tmp_path / capability, capability)
    legacy = collect(workspace)
    typed = _typed_collect(tmp_path, workspace, capability)

    assert isinstance(typed, OperationOutcome)
    legacy_status = {
        "scf": "completed",
        "relax": "completed",
        "cell-relax": "completed",
        # The legacy status requires its historical convergence marker.  The
        # typed MD projection instead recognizes the native thermo block.
        "md": "unfinished",
    }[capability]
    assert legacy.status == legacy_status
    assert typed.envelope.status.collection == "complete"
    assert typed.envelope.status.execution == "not_run"
    assert typed.envelope.status.scientific == "unassessed"
    for name in _shared_metric_names(capability):
        assert name in legacy.metrics
        _assert_fact_equal(_metric_value(typed, name), legacy.metrics[name])
    assert _relative_artifact_paths(workspace, legacy) == {
        artifact.path_rel for artifact in typed.envelope.artifacts
    }

    _assert_independent_fixture_facts(workspace, legacy, typed, capability)


def _copy_workspace(root: Path, capability: str):
    if capability == "scf":
        return copy_abacustest_scf_workspace(root)
    if capability in {"relax", "cell-relax"}:
        return copy_native_relax_workspace(root, capability)
    if capability == "md":
        return copy_native_md_workspace(root)
    raise AssertionError(f"unsupported benchmark capability: {capability}")


def _typed_collect(tmp_path: Path, workspace: Any, capability: str) -> Any:
    operation_id = str(uuid.uuid4())
    workspace_rel = workspace.root.name
    if capability == "scf":
        return ScfServiceSet.default(workspace_root=tmp_path).collect.collect(
            ScfCollectRequest(operation_id=operation_id, workspace_rel=workspace_rel)
        )
    if capability in {"relax", "cell-relax"}:
        return RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(
            RelaxCollectRequest(
                operation_id=operation_id,
                workspace_rel=workspace_rel,
                capability=capability,
            )
        )
    if capability == "md":
        return MdServiceSet.default(workspace_root=tmp_path).collect.collect(
            MdCollectRequest(
                operation_id=operation_id,
                workspace_rel=workspace_rel,
                capability="md",
            )
        )
    raise AssertionError(f"unsupported benchmark capability: {capability}")


def _shared_metric_names(capability: str) -> tuple[str, ...]:
    return {
        "scf": ("total_energy", "natom", "total_time"),
        "relax": ("total_energy", "relax_steps"),
        "cell-relax": ("total_energy", "relax_steps"),
        "md": (
            "total_energy",
            "md_last_total_energy",
            "md_last_potential_energy",
            "md_last_kinetic_energy",
            "md_last_temperature",
            "md_last_pressure",
            "md_dump_frames",
            "md_dump_steps",
        ),
    }[capability]


def _metric_value(typed: OperationOutcome, name: str) -> Any:
    return next(metric.value for metric in typed.envelope.metrics if metric.name == name)


def _relative_artifact_paths(workspace: Any, legacy: Any) -> set[str]:
    root = workspace.root.resolve()
    relative_paths: set[str] = set()
    for artifact_name, raw_path in legacy.artifacts.items():
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            resolved = candidate.resolve()
            relative = resolved.relative_to(root)
        except (OSError, RuntimeError, ValueError) as error:
            pytest.fail(f"legacy artifact {artifact_name!r} escapes workspace: {raw_path!r}: {error}")
        relative_paths.add(relative.as_posix())
    return relative_paths


def _assert_fact_equal(actual: Any, expected: Any) -> None:
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        assert actual == expected
        return
    if isinstance(expected, (int, float)):
        if isinstance(expected, float) and not math.isfinite(expected):
            assert actual == expected
        else:
            assert actual == pytest.approx(expected)
        return
    if isinstance(expected, list):
        assert isinstance(actual, list)
        assert len(actual) == len(expected)
        for actual_item, expected_item in zip(actual, expected):
            _assert_fact_equal(actual_item, expected_item)
        return
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        assert set(actual) == set(expected)
        for key, expected_item in expected.items():
            _assert_fact_equal(actual[key], expected_item)
        return
    raise AssertionError(f"unexpected fixture value type: {type(expected).__name__}")


def _assert_independent_fixture_facts(
    workspace: Any, legacy: Any, typed: OperationOutcome, capability: str
) -> None:
    if capability in {"relax", "cell-relax"}:
        running_log = workspace.root / "outputs" / "OUT.ABACUS" / f"running_{capability}.log"
        final_structure = workspace.root / "outputs" / "OUT.ABACUS" / "STRU_FINAL"
        input_structure = workspace.root / "inputs" / "STRU"
        log_text = running_log.read_text(encoding="utf-8")
        assert "TOTAL ENERGY = -4.2 eV" in log_text
        assert "RELAX STEPS = 3" in log_text
        assert final_structure.read_bytes() == input_structure.read_bytes()
        assert Path(legacy.diagnostics["selected_log_path"]).name == running_log.name
        assert Path(typed.envelope.diagnostics["selected_log_path"]).name == running_log.name
        assert Path(typed.envelope.diagnostics["final_structure_path"]).name == "STRU_FINAL"
        assert legacy.metrics["total_energy"] == pytest.approx(-4.2)
        assert legacy.metrics["relax_steps"] == 3
        return

    if capability == "md":
        expected = {
            "total_energy": -129.256631,
            "md_last_total_energy": -129.254131,
            "md_last_potential_energy": -136.05698,
            "md_last_kinetic_energy": 6.802849,
            "md_last_temperature": 310.0,
            "md_last_pressure": 3.0,
            "md_dump_frames": 2,
            "md_dump_steps": 2,
        }
        for name, expected_value in expected.items():
            legacy_value = legacy.metrics[name]
            typed_value = _metric_value(typed, name)
            assert isinstance(legacy_value, (int, float)) and not isinstance(legacy_value, bool)
            assert isinstance(typed_value, (int, float)) and not isinstance(typed_value, bool)
            assert math.isfinite(float(legacy_value))
            assert math.isfinite(float(typed_value))
            assert legacy_value == pytest.approx(expected_value)
            assert typed_value == pytest.approx(expected_value)
