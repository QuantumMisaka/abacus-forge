from __future__ import annotations
import stat
import uuid
import pytest
from pathlib import Path
from abacus_forge import AtstNebExecuteRequest, AtstNebPostprocessRequest, AtstNebPrepareRequest, AtstNebServiceSet, ForgeErrorEnvelope, OperationOutcome
from abacus_forge.discovery import request_schema_document

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
    p = pathlib.Path(args[args.index("--output-prefix") + 1]); p.parent.mkdir(parents=True, exist_ok=True); pathlib.Path(str(p)+".cif").write_text("post"); pathlib.Path(str(p)+".stru").write_text("post")
    if "no_stru" == "MODE_PLACEHOLDER": pathlib.Path(str(p)+".stru").unlink()
    if "--plot-label" in args: pathlib.Path(args[args.index("--plot-label") + 1] + ".pdf").write_text("plot")
    if "--write-latest" in args:
        q = pathlib.Path(args[args.index("--write-latest") + 1]); pathlib.Path(str(q)+".traj").write_text("traj"); pathlib.Path(str(q)+".extxyz").write_text("xyz")
    if "--write-neb-init-chain" in args: pathlib.Path(args[args.index("--write-neb-init-chain") + 1]).write_text("chain")
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

def test_prepare_anchors_relative_atst_path_to_calling_cwd(tmp_path: Path, monkeypatch) -> None:
    caller = tmp_path / "caller"
    caller.mkdir()
    bin_dir = caller / "bin"
    bin_dir.mkdir()
    fake = _fake_atst(caller)
    fake.rename(bin_dir / "atst")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "init.xyz").write_text("init")
    (workspace / "final.xyz").write_text("final")
    monkeypatch.chdir(caller)

    result = AtstNebServiceSet.default(
        workspace_root=workspace, atst_executable="bin/atst"
    ).prepare.prepare(
        AtstNebPrepareRequest(
            operation_id=_id(),
            workspace_rel=".",
            init_structure_path_rel="init.xyz",
            final_structure_path_rel="final.xyz",
            chain_path_rel="outputs/chain.traj",
        )
    )

    assert isinstance(result, OperationOutcome)
    assert result.status.execution == "completed"
    assert any(item.path_rel == "outputs/chain.traj" for item in result.envelope.artifacts)

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

def test_external_reports_directory_is_rejected_before_log_write(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("workflow: []")
    external = tmp_path.parent / f"{tmp_path.name}-external"
    external.mkdir()
    sentinel = external / "sentinel.log"
    sentinel.write_text("keep")
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "atst").symlink_to(external, target_is_directory=True)
    result = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable="/bin/true").execute.execute(
        AtstNebExecuteRequest(operation_id=_id(), workspace_rel=".", config_path_rel="config.yaml")
    )
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.path"
    assert sentinel.read_text() == "keep"
    assert not any(external.glob("*-stdout.log"))
    assert not any(external.glob("*-stderr.log"))

def test_log_symlink_cannot_overwrite_forge_manifest(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("workflow: []")
    reports = tmp_path / "reports" / "atst"
    reports.mkdir(parents=True)
    manifest = tmp_path / "reports" / "forge-workspace.json"
    manifest.write_text('{"schema_version":"forge.workspace/v1","workspace_rel":".","events":[],"sentinel":"keep"}')
    operation_id = _id()
    (reports / f"{operation_id}-stdout.log").symlink_to(manifest)
    result = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable="/bin/true").execute.execute(
        AtstNebExecuteRequest(operation_id=operation_id, workspace_rel=".", config_path_rel="config.yaml")
    )
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.path"
    assert '"sentinel":"keep"' in manifest.read_text()

def test_derived_output_symlink_cannot_overwrite_trajectory(tmp_path: Path) -> None:
    trajectory = tmp_path / "neb.traj"
    trajectory.write_text("keep trajectory")
    output_dir = tmp_path / "outputs" / "atst"
    output_dir.mkdir(parents=True)
    (output_dir / "neb-ts.cif").symlink_to(trajectory)
    result = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable="/bin/true").postprocess.postprocess(
        AtstNebPostprocessRequest(operation_id=_id(), workspace_rel=".", trajectory_path_rel="neb.traj", output_prefix="outputs/atst/neb-ts")
    )
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.invalid"
    assert trajectory.read_text() == "keep trajectory"

