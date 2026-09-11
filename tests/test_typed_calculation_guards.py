from __future__ import annotations

from pathlib import Path

from abacus_forge import ForgeServices, OperationOutcome, ScfServiceSet, Workspace
from abacus_forge.contracts import (
    ForgeErrorEnvelope,
    ScfCollectRequest,
    ScfExecuteRequest,
    ScfModifyRequest,
    ScfPrepareRequest,
)
from abacus_forge.discovery import request_schema_document
from abacus_forge.input_io import read_input


OPERATION_IDS = {
    "prepare": "123e4567-e89b-42d3-a456-426614174801",
    "modify": "123e4567-e89b-42d3-a456-426614174802",
    "execute": "123e4567-e89b-42d3-a456-426614174803",
    "collect": "123e4567-e89b-42d3-a456-426614174804",
}


def _workspace(root: Path, *, calculation: str | None = "scf", output: bool = False) -> Workspace:
    workspace = Workspace(root / "job")
    workspace.ensure_layout()
    if calculation is not None:
        workspace.write_text("inputs/INPUT", f"INPUT_PARAMETERS\ncalculation {calculation}\n")
        workspace.write_text("inputs/STRU", "ATOMIC_SPECIES\nSi 28.0855 Si_ONCV_PBE-1.0.upf\n")
        workspace.write_text("inputs/KPT", "K_POINTS\n0\nGamma\n1 1 1 0 0 0\n")
    if output:
        workspace.write_text("outputs/OUT.ABACUS/running_scf.log", "TOTAL ENERGY = -1.0\n")
    return workspace


def _request(operation: str, **kwargs: object):
    base = {
        "operation_id": OPERATION_IDS[operation],
        "workspace_rel": "job",
    }
    base.update(kwargs)
    request_type = {
        "prepare": ScfPrepareRequest,
        "modify": ScfModifyRequest,
        "execute": ScfExecuteRequest,
        "collect": ScfCollectRequest,
    }[operation]
    return request_type(**base)


def test_typed_scf_prepare_rejects_conflicting_calculation_before_admission(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path, calculation=None)
    source = workspace.root / "source.STRU"
    source.write_text("structure", encoding="utf-8")
    result = ScfServiceSet.default(workspace_root=tmp_path).prepare.prepare(
        _request("prepare", structure_path_rel="source.STRU", parameters={"calculation": "relax"})
    )
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.schema"
    assert not (workspace.reports_dir / "forge-workspace.json").exists()
    assert not (workspace.root / "forge-unit.json").exists()


def test_typed_scf_prepare_rejects_input_token_injection_before_admission(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path, calculation=None)
    source = workspace.root / "source.STRU"
    source.write_text("structure", encoding="utf-8")
    for parameter_id, parameters in (
        ("123e4567-e89b-42d3-a456-426614174809", {"calculation ": "scf"}),
        ("123e4567-e89b-42d3-a456-426614174810", {"suffix": "ABACUS\ncalculation relax"}),
        ("123e4567-e89b-42d3-a456-426614174812", {"calculation": "scf #comment"}),
    ):
        result = ScfServiceSet.default(workspace_root=tmp_path).prepare.prepare(
            ScfPrepareRequest(
                operation_id=parameter_id,
                workspace_rel="job",
                structure_path_rel="source.STRU",
                parameters=parameters,
            )
        )
        assert isinstance(result, ForgeErrorEnvelope)
        assert result.error_class == "request.schema"
        assert not (workspace.root / "forge-unit.json").exists()


