from __future__ import annotations

import json
from pathlib import Path

import pytest

from abacus_forge import OperationOutcome, ScfCollectRequest, ScfServiceSet, collect
from abacus_forge.collection_results import collection_envelope
from abacus_forge.result import CollectionResult
from abacus_forge.workspace import Workspace
from tests.support.reference_workspaces import FIXTURE_ROOT, copy_abacustest_scf_workspace, copy_native_md_workspace


def test_collect_matches_abacustest_reference_for_force_stress_and_pressure(tmp_path: Path) -> None:
    reference = json.loads((FIXTURE_ROOT / "abacus.json").read_text(encoding="utf-8"))["output"][0]

    workspace = copy_abacustest_scf_workspace(tmp_path / "reference-case")

    result = collect(workspace)

    expected_force = [value for row in reference["force"] for value in row]
    expected_stress = [value for row in reference["stress"] for value in row]
    volume = 8.3004 * 8.3004 * 25.362243471279523
    kbar_to_ev_per_angstrom3 = 3.398927420868445e-6 * 27.211396132 / 0.52917721092**3
    expected_virial = [value * volume * kbar_to_ev_per_angstrom3 for value in expected_stress]

    assert result.status == "completed"
    assert result.diagnostics["selected_log_path"].endswith("running_scf.log")
    assert result.diagnostics["selected_log_reason"] == "matched-input-calculation:running_scf.log"
    assert any(path.endswith("out.log") for path in result.diagnostics["ignored_log_paths"])
    assert result.inputs_snapshot["KPT_PARSED"] == {"mode": "mesh", "mesh": [5, 5, 2], "shifts": [0, 0, 0]}
    assert len(result.metrics["force"]) == 81
    assert len(result.metrics["forces"]) == 1
    assert result.metrics["force"][0] == pytest.approx(expected_force[0])
    assert result.metrics["force"][len(result.metrics["force"]) // 2] == pytest.approx(expected_force[len(expected_force) // 2])
    assert result.metrics["force"][-1] == pytest.approx(expected_force[-1])
    assert result.metrics["stress"] == pytest.approx(expected_stress)
    assert len(result.metrics["stresses"]) == 1
    assert result.metrics["stresses"][0] == pytest.approx(expected_stress)
    assert result.metrics["pressure"] == pytest.approx(-48.548971477133335)
    assert result.metrics["pressures"] == pytest.approx([-48.548971477133335])
    assert result.metrics["virial"][0] == pytest.approx(expected_virial[0])
    assert result.metrics["virial"][len(result.metrics["virial"]) // 2] == pytest.approx(expected_virial[len(expected_virial) // 2])
    assert result.metrics["virial"][-1] == pytest.approx(expected_virial[-1])
    assert len(result.metrics["virials"]) == 1
    assert result.metrics["virials"][0] == pytest.approx(expected_virial)
    assert result.metrics["total_time"] == pytest.approx(932.927)


def test_collect_reads_repository_native_final_energy_marker(tmp_path: Path) -> None:
    workspace = copy_abacustest_scf_workspace(tmp_path / "native-final-energy")

    result = collect(workspace)

    assert result.metrics["total_energy"] == pytest.approx(-28364.4012275304485229)


def test_collect_recognizes_repository_native_scf_convergence_marker(tmp_path: Path) -> None:
    """ABACUS writes ``#SCF IS CONVERGED#`` in running_scf.log."""
    workspace = Workspace(tmp_path / "native-scf-convergence").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    workspace.write_text(
        "outputs/OUT.ABACUS/running_scf.log",
        "#SCF IS CONVERGED#\n"
        "#TOTAL ENERGY# -12.491608215 eV\n"
        "!FINAL_ETOT_IS -12.49160821520403 eV\n"
        "TOTAL  Time  : 1\n",
    )

    result = collect(workspace)

    assert result.status == "completed"
    assert result.metrics["converged"] is True
    assert result.metrics["converge"] is True
    assert result.diagnostics["matched_converged_markers"] == ["scf_is_converged"]


def test_collect_reads_native_abacus_fermi_energy_in_ev_column(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "native-fermi").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    workspace.write_text(
        "outputs/OUT.ABACUS/running_scf.log",
        "      Energy           Rydberg                 eV\n"
        " E_Fermi        -0.2928031394        -3.9837910886\n"
        " #SCF IS CONVERGED#\n",
    )

    result = collect(workspace)

    assert result.metrics["fermi_energy"] == pytest.approx(-3.9837910886)


def test_collect_sidecar_distinguishes_explicit_and_computed_energy_per_atom(tmp_path: Path) -> None:
    explicit = Workspace(tmp_path / "explicit").ensure_layout()
    explicit.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    explicit.write_text(
        "outputs/OUT.ABACUS/running_scf.log",
        "!FINAL_ETOT_IS -10.0 eV\nNATOM = 2\nENERGY PER ATOM = -5.25\n",
    )
    explicit_result = collect(explicit)
    explicit_log = str(explicit.outputs_dir / "OUT.ABACUS" / "running_scf.log")

    assert explicit_result.metric_origins["total_energy"] == explicit_log
    assert explicit_result.metric_origins["energy_per_atom"] == explicit_log
    assert "energy_per_atom" not in explicit_result.derived_metrics
    assert "_metric_origins" not in explicit_result.diagnostics
    assert "_derived_metrics" not in explicit_result.diagnostics

    computed = Workspace(tmp_path / "computed").ensure_layout()
    computed.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    computed.write_text(
        "outputs/OUT.ABACUS/running_scf.log",
        "!FINAL_ETOT_IS -10.0 eV\nNATOM = 2\n",
    )
    computed_result = collect(computed)
    computed_log = str(computed.outputs_dir / "OUT.ABACUS" / "running_scf.log")

    assert computed_result.metrics["energy_per_atom"] == pytest.approx(-5.0)
    assert computed_result.metric_origins["energy_per_atom"] == computed_log
    assert "energy_per_atom" in computed_result.derived_metrics


def test_collect_sidecar_marks_stress_pressure_as_derived(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "stress").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    workspace.write_text(
        "outputs/OUT.ABACUS/running_scf.log",
        "TOTAL ENERGY = -4.0\n"
        "TOTAL-STRESS (KBAR)\n"
        "1 2 3\n4 5 6\n7 8 9\n",
    )

    result = collect(workspace)

    log_path = str(workspace.outputs_dir / "OUT.ABACUS" / "running_scf.log")
    assert result.metric_origins["pressure"] == log_path
    assert "pressure" in result.derived_metrics


def test_collect_sidecar_tracks_output_fallback_and_time_json_override(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "fallback").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    workspace.write_text("outputs/out.log", "total 12.5\n")
    workspace.write_json("outputs/time.json", {"total": 34.5})

    result = collect(workspace)

    assert result.metrics["total_time"] == pytest.approx(34.5)
    assert result.metric_origins["total_time"] == str(workspace.outputs_dir / "time.json")
    assert result.diagnostics["output_log_path"] == str(workspace.outputs_dir / "out.log")
    assert result.diagnostics["time_json"] == str(workspace.outputs_dir / "time.json")


@pytest.mark.parametrize("payload", [{"total": None}, {}])
def test_collect_time_json_without_total_drops_stale_output_provenance(
    tmp_path: Path, payload: dict[str, object]
) -> None:
    workspace = Workspace(tmp_path / "invalid-time").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    workspace.write_text("outputs/out.log", "total 12.5\n")
    workspace.write_json("outputs/time.json", payload)

    result = collect(workspace)

    assert result.metrics["total_time"] is None
    assert "total_time" not in result.metric_origins
    envelope = collection_envelope(result, "invalid-time")
    metric = next(item for item in envelope.metrics if item.name == "total_time")
    assert metric.source_artifact_id is None
    assert metric.unit is None


def test_typed_scf_projection_reports_repository_native_final_energy(tmp_path: Path) -> None:
    workspace = copy_abacustest_scf_workspace(tmp_path / "typed-native-final-energy")
    request = ScfCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174118",
        workspace_rel="typed-native-final-energy",
    )

    result = ScfServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    assert any(
        metric.name == "total_energy" and metric.value == pytest.approx(-28364.4012275304485229)
        for metric in result.envelope.metrics
    )
    assert any(
        observation.name == "total_energy"
        and observation.value == pytest.approx(-28364.4012275304485229)
        for observation in result.observations
    )


def test_typed_scf_metrics_carry_units_kinds_and_contained_sources(tmp_path: Path) -> None:
    workspace = copy_abacustest_scf_workspace(tmp_path / "typed-metadata")
    running_log = workspace.outputs_dir / "OUT.ABACUS" / "running_scf.log"
    running_log.write_text(
        running_log.read_text(encoding="utf-8") + "\nNELEC = 244\nFERMI ENERGY = -1.5\n",
        encoding="utf-8",
    )
    request = ScfCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174121",
        workspace_rel="typed-metadata",
    )

    result = ScfServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    metrics = {metric.name: metric for metric in result.envelope.metrics}
    artifact_ids = {artifact.id for artifact in result.envelope.artifacts}
    assert metrics["total_energy"].unit == "eV"
    assert metrics["total_energy"].kind == "reported"
    assert metrics["total_energy"].source_artifact_id in artifact_ids
    assert metrics["pressure"].unit == "kbar"
    assert metrics["pressure"].kind == "derived"
    assert metrics["pressure"].source_artifact_id in artifact_ids
    assert metrics["total_time"].unit == "s"
    assert metrics["total_time"].source_artifact_id in artifact_ids
    assert metrics["natom"].unit == "atoms"
    assert metrics["nelec"].unit == "electrons"
    assert metrics["energy_per_atom"].unit == "eV/atom"
    assert metrics["energy_per_atom"].kind == "derived"
    assert metrics["energy_per_atom"].source_artifact_id == metrics["total_energy"].source_artifact_id
    assert metrics["fermi_energy"].unit is None
    assert metrics["fermi_energy"].kind == "reported"
    assert metrics["fermi_energy"].source_artifact_id in artifact_ids
    assert result.envelope.diagnostics["legacy_metrics"]["forces"]