def test_derived_output_targets_must_not_alias_each_other(tmp_path: Path) -> None:
    (tmp_path / "neb.traj").write_text("trajectory")
    output_dir = tmp_path / "outputs" / "atst"
    output_dir.mkdir(parents=True)
    (output_dir / "neb-latest.traj").symlink_to(output_dir / "ts.cif")
    result = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable="/bin/true").postprocess.postprocess(
        AtstNebPostprocessRequest(operation_id=_id(), workspace_rel=".", trajectory_path_rel="neb.traj", output_prefix="outputs/atst/ts", write_latest=True)
    )
    assert isinstance(result, ForgeErrorEnvelope)
    assert result.error_class == "request.invalid"

def test_postprocess_cannot_overwrite_forge_audit_or_external_derived_targets(tmp_path: Path) -> None:
    (tmp_path / "neb.traj").write_text("trajectory")
    external = tmp_path.parent / f"{tmp_path.name}-derived-external"
    external.mkdir()
    sentinel = external / "sentinel.cif"
    sentinel.write_text("keep")
    service = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable="/bin/true")
    audit = service.postprocess.postprocess(AtstNebPostprocessRequest(operation_id=_id(), workspace_rel=".", trajectory_path_rel="neb.traj", summary_path_rel="reports/forge-workspace.json"))
    assert isinstance(audit, ForgeErrorEnvelope) and audit.error_class == "request.invalid"
    outputs = tmp_path / "outputs"
    outputs.mkdir()
    (outputs / "atst").symlink_to(external, target_is_directory=True)
    derived = service.postprocess.postprocess(AtstNebPostprocessRequest(operation_id=_id(), workspace_rel=".", trajectory_path_rel="neb.traj", output_prefix="outputs/atst/sentinel"))
    assert isinstance(derived, ForgeErrorEnvelope) and derived.error_class == "request.path"
    assert sentinel.read_text() == "keep"

def test_postprocess_rejects_trajectory_operation_log_collision(tmp_path: Path) -> None:
    op_id = _id(); log_rel = f"reports/atst/{op_id}-post-stdout.log"
    (tmp_path / log_rel).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / log_rel).write_text("input")
    result = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable="missing").postprocess.postprocess(
        AtstNebPostprocessRequest(operation_id=op_id, workspace_rel=".", trajectory_path_rel=log_rel))
    assert isinstance(result, ForgeErrorEnvelope) and result.error_class == "request.invalid"

def test_output_groups_and_optional_stru(tmp_path: Path) -> None:
    (tmp_path / "neb.traj").write_text("trajectory")
    service = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable=str(_fake_atst(tmp_path, "no_stru")))
    result = service.postprocess.postprocess(AtstNebPostprocessRequest(operation_id=_id(), workspace_rel=".", trajectory_path_rel="neb.traj", output_prefix="reports/custom/ts", plot=True))
    assert isinstance(result, OperationOutcome) and result.status.collection == "complete"
    assert any(item.path_rel == "reports/custom/ts.cif" for item in result.envelope.artifacts)
    assert any(item.path_rel == "outputs/atst/nebplots_chain.pdf" for item in result.envelope.artifacts)

def test_missing_latest_extxyz_is_missing_output(tmp_path: Path) -> None:
    (tmp_path / "neb.traj").write_text("trajectory")
    fake = _fake_atst(tmp_path)
    fake.write_text(fake.read_text().replace('pathlib.Path(str(q)+".extxyz").write_text("xyz")', ''))
    result = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable=str(fake)).postprocess.postprocess(AtstNebPostprocessRequest(operation_id=_id(), workspace_rel=".", trajectory_path_rel="neb.traj", write_latest=True))
    assert isinstance(result, OperationOutcome) and result.status.collection == "missing_output"

def test_prepare_chain_collision_and_exact_output(tmp_path: Path) -> None:
    (tmp_path / "init").write_text("i"); (tmp_path / "final").write_text("f")
    op = _id(); log = f"reports/atst/{op}-stdout.log"
    bad = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable=str(_fake_atst(tmp_path))).prepare.prepare(AtstNebPrepareRequest(operation_id=op, workspace_rel=".", init_structure_path_rel="init", final_structure_path_rel="final", chain_path_rel="init"))
    assert isinstance(bad, ForgeErrorEnvelope)
    good = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable=str(_fake_atst(tmp_path))).prepare.prepare(AtstNebPrepareRequest(operation_id=_id(), workspace_rel=".", init_structure_path_rel="init", final_structure_path_rel="final", chain_path_rel="nested/chain.traj"))
    assert isinstance(good, OperationOutcome) and any(a.path_rel == "nested/chain.traj" for a in good.envelope.artifacts)

def test_execute_input_log_collision_is_rejected(tmp_path: Path) -> None:
    op = _id(); rel = f"reports/atst/{op}-stdout.log"; (tmp_path / rel).parent.mkdir(parents=True); (tmp_path / rel).write_text("x")
    result = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable="missing").execute.execute(AtstNebExecuteRequest(operation_id=op, workspace_rel=".", config_path_rel=rel))
    assert isinstance(result, ForgeErrorEnvelope) and result.error_class == "request.invalid"

