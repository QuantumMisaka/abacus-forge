"""Non-interactive, envelope-oriented command-line adapter for Forge v1."""

from __future__ import annotations

import argparse
import json
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TextIO
from typing import Sequence

from abacus_forge.contracts import (
    REQUEST_SCHEMA_VERSION,
    ForgeErrorEnvelope,
    OperationOutcome,
    ScfCollectRequest,
    ScfExecuteRequest,
    ScfModifyRequest,
    ScfPrepareRequest,
    AtstNebPrepareRequest,
    AtstNebExecuteRequest,
    AtstNebPostprocessRequest,
    canonical_relative_path,
)
from abacus_forge.discovery import capabilities_document, request_schema_document
from abacus_forge.errors import (
    ForgeInternalError,
    ForgePathError,
    ForgePersistenceError,
    ForgePreconditionError,
    ForgeRequestError,
    ForgeSchemaError,
    normalize_error_message,
    OperationConflictError,
)
from abacus_forge.services import MdServiceSet, ScfServiceSet, ServiceResult, RelaxServiceSet
from abacus_forge.md_contracts import MdCollectRequest, MdExecuteRequest, MdModifyRequest, MdPrepareRequest
from abacus_forge.postprocess_contracts import BandPostprocessRequest, DosPostprocessRequest
from abacus_forge.pyatb_contracts import (
    PyatbBandCollectRequest,
    PyatbBandExecuteRequest,
    PyatbBandPrepareRequest,
)
from abacus_forge.export_contracts import ExportRequest
from abacus_forge.postprocess_services import PostprocessServiceSet
from abacus_forge.atst_neb import AtstNebServiceSet
from abacus_forge.pyatb_services import PyatbBandServiceSet
from abacus_forge.relax_contracts import (
    RelaxCollectRequest,
    RelaxExecuteRequest,
    RelaxModifyRequest,
    RelaxPrepareRequest,
)


_SCF_DECODERS = {
    "prepare": ScfPrepareRequest.from_dict,
    "modify": ScfModifyRequest.from_dict,
    "execute": ScfExecuteRequest.from_dict,
    "collect": ScfCollectRequest.from_dict,
}
_ATST_NEB_DECODERS = {
    "prepare": AtstNebPrepareRequest.from_dict,
    "execute": AtstNebExecuteRequest.from_dict,
    "postprocess": AtstNebPostprocessRequest.from_dict,
}
_RELAX_DECODERS = {
    "prepare": RelaxPrepareRequest.from_dict,
    "modify": RelaxModifyRequest.from_dict,
    "execute": RelaxExecuteRequest.from_dict,
    "collect": RelaxCollectRequest.from_dict,
}
_MD_DECODERS = {
    "prepare": MdPrepareRequest.from_dict,
    "modify": MdModifyRequest.from_dict,
    "execute": MdExecuteRequest.from_dict,
    "collect": MdCollectRequest.from_dict,
}
_POSTPROCESS_DECODERS = {
    "band": {"postprocess": BandPostprocessRequest.from_dict},
    "dos": {"postprocess": DosPostprocessRequest.from_dict},
}
_PYATB_BAND_DECODERS = {
    "prepare": PyatbBandPrepareRequest.from_dict,
    "execute": PyatbBandExecuteRequest.from_dict,
    "collect": PyatbBandCollectRequest.from_dict,
}
_EXPORT_DECODERS = {"export": ExportRequest.from_dict}
_CAPABILITY_DECODERS = {
    "scf": _SCF_DECODERS,
    "relax": _RELAX_DECODERS,
    "cell-relax": _RELAX_DECODERS,
    "atst-neb": _ATST_NEB_DECODERS,
    "md": _MD_DECODERS,
    **_POSTPROCESS_DECODERS,
    "pyatb-band": _PYATB_BAND_DECODERS,
    "export": _EXPORT_DECODERS,
}
_RELAX_REQUEST_TYPES = (
    RelaxPrepareRequest,
    RelaxModifyRequest,
    RelaxExecuteRequest,
    RelaxCollectRequest,
)
_MD_REQUEST_TYPES = (MdPrepareRequest, MdModifyRequest, MdExecuteRequest, MdCollectRequest)
_MACHINE_OPERATIONS = ("prepare", "modify", "execute", "collect", "postprocess", "export")
_ERROR_EXIT_CODES = {
    "request.invalid": 2,
    "request.schema": 2,
    "request.path": 2,
    "operation.conflict": 2,
    "precondition.missing": 3,
    "persistence.failure": 5,
    "internal.failure": 5,
}


class _MachineUsageError(ForgeRequestError):
    """An argparse usage failure which must be returned as an envelope."""


