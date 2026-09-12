from __future__ import annotations

import io
import json
from pathlib import Path

from abacus_forge import (
    BandPostprocessRequest,
    ForgeResultEnvelope,
    OperationOutcome,
    OperationStatus,
    PostprocessServiceSet,
)
from abacus_forge.band_data import write_sample_band_artifacts
from abacus_forge.machine_cli import run_machine_cli
from tests.support.process import run_cli


def _payload(operation_id: str, *, workspace_rel: str = "job") -> dict[str, object]:
    return {
        "schema_version": "forge.request/v1",
        "capability": "band",
        "operation": "postprocess",
        "operation_id": operation_id,
        "workspace_rel": workspace_rel,
        "source_paths_rel": ["inputs/BANDS_1.dat"],
        "output_dir_rel": "outputs/postprocess",
        "plot_emin": -2.0,
        "plot_emax": 2.0,
        "save_data": True,
        "save_plot": False,
    }


def _workspace(root: Path) -> None:
    job = root / "job"
    job.mkdir(parents=True)
    write_sample_band_artifacts(job / "inputs", include_plot=False)


def _normalize(value: object, *, operation_id: str, root: Path) -> object:
    if isinstance(value, str):
        return value.replace(operation_id, "<operation-id>").replace(str(root), "<workspace-root>")
    if isinstance(value, list):
        return [_normalize(item, operation_id=operation_id, root=root) for item in value]
    if isinstance(value, dict):
        return {key: _normalize(item, operation_id=operation_id, root=root) for key, item in value.items()}
    return value


def test_machine_cli_defaults_band_service_and_returns_one_envelope(tmp_path: Path) -> None:
    _workspace(tmp_path)
    request = _payload("123e4567-e89b-42d3-a456-426614174320")

    process = run_cli(
        "operation",
        "postprocess",
        "--stdin",
        cwd=tmp_path,
        input_text=json.dumps(request),
    )

    assert process.returncode == 0, process.stdout + process.stderr
    assert process.stderr == ""
    result = json.loads(process.stdout)
    assert result["envelope"]["operation"] == "postprocess"
    assert result["envelope"]["status"] == {
        "execution": "not_run",
        "scientific": "unassessed",
        "collection": "complete",
    }
    assert result["envelope"]["artifacts"]
    assert len(list((tmp_path / "job/reports/events").glob("*.json"))) == 1


def test_machine_cli_postprocess_matches_direct_service_facts_in_isolated_workspace(tmp_path: Path) -> None:
    api_root, cli_root = tmp_path / "api", tmp_path / "cli"
    _workspace(api_root)
    _workspace(cli_root)
    api_id = "123e4567-e89b-42d3-a456-426614174321"
    cli_id = "123e4567-e89b-42d3-a456-426614174322"
    request = BandPostprocessRequest.from_dict(_payload(api_id))
    direct = PostprocessServiceSet.default(workspace_root=api_root).band.postprocess(request)
    assert isinstance(direct, OperationOutcome)

    process = run_cli(
        "operation",
        "postprocess",
        "--stdin",
        cwd=cli_root,
        input_text=json.dumps(_payload(cli_id)),
    )

    assert process.returncode == 0, process.stdout + process.stderr
    machine = OperationOutcome.from_dict(json.loads(process.stdout))
    assert _normalize(machine.to_dict(), operation_id=cli_id, root=cli_root) == _normalize(
        direct.to_dict(), operation_id=api_id, root=api_root
    )


class _InjectedPostprocess:
    def __init__(self) -> None:
        self.calls: list[object] = []

    def postprocess(self, request: object) -> OperationOutcome:
        self.calls.append(request)
        request_id = getattr(request, "operation_id")
        envelope = ForgeResultEnvelope(
            operation="postprocess",
            workspace_rel=".",
            status=OperationStatus(execution="completed", scientific="unassessed", collection="complete"),
        )
        return OperationOutcome(operation_id=request_id, envelope=envelope)


class _InjectedServices:
    def __init__(self) -> None:
        self.postprocess = _InjectedPostprocess()


def test_machine_cli_uses_only_injected_narrow_postprocess_service(tmp_path: Path) -> None:
    injected = _InjectedServices()
    stdout, stderr = io.StringIO(), io.StringIO()

    code = run_machine_cli(
        ["operation", "postprocess", "--stdin"],
        stdin=io.StringIO(json.dumps(_payload("123e4567-e89b-42d3-a456-426614174323"))),
        stdout=stdout,
        stderr=stderr,
        cwd=tmp_path,
        services=injected,
    )

    assert code == 0
    assert stderr.getvalue() == ""
    assert len(injected.postprocess.calls) == 1
    assert isinstance(injected.postprocess.calls[0], BandPostprocessRequest)