def test_resolved_symlink_prefix_overlap_is_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real"; real.mkdir()
    try: (tmp_path / "alias").symlink_to(real, target_is_directory=True)
    except OSError: pytest.skip("symlinks unavailable")
    (tmp_path / "neb").write_text("x")
    result = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable="missing").postprocess.postprocess(AtstNebPostprocessRequest(operation_id=_id(), workspace_rel=".", trajectory_path_rel="neb", output_prefix="real/x", plot=True, plot_label="alias/x"))
    assert isinstance(result, ForgeErrorEnvelope) and result.error_class == "request.invalid"

def test_same_operation_id_conflicts_and_refs_are_one_to_one(tmp_path: Path) -> None:
    (tmp_path / "init").write_text("i"); (tmp_path / "final").write_text("f")
    service = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable=str(_fake_atst(tmp_path)))
    req = AtstNebPrepareRequest(operation_id=_id(), workspace_rel=".", init_structure_path_rel="init", final_structure_path_rel="final")
    first = service.prepare.prepare(req); second = service.prepare.prepare(req)
    assert isinstance(first, OperationOutcome) and isinstance(second, ForgeErrorEnvelope)
    assert second.error_class == "operation.conflict"
    (tmp_path / "neb.traj").write_text("x")
    post = service.postprocess.postprocess(AtstNebPostprocessRequest(operation_id=_id(), workspace_rel=".", trajectory_path_rel="neb.traj"))
    assert isinstance(post, OperationOutcome)
    refs = post.envelope.diagnostics["artifact_refs"]
    assert len(refs) == len(post.envelope.artifacts) == len({ref["artifact_id"] for ref in refs})
    assert {ref["artifact_id"] for ref in refs} == {item.id for item in post.envelope.artifacts}
    assert {ref["operation_id"] for ref in refs} == {post.operation_id}

def test_stale_output_does_not_count_but_overwrite_does(tmp_path: Path) -> None:
    (tmp_path / "neb.traj").write_text("x"); (tmp_path / "reports/atst").mkdir(parents=True)
    (tmp_path / "reports/atst/neb-summary.json").write_text("old"); (tmp_path / "outputs/atst/neb-ts.cif").parent.mkdir(parents=True); (tmp_path / "outputs/atst/neb-ts.cif").write_text("old")
    fake = _fake_atst(tmp_path); fake.write_text(fake.read_text().replace('p = pathlib.Path(args[args.index("--output") + 1]); p.parent.mkdir(parents=True, exist_ok=True); p.write_text("{}")', ''))
    stale = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable=str(fake)).postprocess.postprocess(AtstNebPostprocessRequest(operation_id=_id(), workspace_rel=".", trajectory_path_rel="neb.traj"))
    assert isinstance(stale, OperationOutcome) and stale.status.collection in {"missing_output", "partial"}
    fresh = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable=str(_fake_atst(tmp_path))).postprocess.postprocess(AtstNebPostprocessRequest(operation_id=_id(), workspace_rel=".", trajectory_path_rel="neb.traj"))
    assert isinstance(fresh, OperationOutcome) and fresh.status.collection == "complete"

def test_postprocess_init_chain_uses_exact_traj_path(tmp_path: Path) -> None:
    (tmp_path / "neb.traj").write_text("x")
    result = AtstNebServiceSet.default(workspace_root=tmp_path, atst_executable=str(_fake_atst(tmp_path))).postprocess.postprocess(
        AtstNebPostprocessRequest(operation_id=_id(), workspace_rel=".", trajectory_path_rel="neb.traj", write_neb_init_chain=True))
    assert isinstance(result, OperationOutcome) and result.status.collection == "complete"
    command = result.envelope.diagnostics["postprocess_command"]
    index = command.index("--write-neb-init-chain")
    assert command[index + 1] == str((tmp_path / "outputs/atst/neb-init-chain.traj").resolve())
    assert any(item.path_rel == "outputs/atst/neb-init-chain.traj" for item in result.envelope.artifacts)
    assert (tmp_path / "outputs/atst/neb-init-chain.traj").is_file()

def test_discovery_plot_label_condition_has_three_validated_branches() -> None:
    schema = request_schema_document("atst-neb", "postprocess")
    condition = schema["request_schema"]["allOf"][0]
    assert condition["if"]["required"] == ["plot_label"]
    assert condition["if"]["properties"]["plot_label"]["type"] == "string"
    assert condition["then"]["properties"]["plot"]["const"] is True