class _MachineHelp(Exception):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text


class _HelpAction(argparse.Action):
    def __init__(self, option_strings: list[str], dest: str = argparse.SUPPRESS, **kwargs: Any) -> None:
        kwargs.setdefault("nargs", 0)
        kwargs.setdefault("default", argparse.SUPPRESS)
        super().__init__(option_strings, dest, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: str | None = None,
    ) -> None:
        del namespace, values, option_string
        raise _MachineHelp(parser.format_help())


class _MachineParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _MachineUsageError(message)


def build_machine_parser() -> argparse.ArgumentParser:
    """Build only the v1 machine command parser.

    The legacy parser is deliberately not imported or modified here.  This
    parser is suitable for the three commands routed by the public CLI in the
    following task, and is also directly usable by integrations.
    """
    parser = _MachineParser(prog="abacus-forge", add_help=False)
    parser.add_argument("-h", "--help", action=_HelpAction, help="show this help message and exit")
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=_MachineParser)

    operation = subparsers.add_parser("operation", add_help=False)
    operation.add_argument("-h", "--help", action=_HelpAction, help="show this help message and exit")
    operation.add_argument("operation", choices=_MACHINE_OPERATIONS)
    sources = operation.add_mutually_exclusive_group(required=True)
    sources.add_argument("--request", dest="request_file", metavar="FILE")
    sources.add_argument("--stdin", action="store_true")
    operation.add_argument("--format", choices=("json", "text"), default="json", dest="output_format")
    operation.add_argument("--pretty", action="store_true")

    capabilities = subparsers.add_parser("capabilities", add_help=False)
    capabilities.add_argument("-h", "--help", action=_HelpAction, help="show this help message and exit")
    schema = subparsers.add_parser("schema", add_help=False)
    schema.add_argument("-h", "--help", action=_HelpAction, help="show this help message and exit")
    schema.add_argument("capability")
    schema.add_argument("operation")
    return parser


def _reject_json_constant(value: str) -> Any:
    del value
    raise ValueError


def _parse_one_json(text: str) -> object:
    """Decode exactly one JSON value, allowing only trailing whitespace."""
    decoder = json.JSONDecoder(parse_constant=_reject_json_constant)
    start = len(text) - len(text.lstrip())
    value, end = decoder.raw_decode(text, start)
    if text[end:].strip():
        raise ValueError
    return value


def _read_request(args: argparse.Namespace, *, stdin: TextIO, cwd: Path) -> object:
    if args.request_file is not None:
        path = Path(args.request_file)
        if not path.is_absolute():
            path = cwd / path
        try:
            text = path.read_bytes().decode("utf-8")
        except OSError as error:
            raise ForgePathError("request source is not readable UTF-8") from error
        except UnicodeError as error:
            raise ForgeRequestError("request source is not valid UTF-8") from error
    else:
        try:
            text = stdin.read()
        except Exception as error:
            raise ForgeRequestError("request stdin is not readable") from error
    try:
        return _parse_one_json(text)
    except (TypeError, ValueError, UnicodeError) as error:
        raise ForgeRequestError("request source is not one valid JSON value") from error


def _safe_operation_id(payload: object) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    value = payload.get("operation_id")
    if not isinstance(value, str):
        return None
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        return None
    if parsed.version != 4 or str(parsed) != value:
        return None
    return value


def _safe_workspace_rel(payload: object) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    value = payload.get("workspace_rel")
    if not isinstance(value, str):
        return None
    try:
        canonical_relative_path(value)
    except ValueError:
        return None
    return value


def _error(
    error_class: str,
    message: str,
    payload: object = None,
    *,
    affected_fields: Sequence[str] = ("request",),
) -> ForgeErrorEnvelope:
    return ForgeErrorEnvelope(
        error_class=error_class,
        message=normalize_error_message(error_class, message),
        affected_fields=affected_fields,
        operation_id=_safe_operation_id(payload),
        workspace_rel=_safe_workspace_rel(payload),
    )


def _preflight(operation: str, payload: object) -> None:
    """Validate transport-level fields in stable, independent phases."""
    if not isinstance(payload, Mapping):
        raise ForgeRequestError("request must be a JSON object")
    if payload.get("schema_version") != REQUEST_SCHEMA_VERSION:
        raise ForgeSchemaError("request schema_version is unsupported")
    if payload.get("operation") != operation:
        raise ForgeRequestError("request operation does not match command")
    workspace_rel = payload.get("workspace_rel")
    if not isinstance(workspace_rel, str):
        raise ForgePathError("workspace_rel must be a canonical relative path")
    try:
        canonical_relative_path(workspace_rel)
    except ValueError as error:
        raise ForgePathError("workspace_rel must be a canonical relative path") from error


