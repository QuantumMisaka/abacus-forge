from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

import pytest

from abacus_forge import (
    ForgeResultEnvelope,
    PyatbBandCollectRequest,
    PyatbBandPrepareRequest,
    Workspace,
)
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
