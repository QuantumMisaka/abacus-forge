from __future__ import annotations

import json
from pathlib import Path

import pytest

from abacus_forge import (
    MdCollectRequest,
    MdExecuteRequest,
    MdModifyRequest,
    MdPrepareRequest,
    MdServiceSet,
    OperationOutcome,
    ScfExecuteRequest,
    ScfServiceSet,
    Workspace,
)


def _source(path: Path) -> Path:
    path.write_text(
        "ATOMIC_SPECIES\nSi 28.085500 Si.upf\n\nLATTICE_CONSTANT\n1.0\n"
        "LATTICE_CONSTANT_UNIT\nAngstrom\n\nLATTICE_VECTORS\n"
        "8.3004 0.0 0.0\n0.0 8.3004 0.0\n0.0 0.0 25.362243471279523\n\n"
        "ATOMIC_POSITIONS\nDirect\nSi\n0.0\n1\n0.0 0.0 0.0 m 1 1 1\n",
        encoding="utf-8",
    )
    return path


def _request(cls: type, operation: str, workspace: str = "md", **kwargs: object) -> object:
    return cls(
        operation_id=f"123e4567-e89b-42d3-a456-426614174{operation}",
        workspace_rel=workspace,
        capability="md",
        **kwargs,
    )


def test_md_service_set_prepares_md_with_default_profile_and_assets(tmp_path: Path) -> None:
    source = _source(tmp_path / "md-source.STRU")
    pseudo = tmp_path / "Si.upf"
    pseudo.write_text("pseudo", encoding="utf-8")
    workspace = Workspace(tmp_path / "md")
    workspace.ensure_layout()
    source.rename(workspace.root / "source.STRU")
    services = MdServiceSet.default(workspace_root=tmp_path)

    result = services.prepare.prepare(_request(
        MdPrepareRequest, "101", structure_path_rel="source.STRU",
        pseudo_sources={"Si": str(pseudo)},
    ))

    assert isinstance(result, OperationOutcome)
    assert "calculation md" in (workspace.inputs_dir / "INPUT").read_text()
    assert "md_type nve" in (workspace.inputs_dir / "INPUT").read_text()
    assert (workspace.inputs_dir / "Si.upf").read_text() == "pseudo"
    assert result.envelope.diagnostics["task"] == "md"
    assert result.envelope.status.scientific == "unassessed"
    event = json.loads((workspace.reports_dir / "events" / "123e4567-e89b-42d3-a456-426614174101-prepare.json").read_text())
    assert event["payload"] == result.to_dict()


def test_md_service_set_rejects_scf_and_scf_rejects_md_requests(tmp_path: Path) -> None:
    md = MdServiceSet.default(workspace_root=tmp_path)
    scf = ScfServiceSet.default(workspace_root=tmp_path)
    md_request = _request(MdExecuteRequest, "102", dry_run=True)
    scf_request = ScfExecuteRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174103",
        workspace_rel="scf",
        dry_run=True,
    )

    assert md.execute.execute(scf_request).error_class == "request.invalid"
    assert scf.execute.execute(md_request).error_class == "request.invalid"


def test_md_modify_and_collect_are_factual_and_unassessed(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "md")
    workspace.ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation md\nmd_type nve\n")
    workspace.write_text("inputs/STRU", "prepared\n")
    workspace.write_text("inputs/KPT", "prepared\n")
    output = workspace.outputs_dir / "OUT.ABACUS"
    output.mkdir(parents=True)
    (output / "running_md.log").write_text("TOTAL ENERGY = -4.2\nNORMAL END\n", encoding="utf-8")
    (workspace.outputs_dir / "MD_dump").write_text("STEP 1 TEMP 300 ETOT -4.2\n", encoding="utf-8")
    services = MdServiceSet.default(workspace_root=tmp_path)

    modified = services.modify.modify(_request(MdModifyRequest, "104", input_updates={"md_nstep": 20}))
    collected = services.collect.collect(_request(MdCollectRequest, "105"))

    assert isinstance(modified, OperationOutcome)
    assert isinstance(collected, OperationOutcome)
    assert modified.envelope.diagnostics["task"] == "md"
    assert collected.envelope.status.scientific == "unassessed"
    assert collected.envelope.metrics
    assert "trajectory" not in collected.to_dict()


def test_md_context_requires_matching_input_calculation(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "md")
    workspace.ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    services = MdServiceSet.default(workspace_root=tmp_path)

    result = services.collect.collect(_request(MdCollectRequest, "106"))

    assert result.error_class == "precondition.missing"
