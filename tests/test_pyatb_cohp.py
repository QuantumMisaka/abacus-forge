from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

from abacus_forge import (
    ForgeErrorEnvelope, PyatbCohpCollectRequest, PyatbCohpExecuteRequest,
    PyatbCohpPrepareRequest, PyatbCohpServiceSet,
)
from abacus_forge.discovery import capabilities_document, request_schema_document
from abacus_forge.errors import ForgeSchemaError
from abacus_forge.machine_cli import decode_operation_request
from tests.support.process import run_cli


STRU = """ATOMIC_SPECIES
Si 28.0855 Si.upf

NUMERICAL_ORBITAL
Si.orb

LATTICE_CONSTANT
1.0
LATTICE_CONSTANT_UNIT
Angstrom
LATTICE_VECTORS
3 0 0
0 3 0
0 0 3
ATOMIC_POSITIONS
Direct
Si
0.0
2
0 0 0 1 1 1
0.25 0.25 0.25 1 1 1
"""


def request(**updates):
    fields = dict(
        operation_id=str(uuid.uuid4()), workspace_rel=".",
        structure_path_rel="source/STRU", hr_paths_rel=("source/hr.csr",),
        sr_path_rel="source/sr.csr", orbital_paths_rel=("source/Si.orb",),
        fermi_energy=4.0, atom_i_index=1, atom_j_index=2,
        kpoints=((0, 0, 0), (0.5, 0, 0)), kpoint_weights=(1, 3),
        e_range=(0.0, 8.0),
    )
    fields.update(updates)
    return PyatbCohpPrepareRequest(**fields)


def sources(root: Path):
    source = root / "source"
    source.mkdir()
    (source / "STRU").write_text(STRU)
    for name in ("hr.csr", "hr_dn.csr", "sr.csr", "Si.orb"):
        (source / name).write_text(name)


def test_prepare_stages_self_contained_cohp_input_and_discovery(tmp_path):
    sources(tmp_path)
    service = PyatbCohpServiceSet.default(workspace_root=tmp_path)
    result = service.prepare.prepare(request())
    assert result.envelope.status.execution == "not_run"
    text = (tmp_path / "inputs/Input").read_text()
    assert "kpoint_weights  1  3" in text
    assert "kpoint_mode  direct" in text
    assert "orbital_dir  ." in text
    assert (tmp_path / "inputs/Si.orb").is_file()
    assert (tmp_path / "inputs/STRU").read_bytes() == (tmp_path / "source/STRU").read_bytes()
    assert request_schema_document("pyatb-cohp", "prepare")["request_schema"]["additionalProperties"] is False
    assert "pyatb-cohp" in [item["name"] for item in capabilities_document()["capabilities"]]
    assert set(capabilities_document()["contracts"]) == {"cohp", "pyatb-cohp"}
    assert capabilities_document()["contracts"]["cohp"]["method"] == "iao"
    assert capabilities_document()["contracts"]["pyatb-cohp"]["method"] == "direct_nao"
    contract_result = capabilities_document()["contracts"]["pyatb-cohp"]["result"]
    assert contract_result["pair_convention"] == (
        "unordered Hermitian orbital-set pair (identical: 1, disjoint: 2)"
    )
    assert contract_result["pair_factor_rule"] == (
        "identical orbital sets use 1; disjoint sets use 2; partial overlap is rejected"
    )
    assert (tmp_path / "reports/events" / f"{result.operation_id}-prepare.json").is_file()


def test_request_roundtrip_schema_and_strict_validation():
    obj = request()
    assert PyatbCohpPrepareRequest.from_dict(obj.to_dict()) == obj
    assert decode_operation_request("prepare", obj.to_dict()) == obj
    for operation, typed in (("prepare", obj),
                             ("execute", PyatbCohpExecuteRequest(str(uuid.uuid4()), ".")),
                             ("collect", PyatbCohpCollectRequest(str(uuid.uuid4()), "."))):
        schema = request_schema_document("pyatb-cohp", operation)["request_schema"]
        assert set(schema["properties"]) == set(typed.to_dict())
        assert schema["additionalProperties"] is False
        assert typed.__class__.from_dict(typed.to_dict()) == typed
    with pytest.raises(ValueError, match="unknown|unexpected|field"):
        PyatbCohpPrepareRequest.from_dict({**obj.to_dict(), "line_kpoints": []})
    with pytest.raises(ValueError, match="nspin"):
        request(nspin=4)
    for fractional_spin in (1.0, 2.0):
        with pytest.raises(ValueError, match="nspin"):
            request(nspin=fractional_spin)
        with pytest.raises(ForgeSchemaError, match="request fields do not match"):
            decode_operation_request("prepare", {**obj.to_dict(), "nspin": fractional_spin})
    with pytest.raises(ValueError, match="kpoint_weights"):
        request(kpoint_weights=(1,))
    with pytest.raises(ValueError, match="kpoint_weights"):
        request(kpoint_weights=(0, 0))
    with pytest.raises(ValueError, match="finite"):
        request(fermi_energy=float("nan"))


