from __future__ import annotations

import hashlib
import json
import os
import stat
import uuid
from pathlib import Path

import pytest

from abacus_forge import (
    ForgeErrorEnvelope,
    ForgeResultEnvelope,
    PyatbBandCollectRequest,
    PyatbBandExecuteRequest,
    PyatbBandPrepareRequest,
    PyatbBandServiceSet,
    Workspace,
)
from abacus_forge.contracts import OperationOutcome
from abacus_forge.errors import ForgePathError, ForgePreconditionError, ForgeRequestError
from abacus_forge.pyatb import (
    collect_typed_pyatb_band,
    prepare_typed_pyatb_band,
)


STRU = """ATOMIC_SPECIES
Si 28.0855 Si.upf

LATTICE_CONSTANT
1.0
LATTICE_CONSTANT_UNIT
Angstrom

LATTICE_VECTORS
3.0 0.0 0.0
0.0 3.0 0.0
0.0 0.0 3.0

ATOMIC_POSITIONS
Direct
Si
0.0
1
0.0 0.0 0.0 1 1 1
"""


def _id() -> str:
    return str(uuid.uuid4())


def _prepare_request(**updates: object) -> PyatbBandPrepareRequest:
    values: dict[str, object] = {
        "operation_id": _id(),
        "workspace_rel": ".",
        "structure_path_rel": "source/STRU",
        "hr_paths_rel": ("source/hr.csr",),
        "sr_path_rel": "source/sr.csr",
        "rr_path_rel": "source/rr.csr",
        "fermi_energy": 4.25,
        "line_kpoints": (
            {"coords": [0.0, 0.0, 0.0], "label": "G"},
            {"coords": [0.5, 0.0, 0.0], "label": "X"},
        ),
    }
    values.update(updates)
    return PyatbBandPrepareRequest(**values)


def _sources(root: Path, *, spin2: bool = False) -> None:
    source = root / "source"
    source.mkdir(parents=True, exist_ok=True)
    (source / "STRU").write_text(STRU, encoding="utf-8")
    (source / "hr.csr").write_text("hr0", encoding="utf-8")
    if spin2:
        (source / "hr-down.csr").write_text("hr1", encoding="utf-8")
    (source / "sr.csr").write_text("sr", encoding="utf-8")
    (source / "rr.csr").write_text("rr", encoding="utf-8")


