from __future__ import annotations

import json
import math
import re
import uuid
from copy import deepcopy
from pathlib import Path

import pytest

from abacus_forge import BecPostprocessRequest, BecServiceSet, PolarizationCollectRequest, PolarizationServiceSet
from abacus_forge.discovery import capabilities_document, request_schema_document
from abacus_forge.machine_cli import decode_operation_request
from abacus_forge.structure import BOHR_TO_ANG


def _id() -> str:
    return str(uuid.uuid4())


def _column(*, atom_index=1, direction="x", paths=("facts/zero.json", "facts/minus.json", "facts/plus.json")):
    return {"atom_index": atom_index, "direction": direction, "samples": [
        {"displacement_angstrom": 0.0, "polarization_paths_rel": [paths[0]]},
        {"displacement_angstrom": -0.01, "polarization_paths_rel": [paths[1]]},
        {"displacement_angstrom": 0.01, "polarization_paths_rel": [paths[2]]},
    ]}


def _fact(gdir=1):
    row = {"unit": "(e/Omega).bohr", "scalar": 0.1, "modulus": 1.0,
           "cartesian": [0.1, 0.0, 0.0], "source_log_path": "old"}
    return {"schema_version": "forge.polarization/v1", "gdir": gdir,
            "ionic_phase": 0.0, "electronic_phase": 0.0,
            "rows": {"(e/Omega).bohr": row}, "geometry": {}, "input": {}}


def test_strict_request_roundtrips_and_nested_validation():
    polar = PolarizationCollectRequest(_id(), ".", log_path_rel="source/running.log",
                                         structure_path_rel="source/STRU", input_path_rel="source/INPUT")
    assert PolarizationCollectRequest.from_dict(polar.to_dict()) == polar
    assert decode_operation_request("collect", polar.to_dict()) == polar
    bec = BecPostprocessRequest(_id(), ".", columns=[_column()], max_step_fraction=0.25)
    assert BecPostprocessRequest.from_dict(bec.to_dict()) == bec
    assert decode_operation_request("postprocess", bec.to_dict()) == bec
    assert set(request_schema_document("polarization", "collect")["request_schema"]["properties"]) == set(polar.to_dict())
    assert set(request_schema_document("bec", "postprocess")["request_schema"]["properties"]) == set(bec.to_dict())
    assert {item["name"] for item in capabilities_document()["capabilities"]} >= {"polarization", "bec"}
    with pytest.raises(ValueError):
        BecPostprocessRequest(_id(), ".", columns=[{**_column(), "extra": 1}], max_step_fraction=0.25)
    with pytest.raises(ValueError):
        BecPostprocessRequest(_id(), ".", columns=[_column(), _column()], max_step_fraction=0.25)
    with pytest.raises(ValueError):
        BecPostprocessRequest(_id(), ".", columns=[_column()], max_step_fraction=None)
    with pytest.raises(ValueError):
        BecPostprocessRequest(_id(), ".", columns=[_column()], max_step_fraction=0.5)
    assert BecPostprocessRequest(_id(), ".", columns=[_column()], branch_mode="explicit").branch_mode == "explicit"


