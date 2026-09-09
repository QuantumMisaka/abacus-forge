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
    @classmethod
    def contained_log_path(cls, workspace: Workspace, operation_id: str, stream: str) -> Path:
        """Resolve the log directory and final file before creating or writing it."""
        cls.ensure_target(workspace, workspace.root / "reports/atst", "reports_dir")
        return cls.ensure_output_target(workspace, workspace.root / f"reports/atst/{operation_id}-{stream}.log", "reports_log")
    @staticmethod
    def ensure_target(workspace: Workspace, value: str | Path, field: str) -> Path:
        candidate = Path(value)
        if not candidate.is_absolute(): candidate = workspace.root / candidate
        resolved = candidate.resolve(strict=False)
        try: resolved.relative_to(workspace.root)
        except ValueError as error: raise ForgePathError(f"{field} must remain under workspace_rel") from error
        return resolved
    @classmethod
    def ensure_output_target(cls, workspace: Workspace, value: str | Path, field: str) -> Path:
        resolved = cls.ensure_target(workspace, value, field)
        reserved_files = ("reports/forge-workspace.json", "reports/.forge-workspace.lock", "reports/.forge-operation.lock")
        reserved_dirs = ("reports/events", "reports/claims")
        if any(resolved == (workspace.root / item).resolve(strict=False) for item in reserved_files):
            raise ForgePathError(f"{field} must not overwrite Forge audit paths")
        for item in reserved_dirs:
            try:
                resolved.relative_to((workspace.root / item).resolve(strict=False))
            except ValueError:
                continue
            raise ForgePathError(f"{field} must not overwrite Forge audit paths")
        return resolved
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
        stdout_path = self.contained_log_path(workspace, operation_id, "stdout")
        stderr_path = self.contained_log_path(workspace, operation_id, "stderr")
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(command, cwd=workspace.root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
            rc, stdout, stderr, timed_out = result.returncode, result.stdout, result.stderr, False
        except subprocess.TimeoutExpired as error:
            stdout = error.stdout.decode(errors="replace") if isinstance(error.stdout, bytes) else (error.stdout or "")
            stderr = error.stderr.decode(errors="replace") if isinstance(error.stderr, bytes) else (error.stderr or "")
            rc, timed_out = 124, True
        # Re-resolve immediately before writing so a pre-existing symlink cannot
        # redirect the log write outside the admitted workspace.
        stdout_path = self.contained_log_path(workspace, operation_id, "stdout")
        stderr_path = self.contained_log_path(workspace, operation_id, "stderr")
        stdout_path.write_text(stdout, encoding="utf-8")
        stderr_path.write_text(stderr, encoding="utf-8")
        return rc, stdout, stderr, timed_out
    def make_error(self, request: object, error: Exception) -> ForgeErrorEnvelope:
        return _ScfServiceContext(workspace_root=self.workspace_root).error_from_exception(error, request)
    def persist(self, workspace: Workspace, request: object, envelope: ForgeResultEnvelope, token: str) -> OperationOutcome:
        envelope = _with_artifact_refs(envelope, request.operation_id)
        outcome = OperationOutcome(request.operation_id, envelope, _observations(envelope))
        workspace.append_claimed_v1_operation_event(request.operation_id, envelope.operation, outcome.to_dict(), owner_token=token)
        return outcome

    @staticmethod
    def matches_prefix(path: Path, prefix: Path) -> bool:
        return path == prefix or (path.parent == prefix.parent and path.name.startswith(prefix.name + "."))

    @staticmethod
    def suffixed(prefix: Path, suffix: str) -> Path:
        return Path(str(prefix) + suffix)

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
            self._context.ensure_target(workspace, workspace.root / "reports/forge-workspace.json", "forge audit path")
            init = self._context.path(workspace, request.init_structure_path_rel, "init_structure_path_rel")
            final = self._context.path(workspace, request.final_structure_path_rel, "final_structure_path_rel")
            chain = self._context.path(workspace, request.chain_path_rel, "chain_path_rel")
            self._context.ensure_output_target(workspace, chain, "chain_path_rel")
            logs = {workspace.root / "reports/atst" / f"{request.operation_id}-{stream}.log" for stream in ("stdout", "stderr")}
            if any(path.resolve() in {item.resolve() for item in logs} for path in (init, final, chain)):
                return _ScfServiceContext.error("request.invalid", "prepare path collides with operation log", request)
            if chain.resolve() in {init.resolve(), final.resolve()}:
                return _ScfServiceContext.error("request.invalid", "chain path collides with structure input", request)
            with workspace.operation_guard(request.operation_id, "prepare") as token:
                self._context.require_file(init, request.init_structure_path_rel, "init_structure_path_rel")
                self._context.require_file(final, request.final_structure_path_rel, "final_structure_path_rel")
                chain.parent.mkdir(parents=True, exist_ok=True)
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
            workspace = self._context.workspace(request.workspace_rel); self._context.ensure_target(workspace, workspace.root / "reports/forge-workspace.json", "forge audit path"); config = self._context.path(workspace, request.config_path_rel, "config_path_rel")
            logs = {workspace.root / "reports/atst" / f"{request.operation_id}-{stream}.log" for stream in ("stdout", "stderr")}
            if config.resolve() in {item.resolve() for item in logs}:
                return _ScfServiceContext.error("request.invalid", "execute path collides with operation log", request)
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
    @staticmethod
    def _prefixes_overlap(left: Path, right: Path) -> bool:
        return left == right or left.parent == right.parent and (left.name.startswith(right.name + ".") or right.name.startswith(left.name + "."))
    def postprocess(self, request: AtstNebPostprocessRequest) -> ServiceResult:
        if not isinstance(request, AtstNebPostprocessRequest):
            return _ScfServiceContext.error("request.invalid", "expected AtstNebPostprocessRequest", None)
        requested = [Path(request.output_prefix)]
        if request.write_latest: requested.append(Path("outputs/atst/neb-latest"))
        if request.write_neb_init_chain: requested.append(Path("outputs/atst/neb-init-chain.traj"))
        if request.plot: requested.append(Path(request.plot_label or "outputs/atst/nebplots_chain"))
        if any(self._prefixes_overlap(left, right) for i, left in enumerate(requested) for right in requested[i + 1:]):
            return _ScfServiceContext.error("request.invalid", "postprocess output prefixes must not overlap", request)
        if any(self._context.matches_prefix(Path(request.summary_path_rel), item) for item in requested):
            return _ScfServiceContext.error("request.invalid", "summary_path_rel overlaps output prefix", request)
        try:
            workspace = self._context.workspace(request.workspace_rel)
            self._context.ensure_target(workspace, workspace.root / "reports/forge-workspace.json", "forge audit path")
            trajectory = self._context.path(workspace, request.trajectory_path_rel, "trajectory_path_rel")
            summary = self._context.path(workspace, request.summary_path_rel, "summary_path_rel")
            prefix = self._context.path(workspace, request.output_prefix, "output_prefix")
            log_paths = {workspace.root / "reports/atst" / f"{request.operation_id}-{suffix}-{stream}.log" for suffix in ("summary", "post") for stream in ("stdout", "stderr")}
            prefix_paths = [prefix]
            if request.write_latest: prefix_paths.append(self._context.path(workspace, "outputs/atst/neb-latest", "write_latest"))
            if request.write_neb_init_chain: prefix_paths.append(self._context.path(workspace, "outputs/atst/neb-init-chain.traj", "write_neb_init_chain"))
            if request.plot: prefix_paths.append(self._context.path(workspace, request.plot_label or "outputs/atst/nebplots_chain", "plot_label"))
            resolved_prefixes = [item.resolve() for item in prefix_paths]
            if any(self._prefixes_overlap(left, right) for i, left in enumerate(resolved_prefixes) for right in resolved_prefixes[i + 1:]):
                return _ScfServiceContext.error("request.invalid", "postprocess output prefixes must not overlap", request)
            if summary.resolve() == trajectory.resolve() or any(path.resolve() in {item.resolve() for item in log_paths} for path in (summary, trajectory)) or any(self._context.matches_prefix(path, item) for path in (summary, trajectory) for item in prefix_paths):
                return _ScfServiceContext.error("request.invalid", "postprocess input/output paths collide", request)
            if summary.resolve() == (workspace.root / "reports/forge-workspace.json").resolve():
                return _ScfServiceContext.error("request.invalid", "summary_path_rel collides with Forge audit path", request)
            self._context.ensure_output_target(workspace, summary, "summary_path_rel")
            expected_targets = [self._context.suffixed(prefix, suffix) for prefix in (prefix,) for suffix in (".cif", ".stru")]
            if request.write_latest: expected_targets.extend((workspace.root / "outputs/atst/neb-latest.traj", workspace.root / "outputs/atst/neb-latest.extxyz"))
            if request.write_neb_init_chain: expected_targets.append(workspace.root / "outputs/atst/neb-init-chain.traj")
            if request.plot: expected_targets.append(self._context.suffixed(self._context.path(workspace, request.plot_label or "outputs/atst/nebplots_chain", "plot_label"), ".pdf"))
            protected_targets = {trajectory.resolve(), summary.resolve(), *(path.resolve() for path in log_paths)}
            resolved_expected_targets = []
            for target in expected_targets:
                resolved_target = self._context.ensure_output_target(workspace, target, "postprocess output")
                resolved_expected_targets.append(resolved_target)
                if resolved_target in protected_targets:
                    return _ScfServiceContext.error("request.invalid", "postprocess output collides with protected workspace path", request)
            if len(resolved_expected_targets) != len(set(resolved_expected_targets)):
                return _ScfServiceContext.error("request.invalid", "postprocess output targets must be distinct", request)
            with workspace.operation_guard(request.operation_id, "postprocess") as token:
                self._context.require_file(trajectory, request.trajectory_path_rel, "trajectory_path_rel")
                executable = self._context.executable()
                before_outputs = {p.resolve(): (p.stat().st_size, p.stat().st_mtime_ns) for p in workspace.root.rglob("*") if p.is_file()}
                summary.parent.mkdir(parents=True, exist_ok=True)
                prefix.parent.mkdir(parents=True, exist_ok=True)
                summary_cmd = [executable, "neb", "summary", str(trajectory), "--format", "json", "--output", str(summary)]
                if request.n_max:
                    summary_cmd[4:4] = ["--n-max", str(request.n_max)]
                rc1, _, err1, timeout1 = self._context.run(workspace, summary_cmd, request.operation_id + "-summary", None)
                post_before = {p.resolve(): (p.stat().st_size, p.stat().st_mtime_ns) for p in workspace.root.rglob("*") if p.is_file()}
                post_cmd, rc2, err2, timeout2 = [], 0, "", False
                if rc1 == 0 and not timeout1:
                    post_cmd = [executable, "neb", "post", str(trajectory), "--output-prefix", str(prefix)]
                    if request.write_latest:
                        latest = self._context.path(workspace, "outputs/atst/neb-latest", "write_latest")
                        latest.parent.mkdir(parents=True, exist_ok=True)
                        post_cmd += ["--write-latest", str(latest)]
                    if request.write_neb_init_chain:
                        chain = self._context.path(workspace, "outputs/atst/neb-init-chain.traj", "write_neb_init_chain")
                        chain.parent.mkdir(parents=True, exist_ok=True)
                        post_cmd += ["--write-neb-init-chain", str(chain)]
                    for flag, value in (("--plot", request.plot), ("--energy-profile", request.energy_profile), ("--vib-analysis", request.vib_analysis), ("--strict-band", request.strict_band)):
                        if value: post_cmd.append(flag)
                    plot_prefix = self._context.path(workspace, request.plot_label or "outputs/atst/nebplots_chain", "plot_label")
                    plot_prefix.parent.mkdir(parents=True, exist_ok=True)
                    if request.plot: post_cmd += ["--plot-label", str(plot_prefix)]
                    if request.plot_label:
                        plot_prefix.parent.mkdir(parents=True, exist_ok=True)
                    if request.n_max: post_cmd += ["--n-max", str(request.n_max)]
                    post_cmd += ["--vib-thr", str(request.vib_thr)]
                    rc2, _, err2, timeout2 = self._context.run(workspace, post_cmd, request.operation_id + "-post", None)
                rc = rc1 if rc1 != 0 or timeout1 else rc2
                summary_key = summary.resolve()
                summary_changed = summary.is_file() and (summary_key not in before_outputs or (summary.stat().st_size, summary.stat().st_mtime_ns) != before_outputs[summary_key])
                logs = [("summary_stdout", f"reports/atst/{request.operation_id}-summary-stdout.log", "output"), ("summary_stderr", f"reports/atst/{request.operation_id}-summary-stderr.log", "output"), ("post_stdout", f"reports/atst/{request.operation_id}-post-stdout.log", "output"), ("post_stderr", f"reports/atst/{request.operation_id}-post-stderr.log", "output")]
                entries = [("trajectory", request.trajectory_path_rel, "input"), *([("summary", request.summary_path_rel, "output")] if summary_changed else []), *logs]
                prefixes = [prefix]
                if request.write_latest: prefixes.append(workspace.root / "outputs/atst/neb-latest")
                if request.write_neb_init_chain: prefixes.append(workspace.root / "outputs/atst/neb-init-chain.traj")
                if request.plot: prefixes.append(self._context.path(workspace, request.plot_label or "outputs/atst/nebplots_chain", "plot_label"))
                changed_outputs: dict[Path, list[Path]] = {item.resolve(): [] for item in prefixes}
                for candidate in sorted(workspace.root.rglob("*")):
                    key = candidate.resolve()
                    changed = candidate.is_file() and key not in {item.resolve() for item in log_paths} and (key not in post_before or (candidate.stat().st_size, candidate.stat().st_mtime_ns) != post_before[key])
                    if changed and any(self._context.matches_prefix(key, item.resolve()) for item in prefixes):
                        rel = candidate.relative_to(workspace.root).as_posix()
                        entries.append((f"atst-{hashlib.sha256(rel.encode()).hexdigest()[:12]}", rel, "output"))
                        for item in prefixes:
                            if self._context.matches_prefix(key, item.resolve()):
                                changed_outputs[item.resolve()].append(key)
                artifacts = self._context.artifacts(workspace, entries)
                required = [self._context.suffixed(prefix, ".cif")]
                if request.write_latest: required += [workspace.root / "outputs/atst/neb-latest.traj", workspace.root / "outputs/atst/neb-latest.extxyz"]
                if request.write_neb_init_chain: required.append(workspace.root / "outputs/atst/neb-init-chain.traj")
                if request.plot: required.append(self._context.suffixed(self._context.path(workspace, request.plot_label or "outputs/atst/nebplots_chain", "plot_label"), ".pdf"))
                output_exists = all(path.is_file() and (path.resolve() not in post_before or (path.stat().st_size, path.stat().st_mtime_ns) != post_before[path.resolve()]) for path in required)
                collection = "complete" if rc == 0 and summary_changed and output_exists else ("missing_output" if rc == 0 else "partial")
                envelope = ForgeResultEnvelope("postprocess", request.workspace_rel, _status(rc, timeout1 or timeout2, collection=collection), artifacts=artifacts, diagnostics={"summary_command": summary_cmd, "postprocess_command": post_cmd, "returncode": rc, "stderr": "\n".join(x for x in (err1, err2) if x), "summary_returncode": rc1, "postprocess_returncode": rc2})
                return self._context.persist(workspace, request, envelope, token)
        except Exception as error: return self._context.make_error(request, error)

class AtstNebServiceSet:
    def __init__(self, *, workspace_root: str | Path = ".", atst_executable: str = "atst") -> None:
        context = _AtstContext(workspace_root, atst_executable)
        self.prepare = AtstNebPrepareService(context); self.execute = AtstNebExecuteService(context); self.postprocess = AtstNebPostprocessService(context)
    @classmethod
    def default(cls, workspace_root: str | Path = ".", atst_executable: str = "atst") -> "AtstNebServiceSet":
        return cls(workspace_root=workspace_root, atst_executable=atst_executable)