def test_typed_prepare_link_mode_is_relative_and_records_provenance(tmp_path: Path) -> None:
    _sources(tmp_path)
    request = _prepare_request()

    workspace, handoff = prepare_typed_pyatb_band(Workspace(tmp_path), request)

    assert workspace.root == tmp_path
    assert (tmp_path / "inputs/STRU").is_symlink()
    assert not Path(os.readlink(tmp_path / "inputs/STRU")).is_absolute()
    assert (tmp_path / "inputs/pyatb_sources/hr.csr").is_symlink()
    assert Path(os.readlink(tmp_path / "inputs/pyatb_sources/hr.csr")).is_absolute() is False
    assert [record["role"] for record in handoff] == ["structure", "hr", "sr", "rR"]
    for record in handoff:
        assert record["mode"] == "link"
        assert record["source_sha256"] == record["destination_sha256"]
        source = tmp_path / str(record["source"])
        assert record["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
        assert (tmp_path / str(record["destination"])).exists()


def test_typed_prepare_copy_mode_materializes_independent_files(tmp_path: Path) -> None:
    _sources(tmp_path)
    request = _prepare_request(handoff_mode="copy")

    _, handoff = prepare_typed_pyatb_band(tmp_path, request)

    assert all(record["mode"] == "copy" for record in handoff)
    for record in handoff:
        destination = tmp_path / str(record["destination"])
        assert destination.is_file()
        assert not destination.is_symlink()
        assert record["source_sha256"] == record["destination_sha256"]


def test_typed_prepare_renders_explicit_routes_lattice_and_kpt(tmp_path: Path) -> None:
    _sources(tmp_path)

    prepare_typed_pyatb_band(tmp_path, _prepare_request(line_segments=12, max_kpoint_num=77))

    input_text = (tmp_path / "inputs/Input").read_text(encoding="utf-8")
    kpt_text = (tmp_path / "inputs/KPT_band").read_text(encoding="utf-8")
    assert "nspin  1" in input_text
    assert "package  ABACUS" in input_text
    assert "fermi_energy  4.25" in input_text
    assert "fermi_energy_unit  eV" in input_text
    assert "HR_route  pyatb_sources/hr.csr" in input_text
    assert "SR_route  pyatb_sources/sr.csr" in input_text
    assert "rR_route  pyatb_sources/rr.csr" in input_text
    assert "HR_unit  Ry" in input_text
    assert "rR_unit  Bohr" in input_text
    assert "max_kpoint_num  77" in input_text
    assert "lattice_constant_unit  Angstrom" in input_text
    assert "3.000000000000  0.000000000000  0.000000000000" in input_text
    assert "kpoint_mode  line" in input_text
    assert "kpoint_num  2" in input_text
    assert "kpoint_label  G,X" in input_text
    assert "K_POINTS\n2\nLine" in kpt_text
    assert "0.00000000 0.00000000 0.00000000 12 #G" in kpt_text
    assert "0.50000000 0.00000000 0.00000000 1 #X" in kpt_text


def test_typed_prepare_spin_two_has_two_hr_routes_and_shared_sr(tmp_path: Path) -> None:
    _sources(tmp_path, spin2=True)
    request = _prepare_request(
        nspin=2,
        hr_paths_rel=("source/hr.csr", "source/hr-down.csr"),
    )

    prepare_typed_pyatb_band(tmp_path, request)

    input_text = (tmp_path / "inputs/Input").read_text(encoding="utf-8")
    assert "nspin  2" in input_text
    assert "HR_route  pyatb_sources/hr.csr pyatb_sources/hr-down.csr" in input_text
    assert "SR_route  pyatb_sources/sr.csr" in input_text
    assert input_text.count("SR_route") == 1


def test_typed_prepare_rejects_external_source_before_any_staging(tmp_path: Path) -> None:
    _sources(tmp_path)
    external = tmp_path.parent / "external-hr.csr"
    external.write_text("outside", encoding="utf-8")
    (tmp_path / "source/hr.csr").unlink()
    (tmp_path / "source/hr.csr").symlink_to(external)

    with pytest.raises(ForgePathError):
        prepare_typed_pyatb_band(tmp_path, _prepare_request())

    assert not (tmp_path / "inputs").exists()


def test_typed_prepare_rejects_missing_source_without_partial_write(tmp_path: Path) -> None:
    _sources(tmp_path)
    (tmp_path / "source/sr.csr").unlink()

    with pytest.raises(ForgePreconditionError):
        prepare_typed_pyatb_band(tmp_path, _prepare_request())

    assert not (tmp_path / "inputs").exists()


def test_typed_prepare_rejects_duplicate_matrix_basename_without_partial_write(tmp_path: Path) -> None:
    _sources(tmp_path)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a/shared.csr").write_text("a", encoding="utf-8")
    (tmp_path / "b/shared.csr").write_text("b", encoding="utf-8")
    request = _prepare_request(hr_paths_rel=("a/shared.csr", "b/shared.csr"), nspin=2)

    with pytest.raises(ForgeRequestError):
        prepare_typed_pyatb_band(tmp_path, request)

    assert not (tmp_path / "inputs").exists()


def test_typed_prepare_rejects_existing_conflict_without_overwriting_or_partial_write(tmp_path: Path) -> None:
    _sources(tmp_path)
    destination = tmp_path / "inputs/pyatb_sources"
    destination.mkdir(parents=True)
    (destination / "hr.csr").write_text("keep", encoding="utf-8")

    with pytest.raises(ForgeRequestError):
        prepare_typed_pyatb_band(tmp_path, _prepare_request())

    assert not (tmp_path / "inputs/STRU").exists()
    assert (destination / "hr.csr").read_text(encoding="utf-8") == "keep"


def test_typed_prepare_retains_an_exact_existing_source_destination(tmp_path: Path) -> None:
    _sources(tmp_path)
    (tmp_path / "inputs/pyatb_sources").mkdir(parents=True)
    (tmp_path / "inputs/pyatb_sources/hr.csr").symlink_to(
        Path("../../source/hr.csr")
    )
    request = _prepare_request()

    _, handoff = prepare_typed_pyatb_band(tmp_path, request)

    assert (tmp_path / "inputs/pyatb_sources/hr.csr").is_symlink()
    assert Path(os.readlink(tmp_path / "inputs/pyatb_sources/hr.csr")).is_absolute() is False
    hr_record = next(record for record in handoff if record["role"] == "hr")
    assert hr_record["mode"] == "link"
    assert hr_record["source_sha256"] == hr_record["destination_sha256"]


def test_typed_prepare_link_alias_records_lexical_destination_without_replacing_alias(tmp_path: Path) -> None:
    _sources(tmp_path)
    destination = tmp_path / "inputs/pyatb_sources"
    destination.mkdir(parents=True)
    alias = destination / "hr.csr"
    alias.symlink_to(Path("../../source/hr.csr"))
    original_target = os.readlink(alias)

    _, handoff = prepare_typed_pyatb_band(tmp_path, _prepare_request())

    hr_record = next(record for record in handoff if record["role"] == "hr")
    assert hr_record["destination"] == "inputs/pyatb_sources/hr.csr"
    assert os.readlink(alias) == original_target


@pytest.mark.parametrize("handoff_mode", ("link", "copy"))
def test_typed_prepare_rejects_directory_alias_without_partial_write(
    tmp_path: Path, handoff_mode: str
) -> None:
    _sources(tmp_path)
    (tmp_path / "matrix-store").mkdir()
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "pyatb_sources").symlink_to(Path("../matrix-store"), target_is_directory=True)

    with pytest.raises(ForgeRequestError):
        prepare_typed_pyatb_band(
            tmp_path, _prepare_request(handoff_mode=handoff_mode)
        )

    staging_parent = inputs / "pyatb_sources"
    assert staging_parent.is_symlink()
    assert os.readlink(staging_parent) == "../matrix-store"
    assert not (tmp_path / "matrix-store/hr.csr").exists()
    assert not (tmp_path / "inputs/STRU").exists()
    assert not (tmp_path / "inputs/Input").exists()
    assert not (tmp_path / "inputs/KPT_band").exists()