def test_typed_scf_explicit_energy_per_atom_stays_reported_and_unitless(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "typed-explicit-energy-per-atom").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    workspace.write_text(
        "outputs/OUT.ABACUS/running_scf.log",
        "!FINAL_ETOT_IS -10.0 eV\nNATOM = 2\nENERGY PER ATOM = -5.25\n",
    )
    request = ScfCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174122",
        workspace_rel="typed-explicit-energy-per-atom",
    )

    result = ScfServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    metrics = {metric.name: metric for metric in result.envelope.metrics}
    assert metrics["energy_per_atom"].value == pytest.approx(-5.25)
    assert metrics["energy_per_atom"].unit is None
    assert metrics["energy_per_atom"].kind == "reported"
    assert metrics["energy_per_atom"].source_artifact_id is not None


def test_typed_scf_output_fallback_source_keeps_log_timing_unitless(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "typed-output-fallback").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    workspace.write_text("outputs/out.log", "total 12.5\n")
    request = ScfCollectRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174123",
        workspace_rel="typed-output-fallback",
    )

    result = ScfServiceSet.default(workspace_root=tmp_path).collect.collect(request)

    assert isinstance(result, OperationOutcome)
    metrics = {metric.name: metric for metric in result.envelope.metrics}
    assert metrics["total_time"].value == pytest.approx(12.5)
    assert metrics["total_time"].unit is None
    assert metrics["total_time"].source_artifact_id == next(
        artifact.id
        for artifact in result.envelope.artifacts
        if artifact.path_rel == "outputs/out.log"
    )