def _decode_request(operation: str, payload: object, decoders: Mapping[str, Any]):
    """Decode one supported SCF operation through its explicit typed decoder."""
    decoder = decoders.get(operation)
    if decoder is None:
        raise ForgeRequestError("operation is not implemented by the v1 machine adapter")
    _preflight(operation, payload)
    try:
        return decoder(payload)  # type: ignore[arg-type]
    except (ForgeRequestError, ForgePathError, ForgeSchemaError):
        raise
    except (TypeError, ValueError, KeyError) as error:
        raise ForgeSchemaError("request fields do not match the operation schema") from error


def decode_scf_request(operation: str, payload: object):
    """Decode one supported SCF operation through its explicit typed decoder."""
    return _decode_request(operation, payload, _SCF_DECODERS)


def decode_atst_neb_request(operation: str, payload: object):
    """Decode one ATST NEB operation through its explicit typed decoder."""
    if not isinstance(payload, Mapping) or payload.get("capability") != "atst-neb":
        raise ForgeRequestError("ATST NEB requests require capability='atst-neb'")
    return _decode_request(operation, payload, _ATST_NEB_DECODERS)


def decode_operation_request(operation: str, payload: object):
    """Decode one request using the explicit capability registry."""
    _preflight(operation, payload)
    capability = payload.get("capability", "scf")  # type: ignore[union-attr]
    if not isinstance(capability, str) or capability not in _CAPABILITY_DECODERS:
        raise ForgeRequestError("unknown capability")
    return _decode_request(operation, payload, _CAPABILITY_DECODERS[capability])


def _error_from_exception(error: Exception, payload: object) -> ForgeErrorEnvelope:
    if isinstance(error, ForgePathError):
        return _error("request.path", str(error), payload, affected_fields=("workspace_rel",))
    if isinstance(error, ForgeSchemaError):
        return _error("request.schema", str(error), payload)
    if isinstance(error, OperationConflictError):
        return _error("operation.conflict", str(error), payload, affected_fields=("operation_id",))
    if isinstance(error, ForgePreconditionError):
        return _error("precondition.missing", str(error), payload, affected_fields=("request",))
    if isinstance(error, ForgePersistenceError):
        return _error("persistence.failure", str(error), payload, affected_fields=("workspace_rel",))
    if isinstance(error, ForgeInternalError):
        return _error("internal.failure", str(error), payload)
    if isinstance(error, ForgeRequestError):
        return _error("request.invalid", str(error), payload)
    return _error("internal.failure", "unexpected Forge machine adapter failure", payload)


def _dispatch(operation: str, request: object, services: object) -> ServiceResult:
    service: object
    if operation == "postprocess" and isinstance(services, PostprocessServiceSet):
        if isinstance(request, BandPostprocessRequest):
            service = services.band
        elif isinstance(request, DosPostprocessRequest):
            service = services.dos
        else:
            service = services
    else:
        service = getattr(services, operation)
    method = getattr(service, operation)
    return method(request)


def exit_code_for(result: object) -> int:
    """Map a typed service result to the stable v1 process exit class."""
    if isinstance(result, ForgeErrorEnvelope):
        return _ERROR_EXIT_CODES[result.error_class]
    if isinstance(result, OperationOutcome):
        return 4 if result.status.execution == "failed" else 0
    return 5


def _to_dict(result: object) -> object:
    if isinstance(result, (ForgeErrorEnvelope, OperationOutcome)):
        return result.to_dict()
    if isinstance(result, Mapping):
        return dict(result)
    raise TypeError("machine result is not serializable")


def render_json(result: object, *, pretty: bool = False) -> str:
    """Render one result/document as canonical JSON with one trailing newline."""
    return json.dumps(
        _to_dict(result),
        allow_nan=False,
        sort_keys=True,
        indent=2 if pretty else None,
    ) + "\n"