def test_typed_prepare_copy_rejects_exact_symlink_alias_without_mutation(tmp_path: Path) -> None:
    _sources(tmp_path)
    destination = tmp_path / "inputs/pyatb_sources"
    destination.mkdir(parents=True)
    alias = destination / "hr.csr"
    alias.symlink_to(Path("../../source/hr.csr"))
    original_target = os.readlink(alias)

    with pytest.raises(ForgeRequestError):
        prepare_typed_pyatb_band(tmp_path, _prepare_request(handoff_mode="copy"))

    assert alias.is_symlink()
    assert os.readlink(alias) == original_target
    assert sorted(path.name for path in destination.iterdir()) == ["hr.csr"]
    assert not (tmp_path / "inputs/STRU").exists()
    assert not (tmp_path / "inputs/Input").exists()
    assert not (tmp_path / "inputs/KPT_band").exists()


@pytest.mark.parametrize(
    "unsafe_basename",
    ("bad name.csr", "bad,name.csr", "bad{name}.csr", "bad#name.csr", "bad\nname.csr"),
)
def test_typed_prepare_rejects_unsafe_matrix_token_before_writes(
    tmp_path: Path, unsafe_basename: str
) -> None:
    _sources(tmp_path)
    source = tmp_path / "source" / unsafe_basename
    source.write_text("unsafe", encoding="utf-8")

    with pytest.raises(ForgeRequestError):
        prepare_typed_pyatb_band(
            tmp_path,
            _prepare_request(hr_paths_rel=(f"source/{unsafe_basename}",)),
        )

    assert not (tmp_path / "inputs").exists()


@pytest.mark.parametrize(
    "unsafe_label",
    ("K 1", "K,1", "K{1}", "K#1", "K\n1", "K//1"),
)
def test_typed_prepare_rejects_unsafe_line_label_before_writes(
    tmp_path: Path, unsafe_label: str
) -> None:
    _sources(tmp_path)
    line_kpoints = (
        {"coords": [0.0, 0.0, 0.0], "label": unsafe_label},
        {"coords": [0.5, 0.0, 0.0], "label": "X"},
    )

    with pytest.raises(ForgeRequestError):
        prepare_typed_pyatb_band(
            tmp_path,
            _prepare_request(line_kpoints=line_kpoints),
        )

    assert not (tmp_path / "inputs").exists()