def test_typed_collection_omits_source_id_for_external_origin(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "typed-external-origin").ensure_layout()
    outside = tmp_path / "outside.log"
    outside.write_text("TOTAL ENERGY = -1.0\n", encoding="utf-8")
    result = CollectionResult(
        workspace.root,
        "completed",
        metrics={"total_energy": -1.0},
        artifacts={"outside": str(outside)},
        metric_origins={"total_energy": str(outside)},
    )

    envelope = collection_envelope(result, "typed-external-origin")

    metric = next(item for item in envelope.metrics if item.name == "total_energy")
    assert metric.source_artifact_id is None
    assert not envelope.artifacts


def test_typed_collection_omits_source_id_for_escaped_origin(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "typed-escaped-origin").ensure_layout()
    outside = tmp_path / "outside.log"
    outside.write_text("TOTAL ENERGY = -1.0\n", encoding="utf-8")
    escaped = workspace.outputs_dir / "alias.log"
    escaped.symlink_to(outside)
    result = CollectionResult(
        workspace.root,
        "completed",
        metrics={"total_energy": -1.0},
        artifacts={"outputs/alias.log": str(escaped)},
        metric_origins={"total_energy": str(escaped)},
    )

    envelope = collection_envelope(result, "typed-escaped-origin")

    metric = next(item for item in envelope.metrics if item.name == "total_energy")
    assert metric.source_artifact_id is None
    assert not envelope.artifacts


