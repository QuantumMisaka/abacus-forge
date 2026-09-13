"""Opt-in native versus abacuslite collection parity on real ABACUS output.

The test deliberately requires an explicit JSON matrix.  A missing matrix is a
skip for ordinary developer runs, while a release-candidate job must require
the test selection and reject skips in its CI policy.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
import re
import shutil
import sys

import pytest

from abacus_forge.api import UnitSpec, execute_unit
from abacus_forge.collection import collect_contained
from abacus_forge import collection_results, md_results, relax_results
from abacus_forge.input_io import read_input
from abacus_forge.modify import modify_input


_MATRIX_ENV = "ABACUS_FORGE_ABACUSLITE_DUAL_TRACK_MATRIX"
_PACKAGE_ENV = "ABACUS_FORGE_ABACUSLITE_PATH"
_LD_ENV = "ABACUS_FORGE_ABACUSLITE_LD_LIBRARY_PATH"
_REQUIRE_FULL_MATRIX_ENV = "ABACUS_FORGE_ABACUSLITE_REQUIRE_FULL_MATRIX"
_CAPABILITIES = ("scf", "relax", "cell-relax", "md")
_TRACKS = ("develop", "lts")
_ENERGY_TOLERANCE_EV = 5e-3
_FORCE_TOLERANCE_EV_PER_ANGSTROM = 1e-3
_STRESS_TOLERANCE_KBAR = 1e-3
_RELEASE_REQUIRED_FIELDS = frozenset({
    "track", "basis", "nspin", "executable_sha256", "input_identity",
})
_BACKEND_SPECIFIC_DIAGNOSTICS = frozenset({"native_final_energy_markers"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _matrix() -> list[dict[str, object]]:
    raw = os.environ.get(_MATRIX_ENV)
    if not raw:
        pytest.skip(f"set {_MATRIX_ENV} to run native/abacuslite real parity")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        pytest.fail(f"{_MATRIX_ENV} must be a JSON array: {exc}")
    if not isinstance(value, list) or not value:
        pytest.fail(f"{_MATRIX_ENV} must be a non-empty JSON array")
    cases: list[dict[str, object]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            pytest.fail(f"{_MATRIX_ENV}[{index}] must be an object")
        required = {"capability", "version", "executable", "workspace"}
        missing = sorted(required - set(item))
        if missing:
            pytest.fail(f"{_MATRIX_ENV}[{index}] missing: {', '.join(missing)}")
        capability = item["capability"]
        version = item["version"]
        executable = item["executable"]
        workspace = item["workspace"]
        if capability not in _CAPABILITIES:
            pytest.fail(f"unsupported capability in matrix: {capability!r}")
        if not all(isinstance(value, str) and value.strip() for value in (version, executable, workspace)):
            pytest.fail(f"matrix case {index} requires non-empty string values")
        cases.append(item)
    if os.environ.get(_REQUIRE_FULL_MATRIX_ENV) == "1":
        _assert_release_matrix(cases)
    return cases


def _assert_release_matrix(cases: list[dict[str, object]]) -> None:
    """Require the release gate to name every track/capability cell.

    The ordinary developer harness intentionally accepts a smaller smoke list.
    A release job opts into this check and must additionally provide the
    provenance fields required by the SPEC; a single passing SCF case cannot
    satisfy the release matrix.
    """
    for index, case in enumerate(cases):
        missing = sorted(_RELEASE_REQUIRED_FIELDS - set(case))
        if missing:
            pytest.fail(
                f"release matrix case {index} missing provenance: {', '.join(missing)}"
            )
        if case["track"] not in _TRACKS:
            pytest.fail(f"release matrix case {index} has unsupported track: {case['track']!r}")
        if case["basis"] not in {"pw", "lcao"}:
            pytest.fail(f"release matrix case {index} has unsupported basis: {case['basis']!r}")
        nspin = case["nspin"]
        if not isinstance(nspin, int) or isinstance(nspin, bool) or nspin not in {1, 2, 4}:
            pytest.fail(f"release matrix case {index} requires nspin 1, 2, or 4")
        for field in ("executable_sha256", "input_identity"):
            if not isinstance(case[field], str) or not str(case[field]).strip():
                pytest.fail(f"release matrix case {index} requires non-empty {field}")
        if not _SHA256.fullmatch(str(case["executable_sha256"])):
            pytest.fail(f"release matrix case {index} requires a lowercase executable SHA-256")
    observed = {(str(case["track"]), str(case["capability"])) for case in cases}
    required = {(track, capability) for track in _TRACKS for capability in _CAPABILITIES}
    missing = sorted(required - observed)
    if missing:
        pytest.fail(
            f"release matrix is incomplete; missing track/capability cells: {missing}"
        )


def _shape(value: object) -> tuple[object, ...]:
    if isinstance(value, (list, tuple)):
        return (len(value), tuple(_shape(item) for item in value))
    if isinstance(value, dict):
        return (tuple(sorted(value)),)
    return ()


def _compare_value(native: object, optional: object, *, tolerance: float, name: str) -> None:
    """Compare JSON facts without flattening arrays or losing atom/frame shape."""
    if isinstance(native, (list, tuple)) or isinstance(optional, (list, tuple)):
        assert isinstance(native, (list, tuple)) and isinstance(optional, (list, tuple)), name
        assert _shape(native) == _shape(optional), name
        assert len(native) == len(optional), name
        for index, (left, right) in enumerate(zip(native, optional)):
            _compare_value(left, right, tolerance=tolerance, name=f"{name}[{index}]")
        return
    if isinstance(native, dict) or isinstance(optional, dict):
        assert isinstance(native, dict) and isinstance(optional, dict), name
        assert set(native) == set(optional), name
        for key in sorted(native):
            _compare_value(native[key], optional[key], tolerance=tolerance, name=f"{name}.{key}")
        return
    if isinstance(native, bool) or isinstance(optional, bool):
        assert native is optional, name
        return
    if isinstance(native, (int, float)) or isinstance(optional, (int, float)):
        assert isinstance(native, (int, float)) and isinstance(optional, (int, float)), name
        assert native == pytest.approx(optional, abs=tolerance), name
        return
    assert native == optional, name


def _metric_tolerance(name: str) -> float:
    lowered = name.lower()
    if "force" in lowered:
        return _FORCE_TOLERANCE_EV_PER_ANGSTROM
    if "stress" in lowered or lowered in {"pressure", "pressures", "virial", "virials"}:
        return _STRESS_TOLERANCE_KBAR
    return _ENERGY_TOLERANCE_EV


def _typed_envelope(capability: str, result: object, workspace_rel: str):
    if capability in {"relax", "cell-relax"}:
        return relax_results.collection_envelope(result, workspace_rel)
    if capability == "md":
        return md_results.collection_envelope(result, workspace_rel)
    return collection_results.collection_envelope(result, workspace_rel)


def _normalise_paths(value: object, root: Path) -> object:
    if isinstance(value, Mapping):
        return {key: _normalise_paths(item, root) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_normalise_paths(item, root) for item in value)
    if isinstance(value, str):
        try:
            path = Path(value)
            if path.is_absolute():
                return path.resolve().relative_to(root.resolve()).as_posix()
        except (OSError, RuntimeError, ValueError):
            pass
    return value


def _artifact_signature(envelope: object) -> dict[str, tuple[object, ...]]:
    return {
        artifact.path_rel: (
            artifact.role, artifact.stage, artifact.availability, artifact.media_type,
            artifact.sha256, artifact.size_bytes,
        )
        for artifact in envelope.artifacts
    }


def _metric_source_paths(envelope: object) -> dict[str, str | None]:
    paths = {artifact.id: artifact.path_rel for artifact in envelope.artifacts}
    return {
        metric.name: paths.get(metric.source_artifact_id) if metric.source_artifact_id else None
        for metric in envelope.metrics
    }


def _prepare_input_for_capability(root: Path, capability: str, case: Mapping[str, object]) -> None:
    """Reject accidental task/source mismatches; permit an explicit rewrite."""
    input_path = root / "inputs" / "INPUT"
    if not input_path.is_file():
        pytest.fail(f"dual-track source has no inputs/INPUT: {root}")
    actual = str(read_input(input_path).get("calculation", "")).strip().lower()
    if actual == capability:
        return
    target = case.get("input_calculation")
    if target != capability or case.get("rewrite_input_calculation") is not True:
        pytest.fail(
            f"matrix source calculation {actual!r} does not match capability {capability!r}; "
            "set input_calculation to the capability and rewrite_input_calculation=true "
            "to make the transformation explicit"
        )
    modify_input(input_path, updates={"calculation": capability}, destination=input_path)


def _assert_parity(native: object, optional: object, *, native_root: Path, optional_root: Path) -> None:
    assert native.status.to_dict() == optional.status.to_dict()
    native_metrics = {metric.name: metric for metric in native.metrics}
    optional_metrics = {metric.name: metric for metric in optional.metrics}
    assert set(native_metrics) == set(optional_metrics)
    assert _metric_source_paths(native) == _metric_source_paths(optional)
    for name in sorted(native_metrics):
        left = native_metrics[name]
        right = optional_metrics[name]
        assert left.unit == right.unit, name
        assert left.kind == right.kind, name
        _compare_value(left.value, right.value, tolerance=_metric_tolerance(name), name=name)
    assert _artifact_signature(native) == _artifact_signature(optional)
    native_checks = [(check.name, check.status, check.message) for check in native.checks]
    optional_checks = [(check.name, check.status, check.message) for check in optional.checks]
    assert native_checks == optional_checks
    assert tuple(native.warnings) == tuple(optional.warnings)
    native_diagnostics = dict(native.diagnostics)
    optional_diagnostics = dict(optional.diagnostics)
    native_parser = native_diagnostics.pop("parser", None)
    optional_parser = optional_diagnostics.pop("parser", None)
    for name in _BACKEND_SPECIFIC_DIAGNOSTICS:
        native_diagnostics.pop(name, None)
        optional_diagnostics.pop(name, None)
    # ``legacy_metrics`` repeats the typed metric values and is covered by the
    # metric comparison above (with field-specific tolerances).
    native_diagnostics.pop("legacy_metrics", None)
    optional_diagnostics.pop("legacy_metrics", None)
    assert _normalise_paths(native_diagnostics, native_root) == _normalise_paths(optional_diagnostics, optional_root)
    assert isinstance(native_parser, Mapping) and native_parser.get("actual_backend") == "native"
    assert isinstance(optional_parser, Mapping) and optional_parser.get("actual_backend") == "abacuslite"
    assert native_parser.get("log_source_rel") == optional_parser.get("log_source_rel")


@pytest.mark.real_smoke
def test_native_and_abacuslite_collect_real_output_parity(tmp_path: Path) -> None:
    """Execute each explicitly supplied producer once and collect two copies."""
    cases = _matrix()
    package_path = os.environ.get(_PACKAGE_ENV)
    if not package_path:
        pytest.fail(f"set {_PACKAGE_ENV} when {_MATRIX_ENV} is supplied")
    package_root = Path(package_path).expanduser().resolve()
    if not (package_root / "abacuslite").is_dir():
        pytest.fail(f"{_PACKAGE_ENV} must contain an abacuslite package: {package_root}")
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    library_path = os.environ.get(_LD_ENV)
    if library_path:
        os.environ["LD_LIBRARY_PATH"] = library_path + os.pathsep + os.environ.get("LD_LIBRARY_PATH", "")

    for index, case in enumerate(cases):
        capability = str(case["capability"])
        version = str(case["version"])
        executable = str(case["executable"])
        source = Path(str(case["workspace"])).expanduser().resolve()
        executable_path = Path(executable).expanduser()
        if not source.is_dir():
            pytest.fail(f"dual-track source is not a directory: {source}")
        if not executable_path.is_file() or not os.access(executable_path, os.X_OK):
            pytest.fail(f"dual-track executable is not executable: {executable_path}")

        native_root = tmp_path / f"{index}-{capability}-native"
        optional_root = tmp_path / f"{index}-{capability}-abacuslite"
        shutil.copytree(source, native_root, symlinks=False)
        _prepare_input_for_capability(native_root, capability, case)
        executed = execute_unit(UnitSpec(
            task=capability,
            unit="default",
            workdir=native_root,
            executable=str(executable_path),
        ))
        assert executed.returncode == 0, executed.stderr or executed.stdout
        shutil.copytree(native_root, optional_root, symlinks=False)

        native_result = collect_contained(native_root, parser_backend="native")
        optional = collect_contained(
            optional_root,
            parser_backend="abacuslite",
            output_version=version,
        )
        assert optional.diagnostics["parser"]["actual_backend"] == "abacuslite"
        native_envelope = _typed_envelope(capability, native_result, native_root.name)
        optional_envelope = _typed_envelope(capability, optional, optional_root.name)
        _assert_parity(
            native_envelope,
            optional_envelope,
            native_root=native_root,
            optional_root=optional_root,
        )
