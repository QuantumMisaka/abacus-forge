"""Stage 0 parity checks against the canonical ABACUS abacuslite fixtures.

These checks deliberately run only when ``--run-benchmark`` is requested and
the caller provides ``ABACUS_FORGE_CANONICAL_ABACUSLITE``.  The environment
variable points at the checkout directory that contains the canonical
``abacuslite`` package (normally ``interfaces/ASE_interface`` in
``abacus-develop``).
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor
import stat
from typing import Any

import pytest

from abacus_forge.collection import collect_contained
from abacus_forge.contracts import OperationOutcome, ScfCollectRequest
from abacus_forge.services import ScfServiceSet
from abacus_forge.workspace import Workspace


_CANONICAL_ENV = "ABACUS_FORGE_CANONICAL_ABACUSLITE"
_KBAR_TO_CANONICAL_STRESS = 0.0006241504912713559


@pytest.fixture(scope="module")
def canonical_root() -> Path:
    raw = os.environ.get(_CANONICAL_ENV)
    if not raw:
        pytest.skip(f"set {_CANONICAL_ENV} to run canonical abacuslite parity")
    root = Path(raw).expanduser().resolve()
    if not (root / "abacuslite").is_dir():
        pytest.skip(f"{_CANONICAL_ENV} must contain an abacuslite package: {root}")
    return root


def _canonical_module(root: Path, backend: str) -> Any:
    # The adapter itself performs delayed imports.  Prepending the canonical
    # checkout here makes the direct oracle and Forge select the same package
    # even when a different optional installation is present in the venv.
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    importlib.invalidate_caches()
    module_name = f"abacuslite.io.{backend}"
    return importlib.import_module(module_name)


def _direct_oracle(module: Any, log_path: Path) -> dict[str, Any]:
    energies = module.read_energies_from_running_log(log_path)
    if isinstance(energies, tuple):
        energy_frames = energies[-1]
    else:
        energy_frames = energies
    assert energy_frames
    final_energy = energy_frames[-1]
    total_key = next(
        key
        for key in ("E_KS(sigma->0)", "E_KohnSham", "total_energy", "energy")
        if key in final_energy
    )
    fermi = final_energy.get("E_Fermi")

    forces = module.read_forces_from_running_log(log_path)
    stresses = module.read_stress_from_running_log(log_path)

    def flatten(value: Any) -> list[float]:
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, (list, tuple)):
            output: list[float] = []
            for item in value:
                output.extend(flatten(item))
            return output
        return [float(value)]

    return {
        "total_energy": float(final_energy[total_key]),
        "fermi_energy": None if fermi is None else float(fermi),
        "forces": [flatten(frame) for frame in forces],
        # Canonical readers return ASE stress in eV/A^3.  Forge exposes the
        # ABACUS kbar convention, including the historical sign inversion.
        "stresses": [
            [-item / _KBAR_TO_CANONICAL_STRESS for item in flatten(frame)]
            for frame in stresses
        ],
    }


def _fixture_workspace(
    tmp_path: Path,
    fixture_path: Path,
    capability: str,
    version: str,
    *,
    include_input: bool = True,
    content_transform: Any | None = None,
) -> Workspace:
    workspace = Workspace(tmp_path / f"{capability}-{version}").ensure_layout()
    content = fixture_path.read_text(encoding="utf-8")
    # The canonical files intentionally omit a producer-version banner.  The
    # banner is the version-selection input for Forge and does not affect any
    # canonical reader's format parsing.
    content = f"ABACUS VERSION: {version}\n{content}"
    if content_transform is not None:
        content = content_transform(content)
    workspace.write_text(f"outputs/running_{capability}.log", content)
    if include_input:
        workspace.write_text(
            "inputs/INPUT",
            "INPUT_PARAMETERS\n"
            f"calculation {capability}\n"
            "suffix ABACUS\n",
        )
    return workspace


def _assert_frames_close(actual: Any, expected: list[list[float]]) -> None:
    assert len(actual) == len(expected)
    for actual_frame, expected_frame in zip(actual, expected):
        assert actual_frame == pytest.approx(expected_frame)


@pytest.mark.benchmark
@pytest.mark.parametrize(
    ("capability", "version", "backend", "fixture"),
    [
        ("scf", "v3.10.1", "legacyio", "lcao-symm1-nspin1-multik-scf_"),
        ("scf", "v3.11.0-beta8+56", "latestio", "lcao-symm1-nspin1-multik-scf"),
        ("relax", "v3.10.1", "legacyio", "lcao-symm0-nspin2-multik-relax_"),
        ("relax", "v3.11.0-beta8+56", "latestio", "lcao-symm0-nspin2-multik-relax"),
        ("cell-relax", "v3.10.1", "legacyio", "lcao-symm0-nspin2-multik-cellrelax_"),
        ("cell-relax", "v3.11.0-beta8+56", "latestio", "lcao-symm0-nspin2-multik-cellrelax"),
        ("md", "v3.10.1", "legacyio", "pw-symm0-nspin4-gamma-md_"),
        ("md", "v3.11.0-beta8+56", "latestio", "pw-symm0-nspin4-gamma-md"),
    ],
)
def test_forge_matches_canonical_abacuslite_for_four_capabilities(
    tmp_path: Path,
    canonical_root: Path,
    capability: str,
    version: str,
    backend: str,
    fixture: str,
) -> None:
    module = _canonical_module(canonical_root, backend)
    fixture_path = canonical_root / "abacuslite" / "io" / "testfiles" / fixture
    workspace = _fixture_workspace(tmp_path, fixture_path, capability, version)
    log_path = workspace.outputs_dir / f"running_{capability}.log"

    expected = _direct_oracle(module, log_path)
    result = collect_contained(
        workspace,
        parser_backend="abacuslite",
        output_version=version,
    )

    assert result.diagnostics["parser"]["actual_backend"] == "abacuslite"
    assert result.diagnostics["parser"]["io_backend"] == backend
    assert result.diagnostics["parser"]["output_version_normalized"] == version
    assert result.metrics["total_energy"] == pytest.approx(expected["total_energy"])
    if expected["fermi_energy"] is not None:
        assert result.metrics["fermi_energy"] == pytest.approx(expected["fermi_energy"])

    if expected["forces"]:
        _assert_frames_close(result.metrics["forces"], expected["forces"])
        assert result.metrics["force"] == pytest.approx(expected["forces"][-1])
    else:
        assert "force" not in result.metrics
        assert "forces" not in result.metrics

    if expected["stresses"]:
        _assert_frames_close(result.metrics["stresses"], expected["stresses"])
        assert result.metrics["stress"] == pytest.approx(expected["stresses"][-1])
    else:
        assert "stress" not in result.metrics
        assert "stresses" not in result.metrics


@pytest.mark.benchmark
def test_alternate_versions_share_one_process_without_cross_contamination(
    tmp_path: Path,
    canonical_root: Path,
) -> None:
    fixture_dir = canonical_root / "abacuslite" / "io" / "testfiles"
    cases = [
        ("v3.10.1", "legacyio", "lcao-symm0-nspin2-multik-relax_"),
        ("v3.11.0-beta8+56", "latestio", "lcao-symm0-nspin2-multik-relax"),
    ]
    observed: list[tuple[str, str, float]] = []
    for index, (version, backend, fixture) in enumerate(cases):
        workspace = _fixture_workspace(
            tmp_path / str(index), fixture_dir / fixture, "relax", version
        )
        log_path = workspace.outputs_dir / "running_relax.log"
        expected = _direct_oracle(_canonical_module(canonical_root, backend), log_path)
        result = collect_contained(
            workspace,
            parser_backend="abacuslite",
            output_version=version,
        )
        observed.append((backend, result.diagnostics["parser"]["io_backend"], float(result.metrics["total_energy"])))
        assert result.metrics["total_energy"] == pytest.approx(expected["total_energy"])
    assert [(item[0], item[1]) for item in observed] == [
        ("legacyio", "legacyio"),
        ("latestio", "latestio"),
    ]
    # The fixtures represent different producer generations and therefore may
    # have different final energies.  The invariant is that each invocation
    # used its requested IO module in the same process.
    assert observed[0][2] != observed[1][2]


@pytest.mark.benchmark
def test_output_only_collect_without_auxiliary_files_matches_canonical(
    tmp_path: Path,
    canonical_root: Path,
) -> None:
    backend = "latestio"
    version = "v3.11.0-beta8+56"
    fixture = canonical_root / "abacuslite" / "io" / "testfiles" / "lcao-symm1-nspin1-multik-scf"
    workspace = _fixture_workspace(tmp_path, fixture, "scf", version, include_input=False)
    log_path = workspace.outputs_dir / "running_scf.log"
    expected = _direct_oracle(_canonical_module(canonical_root, backend), log_path)

    # This is intentionally an output-only workspace: the lower-level
    # readers must not require INPUT, eig_occ.txt, or MD_dump.
    assert not (workspace.inputs_dir / "INPUT").exists()
    assert not (workspace.outputs_dir / "eig_occ.txt").exists()
    assert not (workspace.outputs_dir / "MD_dump").exists()
    result = collect_contained(workspace, parser_backend="abacuslite", output_version=version)

    assert result.metrics["total_energy"] == pytest.approx(expected["total_energy"])
    assert result.diagnostics["parser"]["version_source"] == "log"
    assert result.diagnostics["parser"]["log_source_rel"] == "outputs/running_scf.log"


@pytest.mark.benchmark
def test_truncated_log_keeps_confirmed_backend_facts_without_fallback(
    tmp_path: Path,
    canonical_root: Path,
) -> None:
    version = "v3.11.0-beta8+56"
    fixture = canonical_root / "abacuslite" / "io" / "testfiles" / "lcao-symm0-nspin2-multik-relax"

    def truncate(content: str) -> str:
        marker = "#TOTAL-FORCE"
        cut = content.rfind(marker)
        assert cut > 0
        return content[:cut]

    workspace = _fixture_workspace(
        tmp_path,
        fixture,
        "relax",
        version,
        content_transform=truncate,
    )
    log_path = workspace.outputs_dir / "running_relax.log"
    expected = _direct_oracle(_canonical_module(canonical_root, "latestio"), log_path)
    result = collect_contained(workspace, parser_backend="abacuslite", output_version=version)

    assert result.metrics["total_energy"] == pytest.approx(expected["total_energy"])
    if expected["forces"]:
        _assert_frames_close(result.metrics["forces"], expected["forces"])
    else:
        assert "forces" not in result.metrics
    assert result.diagnostics["parser"]["actual_backend"] == "abacuslite"


@pytest.mark.benchmark
def test_nonconverged_log_retains_numeric_parity_and_partial_status(
    tmp_path: Path,
    canonical_root: Path,
) -> None:
    version = "v3.11.0-beta8+56"
    fixture = canonical_root / "abacuslite" / "io" / "testfiles" / "lcao-symm0-nspin2-multik-relax"
    workspace = _fixture_workspace(
        tmp_path,
        fixture,
        "relax",
        version,
        content_transform=lambda content: content + "\nSCF NOT CONVERGED\n",
    )
    log_path = workspace.outputs_dir / "running_relax.log"
    expected = _direct_oracle(_canonical_module(canonical_root, "latestio"), log_path)
    result = collect_contained(workspace, parser_backend="abacuslite", output_version=version)

    assert result.status == "unfinished"
    assert result.metrics["converged"] is False
    assert result.metrics["total_energy"] == pytest.approx(expected["total_energy"])
    _assert_frames_close(result.metrics["forces"], expected["forces"])


@pytest.mark.benchmark
def test_ambiguous_and_outside_logs_do_not_dispatch_optional_backend(
    tmp_path: Path,
    canonical_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus_forge import collection

    version = "v3.11.0-beta8+56"
    _canonical_module(canonical_root, "latestio")
    calls: list[Path] = []
    original = collection.parse_abacuslite

    def record_dispatch(path: Path, **kwargs: Any) -> dict[str, Any]:
        calls.append(path)
        return original(path, **kwargs)

    monkeypatch.setattr(collection, "parse_abacuslite", record_dispatch)

    ambiguous = Workspace(tmp_path / "ambiguous").ensure_layout()
    ambiguous.write_text("outputs/running_scf.log", "ABACUS VERSION: v3.11.0-beta8+56\nTOTAL ENERGY = -1\n")
    ambiguous.write_text("outputs/running_relax.log", "ABACUS VERSION: v3.11.0-beta8+56\nTOTAL ENERGY = -2\n")
    ambiguous_result = collect_contained(
        ambiguous, parser_backend="abacuslite", output_version=version
    )
    assert ambiguous_result.status in {"missing-output", "unfinished"}
    assert ambiguous_result.diagnostics["log_selection_ambiguous"] is True
    assert ambiguous_result.diagnostics["parser"]["actual_backend"] is None
    assert "total_energy" not in ambiguous_result.metrics

    outside = tmp_path / "outside-running.log"
    outside.write_text("ABACUS VERSION: v3.11.0-beta8+56\nTOTAL ENERGY = -3\n", encoding="utf-8")
    contained = Workspace(tmp_path / "outside-alias").ensure_layout()
    (contained.outputs_dir / "running_scf.log").symlink_to(outside)
    contained_result = collect_contained(contained, parser_backend="abacuslite", output_version=version)
    assert contained_result.status in {"missing-output", "unfinished"}
    assert contained_result.diagnostics["parser"]["actual_backend"] is None
    assert contained_result.diagnostics["parser"]["log_source_rel"] is None
    assert calls == []


@pytest.mark.benchmark
def test_two_workspaces_can_collect_concurrently_with_version_isolation(
    tmp_path: Path,
    canonical_root: Path,
) -> None:
    cases = [
        ("v3.10.1", "legacyio", "lcao-symm0-nspin2-multik-relax_"),
        ("v3.11.0-beta8+56", "latestio", "lcao-symm0-nspin2-multik-relax"),
    ]
    fixture_dir = canonical_root / "abacuslite" / "io" / "testfiles"
    _canonical_module(canonical_root, "legacyio")
    _canonical_module(canonical_root, "latestio")

    def collect_one(index: int, version: str, backend: str, fixture: str) -> tuple[str, str, float]:
        workspace = _fixture_workspace(tmp_path / str(index), fixture_dir / fixture, "relax", version)
        result = collect_contained(workspace, parser_backend="abacuslite", output_version=version)
        return backend, result.diagnostics["parser"]["io_backend"], float(result.metrics["total_energy"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        observed = list(pool.map(lambda item: collect_one(*item), [(0, *cases[0]), (1, *cases[1])]))
    assert [(row[0], row[1]) for row in observed] == [
        ("legacyio", "legacyio"),
        ("latestio", "latestio"),
    ]


@pytest.mark.benchmark
def test_read_only_domain_files_and_append_only_audit_are_preserved(
    tmp_path: Path,
    canonical_root: Path,
) -> None:
    version = "v3.11.0-beta8+56"
    fixture = canonical_root / "abacuslite" / "io" / "testfiles" / "lcao-symm1-nspin1-multik-scf"
    workspace = _fixture_workspace(tmp_path, fixture, "scf", version)
    domain_paths = [workspace.inputs_dir / "INPUT", workspace.outputs_dir / "running_scf.log"]
    for path in domain_paths:
        path.chmod(0o444)
    before = {
        path.relative_to(workspace.root).as_posix(): (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        for path in domain_paths
    }

    service = ScfServiceSet.default(
        workspace_root=tmp_path,
        parser_backend="abacuslite",
        output_version=version,
    )
    requests = [
        ScfCollectRequest(
            operation_id="123e4567-e89b-42d3-a456-426614174920",
            workspace_rel=workspace.root.relative_to(tmp_path).as_posix(),
        ),
        ScfCollectRequest(
            operation_id="123e4567-e89b-42d3-a456-426614174921",
            workspace_rel=workspace.root.relative_to(tmp_path).as_posix(),
        ),
    ]
    outcomes = [service.collect.collect(request) for request in requests]
    assert all(isinstance(outcome, OperationOutcome) for outcome in outcomes)
    for path in domain_paths:
        relative = path.relative_to(workspace.root).as_posix()
        assert (path.read_bytes(), stat.S_IMODE(path.stat().st_mode)) == before[relative]

    event_paths = sorted((workspace.reports_dir / "events").glob("*.json"))
    assert len(event_paths) == 2
    manifest = json.loads((workspace.reports_dir / "forge-workspace.json").read_text(encoding="utf-8"))
    assert len(manifest["events"]) == 2