def test_typed_prepare_rejects_malformed_stru_without_partial_write(tmp_path: Path) -> None:
    _sources(tmp_path)
    (tmp_path / "source/STRU").write_text("not a STRU", encoding="utf-8")

    with pytest.raises((ForgeRequestError, ValueError)):
        prepare_typed_pyatb_band(tmp_path, _prepare_request())

    assert not (tmp_path / "inputs").exists()


def test_typed_prepare_does_not_consult_legacy_scf_collection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _sources(tmp_path)
    (tmp_path / "outputs").mkdir()
    (tmp_path / "outputs/stdout.log").write_text("FERMI ENERGY = 99.0\n", encoding="utf-8")

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("typed PyATB preparation must not collect SCF output")

    monkeypatch.setattr("abacus_forge.pyatb.collect", fail_if_called)
    prepare_typed_pyatb_band(tmp_path, _prepare_request())

    assert "fermi_energy  4.25" in (tmp_path / "inputs/Input").read_text(encoding="utf-8")


def _write_band_outputs(workspace: Path, *, info: str = "Band gap is 1.25 eV\n", data: bool = True, picture: bool = True) -> None:
    output = workspace / "inputs/Out/Band_Structure"
    output.mkdir(parents=True, exist_ok=True)
    (output / "band_info.dat").write_text(info, encoding="utf-8")
    if data:
        (output / "band.dat").write_text("band data", encoding="utf-8")
    if picture:
        (output / "band.png").write_bytes(b"image")


def test_typed_collect_records_explicit_outputs_and_reported_parser_fact(tmp_path: Path) -> None:
    _write_band_outputs(tmp_path)
    request = PyatbBandCollectRequest(
        operation_id=_id(),
        workspace_rel=".",
        band_data_paths_rel=("inputs/Out/Band_Structure/band.dat",),
        band_picture_paths_rel=("inputs/Out/Band_Structure/band.png",),
    )

    result = collect_typed_pyatb_band(tmp_path, request)

    assert isinstance(result, ForgeResultEnvelope)
    assert result.status.execution == "not_run"
    assert result.status.scientific == "unassessed"
    assert result.status.collection == "complete"
    artifacts = {artifact.path_rel: artifact for artifact in result.artifacts}
    assert set(artifacts) == {
        "inputs/Out/Band_Structure/band_info.dat",
        "inputs/Out/Band_Structure/band.dat",
        "inputs/Out/Band_Structure/band.png",
    }
    assert all(artifact.role == "output" for artifact in artifacts.values())
    metric = next(metric for metric in result.metrics if metric.name == "band_gap")
    assert metric.value == 1.25
    assert metric.kind == "reported"
    assert metric.unit == "eV"
    assert metric.source_artifact_id == artifacts["inputs/Out/Band_Structure/band_info.dat"].id
    assert not result.checks
    assert result.diagnostics["missing_output_paths_rel"] == ()
    assert result.diagnostics["malformed_output_paths_rel"] == ()


def test_typed_collect_missing_and_partial_are_factual(tmp_path: Path) -> None:
    missing = collect_typed_pyatb_band(
        tmp_path,
        PyatbBandCollectRequest(operation_id=_id(), workspace_rel="."),
    )
    assert missing.status.collection == "missing_output"
    assert missing.status.scientific == "unassessed"
    assert not missing.artifacts
    assert missing.diagnostics["missing_output_paths_rel"] == (
        "inputs/Out/Band_Structure/band_info.dat",
    )

    _write_band_outputs(tmp_path, info="Band output exists but has no parseable gap\n", data=False, picture=False)
    partial = collect_typed_pyatb_band(
        tmp_path,
        PyatbBandCollectRequest(operation_id=_id(), workspace_rel=".", band_data_paths_rel=("inputs/Out/Band_Structure/band.dat",)),
    )
    assert partial.status.collection == "partial"
    assert partial.status.scientific == "unassessed"
    assert {artifact.path_rel for artifact in partial.artifacts} == {
        "inputs/Out/Band_Structure/band_info.dat"
    }
    assert partial.metrics == ()
    assert partial.diagnostics["missing_output_paths_rel"] == (
        "inputs/Out/Band_Structure/band.dat",
    )
    assert partial.diagnostics["malformed_output_paths_rel"] == (
        "inputs/Out/Band_Structure/band_info.dat",
    )
    assert "accepted" not in str(partial.to_dict()).lower()
    assert "rejected" not in str(partial.to_dict()).lower()


