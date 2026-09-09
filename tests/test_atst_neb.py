from __future__ import annotations
import stat
import uuid
from pathlib import Path
from abacus_forge import AtstNebExecuteRequest, AtstNebPostprocessRequest, AtstNebPrepareRequest, AtstNebServiceSet, ForgeErrorEnvelope, OperationOutcome

def _id() -> str: return str(uuid.uuid4())

def _fake_atst(tmp_path: Path, mode: str = "success") -> Path:
    script = tmp_path / "atst"
    script.write_text("""#!/usr/bin/env python3
import pathlib, sys, time
args = sys.argv[1:]
if "MODE_PLACEHOLDER" == "nonzero": raise SystemExit(7)
if "MODE_PLACEHOLDER" == "timeout": time.sleep(2)
if args[:2] == ["neb", "make"]:
    p = pathlib.Path(args[args.index("-o") + 1]); p.parent.mkdir(parents=True, exist_ok=True); p.write_text("chain")
if args[:2] == ["neb", "summary"]:
    p = pathlib.Path(args[args.index("--output") + 1]); p.parent.mkdir(parents=True, exist_ok=True); p.write_text("{}")
if args[:2] == ["neb", "post"]:
    p = pathlib.Path(args[args.index("--output-prefix") + 1]); p.parent.mkdir(parents=True, exist_ok=True); p.with_suffix(".cif").write_text("post"); p.with_suffix(".stru").write_text("post")
print("ok")
""".replace("MODE_PLACEHOLDER", mode), encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script

def test_prepare_persists_artifacts_and_unassessed_status(tmp_path: Path) -> None:
    (tmp_path / "init.xyz").write_text("init"); (tmp_path / "final.xyz").write_text("final")
    result = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable=str(_fake_atst(tmp_path))).prepare.prepare(
        AtstNebPrepareRequest(operation_id=_id(), workspace_rel=".", init_structure_path_rel="init.xyz", final_structure_path_rel="final.xyz"))
    assert isinstance(result, OperationOutcome); assert result.status.execution == "completed"; assert result.status.scientific == "unassessed"
    assert any(item.role == "output" for item in result.envelope.artifacts)
    assert (tmp_path / "reports/forge-workspace.json").is_file()

def test_execute_dry_run_and_postprocess(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("workflow: []"); (tmp_path / "neb.traj").write_text("trajectory")
    services = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable=str(_fake_atst(tmp_path)))
    execute = services.execute.execute(AtstNebExecuteRequest(operation_id=_id(), workspace_rel=".", config_path_rel="config.yaml", dry_run=True, check_input=True))
    assert isinstance(execute, OperationOutcome) and execute.status.scientific == "unassessed"
    post = services.postprocess.postprocess(AtstNebPostprocessRequest(operation_id=_id(), workspace_rel=".", trajectory_path_rel="neb.traj"))
    assert isinstance(post, OperationOutcome) and post.status.collection == "complete"

def test_missing_precondition_and_executable_are_frozen_errors(tmp_path: Path) -> None:
    request = AtstNebPrepareRequest(operation_id=_id(), workspace_rel=".", init_structure_path_rel="missing", final_structure_path_rel="final")
    missing = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable="does-not-exist").prepare.prepare(request)
    assert isinstance(missing, ForgeErrorEnvelope); assert missing.error_class == "precondition.missing"

def test_nonzero_and_timeout_are_failed_outcomes(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("workflow: []")
    failed = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable=str(_fake_atst(tmp_path, "nonzero"))).execute.execute(
        AtstNebExecuteRequest(operation_id=_id(), workspace_rel=".", config_path_rel="config.yaml"))
    assert isinstance(failed, OperationOutcome) and failed.status.execution == "failed"
    timed = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable=str(_fake_atst(tmp_path, "timeout"))).execute.execute(
        AtstNebExecuteRequest(operation_id=_id(), workspace_rel=".", config_path_rel="config.yaml", timeout_seconds=0.05))
    assert isinstance(timed, OperationOutcome) and timed.status.execution == "failed"

def test_postprocess_rejects_overlapping_prefixes_and_log_summary(tmp_path: Path) -> None:
    (tmp_path / "neb.traj").write_text("trajectory")
    service = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable=str(_fake_atst(tmp_path)))
    overlap = service.postprocess.postprocess(AtstNebPostprocessRequest(operation_id=_id(), workspace_rel=".", trajectory_path_rel="neb.traj", output_prefix="reports/custom/x", plot=True, plot_label="reports/custom/x.pdf"))
    assert isinstance(overlap, ForgeErrorEnvelope) and overlap.error_class == "request.invalid"
    op_id = _id()
    collision = service.postprocess.postprocess(AtstNebPostprocessRequest(operation_id=op_id, workspace_rel=".", trajectory_path_rel="neb.traj", summary_path_rel=f"reports/atst/{op_id}-summary-stdout.log"))
    assert isinstance(collision, ForgeErrorEnvelope) and collision.error_class == "request.invalid"

def test_missing_executable_is_precondition_after_inputs_exist(tmp_path: Path) -> None:
    (tmp_path / "neb.traj").write_text("trajectory")
    result = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable="missing-atst").postprocess.postprocess(
        AtstNebPostprocessRequest(operation_id=_id(), workspace_rel=".", trajectory_path_rel="neb.traj"))
    assert isinstance(result, ForgeErrorEnvelope) and result.error_class == "precondition.missing"