def test_prepare_nspin2_roundtrips_two_hr_paths_and_selected_spin(tmp_path):
    """The allowed collinear-spin path stages two HR files verbatim."""

    sources(tmp_path)
    obj = request(
        nspin=2,
        hr_paths_rel=("source/hr.csr", "source/hr_dn.csr"),
        spin="down",
    )
    assert PyatbCohpPrepareRequest.from_dict(obj.to_dict()) == obj

    service = PyatbCohpServiceSet.default(workspace_root=tmp_path)
    result = service.prepare.prepare(obj)
    assert result.envelope.status.execution == "not_run"
    text = (tmp_path / "inputs/Input").read_text()
    assert "nspin  2" in text
    assert "spin  down" in text
    assert (tmp_path / "inputs/pyatb_sources/hr.csr").read_bytes() == b"hr.csr"
    assert (tmp_path / "inputs/pyatb_sources/hr_dn.csr").read_bytes() == b"hr_dn.csr"
    assert (tmp_path / "inputs/Input").read_text().count("pyatb_sources/hr") == 2


def test_prepare_rejects_all_sources_and_collisions_before_domain_writes(tmp_path):
    sources(tmp_path)
    service = PyatbCohpServiceSet.default(workspace_root=tmp_path)
    (tmp_path / "source/STRU").write_text(STRU.replace("Si.orb", "../Si.orb"))
    bad = service.prepare.prepare(request())
    assert isinstance(bad, ForgeErrorEnvelope)
    assert not (tmp_path / "inputs").exists()
    (tmp_path / "source/STRU").write_text(STRU)
    (tmp_path / "inputs").mkdir()
    (tmp_path / "inputs/Input").write_text("keep")
    collision = service.prepare.prepare(request())
    assert isinstance(collision, ForgeErrorEnvelope)
    assert (tmp_path / "inputs/Input").read_text() == "keep"
    assert not (tmp_path / "inputs/STRU").exists()


def test_prepare_rejects_orbital_name_colliding_with_generated_directory(tmp_path):
    sources(tmp_path)
    (tmp_path / "source/STRU").write_text(STRU.replace("Si.orb", "pyatb_sources"))
    (tmp_path / "source/pyatb_sources").write_text("orbital")
    result = PyatbCohpServiceSet.default(workspace_root=tmp_path).prepare.prepare(
        request(orbital_paths_rel=("source/pyatb_sources",)))
    assert isinstance(result, ForgeErrorEnvelope)
    assert not (tmp_path / "inputs").exists()


def _metadata(spectrum="COHP.dat", **changes):
    meta = {
        "method": "COHP", "spin": "sum", "invert": True,
        "sign_convention": "negative population", "spectrum_label": "-COHP",
        "spectrum_unit": "dimensionless", "fermi_energy_eV": 4.0,
        "energy_shifted_to_efermi": True, "files": {"spectrum": spectrum},
        "atom_i_orbitals": [0], "atom_j_orbitals": [1], "pair_factor": 2.0,
        "pair_convention": "unordered Hermitian orbital-set pair (identical: 1, disjoint: 2)",
        "total_orbitals": 2,
        "atoms": [
            {"index": 1, "start": 0, "stop": 1},
            {"index": 2, "start": 1, "stop": 2},
        ],
        "kpoint_weight_mode": "explicit_normalized",
        "occupied_integral": {"method": "ICOHP", "occupation": "E <= EF (zero temperature)",
                              "unit": "eV", "raw_value": -1.25, "value": 1.25,
                              "label": "-ICOHP", "spin_degeneracy": 2.0},
        "broadening": {"sigma_eV": 0.15, "de_eV": 0.05},
    }
    meta.update(changes)
    return meta


