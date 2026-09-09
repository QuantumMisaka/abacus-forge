"""Optional ATST-tools NEB adapter."""
from __future__ import annotations
import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Protocol
from abacus_forge.contracts import ArtifactRecord, AtstNebExecuteRequest, AtstNebPostprocessRequest, AtstNebPrepareRequest, ForgeErrorEnvelope, ForgeResultEnvelope, OperationOutcome, OperationStatus
from abacus_forge.errors import ForgePathError, ForgePreconditionError
from abacus_forge.services import _ScfServiceContext, _observations, _with_artifact_refs
from abacus_forge.workspace import Workspace

ServiceResult = OperationOutcome | ForgeErrorEnvelope
class AtstNebPrepareServiceProtocol(Protocol):
    def prepare(self, request: AtstNebPrepareRequest) -> ServiceResult: ...
class AtstNebExecuteServiceProtocol(Protocol):
    def execute(self, request: AtstNebExecuteRequest) -> ServiceResult: ...
class AtstNebPostprocessServiceProtocol(Protocol):
    def postprocess(self, request: AtstNebPostprocessRequest) -> ServiceResult: ...

class _AtstContext:
    def __init__(self, workspace_root: str | Path = ".", atst_executable: str = "atst") -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.atst_executable = atst_executable
    def workspace(self, workspace_rel: str) -> Workspace:
        root = (self.workspace_root / workspace_rel).resolve()
        try: root.relative_to(self.workspace_root)
        except ValueError as error: raise ForgePathError("workspace_rel must remain under workspace_root") from error
        return Workspace(root)
    @staticmethod
    def path(workspace: Workspace, value: str, field: str) -> Path:
        candidate = (workspace.root / value).resolve()
        try: candidate.relative_to(workspace.root)
        except ValueError as error: raise ForgePathError(f"{field} must remain under workspace_rel") from error
        return candidate
    @staticmethod
    def require_file(path: Path, value: str, field: str) -> None:
        if not path.is_file(): raise ForgePreconditionError(f"{field} file not found: {value}")
    def executable(self) -> str:
        candidate = Path(self.atst_executable)
        if candidate.is_absolute():
            if candidate.is_file() and candidate.stat().st_mode & 0o111: return str(candidate)
        else:
            found = shutil.which(self.atst_executable)
            if found: return found
        raise ForgePreconditionError("configured atst executable is missing or not executable")
    @staticmethod
    def artifacts(workspace: Workspace, entries: list[tuple[str, str, str]]) -> tuple[ArtifactRecord, ...]:
        records, seen = [], set()
        for artifact_id, path_rel, role in entries:
            path = workspace.resolve_relative(path_rel)
            if not path.is_file() or path_rel in seen: continue
            seen.add(path_rel)
            records.append(ArtifactRecord(id=artifact_id, path_rel=path_rel, role=role, stage="atst-neb", sha256=hashlib.sha256(path.read_bytes()).hexdigest(), size_bytes=path.stat().st_size))
        return tuple(records)
    def run(self, workspace: Workspace, command: list[str], operation_id: str, timeout: float | None) -> tuple[int, str, str, bool]:
        reports = workspace.root / "reports" / "atst"; reports.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(command, cwd=workspace.root, capture_output=True, text=True, timeout=timeout, check=False)
            rc, stdout, stderr, timed_out = result.returncode, result.stdout, result.stderr, False
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout.decode() if isinstance(error.stdout, bytes) else (error.stdout or "")
            stderr = error.stderr.decode() if isinstance(error.stderr, bytes) else (error.stderr or "")
            rc, timed_out = 124, True
        (reports / f"{operation_id}-stdout.log").write_text(stdout, encoding="utf-8")
        (reports / f"{operation_id}-stderr.log").write_text(stderr, encoding="utf-8")
        return rc, stdout, stderr, timed_out
    def make_error(self, request: object, error: Exception) -> ForgeErrorEnvelope:
        return _ScfServiceContext(workspace_root=self.workspace_root).error_from_exception(error, request)
    def persist(self, workspace: Workspace, request: object, envelope: ForgeResultEnvelope, token: str) -> OperationOutcome:
        envelope = _with_artifact_refs(envelope, request.operation_id)
        outcome = OperationOutcome(request.operation_id, envelope, _observations(envelope))
        workspace.append_claimed_v1_operation_event(request.operation_id, envelope.operation, outcome.to_dict(), owner_token=token)
        return outcome