def test_polarization_collect_persists_fact_and_source_artifacts(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    for name in ("running.log", "STRU", "INPUT"):
        (source / name).write_text(name)
    calls = []
    def parser(log_path, structure_path, input_path):
        calls.append((log_path, structure_path, input_path))
        return _fact()
    service = PolarizationServiceSet.default(workspace_root=tmp_path, parser=parser)
    result = service.collect.collect(PolarizationCollectRequest(
        _id(), ".", log_path_rel="source/running.log", structure_path_rel="source/STRU",
        input_path_rel="source/INPUT"))
    assert result.envelope.status.collection == "complete"
    assert result.envelope.status.scientific == "unassessed"
    assert len(calls) == 1
    saved = json.loads((tmp_path / "outputs/polarization.json").read_text())
    assert saved["schema_version"] == "forge.polarization/v1"
    assert saved["rows"]["(e/Omega).bohr"]["source_log_path"] == "source/running.log"
    assert {a.path_rel for a in result.envelope.artifacts} == {
        "source/running.log", "source/STRU", "source/INPUT", "outputs/polarization.json",
    }
    assert len(list((tmp_path / "reports/events").glob("*-collect.json"))) == 1


def test_bec_missing_fact_keeps_independent_column(tmp_path: Path):
    fact_dir = tmp_path / "facts"
    fact_dir.mkdir()
    (fact_dir / "valid.json").write_text(json.dumps(_fact()))
    first = _column(paths=("facts/valid.json", "facts/missing.json", "facts/missing2.json"))
    second = _column(atom_index=2, paths=("facts/missing3.json", "facts/missing4.json", "facts/missing5.json"))
    seen = []
    def algorithm(columns, facts, *, branch_mode, max_step_fraction):
        seen.append((columns, facts, branch_mode, max_step_fraction))
        return {"schema_version": "forge.bec/v1", "requested_columns": [{"atom_index": 1, "direction": "x"}, {"atom_index": 2, "direction": "x"}],
                "computed_columns": [{"atom_index": 1, "direction": "x", "values": [1., 2., 3.], "unit": "e"}],
                "columns": [{"atom_index": 1, "direction": "x", "status": "computed", "reason": None, "values": [1., 2., 3.], "branch_trace": []},
                            {"atom_index": 2, "direction": "x", "status": "missing", "reason": "missing fact", "values": None, "branch_trace": []}],
                "tensor": [], "requested_complete": False, "full_tensor_complete": False}
    service = BecServiceSet.default(workspace_root=tmp_path, algorithm=algorithm)
    result = service.postprocess.postprocess(BecPostprocessRequest(
        _id(), ".", columns=[first, second], max_step_fraction=0.25))
    assert result.envelope.status.collection == "partial"
    assert set(seen[0][1]) == {"facts/valid.json"}
    assert result.envelope.diagnostics["requested_complete"] is False
    assert (tmp_path / "outputs/bec.json").is_file()


def _source_shaped_log(gdir: int, scalar: float) -> str:
    lattice = ((2.0, 0.0, 0.0), (1.0, 2.0, 0.0), (0.0, 0.0, 3.0))[gdir - 1]
    quantum = math.sqrt(sum(value * value for value in lattice))
    direction = [value / quantum for value in lattice]
    si_factor = 1.60097e-19 / (5.29177e-11) ** 2
    rows = []
    for unit, factor in (("(e/Omega).bohr", 1.0), ("e/bohr^2", 1 / 12), ("C/m^2", si_factor / 12)):
        cartesian = [scalar * axis * factor for axis in direction]
        rows.append(f" P = {scalar * factor:.7f} (mod {quantum * factor:.7f}) "
                    f"({cartesian[0]:.7f}, {cartesian[1]:.7f}, {cartesian[2]:.7f}) {unit}")
    return ("VALUES OF POLARIZATION\nThe Ionic Phase: 0.0\nElectronic Phase: 0.0\n"
            f"The calculated polarization direction is in R{gdir} direction\n" + "\n".join(rows) + "\n")


def _write_native_sources(root: Path, displacement: float, gdir: int, scalar: float) -> tuple[str, str, str]:
    relative = f"source/{displacement:+.5f}/r{gdir}"
    directory = root / relative
    directory.mkdir(parents=True)
    (directory / "running.log").write_text(_source_shaped_log(gdir, scalar), encoding="utf-8")
    direct_x = displacement / (2 * BOHR_TO_ANG)
    (directory / "STRU").write_text(
        "ATOMIC_SPECIES\nH 1.0 H.upf\n\nLATTICE_CONSTANT\n"
        "1.0\n\nLATTICE_VECTORS\n2 0 0\n1 2 0\n0 0 3\n\n"
        "ATOMIC_POSITIONS\nDirect\nH\n0\n1\n"
        f"{direct_x:.12f} 0 0 m 1 1 1\n", encoding="utf-8")
    (directory / "INPUT").write_text(
        f"INPUT_PARAMETERS\nberry_phase 1\ngdir {gdir}\nnspin 1\ncalculation nscf\n", encoding="utf-8")
    return tuple(f"{relative}/{name}" for name in ("running.log", "STRU", "INPUT"))


def test_native_source_shaped_collect_to_bec_service_chain(tmp_path: Path):
    collect = PolarizationServiceSet.default(workspace_root=tmp_path).collect
    delta = 0.1 * BOHR_TO_ANG
    samples = []
    for sample_index, displacement in enumerate((-delta, 0.0, delta)):
        paths = []
        for gdir in (1, 2, 3):
            scalar = {1: (-0.02, 0.0, 0.02), 2: (0.0, 0.0, 0.0), 3: (0.0, 0.0, 0.0)}[gdir][sample_index]
            log_rel, stru_rel, input_rel = _write_native_sources(tmp_path, displacement, gdir, scalar)
            fact_rel = f"facts/s{sample_index}/r{gdir}.json"
            outcome = collect.collect(PolarizationCollectRequest(
                _id(), ".", log_path_rel=log_rel, structure_path_rel=stru_rel,
                input_path_rel=input_rel, output_path_rel=fact_rel))
            assert outcome.envelope.status.collection == "complete", outcome
            fact = json.loads((tmp_path / fact_rel).read_text())
            assert fact["source_log_path"] == log_rel
            assert fact["rows"]["e/bohr^2"]["source_log_path"] == log_rel
            paths.append(fact_rel)
        samples.append({"displacement_angstrom": displacement, "polarization_paths_rel": paths})
    request = BecPostprocessRequest(_id(), ".", columns=[{"atom_index": 1, "direction": "x", "samples": samples}],
                                    max_step_fraction=0.2)
    outcome = BecServiceSet.default(workspace_root=tmp_path).postprocess.postprocess(request)
    assert outcome.envelope.status.collection == "complete", outcome
    result = json.loads((tmp_path / "outputs/bec.json").read_text())
    assert result["requested_complete"] is True
    assert result["full_tensor_complete"] is False
    assert result["computed_columns"][0]["values"] == pytest.approx([0.2, 0.0, 0.0], abs=1e-6)

    malformed_rel = "facts/malformed.json"
    (tmp_path / malformed_rel).write_text("{bad json", encoding="utf-8")
    bad_samples = deepcopy(samples)
    bad_samples[1]["polarization_paths_rel"][1] = malformed_rel
    partial_request = BecPostprocessRequest(
        _id(), ".", columns=[{"atom_index": 1, "direction": "x", "samples": samples},
                             {"atom_index": 1, "direction": "y", "samples": bad_samples}],
        max_step_fraction=0.2, output_path_rel="outputs/bec-partial.json")
    partial = BecServiceSet.default(workspace_root=tmp_path).postprocess.postprocess(partial_request)
    assert partial.envelope.status.collection == "partial"
    assert list(partial.envelope.diagnostics["invalid_source_paths_rel"]) == [malformed_rel]
    partial_result = json.loads((tmp_path / "outputs/bec-partial.json").read_text())
    assert [entry["status"] for entry in partial_result["columns"]] == ["computed", "invalid"]
    assert malformed_rel in {artifact.path_rel for artifact in partial.envelope.artifacts}


def test_explicit_missing_offsets_are_column_diagnostics(tmp_path: Path):
    (tmp_path / "facts").mkdir()
    (tmp_path / "facts/zero.json").write_text(json.dumps(_fact()))
    offsets = {"1": 0, "2": 0, "3": 0}
    good = _column()
    bad = _column(atom_index=2)
    for sample in good["samples"]:
        sample["branch_offsets"] = offsets
    for sample in bad["samples"][:-1]:
        sample["branch_offsets"] = offsets
    request = BecPostprocessRequest(_id(), ".", columns=[good, bad], branch_mode="explicit")
    assert "branch_offsets" not in request.to_dict()["columns"][1]["samples"][-1]
    # Missing offsets reach the numerical boundary for a per-column result.
    calls = []
    def algorithm(columns, facts, *, branch_mode, max_step_fraction):
        calls.append(columns)
        return {"schema_version": "forge.bec/v1", "requested_complete": False,
                "full_tensor_complete": False, "computed_columns": [{"atom_index": 1, "direction": "x", "values": [1, 0, 0], "unit": "e"}],
                "columns": [{"atom_index": 1, "direction": "x", "status": "computed"},
                            {"atom_index": 2, "direction": "x", "status": "missing", "reason": "missing offsets"}]}
    service = BecServiceSet.default(workspace_root=tmp_path, algorithm=algorithm)
    result = service.postprocess.postprocess(request)
    assert len(calls) == 1
    assert result.envelope.status.collection == "partial"
    assert json.loads((tmp_path / "outputs/bec.json").read_text())["columns"][1]["status"] == "missing"


def test_output_preflight_rejects_external_and_existing_targets(tmp_path: Path):
    outside = tmp_path.parent / f"outside-{uuid.uuid4()}"
    outside.mkdir()
    (tmp_path / "outputs").symlink_to(outside, target_is_directory=True)
    request = BecPostprocessRequest(_id(), ".", columns=[_column()], max_step_fraction=0.25)
    result = BecServiceSet.default(workspace_root=tmp_path).postprocess.postprocess(request)
    assert result.error_class == "request.path"
    assert list(outside.iterdir()) == []
    assert not (tmp_path / "reports").exists()


def test_contained_parent_alias_works_but_final_symlink_is_occupied(tmp_path: Path):
    (tmp_path / "facts").mkdir()
    (tmp_path / "alias").symlink_to(tmp_path / "facts", target_is_directory=True)
    (tmp_path / "source").mkdir()
    for name in ("running.log", "STRU", "INPUT"):
        (tmp_path / "source" / name).write_text(name)
    service = PolarizationServiceSet.default(workspace_root=tmp_path, parser=lambda *_: _fact())
    request = PolarizationCollectRequest(_id(), ".", log_path_rel="source/running.log",
                                         structure_path_rel="source/STRU", input_path_rel="source/INPUT",
                                         output_path_rel="alias/out.json")
    assert service.collect.collect(request).envelope.status.collection == "complete"
    assert (tmp_path / "facts/out.json").is_file()
    (tmp_path / "facts/final.json").symlink_to(tmp_path / "facts/missing.json")
    blocked = PolarizationCollectRequest(_id(), ".", log_path_rel="source/running.log",
                                         structure_path_rel="source/STRU", input_path_rel="source/INPUT",
                                         output_path_rel="alias/final.json")
    result = service.collect.collect(blocked)
    assert result.error_class == "request.invalid"
    assert not (tmp_path / "facts/missing.json").exists()


def test_guide_requests_match_typed_discovery_schema():
    guide = (Path(__file__).parent.parent / "docs/guide.md").read_text(encoding="utf-8")
    section = guide.split('<a id="polarization-and-bec"></a>', 1)[1]
    payloads = [json.loads(text) for text in re.findall(r"```json\n(.*?)\n```", section, flags=re.S)[:2]]
    assert [payload["capability"] for payload in payloads] == ["polarization", "bec"]
    for payload in payloads:
        assert decode_operation_request(payload["operation"], payload).to_dict() == payload
        schema = request_schema_document(payload["capability"], payload["operation"])["request_schema"]
        assert set(payload) == set(schema["properties"])