def test_collect_prefers_last_native_final_energy_marker(tmp_path: Path) -> None:
    workspace = copy_abacustest_scf_workspace(tmp_path / "native-final-energy")
    path = workspace.outputs_dir / "OUT.ABACUS" / "running_scf.log"
    path.write_text(path.read_text(encoding="utf-8") +
                    "!FINAL_ETOT_IS -10.25 eV\n!FINAL_ETOT_IS -9.75 eV\n",
                    encoding="utf-8")

    result = collect(workspace)

    assert result.metrics["total_energy"] == pytest.approx(-9.75)


def test_collect_parses_native_md_rows_and_keeps_energy_families_separate(tmp_path: Path) -> None:
    result = collect(copy_native_md_workspace(tmp_path / "native-md"))
    factor = 13.605698

    assert result.metrics["total_energy"] == pytest.approx(-129.256631)
    assert result.metrics["md_last_total_energy"] == pytest.approx(-9.5 * factor)
    assert result.metrics["md_last_potential_energy"] == pytest.approx(-10.0 * factor)
    assert result.metrics["md_last_kinetic_energy"] == pytest.approx(0.5 * factor)
    assert result.metrics["md_last_temperature"] == pytest.approx(310.0)
    assert result.metrics["md_last_pressure"] == pytest.approx(3.0)
    assert result.metrics["md_dump_frames"] == 2
    assert result.metrics["md_dump_steps"] == 2
    assert result.diagnostics["native_md_block_complete"] is True


def test_collect_accepts_native_md_header_without_units(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "native-md-no-units").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation md\n")
    workspace.write_text(
        "outputs/OUT.ABACUS/running_md.log",
        "Energy              Potential           Kinetic             Temperature         Pressure (KBAR)\n"
        "-1.0                -1.2                0.2                 300                 4.0\n",
    )
    result = collect(workspace)
    assert result.metrics["md_last_total_energy"] == pytest.approx(-13.605698)
    assert result.metrics["md_last_pressure"] == pytest.approx(4.0)
    assert result.diagnostics["native_md_block_complete"] is True


def test_collect_extracts_native_abacus_and_md_metrics(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "native-metrics").ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation md\n")
    workspace.write_text("inputs/KPT", "K_POINTS\n0\nGamma\n1 1 1 0 0 0\n")
    workspace.write_text(
        "outputs/stdout.log",
        "\n".join(
            [
                "ABACUS VERSION: 3.8.0",
                "TOTAL ENERGY = -6.0",
                "NATOM = 2",
                "NELEC = 8",
                "VOLUME = 20.0",
                "RELAX STEPS = 4",
                "LARGEST GRADIENT = 0.001",
                "DRHO_LAST = 1e-8",
                "SCF CONVERGED",
                "NORMAL END",
            ]
        )
        + "\n",
    )
    workspace.write_text("outputs/stderr.log", "")
    workspace.write_text("outputs/MD_dump", "STEP 1 TEMP 300 ETOT -5.9\nSTEP 2 TEMP 305 ETOT -6.0\n")

    result = collect(workspace)

    assert result.metrics["version"] == "3.8.0"
    assert result.metrics["natom"] == 2
    assert result.metrics["nelec"] == 8
    assert result.metrics["volume"] == 20.0
    assert result.metrics["energy_per_atom"] == -3.0
    assert result.metrics["relax_steps"] == 4
    assert result.metrics["largest_gradient"] == pytest.approx(0.001)
    assert result.metrics["drho_last"] == pytest.approx(1e-8)
    assert result.metrics["normal_end"] is True
    assert result.metrics["converge"] is True
    assert result.metrics["md_steps"] == 2
    assert result.metrics["md_last_temperature"] == 305