def _write_outputs(root, meta=None, spectrum="# energy_eV -COHP\n-1 0.2\n0 0.3\n"):
    output = root / "inputs/Out/COHP"
    output.mkdir(parents=True, exist_ok=True)
    (output / "COHP.dat").write_text(spectrum)
    (output / "COHP.meta.json").write_text(json.dumps(_metadata() if meta is None else meta))


def test_collect_validates_spectrum_and_metadata_facts(tmp_path):
    _write_outputs(tmp_path)
    service = PyatbCohpServiceSet.default(workspace_root=tmp_path)
    result = service.collect.collect(PyatbCohpCollectRequest(str(uuid.uuid4()), "."))
    assert result.envelope.status.collection == "complete"
    assert result.envelope.status.scientific == "unassessed"
    assert {metric.name: metric.value for metric in result.envelope.metrics} == {
        "icohp_raw": -1.25, "icohp": 1.25,
    }
    assert {artifact.path_rel for artifact in result.envelope.artifacts} == {
        "inputs/Out/COHP/COHP.dat", "inputs/Out/COHP/COHP.meta.json",
    }
    assert len(list((tmp_path / "reports/events").glob("*-collect.json"))) == 1
    (tmp_path / "inputs/Out/COHP/COHP.meta.json").write_text(json.dumps(_metadata("../COHP.dat")))
    malformed = service.collect.collect(PyatbCohpCollectRequest(str(uuid.uuid4()), "."))
    assert malformed.envelope.status.collection == "partial"
    assert malformed.envelope.metrics == ()
    assert "inputs/Out/COHP/COHP.meta.json" in malformed.envelope.diagnostics["malformed_output_paths_rel"]
    (tmp_path / "inputs/Out/COHP/COHP.dat").write_text("0 1\n0 2\n")
    malformed_spectrum = service.collect.collect(PyatbCohpCollectRequest(str(uuid.uuid4()), "."))
    assert malformed_spectrum.envelope.status.collection == "partial"
    assert len(list((tmp_path / "reports/events").glob("*-collect.json"))) == 3


def test_collect_missing_is_not_complete(tmp_path):
    service = PyatbCohpServiceSet.default(workspace_root=tmp_path)
    result = service.collect.collect(PyatbCohpCollectRequest(str(uuid.uuid4()), "."))
    assert result.envelope.status.collection == "missing_output"


@pytest.mark.parametrize("missing,changes", [
    ("total_orbitals", {}),
    (None, {"total_orbitals": 1}),
    (None, {"atoms": []}),
    (None, {"atoms": [{"index": 1, "start": 0, "stop": 1}]}),
    (None, {"atom_i_orbitals": [0, 2]}),
    (None, {"atom_i_orbitals": [0, 0]}),
    (None, {"atom_j_orbitals": [1, 1]}),
    ("pair_convention", {}),
    (None, {"pair_convention": "unordered Hermitian atom pair"}),
    (None, {"atom_i_orbitals": [0, 1], "atom_j_orbitals": [1]}),
    (None, {"atom_i_orbitals": [0], "atom_j_orbitals": [1], "pair_factor": 1.0}),
    (None, {"atom_i_orbitals": [0], "atom_j_orbitals": [0], "pair_factor": 2.0,
            "total_orbitals": 1, "atoms": [{"index": 1, "start": 0, "stop": 1}]}),
])
def test_collect_rejects_unmapped_orbital_facts(tmp_path, missing, changes):
    _write_outputs(tmp_path)
    path = tmp_path / "inputs/Out/COHP/COHP.meta.json"
    meta = json.loads(path.read_text())
    if missing:
        meta.pop(missing)
    meta.update(changes)
    path.write_text(json.dumps(meta))

    service = PyatbCohpServiceSet.default(workspace_root=tmp_path)
    result = service.collect.collect(PyatbCohpCollectRequest(str(uuid.uuid4()), "."))
    assert result.envelope.status.collection == "partial"
    assert result.envelope.metrics == ()
    assert "inputs/Out/COHP/COHP.meta.json" in (
        result.envelope.diagnostics["malformed_output_paths_rel"]
    )