def test_typed_collect_uses_total_band_gap_section_when_multiple_spin_sections_exist(tmp_path: Path) -> None:
    _write_band_outputs(
        tmp_path,
        info=(
            "For nspin up:\n"
            "Band gap (eV): 0.25\n"
            "For nspin down:\n"
            "Band gap (eV): 0.50\n"
            "For total band:\n"
            "Band gap (eV): 0.75\n"
        ),
        data=False,
        picture=False,
    )

    result = collect_typed_pyatb_band(
        tmp_path,
        PyatbBandCollectRequest(operation_id=_id(), workspace_rel="."),
    )

    metric = next(metric for metric in result.metrics if metric.name == "band_gap")
    assert metric.value == 0.75
    assert result.diagnostics["malformed_output_paths_rel"] == ()


def test_typed_collect_omits_ambiguous_spin_gap_without_total_section(tmp_path: Path) -> None:
    _write_band_outputs(
        tmp_path,
        info=(
            "For nspin up:\n"
            "Band gap (eV): 0.25\n"
            "For nspin down:\n"
            "Band gap (eV): 0.50\n"
        ),
        data=False,
        picture=False,
    )

    result = collect_typed_pyatb_band(
        tmp_path,
        PyatbBandCollectRequest(operation_id=_id(), workspace_rel="."),
    )

    assert result.metrics == ()
    assert result.diagnostics["malformed_output_paths_rel"] == (
        "inputs/Out/Band_Structure/band_info.dat",
    )


def test_typed_collect_accepts_a_decimal_band_gap_without_leading_zero(tmp_path: Path) -> None:
    _write_band_outputs(tmp_path, info="Band gap (eV): .25\n", data=False, picture=False)

    result = collect_typed_pyatb_band(
        tmp_path,
        PyatbBandCollectRequest(operation_id=_id(), workspace_rel="."),
    )

    metric = next(metric for metric in result.metrics if metric.name == "band_gap")
    assert metric.value == 0.25


@pytest.mark.parametrize(
    "info",
    (
        "Band gap (eV): nan\nEigenvalue of VBM (eV): 2.0000\n",
        "Band gap (eV): nan 2.0000\n",
        "Band gap (eV): Inf\nEigenvalue of VBM (eV): 2.0000\n",
        "Band gap (eV):\nEigenvalue of VBM (eV): 2.0000\n",
        "Band gap (eV): 1e\n",
        "Band gap (eV): 1.2.3\n",
    ),
)
def test_typed_collect_marks_nonfinite_empty_or_incomplete_band_gap_malformed(
    tmp_path: Path, info: str
) -> None:
    _write_band_outputs(tmp_path, info=info, data=False, picture=False)

    result = collect_typed_pyatb_band(
        tmp_path,
        PyatbBandCollectRequest(operation_id=_id(), workspace_rel="."),
    )

    assert result.metrics == ()
    assert result.diagnostics["malformed_output_paths_rel"] == (
        "inputs/Out/Band_Structure/band_info.dat",
    )


def test_typed_collect_omits_escaped_symlink_outputs(tmp_path: Path) -> None:
    external = tmp_path.parent / "external-band-info.dat"
    external.write_text("Band gap is 5.0 eV\n", encoding="utf-8")
    output = tmp_path / "inputs/Out/Band_Structure"
    output.mkdir(parents=True)
    (output / "band_info.dat").symlink_to(external)

    result = collect_typed_pyatb_band(
        tmp_path,
        PyatbBandCollectRequest(operation_id=_id(), workspace_rel="."),
    )

    assert result.status.collection == "partial"
    assert not result.artifacts
    assert result.diagnostics["escaped_output_paths_rel"] == (
        "inputs/Out/Band_Structure/band_info.dat",
    )


def _write_executable(path: Path, body: str) -> Path:
    path.write_text("#!/usr/bin/env python3\n" + body + "\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def _typed_service_prepare(
    root: Path,
    *,
    operation_id: str | None = None,
    handoff_mode: str = "link",
) -> tuple[PyatbBandServiceSet, PyatbBandPrepareRequest, OperationOutcome]:
    _sources(root)
    request = _prepare_request(
        operation_id=operation_id or _id(),
        handoff_mode=handoff_mode,
    )
    services = PyatbBandServiceSet.default(workspace_root=root)
    result = services.prepare.prepare(request)
    assert isinstance(result, OperationOutcome)
    return services, request, result