def test_typed_scf_modify_rejects_rewrite_or_removal_before_input_mutation(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    before = (workspace.inputs_dir / "INPUT").read_text()
    services = ScfServiceSet.default(workspace_root=tmp_path)
    request = ScfModifyRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174805",
        workspace_rel="job",
        input_updates={"calculation": "relax"},
    )
    result = services.modify.modify(request)
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.schema"
    assert (workspace.inputs_dir / "INPUT").read_text() == before

    for operation_id, remove_parameters in (
        ("123e4567-e89b-42d3-a456-426614174813", ("ecutwfc ",)),
        ("123e4567-e89b-42d3-a456-426614174814", ("ecutwfc#comment",)),
    ):
        result = services.modify.modify(
            ScfModifyRequest(
                operation_id=operation_id,
                workspace_rel="job",
                remove_parameters=remove_parameters,
            )
        )
        assert isinstance(result, ForgeErrorEnvelope)
        assert result.error_class == "request.schema"
        assert (workspace.inputs_dir / "INPUT").read_text() == before

    injected = services.modify.modify(
        ScfModifyRequest(
            operation_id="123e4567-e89b-42d3-a456-426614174811",
            workspace_rel="job",
            input_updates={"suffix": "ABACUS\ncalculation relax"},
        )
    )
    assert isinstance(injected, ForgeErrorEnvelope)
    assert injected.error_class == "request.schema"
    assert (workspace.inputs_dir / "INPUT").read_text() == before
    assert not (workspace.reports_dir / "forge-workspace.json").exists()
    assert not (workspace.reports_dir / "claims").exists()
    assert not (workspace.reports_dir / "events").exists()

    result = services.modify.modify(
        ScfModifyRequest(
            operation_id="123e4567-e89b-42d3-a456-426614174806",
            workspace_rel="job",
            remove_parameters=("calculation",),
        )
    )
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.schema"
    assert (workspace.inputs_dir / "INPUT").read_text() == before

    same_profile = services.modify.modify(
        ScfModifyRequest(
            operation_id="123e4567-e89b-42d3-a456-426614174809",
            workspace_rel="job",
            input_updates={"calculation": "scf"},
        )
    )
    assert isinstance(same_profile, OperationOutcome)
    assert read_input(workspace.inputs_dir / "INPUT")["calculation"] == "scf"


def test_typed_scf_execute_and_collect_reject_mismatched_input(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path, calculation="relax", output=True)
    services = ScfServiceSet.default(workspace_root=tmp_path)
    execute = services.execute.execute(_request("execute", dry_run=True))
    collect = services.collect.collect(_request("collect"))
    assert isinstance(execute, ForgeErrorEnvelope)
    assert execute.error_class == "precondition.missing"
    assert isinstance(collect, ForgeErrorEnvelope)
    assert collect.error_class == "precondition.missing"


def test_typed_scf_modify_rejects_duplicate_existing_calculation_as_precondition(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\ncalculation relax\n")
    result = ScfServiceSet.default(workspace_root=tmp_path).modify.modify(
        ScfModifyRequest(
            operation_id="123e4567-e89b-42d3-a456-426614174815",
            workspace_rel="job",
            input_updates={"ecutwfc": 80},
        )
    )
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "precondition.missing"
    assert "calculation relax" in (workspace.inputs_dir / "INPUT").read_text()


def test_typed_scf_collect_allows_external_output_only_workspace(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path, calculation=None, output=True)
    result = ScfServiceSet.default(workspace_root=tmp_path).collect.collect(_request("collect"))
    assert isinstance(result, OperationOutcome)


def test_scf_compatibility_facade_keeps_permissive_input_behavior(tmp_path: Path) -> None:
    _workspace(tmp_path, calculation="relax", output=True)
    result = ForgeServices.default(workspace_root=tmp_path).collect_scf(_request("collect"))
    assert isinstance(result, OperationOutcome)


def test_scf_compatibility_facade_keeps_calculation_rewrite_and_removal(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    facade = ForgeServices.default(workspace_root=tmp_path)
    rewritten = facade.modify_scf(
        ScfModifyRequest(
            operation_id="123e4567-e89b-42d3-a456-426614174807",
            workspace_rel="job",
            input_updates={"calculation": "relax"},
        )
    )
    assert isinstance(rewritten, OperationOutcome)
    assert read_input(workspace.inputs_dir / "INPUT")["calculation"] == "relax"

    removed = facade.modify_scf(
        ScfModifyRequest(
            operation_id="123e4567-e89b-42d3-a456-426614174808",
            workspace_rel="job",
            remove_parameters=("calculation",),
        )
    )
    assert isinstance(removed, OperationOutcome)
    assert "calculation" not in read_input(workspace.inputs_dir / "INPUT")


def test_scf_discovery_freezes_calculation_profile() -> None:
    prepare = request_schema_document("scf", "prepare")["request_schema"]
    modify = request_schema_document("scf", "modify")["request_schema"]
    assert prepare["properties"]["parameters"]["properties"]["calculation"] == {
        "type": "string", "const": "scf"
    }
    assert modify["properties"]["input_updates"]["properties"]["calculation"] == {
        "type": "string", "const": "scf"
    }
    assert modify["properties"]["input_updates"]["propertyNames"]["pattern"] == r"^[^\s#]+$"
    assert prepare["properties"]["parameters"]["propertyNames"]["pattern"] == r"^[^\s#]+$"
    assert modify["properties"]["remove_parameters"]["items"]["not"] == {"const": "calculation"}
    assert modify["properties"]["remove_parameters"]["items"]["pattern"] == r"^[^\s#]+$"