def test_collect_accepts_identical_intrasite_orbitals(tmp_path):
    """PyATB defines identical orbital sets as an intrasite pair with factor one."""

    meta = _metadata(
        atom_i_orbitals=[0],
        atom_j_orbitals=[0],
        pair_factor=1.0,
        total_orbitals=1,
        atoms=[{"index": 1, "start": 0, "stop": 1}],
    )
    _write_outputs(tmp_path, meta=meta)
    service = PyatbCohpServiceSet.default(workspace_root=tmp_path)
    result = service.collect.collect(PyatbCohpCollectRequest(str(uuid.uuid4()), "."))
    assert result.envelope.status.collection == "complete"
    assert {metric.name: metric.value for metric in result.envelope.metrics} == {
        "icohp_raw": -1.25, "icohp": 1.25,
    }


def _executable(path: Path, body: str) -> Path:
    path.write_text("#!/usr/bin/env python3\n" + body)
    path.chmod(0o755)
    return path


@pytest.mark.parametrize("body,expected,timeout", [
    ("print('ran')\n", "completed", 2.0),
    ("import sys\nprint('bad', file=sys.stderr)\nsys.exit(7)\n", "failed", 2.0),
    ("import time\ntime.sleep(1)\n", "failed", 0.05),
])
def test_execute_uses_one_local_process_and_retains_logs(tmp_path, body, expected, timeout):
    sources(tmp_path)
    service = PyatbCohpServiceSet.default(workspace_root=tmp_path)
    assert service.prepare.prepare(request()).envelope.status.execution == "not_run"
    executable = _executable(tmp_path / "fake-pyatb", body)
    outcome = service.execute.execute(PyatbCohpExecuteRequest(
        str(uuid.uuid4()), ".", executable=str(executable), timeout_seconds=timeout))
    assert outcome.envelope.status.execution == expected
    assert outcome.envelope.status.collection == "not_collected"
    assert (tmp_path / "outputs/stdout.log").is_file()
    assert (tmp_path / "outputs/stderr.log").is_file()
    assert len(list((tmp_path / "reports/events").glob("*-execute.json"))) == 1


def test_execute_rejects_existing_out_even_for_dry_run(tmp_path):
    sources(tmp_path)
    service = PyatbCohpServiceSet.default(workspace_root=tmp_path)
    service.prepare.prepare(request())
    target = tmp_path / "inputs/Out"
    target.mkdir()
    (target / "keep").write_text("unaltered")
    result = service.execute.execute(PyatbCohpExecuteRequest(str(uuid.uuid4()), ".", dry_run=True))
    assert isinstance(result, ForgeErrorEnvelope)
    assert (target / "keep").read_text() == "unaltered"


@pytest.mark.parametrize("dry_run", [False, True])
def test_execute_rejects_outputs_parent_symlink_outside_workspace(tmp_path, dry_run):
    sources(tmp_path)
    service = PyatbCohpServiceSet.default(workspace_root=tmp_path)
    assert service.prepare.prepare(request()).envelope.status.execution == "not_run"
    outside = tmp_path.parent / f"{tmp_path.name}-external-logs"
    outside.mkdir()
    (tmp_path / "outputs").rename(tmp_path / "outputs-saved")
    (tmp_path / "outputs").symlink_to(outside, target_is_directory=True)
    result = service.execute.execute(PyatbCohpExecuteRequest(
        str(uuid.uuid4()), ".", executable="/bin/true", dry_run=dry_run))
    assert isinstance(result, ForgeErrorEnvelope)
    assert not (outside / "stdout.log").exists()
    assert not (outside / "stderr.log").exists()


def test_machine_cli_prepare_matches_python_service(tmp_path):
    api = tmp_path / "api"
    cli = tmp_path / "cli"
    api.mkdir()
    cli.mkdir()
    sources(api)
    sources(cli)
    req = request()
    api_result = PyatbCohpServiceSet.default(workspace_root=api).prepare.prepare(req)
    process = run_cli("operation", "prepare", "--stdin", cwd=cli,
                      input_text=json.dumps(req.to_dict()))
    assert process.returncode == 0, process.stdout + process.stderr
    response = json.loads(process.stdout)
    assert response["envelope"]["status"] == api_result.envelope.to_dict()["status"]
    assert (api / "inputs/Input").read_bytes() == (cli / "inputs/Input").read_bytes()