def test_typed_prepare_service_persists_manifest_facts_and_refs_once(tmp_path: Path) -> None:
    _, request, result = _typed_service_prepare(tmp_path)

    assert result.status.execution == "not_run"
    assert result.status.collection == "not_collected"
    assert result.status.scientific == "unassessed"
    assert result.envelope.workspace_rel == "."
    assert result.envelope.diagnostics["task"] == "band"
    assert result.envelope.diagnostics["unit"] == "pyatb"
    assert result.envelope.diagnostics["engine"] == "pyatb"
    json.dumps(result.to_dict(), allow_nan=False)
    refs = result.envelope.diagnostics["artifact_refs"]
    assert {ref["artifact_id"] for ref in refs} == {artifact.id for artifact in result.envelope.artifacts}
    manifest = json.loads((tmp_path / "forge-unit.json").read_text(encoding="utf-8"))
    assert manifest["task"] == "band"
    assert manifest["unit"] == "pyatb"
    assert manifest["engine"] == "pyatb"
    assert manifest["metadata"]["pyatb_handoff"]
    typed_manifest = result.envelope.diagnostics["pyatb_manifest"]
    assert typed_manifest["schema_version"] == "forge.pyatb-manifest/v1"
    by_path = {entry["path_rel"]: entry for entry in typed_manifest["inputs"]}
    artifact_ids = {artifact.id for artifact in result.envelope.artifacts}
    assert {"inputs/STRU", "inputs/Input", "inputs/KPT_band"} <= set(by_path)
    assert all(entry["artifact_id"] in artifact_ids for entry in by_path.values())
    assert by_path["inputs/STRU"]["source_path_rel"] == "source/STRU"
    assert by_path["inputs/STRU"]["source_sha256"] == by_path["inputs/STRU"]["sha256"]
    events = sorted((tmp_path / "reports/events").glob("*.json"))
    assert len(events) == 1
    assert json.loads(events[0].read_text(encoding="utf-8"))["id"] == request.operation_id


@pytest.mark.parametrize("spin2", (False, True))
def test_typed_prepare_manifest_records_matrix_provenance_and_spin(
    tmp_path: Path, spin2: bool
) -> None:
    _sources(tmp_path, spin2=spin2)
    request = _prepare_request(
        hr_paths_rel=("source/hr.csr", "source/hr-down.csr") if spin2 else ("source/hr.csr",),
        nspin=2 if spin2 else 1,
    )
    result = PyatbBandServiceSet.default(workspace_root=tmp_path).prepare.prepare(request)
    assert isinstance(result, OperationOutcome)
    entries = {entry["path_rel"]: entry for entry in result.envelope.diagnostics["pyatb_manifest"]["inputs"]}
    hr_entries = [entry for entry in entries.values() if entry["kind"] == "matrix_hr"]
    assert [entry["spin"] for entry in hr_entries] == (["up", "down"] if spin2 else ["shared"])
    assert entries["inputs/pyatb_sources/sr.csr"]["kind"] == "matrix_sr"
    assert entries["inputs/pyatb_sources/sr.csr"]["spin"] == "shared"
    assert entries["inputs/pyatb_sources/rr.csr"]["kind"] == "matrix_rr"
    assert entries["inputs/pyatb_sources/rr.csr"]["spin"] == "shared"
    for entry in entries.values():
        assert entry["artifact_id"]
        assert entry["sha256"]
        assert entry["size_bytes"] >= 0