def _status(returncode: int, timed_out: bool, dry_run: bool = False, collection: str = "not_collected") -> OperationStatus:
    execution = "failed" if timed_out or returncode != 0 else ("skipped" if dry_run else "completed")
    return OperationStatus(execution=execution, scientific="unassessed", collection=collection)

class AtstNebPrepareService:
    def __init__(self, context: _AtstContext) -> None: self._context = context
    def prepare(self, request: AtstNebPrepareRequest) -> ServiceResult:
        if not isinstance(request, AtstNebPrepareRequest):
            return _ScfServiceContext.error("request.invalid", "expected AtstNebPrepareRequest", None)
        try:
            workspace = self._context.workspace(request.workspace_rel)
            init = self._context.path(workspace, request.init_structure_path_rel, "init_structure_path_rel")
            final = self._context.path(workspace, request.final_structure_path_rel, "final_structure_path_rel")
            chain = self._context.path(workspace, request.chain_path_rel, "chain_path_rel")
            with workspace.operation_guard(request.operation_id, "prepare") as token:
                self._context.require_file(init, request.init_structure_path_rel, "init_structure_path_rel")
                self._context.require_file(final, request.final_structure_path_rel, "final_structure_path_rel")
                command = [self._context.executable(), "neb", "make", str(init), str(final), str(request.n_images), "--method", request.method, "-o", str(chain)]
                if request.no_align: command.append("--no-align")
                rc, _, stderr, timeout = self._context.run(workspace, command, request.operation_id, None)
                logs = [("stdout_log", f"reports/atst/{request.operation_id}-stdout.log", "output"), ("stderr_log", f"reports/atst/{request.operation_id}-stderr.log", "output")]
                artifacts = self._context.artifacts(workspace, [("init", request.init_structure_path_rel, "input"), ("final", request.final_structure_path_rel, "input"), ("neb_chain", request.chain_path_rel, "output"), *logs])
                envelope = ForgeResultEnvelope("prepare", request.workspace_rel, _status(rc, timeout), artifacts=artifacts, diagnostics={"command": command, "returncode": rc, "stderr": stderr, "timed_out": timeout})
                return self._context.persist(workspace, request, envelope, token)
        except Exception as error: return self._context.make_error(request, error)

class AtstNebExecuteService:
    def __init__(self, context: _AtstContext) -> None: self._context = context
    def execute(self, request: AtstNebExecuteRequest) -> ServiceResult:
        if not isinstance(request, AtstNebExecuteRequest):
            return _ScfServiceContext.error("request.invalid", "expected AtstNebExecuteRequest", None)
        try:
            workspace = self._context.workspace(request.workspace_rel); config = self._context.path(workspace, request.config_path_rel, "config_path_rel")
            with workspace.operation_guard(request.operation_id, "execute") as token:
                self._context.require_file(config, request.config_path_rel, "config_path_rel")
                command = [self._context.executable(), "run", str(config)]
                if request.dry_run: command.append("--dry-run")
                if request.check_input: command.append("--check-input")
                command += ["--check-input-timeout", str(request.check_input_timeout)]
                if request.abacus_executable: command += ["--abacus-executable", request.abacus_executable]
                rc, _, stderr, timeout = self._context.run(workspace, command, request.operation_id, request.timeout_seconds)
                logs = [("stdout_log", f"reports/atst/{request.operation_id}-stdout.log", "output"), ("stderr_log", f"reports/atst/{request.operation_id}-stderr.log", "output")]
                artifacts = self._context.artifacts(workspace, [("config", request.config_path_rel, "input"), *logs])
                envelope = ForgeResultEnvelope("execute", request.workspace_rel, _status(rc, timeout, request.dry_run), artifacts=artifacts, diagnostics={"command": command, "returncode": rc, "stderr": stderr, "timed_out": timeout})
                return self._context.persist(workspace, request, envelope, token)
        except Exception as error: return self._context.make_error(request, error)