def render_text(result: object) -> str:
    """Project the same envelope into a factual, non-interpretive text view."""
    payload = _to_dict(result)
    if not isinstance(payload, Mapping):
        return render_json(payload)

    lines = [f"schema_version: {payload.get('schema_version', '')}"]
    error = payload.get("error")
    if isinstance(error, Mapping):
        lines.append(f"error: {error.get('class', '')}")
        lines.append(f"message: {error.get('message', '')}")
        if payload.get("operation_id") is not None:
            lines.append(f"operation_id: {payload['operation_id']}")
        if payload.get("workspace_rel") is not None:
            lines.append(f"workspace_rel: {payload['workspace_rel']}")
        return "\n".join(lines) + "\n"

    envelope = payload.get("envelope")
    if isinstance(envelope, Mapping):
        lines.extend(
            [
                f"operation_id: {payload.get('operation_id', '')}",
                f"operation: {envelope.get('operation', '')}",
                f"workspace_rel: {envelope.get('workspace_rel', '')}",
            ]
        )
        status = envelope.get("status")
        if isinstance(status, Mapping):
            lines.append(f"execution: {status.get('execution', '')}")
            lines.append(f"collection: {status.get('collection', '')}")
        artifacts = envelope.get("artifacts")
        if isinstance(artifacts, Sequence) and not isinstance(artifacts, (str, bytes)):
            for artifact in artifacts:
                if isinstance(artifact, Mapping) and "path_rel" in artifact:
                    lines.append(f"artifact: {artifact['path_rel']}")
    return "\n".join(lines) + "\n"


def _render(result: object, *, output_format: str = "json", pretty: bool = False) -> str:
    if output_format == "text":
        return render_text(result)
    return render_json(result, pretty=pretty)


render_result = _render


def run_machine_cli(
    argv: Sequence[str],
    *,
    stdin: TextIO,
    stdout: TextIO,
    stderr: TextIO,
    cwd: Path,
    services: ScfServiceSet | RelaxServiceSet | MdServiceSet | PostprocessServiceSet | PyatbBandServiceSet | None = None,
    atst_services: AtstNebServiceSet | None = None,
    pyatb_services: PyatbBandServiceSet | None = None,
) -> int:
    """Run one non-interactive machine command and write one stdout document."""
    parser = build_machine_parser()
    try:
        args = parser.parse_args(list(argv))
    except _MachineHelp as help_message:
        stdout.write(help_message.text)
        return 0
    except _MachineUsageError as error:
        result = _error("request.invalid", str(error))
        stdout.write(render_json(result))
        return exit_code_for(result)

    if args.command == "capabilities":
        stdout.write(render_json(capabilities_document()))
        return 0
    if args.command == "schema":
        try:
            document = request_schema_document(args.capability, args.operation)
        except ForgeRequestError as error:
            result = _error_from_exception(error, None)
            stdout.write(render_json(result))
            return exit_code_for(result)
        stdout.write(render_json(document))
        return 0

    if args.output_format == "text" and args.pretty:
        result = _error(
            "request.invalid",
            "--pretty cannot be combined with --format text",
            affected_fields=("format", "pretty"),
        )
        stdout.write(_render(result, output_format=args.output_format))
        return exit_code_for(result)

    payload: object = None
    try:
        payload = _read_request(args, stdin=stdin, cwd=Path(cwd))
        request = decode_operation_request(args.operation, payload)
    except (ForgeRequestError, ForgePathError, ForgeSchemaError) as error:
        result = _error_from_exception(error, payload)
        stdout.write(_render(result, output_format=args.output_format, pretty=args.pretty))
        return exit_code_for(result)

    try:
        if services is not None:
            service_set = services
        elif isinstance(request, (AtstNebPrepareRequest, AtstNebExecuteRequest, AtstNebPostprocessRequest)):
            service_set = atst_services if atst_services is not None else AtstNebServiceSet.default(workspace_root=Path(cwd))
        elif isinstance(request, (BandPostprocessRequest, DosPostprocessRequest)):
            service_set = PostprocessServiceSet.default(workspace_root=Path(cwd))
        elif isinstance(request, (PyatbBandPrepareRequest, PyatbBandExecuteRequest, PyatbBandCollectRequest)):
            service_set = pyatb_services if pyatb_services is not None else PyatbBandServiceSet.default(workspace_root=Path(cwd))
        elif isinstance(request, _RELAX_REQUEST_TYPES):
            service_set = RelaxServiceSet.default(workspace_root=Path(cwd))
        elif isinstance(request, _MD_REQUEST_TYPES):
            service_set = MdServiceSet.default(workspace_root=Path(cwd))
        else:
            service_set = ScfServiceSet.default(workspace_root=Path(cwd))
        result = _dispatch(args.operation, request, service_set)
        if not isinstance(result, (OperationOutcome, ForgeErrorEnvelope)):
            raise TypeError("service returned an unsupported result")
    except Exception as error:
        result = _error_from_exception(error, payload)

    stdout.write(_render(result, output_format=args.output_format, pretty=args.pretty))
    return exit_code_for(result)


__all__ = [
    "build_machine_parser",
    "decode_operation_request",
    "decode_scf_request",
    "decode_atst_neb_request",
    "exit_code_for",
    "render_json",
    "render_result",
    "render_text",
    "run_machine_cli",
]