def test_typed_execute_service_uses_only_request_runner_fields_and_records_runtime_facts(
    tmp_path: Path,
) -> None:
    services, _, _ = _typed_service_prepare(tmp_path)
    executable = _write_executable(
        tmp_path / "fake-pyatb.py",
        "from pathlib import Path\n"
        "out = Path.cwd() / 'Out' / 'Band_Structure'\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'band_info.dat').write_text('Band gap is 1.5\\n', encoding='utf-8')\n"
        "(out / 'band.dat').write_text('bands\\n', encoding='utf-8')\n"
        "(out / 'band.png').write_bytes(b'picture')\n"
        "print('typed pyatb done')",
    )
    request = PyatbBandExecuteRequest(
        operation_id=_id(),
        workspace_rel=".",
        executable=str(executable),
        mpi_ranks=1,
        omp_threads=3,
        timeout_seconds=5,
    )

    result = services.execute.execute(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.execution == "completed"
    assert result.status.scientific == "unassessed"
    assert result.status.collection == "not_collected"
    assert (tmp_path / "outputs/stdout.log").is_file()
    assert (tmp_path / "outputs/stderr.log").is_file()
    assert "typed pyatb done" in (tmp_path / "outputs/stdout.log").read_text(encoding="utf-8")
    assert next(metric for metric in result.envelope.metrics if metric.name == "returncode").value == 0
    assert result.envelope.diagnostics["termination"] == "exited"
    assert result.envelope.diagnostics["artifact_refs"]
    assert json.loads((tmp_path / "forge-result.json").read_text(encoding="utf-8"))["engine"] == "pyatb"


def test_typed_execute_missing_executable_is_precondition_and_nonzero_is_failed(
    tmp_path: Path,
) -> None:
    services, _, _ = _typed_service_prepare(tmp_path)
    missing = services.execute.execute(
        PyatbBandExecuteRequest(operation_id=_id(), workspace_rel=".", executable="definitely-missing-pyatb")
    )
    assert isinstance(missing, ForgeErrorEnvelope)
    assert missing.error_class == "precondition.missing"

    failing = _write_executable(tmp_path / "fail-pyatb.py", "raise SystemExit(17)")
    failed = services.execute.execute(
        PyatbBandExecuteRequest(operation_id=_id(), workspace_rel=".", executable=str(failing))
    )
    assert isinstance(failed, OperationOutcome)
    assert failed.status.execution == "failed"
    assert next(metric for metric in failed.envelope.metrics if metric.name == "returncode").value == 17


def test_typed_execute_timeout_and_dry_run_do_not_reuse_stale_logs(tmp_path: Path) -> None:
    services, _, _ = _typed_service_prepare(tmp_path)
    sleeper = _write_executable(
        tmp_path / "sleep-pyatb.py",
        "import time\n"
        "print('before timeout')\n"
        "time.sleep(0.3)",
    )
    timed = services.execute.execute(
        PyatbBandExecuteRequest(
            operation_id=_id(), workspace_rel=".", executable=str(sleeper), timeout_seconds=0.02
        )
    )
    assert isinstance(timed, OperationOutcome)
    assert timed.status.execution == "failed"
    assert timed.envelope.diagnostics["termination"] == "timeout"

    stdout = tmp_path / "outputs/stdout.log"
    stderr = tmp_path / "outputs/stderr.log"
    stdout.write_text("stale stdout", encoding="utf-8")
    stderr.write_text("stale stderr", encoding="utf-8")
    dry = services.execute.execute(
        PyatbBandExecuteRequest(
            operation_id=_id(), workspace_rel=".", executable="also-missing", dry_run=True
        )
    )
    assert isinstance(dry, OperationOutcome)
    assert dry.status.execution == "skipped"
    assert stdout.read_text(encoding="utf-8") == "stale stdout"
    assert stderr.read_text(encoding="utf-8") == "stale stderr"


def test_typed_service_collect_is_independent_and_persists_one_event(tmp_path: Path) -> None:
    services, _, _ = _typed_service_prepare(tmp_path)
    _write_band_outputs(tmp_path)
    request = PyatbBandCollectRequest(
        operation_id=_id(),
        workspace_rel=".",
        band_data_paths_rel=("inputs/Out/Band_Structure/band.dat",),
        band_picture_paths_rel=("inputs/Out/Band_Structure/band.png",),
    )

    result = services.collect.collect(request)

    assert isinstance(result, OperationOutcome)
    assert result.status.execution == "not_run"
    assert result.status.collection == "complete"
    assert result.status.scientific == "unassessed"
    assert {artifact.path_rel for artifact in result.envelope.artifacts} == {
        "inputs/Out/Band_Structure/band_info.dat",
        "inputs/Out/Band_Structure/band.dat",
        "inputs/Out/Band_Structure/band.png",
    }
    assert len(list((tmp_path / "reports/events").glob("*.json"))) == 2
    assert all(ref["operation_id"] == request.operation_id for ref in result.envelope.diagnostics["artifact_refs"])


def test_typed_prepare_duplicate_operation_id_is_durable_conflict(tmp_path: Path) -> None:
    services, request, first = _typed_service_prepare(tmp_path)
    assert first.status.execution == "not_run"
    second = services.prepare.prepare(request)
    assert isinstance(second, ForgeErrorEnvelope)
    assert second.error_class == "operation.conflict"