class AtstNebPostprocessService:
    def __init__(self, context: _AtstContext) -> None: self._context = context
    def postprocess(self, request: AtstNebPostprocessRequest) -> ServiceResult:
        if not isinstance(request, AtstNebPostprocessRequest):
            return _ScfServiceContext.error("request.invalid", "expected AtstNebPostprocessRequest", None)
        try:
            workspace = self._context.workspace(request.workspace_rel)
            trajectory = self._context.path(workspace, request.trajectory_path_rel, "trajectory_path_rel")
            summary = self._context.path(workspace, request.summary_path_rel, "summary_path_rel")
            prefix = self._context.path(workspace, request.output_prefix, "output_prefix")
            with workspace.operation_guard(request.operation_id, "postprocess") as token:
                self._context.require_file(trajectory, request.trajectory_path_rel, "trajectory_path_rel")
                executable = self._context.executable()
                summary_cmd = [executable, "neb", "summary", str(trajectory), "--format", "json", "--output", str(summary)]
                if request.n_max:
                    summary_cmd[4:4] = ["--n-max", str(request.n_max)]
                rc1, _, err1, timeout1 = self._context.run(workspace, summary_cmd, request.operation_id + "-summary", None)
                post_cmd, rc2, err2, timeout2 = [], 0, "", False
                if rc1 == 0 and not timeout1:
                    post_cmd = [executable, "neb", "post", str(trajectory), "--output-prefix", str(prefix)]
                    if request.write_latest:
                        post_cmd += ["--write-latest", str(self._context.path(workspace, "outputs/atst/neb-latest.traj", "write_latest"))]
                    if request.write_neb_init_chain:
                        post_cmd += ["--write-neb-init-chain", str(self._context.path(workspace, "outputs/atst/neb-init-chain.traj", "write_neb_init_chain"))]
                    for flag, value in (("--plot", request.plot), ("--energy-profile", request.energy_profile), ("--vib-analysis", request.vib_analysis), ("--strict-band", request.strict_band)):
                        if value: post_cmd.append(flag)
                    if request.plot_label: post_cmd += ["--plot-label", request.plot_label]
                    post_cmd += ["--vib-thr", str(request.vib_thr)]
                    rc2, _, err2, timeout2 = self._context.run(workspace, post_cmd, request.operation_id + "-post", None)
                rc = rc1 if rc1 != 0 or timeout1 else rc2
                logs = [("summary_stdout", f"reports/atst/{request.operation_id}-summary-stdout.log", "output"), ("summary_stderr", f"reports/atst/{request.operation_id}-summary-stderr.log", "output"), ("post_stdout", f"reports/atst/{request.operation_id}-post-stdout.log", "output"), ("post_stderr", f"reports/atst/{request.operation_id}-post-stderr.log", "output")]
                artifacts = self._context.artifacts(workspace, [("trajectory", request.trajectory_path_rel, "input"), ("summary", request.summary_path_rel, "output"), *logs])
                envelope = ForgeResultEnvelope("postprocess", request.workspace_rel, _status(rc, timeout1 or timeout2, collection="complete" if rc == 0 else "partial"), artifacts=artifacts, diagnostics={"summary_command": summary_cmd, "postprocess_command": post_cmd, "returncode": rc, "stderr": "\n".join(x for x in (err1, err2) if x), "summary_returncode": rc1, "postprocess_returncode": rc2})
                return self._context.persist(workspace, request, envelope, token)
        except Exception as error: return self._context.make_error(request, error)

class AtstNebServiceSet:
    def __init__(self, *, workspace_root: str | Path = ".", atst_executable: str = "atst") -> None:
        context = _AtstContext(workspace_root, atst_executable)
        self.prepare = AtstNebPrepareService(context); self.execute = AtstNebExecuteService(context); self.postprocess = AtstNebPostprocessService(context)
    @classmethod
    def default(cls, workspace_root: str | Path = ".", atst_executable: str = "atst") -> "AtstNebServiceSet":
        return cls(workspace_root=workspace_root, atst_executable=atst_executable)
