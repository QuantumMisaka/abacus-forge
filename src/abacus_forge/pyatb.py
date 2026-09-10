"""PyATB prepare/run/collect helpers for ABACUS LCAO outputs."""

from __future__ import annotations

import os
import re
import shutil
import hashlib
import math
import mimetypes
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from abacus_forge.api import collect
from abacus_forge.contracts import (
    ArtifactRecord,
    ForgeResultEnvelope,
    JSONValue,
    MetricRecord,
    OperationStatus,
    canonical_relative_path,
)
from abacus_forge.errors import ForgePathError, ForgePreconditionError, ForgeRequestError
from abacus_forge.input_io import read_input, read_kpt, write_kpt_line_mode
from abacus_forge.result import CollectionResult, RunResult
from abacus_forge.runner import LocalRunner
from abacus_forge.structure import AbacusStructure
from abacus_forge.workspace import Workspace


def prepare_pyatb_band(
    workspace: str | Path | Workspace,
    *,
    scf_workspace: str | Path | Workspace,
    line_kpoints: Sequence[Mapping[str, Any] | tuple[Iterable[float], str | None]],
    line_segments: int = 20,
    efermi: float | None = None,
    link_outputs: bool = True,
    max_kpoint_num: int = 4000,
) -> Workspace:
    """Prepare a PyATB band workspace from an ABACUS LCAO SCF workspace."""

    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    scf_ws = scf_workspace if isinstance(scf_workspace, Workspace) else Workspace(Path(scf_workspace))
    ws.ensure_layout()

    scf_inputs = scf_ws.inputs_dir
    input_params = read_input(scf_inputs / "INPUT")
    suffix = str(input_params.get("suffix", "ABACUS")).strip() or "ABACUS"
    out_dir = _find_abacus_out_dir(scf_ws, suffix=suffix)
    if out_dir is None:
        raise FileNotFoundError(f"ABACUS OUT.{suffix} directory not found under {scf_ws.root}")

    matrix = _matrix_routes(out_dir, nspin=_int_value(input_params.get("nspin"), default=1))
    missing_required = [path for path in matrix["required_paths"] if not path.exists()]
    if missing_required:
        missing = ", ".join(str(path) for path in missing_required)
        raise FileNotFoundError(f"PyATB matrix file(s) missing: {missing}")

    _stage_file(scf_inputs / "INPUT", ws.inputs_dir / "INPUT")
    _stage_file(scf_inputs / "STRU", ws.inputs_dir / "STRU")
    write_kpt_line_mode(ws.inputs_dir / "KPT_band", line_kpoints, segments=line_segments)
    _stage_output_dir(out_dir, ws.inputs_dir / out_dir.name, link=link_outputs)

    fermi_energy = float(efermi) if efermi is not None else _fermi_energy_from_collect(scf_ws)
    structure = AbacusStructure.from_input(ws.inputs_dir / "STRU", structure_format="stru")
    input_text = _render_pyatb_band_input(
        input_params=input_params,
        out_dir_name=out_dir.name,
        matrix_routes=matrix["routes"],
        lattice_vectors=structure.atoms.cell.array,
        line_kpt=read_kpt(ws.inputs_dir / "KPT_band"),
        fermi_energy=fermi_energy,
        max_kpoint_num=max_kpoint_num,
    )
    ws.write_text("inputs/Input", input_text)
    ws.record_metadata(
        {
            "kind": "abacus-forge.pyatb-band",
            "scf_workspace": str(scf_ws.root),
            "abacus_out_dir": str(out_dir),
            "line_segments": int(line_segments),
            "fermi_energy": fermi_energy,
            "matrix_files": [str(path) for path in matrix["required_paths"]],
        }
    )
    return ws


def run_pyatb(
    workspace: str | Path | Workspace,
    *,
    executable: str = "pyatb",
    omp: int = 1,
    timeout_seconds: float | None = None,
    env_overrides: Mapping[str, str] | None = None,
    check: bool = False,
) -> RunResult:
    """Run PyATB in a prepared workspace."""

    runner = LocalRunner(
        executable=executable,
        omp_threads=omp,
        timeout_seconds=timeout_seconds,
        env_overrides=dict(env_overrides or {}),
    )
    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    return runner.run(ws, check=check)


def collect_pyatb(workspace: str | Path | Workspace) -> CollectionResult:
    """Collect PyATB band artifacts and lightweight metrics."""

    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    ws.ensure_layout()
    artifacts = _collect_artifacts(ws)
    stderr_path = ws.outputs_dir / "stderr.log"
    metrics: dict[str, Any] = {}
    diagnostics: dict[str, Any] = {
        "pyatb_band_info_candidates": [],
        "pyatb_band_picture_candidates": [],
    }

    band_info = _first_existing(
        ws.inputs_dir / "Out" / "Band_Structure" / "band_info.dat",
        ws.outputs_dir / "Out" / "Band_Structure" / "band_info.dat",
    )
    if band_info is not None:
        diagnostics["pyatb_band_info_candidates"].append(str(band_info))
        metrics.update(_parse_band_info(band_info))

    band_picture = _first_existing(
        ws.inputs_dir / "Out" / "Band_Structure" / "band.png",
        ws.inputs_dir / "Out" / "Band_Structure" / "band.pdf",
        ws.inputs_dir / "band.png",
        ws.outputs_dir / "band.png",
    )
    if band_picture is not None:
        diagnostics["pyatb_band_picture_candidates"].append(str(band_picture))
        metrics.setdefault("band_picture", str(band_picture))

    stderr_nonempty = bool(stderr_path.exists() and stderr_path.read_text(encoding="utf-8", errors="ignore").strip())
    diagnostics["stderr_nonempty"] = stderr_nonempty
    status = "failed" if stderr_nonempty else ("completed" if metrics else "missing-output")
    return CollectionResult(
        workspace=ws.root,
        status=status,
        metrics=metrics,
        artifacts=artifacts,
        diagnostics=diagnostics,
        inputs_snapshot={"PYATB_INPUT": (ws.inputs_dir / "Input").read_text(encoding="utf-8") if (ws.inputs_dir / "Input").exists() else ""},
    )


def _render_pyatb_band_input(
    *,
    input_params: Mapping[str, str],
    out_dir_name: str,
    matrix_routes: dict[str, str],
    lattice_vectors: Any,
    line_kpt: Mapping[str, Any],
    fermi_energy: float,
    max_kpoint_num: int,
) -> str:
    nspin = _int_value(input_params.get("nspin"), default=1)
    labels = []
    points = []
    for point in line_kpt.get("points", []):
        labels.append(_normalize_label(point.get("label")))
        coords = " ".join(str(float(value)) for value in point["coords"])
        points.append(f"    {coords} {int(point.get('npoints', 1))}")
    input_parameters = {
        "nspin": nspin,
        "package": "ABACUS",
        "fermi_energy": fermi_energy,
        "HR_route": matrix_routes["HR_route"],
        "SR_route": matrix_routes["SR_route"],
        "rR_route": matrix_routes["rR_route"],
        "HR_unit": "Ry",
        "rR_unit": "Bohr",
        "max_kpoint_num": max_kpoint_num,
    }
    rows = ["INPUT_PARAMETERS", "{"]
    rows.extend(f"    {key}  {value}" for key, value in input_parameters.items())
    rows.extend(["}", "", "LATTICE", "{", "    lattice_constant  1.8897162", "    lattice_constant_unit  Bohr", "    lattice_vector"])
    for vector in lattice_vectors:
        rows.append(f"    {float(vector[0]):.8f}  {float(vector[1]):.8f}  {float(vector[2]):.8f}")
    rows.extend(
        [
            "}",
            "",
            "BAND_STRUCTURE",
            "{",
            "    kpoint_mode   line",
            f"    kpoint_num    {len(points)}",
            f"    kpoint_label  {', '.join(labels)}",
            "    high_symmetry_kpoint",
            *points,
            "}",
            "",
        ]
    )
    return "\n".join(rows)


def _matrix_routes(out_dir: Path, *, nspin: int) -> dict[str, Any]:
    hr0 = out_dir / "data-HR-sparse_SPIN0.csr"
    sr0 = out_dir / "data-SR-sparse_SPIN0.csr"
    rr = out_dir / "data-rR-sparse.csr"
    hr_routes = [f"{out_dir.name}/{hr0.name}"]
    sr_routes = [f"{out_dir.name}/{sr0.name}"]
    required = [hr0, sr0, rr]
    if nspin == 2:
        hr1 = out_dir / "data-HR-sparse_SPIN1.csr"
        sr1 = out_dir / "data-SR-sparse_SPIN1.csr"
        if hr1.exists():
            hr_routes.append(f"{out_dir.name}/{hr1.name}")
            required.append(hr1)
            if sr1.exists():
                sr_routes.append(f"{out_dir.name}/{sr1.name}")
                required.append(sr1)
            else:
                sr_routes.append(f"{out_dir.name}/{sr0.name}")
    return {
        "required_paths": required,
        "routes": {
            "HR_route": " ".join(hr_routes),
            "SR_route": " ".join(sr_routes),
            "rR_route": f"{out_dir.name}/{rr.name}",
        },
    }


def _find_abacus_out_dir(workspace: Workspace, *, suffix: str) -> Path | None:
    for candidate in (
        workspace.inputs_dir / f"OUT.{suffix}",
        workspace.outputs_dir / f"OUT.{suffix}",
        workspace.inputs_dir / "OUT.ABACUS",
        workspace.outputs_dir / "OUT.ABACUS",
    ):
        if candidate.exists() and candidate.is_dir():
            return candidate
    for base in (workspace.inputs_dir, workspace.outputs_dir):
        if base.exists():
            matches = sorted(path for path in base.glob("OUT.*") if path.is_dir())
            if matches:
                return matches[0]
    return None


def _stage_file(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    shutil.copy2(source, destination)


def _stage_output_dir(source: Path, destination: Path, *, link: bool) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    if link:
        os.symlink(source.resolve(), destination)
    else:
        shutil.copytree(source, destination)


def _fermi_energy_from_collect(workspace: Workspace) -> float:
    result = collect(workspace)
    value = result.metrics.get("fermi_energy")
    if value is None:
        raise ValueError(f"fermi_energy is required to prepare PyATB input for {workspace.root}")
    return float(value)


def _collect_artifacts(workspace: Workspace) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for relative in ("inputs", "outputs", "reports"):
        base = workspace.root / relative
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file():
                artifacts[str(path.relative_to(workspace.root))] = str(path)
    return artifacts


def _parse_band_info(path: Path) -> dict[str, Any]:
    metrics: dict[str, Any] = {"band_info": str(path)}
    text = path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"Band\s+gap[^-+0-9]*([-+]?\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if match:
        metrics["band_gap"] = float(match.group(1))
    return metrics


def _first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists() and path.is_file():
            return path
    return None


def _normalize_label(value: Any) -> str:
    label = str(value or "").strip()
    if label in {"", "None"}:
        return "K"
    return "G" if label.lower() in {"gamma", "\\gamma"} else label


def _int_value(value: Any, *, default: int) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Explicit typed PyATB band handoff
# ---------------------------------------------------------------------------
#
# The helpers below intentionally sit beside, rather than inside, the legacy
# SCF-discovery helpers above.  Their input is a fully declared typed request;
# they do not inspect a sibling SCF workspace or infer any value from a log.


def prepare_typed_pyatb_band(
    workspace: str | Path | Workspace,
    request: Any,
) -> tuple[Workspace, tuple[dict[str, JSONValue], ...]]:
    """Materialize one explicit PyATB band handoff in ``workspace``.

    Matrix inputs are deliberately addressed relative to the destination
    workspace.  A relative symlink is the default because ABACUS matrix files
    can be large; callers that require a snapshot can select ``copy`` on the
    request.  Every source and destination is validated before any destination
    is created so rejected requests do not leave a partial handoff behind.
    """

    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    root = ws.root.resolve()
    source_specs = _typed_pyatb_source_specs(request)
    handoff_mode = getattr(request, "handoff_mode", "link")
    if handoff_mode not in {"link", "copy"}:
        raise ForgeRequestError("handoff_mode must be one of: copy, link")

    matrix_basenames = [Path(path_rel).name for _, path_rel, _ in source_specs[1:]]
    if len(matrix_basenames) != len(set(matrix_basenames)):
        raise ForgeRequestError("PyATB matrix source basenames must be unique")
    if any(
        not basename
        or any(character.isspace() for character in basename)
        or any(character in basename for character in ",{}#")
        or "//" in basename
        for basename in matrix_basenames
    ):
        raise ForgeRequestError(
            "PyATB matrix source basenames must be single input tokens"
        )
    _validate_typed_line_point_tokens(request)

    # Resolve and hash every source, and calculate every destination, before
    # creating the workspace layout.  This is the no-partial-write boundary.
    resolved_sources: list[tuple[str, str, Path, Path, str]] = []
    for role, source_rel, destination_rel in source_specs:
        source_path = _typed_workspace_source(root, source_rel, role)
        destination_path = _typed_destination(root, destination_rel, role)
        _validate_typed_destination_conflict(
            destination_path,
            source_path,
            root=root,
            role=role,
            mode=handoff_mode,
        )
        try:
            source_sha256 = _sha256_file(source_path)
        except OSError as error:
            raise ForgePreconditionError(
                f"{role} source cannot be read: {source_rel}"
            ) from error
        resolved_sources.append(
            (role, source_rel, source_path, destination_path, source_sha256)
        )

    generated_targets = (
        _typed_destination(root, "inputs/Input", "PyATB Input"),
        _typed_destination(root, "inputs/KPT_band", "PyATB KPT_band"),
    )
    for target in generated_targets:
        if target.exists() or target.is_symlink():
            raise ForgeRequestError(f"generated destination already exists: {_relative_to_root(root, target)}")

    # Parse and render before staging.  In particular, a malformed STRU must
    # not leave a valid matrix handoff behind.
    structure_source = resolved_sources[0][2]
    structure = _parse_typed_stru(structure_source)
    matrix_routes = _typed_matrix_routes(resolved_sources)
    kpt_text = _render_typed_kpt(request)
    input_text = _render_typed_pyatb_input(
        request=request,
        lattice_vectors=structure.atoms.cell.array,
        matrix_routes=matrix_routes,
    )

    ws.ensure_layout()
    handoff: list[dict[str, JSONValue]] = []
    for role, source_rel, source_path, destination_path, source_sha256 in resolved_sources:
        destination_rel = _relative_to_root(root, destination_path)
        _stage_typed_file(
            source_path,
            destination_path,
            mode=handoff_mode,
        )
        destination_sha256 = _sha256_file(destination_path)
        handoff.append(
            {
                "role": role,
                "source": source_rel,
                "destination": destination_rel,
                "mode": handoff_mode,
                "source_sha256": source_sha256,
                "destination_sha256": destination_sha256,
            }
        )

    ws.write_text("inputs/KPT_band", kpt_text)
    ws.write_text("inputs/Input", input_text)
    return ws, tuple(handoff)


def collect_typed_pyatb_band(
    workspace: str | Path | Workspace,
    request: Any,
) -> ForgeResultEnvelope:
    """Collect explicitly requested PyATB band outputs as factual records.

    Only contained files are represented as artifacts.  ``band_gap`` is copied
    from the textual ``band_info.dat`` report when it is parseable; no band
    data is recomputed and no scientific acceptance decision is emitted.
    """

    ws = workspace if isinstance(workspace, Workspace) else Workspace(Path(workspace))
    root = ws.root.resolve()
    requested_paths = _typed_collection_paths(request)
    present_paths: list[str] = []
    missing_paths: list[str] = []
    malformed_paths: list[str] = []
    escaped_paths: list[str] = []
    unavailable_paths: list[str] = []
    resolved_files: dict[str, Path] = {}

    for path_rel in requested_paths:
        candidate = root / Path(path_rel)
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root)
        except ValueError:
            escaped_paths.append(path_rel)
            continue
        except (FileNotFoundError, OSError, RuntimeError):
            missing_paths.append(path_rel)
            continue
        if not resolved.is_file():
            unavailable_paths.append(path_rel)
            continue
        try:
            # Reading now ensures a disappearing/unreadable file is not
            # advertised as an artifact with an unverifiable digest.
            _sha256_file(resolved)
        except OSError:
            unavailable_paths.append(path_rel)
            continue
        present_paths.append(path_rel)
        resolved_files[path_rel] = resolved

    artifacts: list[ArtifactRecord] = []
    artifact_by_path: dict[str, ArtifactRecord] = {}
    for path_rel in present_paths:
        resolved = resolved_files[path_rel]
        try:
            digest = _sha256_file(resolved)
            size_bytes = resolved.stat().st_size
            artifact = ArtifactRecord(
                id=_typed_output_artifact_id(path_rel),
                path_rel=path_rel,
                role="output",
                stage="collect",
                media_type=mimetypes.guess_type(path_rel)[0] or "application/octet-stream",
                sha256=digest,
                size_bytes=size_bytes,
            )
        except OSError:
            unavailable_paths.append(path_rel)
            continue
        artifacts.append(artifact)
        artifact_by_path[path_rel] = artifact

    metrics: list[MetricRecord] = []
    band_info_rel = str(getattr(request, "band_info_path_rel"))
    band_info = resolved_files.get(band_info_rel)
    if band_info is not None and band_info_rel in artifact_by_path:
        unavailable_band_info = False
        try:
            band_gap = _typed_parse_band_gap(band_info)
        except OSError:
            unavailable_paths.append(band_info_rel)
            unavailable_band_info = True
            artifact_by_path.pop(band_info_rel, None)
            artifacts = [artifact for artifact in artifacts if artifact.path_rel != band_info_rel]
            band_gap = None
        except UnicodeError:
            # The file was read but contains invalid text; retain its real
            # artifact and report parser malformation, without inventing a
            # metric or treating it as an unavailable file.
            band_gap = None
        if unavailable_band_info:
            pass
        elif band_gap is None:
            malformed_paths.append(band_info_rel)
        else:
            metrics.append(
                MetricRecord(
                    name="band_gap",
                    value=band_gap,
                    unit="eV",
                    kind="reported",
                    source_artifact_id=artifact_by_path[band_info_rel].id,
                )
            )

    # Keep diagnostics as a compact, path-relative fact set.  A required band
    # info file is the minimum usable collection; optional data/pictures are
    # still part of completeness when explicitly requested.
    if present_paths and not missing_paths and not malformed_paths and not escaped_paths and not unavailable_paths:
        collection = "complete"
        reason = "all_requested_outputs_present"
    elif present_paths or malformed_paths or escaped_paths or unavailable_paths:
        collection = "partial"
        reason = "requested_outputs_missing_or_unavailable_or_malformed"
    else:
        collection = "missing_output"
        reason = "no_requested_outputs_present"

    diagnostics: dict[str, JSONValue] = {
        "requested_output_paths_rel": list(requested_paths),
        "present_output_paths_rel": list(present_paths),
        "missing_output_paths_rel": list(dict.fromkeys(missing_paths)),
        "malformed_output_paths_rel": list(dict.fromkeys(malformed_paths)),
        "escaped_output_paths_rel": list(dict.fromkeys(escaped_paths)),
        "unavailable_output_paths_rel": list(dict.fromkeys(unavailable_paths)),
        "collection_reason": reason,
    }
    return ForgeResultEnvelope(
        operation="collect",
        workspace_rel=".",
        status=OperationStatus(
            execution="not_run",
            scientific="unassessed",
            collection=collection,
        ),
        artifacts=tuple(artifacts),
        metrics=tuple(metrics),
        diagnostics=diagnostics,
    )


def _typed_pyatb_source_specs(request: Any) -> tuple[tuple[str, str, str], ...]:
    """Return role/source/destination triples in deterministic request order."""

    try:
        structure_rel = _typed_relative_file(request.structure_path_rel, "structure_path_rel")
        hr_paths = tuple(
            _typed_relative_file(path, "hr_paths_rel")
            for path in request.hr_paths_rel
        )
        sr_path = _typed_relative_file(request.sr_path_rel, "sr_path_rel")
        rr_path = _typed_relative_file(request.rr_path_rel, "rr_path_rel")
    except AttributeError as error:
        raise ForgeRequestError("request is missing typed PyATB handoff fields") from error

    specs: list[tuple[str, str, str]] = [
        ("structure", structure_rel, "inputs/STRU"),
    ]
    specs.extend(
        ("hr", source_rel, f"inputs/pyatb_sources/{Path(source_rel).name}")
        for source_rel in hr_paths
    )
    specs.extend(
        [
            ("sr", sr_path, f"inputs/pyatb_sources/{Path(sr_path).name}"),
            ("rR", rr_path, f"inputs/pyatb_sources/{Path(rr_path).name}"),
        ]
    )
    return tuple(specs)


def _typed_collection_paths(request: Any) -> tuple[str, ...]:
    try:
        band_info = _typed_relative_file(request.band_info_path_rel, "band_info_path_rel")
        data_paths = tuple(
            _typed_relative_file(path, "band_data_paths_rel")
            for path in request.band_data_paths_rel
        )
        picture_paths = tuple(
            _typed_relative_file(path, "band_picture_paths_rel")
            for path in request.band_picture_paths_rel
        )
    except AttributeError as error:
        raise ForgeRequestError("request is missing typed PyATB collection fields") from error
    # Keep request order while avoiding duplicate artifacts when the same
    # standard output is named in more than one optional list.
    return tuple(dict.fromkeys((band_info, *data_paths, *picture_paths)))


def _typed_relative_file(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ForgeRequestError(f"{field_name} must identify a workspace-relative file")
    try:
        normalized = canonical_relative_path(value)
    except ValueError as error:
        raise ForgePathError(f"{field_name} must be a canonical relative path") from error
    if normalized == ".":
        raise ForgeRequestError(f"{field_name} must identify a workspace-relative file")
    return normalized


def _validate_typed_line_point_tokens(request: Any) -> None:
    """Reject labels that would change the grammar of generated PyATB text.

    Labels stay intentionally permissive in the public request contract.  A
    typed prepare operation validates the narrower token surface at the last
    boundary before rendering labels into ``Input`` and ``KPT_band``.
    """

    try:
        points = request.line_kpoints
    except AttributeError as error:
        raise ForgeRequestError("request is missing typed PyATB line points") from error
    try:
        for index, point in enumerate(points):
            label = point.get("label")
            if label is None:
                continue
            _validate_typed_input_token(label, f"line_kpoints[{index}].label")
    except AttributeError as error:
        raise ForgeRequestError("line_kpoints entries must be objects") from error


def _validate_typed_input_token(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ForgeRequestError(f"{field_name} must be a non-empty PyATB token")
    if (
        any(character.isspace() for character in value)
        or any(character in value for character in ",{}#")
        or "//" in value
    ):
        raise ForgeRequestError(
            f"{field_name} contains characters unsafe for a PyATB input token"
        )


def _typed_workspace_source(root: Path, path_rel: str, role: str) -> Path:
    candidate = root / Path(path_rel)
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as error:
        raise ForgePreconditionError(f"{role} source file not found: {path_rel}") from error
    except (OSError, RuntimeError) as error:
        raise ForgePreconditionError(f"{role} source cannot be resolved: {path_rel}") from error
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ForgePathError(f"{role} source escapes workspace: {path_rel}") from error
    if not resolved.is_file():
        raise ForgePreconditionError(f"{role} source is not a regular file: {path_rel}")
    return resolved


def _typed_destination(root: Path, path_rel: str, role: str) -> Path:
    normalized = _typed_relative_file(path_rel, role)
    candidate = root / Path(normalized)
    try:
        parent = candidate.parent.resolve(strict=False)
        parent.relative_to(root)
    except (OSError, RuntimeError, ValueError) as error:
        raise ForgePathError(f"{role} destination escapes workspace: {normalized}") from error
    for ancestor in candidate.parents:
        if ancestor == root:
            break
        if ancestor.is_symlink():
            raise ForgeRequestError(
                f"{role} destination parent cannot be a symlink: {ancestor.name}"
            )
    if candidate.parent.exists() and not candidate.parent.is_dir():
        raise ForgeRequestError(f"{role} destination parent is not a directory: {normalized}")
    try:
        candidate.resolve(strict=False).relative_to(root)
    except (OSError, RuntimeError, ValueError) as error:
        raise ForgePathError(f"{role} destination escapes workspace: {normalized}") from error
    return candidate


def _validate_typed_destination_conflict(
    destination: Path,
    source: Path,
    *,
    root: Path,
    role: str,
    mode: str,
) -> None:
    """Reject an existing destination unless it is the exact source alias."""

    if not destination.exists() and not destination.is_symlink():
        return
    if destination.is_symlink():
        if mode == "copy":
            raise ForgeRequestError(
                f"{role} copy destination cannot be an existing symlink: {destination.name}"
            )
        try:
            destination_target = destination.resolve(strict=True)
        except (FileNotFoundError, OSError, RuntimeError) as error:
            raise ForgeRequestError(
                f"{role} destination is an unusable existing link: {destination.name}"
            ) from error
    else:
        destination_target = destination.resolve(strict=True)
    try:
        destination_target.relative_to(root)
    except ValueError as error:
        raise ForgePathError(
            f"{role} destination escapes workspace: {destination.name}"
        ) from error
    if destination_target != source.resolve(strict=True):
        raise ForgeRequestError(f"{role} destination already exists: {destination.name}")


def _parse_typed_stru(path: Path) -> AbacusStructure:
    try:
        structure = AbacusStructure.from_input(path, structure_format="stru")
    except Exception as error:
        raise ForgeRequestError(f"declared STRU cannot be parsed: {path.name}") from error
    cell = structure.atoms.cell.array
    if len(structure.atoms) == 0 or getattr(cell, "shape", ()) != (3, 3):
        raise ForgeRequestError("declared STRU must contain atoms and three lattice vectors")
    if not all(math.isfinite(float(value)) for value in cell.flat):
        raise ForgeRequestError("declared STRU lattice vectors must be finite")
    # A zero-volume cell is not a usable PyATB lattice and usually indicates a
    # truncated hand-authored STRU.  This is input parsing, not a scientific
    # acceptance check.
    try:
        volume = float(structure.atoms.get_volume())
    except Exception as error:
        raise ForgeRequestError("declared STRU lattice vectors are invalid") from error
    if not math.isfinite(volume) or volume <= 0:
        raise ForgeRequestError("declared STRU lattice vectors must span a cell")
    return structure


def _typed_matrix_routes(
    sources: Sequence[tuple[str, str, Path, Path, str]],
) -> dict[str, str]:
    routes: dict[str, list[str]] = {"HR_route": [], "SR_route": [], "rR_route": []}
    for role, _, _, destination, _ in sources:
        # ``destination`` is ``<root>/inputs/pyatb_sources/<name>``.  PyATB's
        # Input is executed from ``<root>/inputs`` and therefore uses the
        # route relative to that directory.
        route = f"pyatb_sources/{destination.name}"
        if role == "hr":
            routes["HR_route"].append(route)
        elif role == "sr":
            routes["SR_route"].append(route)
        elif role == "rR":
            routes["rR_route"].append(route)
    return {name: " ".join(values) for name, values in routes.items()}


def _render_typed_kpt(request: Any) -> str:
    points = list(request.line_kpoints)
    segments = int(request.line_segments)
    rows = ["K_POINTS", str(len(points)), "Line"]
    last_index = len(points) - 1
    for index, point in enumerate(points):
        coords = point["coords"]
        label = point.get("label")
        npoints = 1 if index == last_index else segments
        values = " ".join(f"{float(value):.8f}" for value in coords)
        suffix = f" #{label}" if label else ""
        rows.append(f"{values} {npoints}{suffix}")
    return "\n".join(rows) + "\n"


def _render_typed_pyatb_input(
    *,
    request: Any,
    lattice_vectors: Any,
    matrix_routes: Mapping[str, str],
) -> str:
    rows = ["INPUT_PARAMETERS", "{"]
    values = (
        ("nspin", int(request.nspin)),
        ("package", "ABACUS"),
        ("fermi_energy", float(request.fermi_energy)),
        ("fermi_energy_unit", "eV"),
        ("HR_route", matrix_routes["HR_route"]),
        ("SR_route", matrix_routes["SR_route"]),
        ("rR_route", matrix_routes["rR_route"]),
        ("HR_unit", "Ry"),
        ("rR_unit", "Bohr"),
        ("max_kpoint_num", int(request.max_kpoint_num)),
    )
    rows.extend(f"    {name}  {value}" for name, value in values)
    rows.extend(
        [
            "}",
            "",
            "LATTICE",
            "{",
            "    lattice_constant  1.0",
            "    lattice_constant_unit  Angstrom",
            "    lattice_vector",
        ]
    )
    for vector in lattice_vectors:
        rows.append(
            "    " + "  ".join(f"{float(value):.12f}" for value in vector)
        )

    labels = [str(point.get("label") or "K") for point in request.line_kpoints]
    rows.extend(
        [
            "}",
            "",
            "BAND_STRUCTURE",
            "{",
            "    wf_collect  0",
            "    kpoint_mode  line",
            f"    kpoint_num  {len(request.line_kpoints)}",
            "    high_symmetry_kpoint",
        ]
    )
    last_index = len(request.line_kpoints) - 1
    for index, point in enumerate(request.line_kpoints):
        coords = "  ".join(f"{float(value):.12f}" for value in point["coords"])
        npoints = 1 if index == last_index else int(request.line_segments)
        label = point.get("label")
        suffix = f"  # {label}" if label else ""
        rows.append(f"    {coords}  {npoints}{suffix}")
    rows.extend(
        [
            f"    kpoint_label  {','.join(labels)}",
            "}",
            "",
        ]
    )
    return "\n".join(rows)


def _stage_typed_file(source: Path, destination: Path, *, mode: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        # The preflight above permits only an exact source alias.  Retain it
        # rather than unlinking a caller-owned path.
        if destination.is_symlink() and mode == "copy":
            raise ForgeRequestError(
                f"copy destination cannot be an existing symlink: {destination.name}"
            )
        if destination.resolve(strict=True) == source.resolve(strict=True):
            return
        raise ForgeRequestError(f"destination already exists: {destination.name}")
    if mode == "link":
        relative_source = os.path.relpath(source, destination.parent)
        os.symlink(relative_source, destination)
    elif mode == "copy":
        shutil.copy2(source, destination)
    else:  # defensive for callers bypassing the typed request constructor
        raise ForgeRequestError("handoff_mode must be one of: copy, link")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_to_root(root: Path, path: Path) -> str:
    try:
        # Provenance records the destination's lexical workspace route.  In
        # particular, an existing symlink alias must not collapse to its
        # resolved source path in the public handoff record.
        return canonical_relative_path(path.relative_to(root).as_posix())
    except (OSError, RuntimeError, ValueError) as error:
        raise ForgePathError("path escapes workspace") from error


def _typed_output_artifact_id(path_rel: str) -> str:
    return f"artifact-{hashlib.sha256(path_rel.encode('utf-8')).hexdigest()[:12]}"


_TYPED_BAND_GAP_RE = re.compile(
    r"^[ \t]*Band[ \t]+gap\b"
    r"(?:[ \t]+is[ \t]+|[ \t]*(?:\([^:\r\n]*\)[ \t]*)?[:=][ \t]*|"
    r"[ \t]+(?=[+-]?(?:\d|\.)))"
    r"(?P<value>[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?)"
    r"(?![0-9A-Za-z_.])[ \t]*(?:eV)?[ \t]*\r?$",
    re.IGNORECASE | re.MULTILINE,
)

_TYPED_BAND_SECTION_RE = re.compile(
    r"^[ \t]*For[ \t]+[^:\r\n]+:[ \t]*(?:\r?\n|$)",
    re.IGNORECASE | re.MULTILINE,
)
_TYPED_TOTAL_BAND_HEADER_RE = re.compile(
    r"^[ \t]*For[ \t]+total[ \t]+band[ \t]*:[ \t]*(?:\r?\n|$)",
    re.IGNORECASE | re.MULTILINE,
)


def _typed_parse_band_gap(path: Path) -> float | None:
    text = path.read_text(encoding="utf-8", errors="strict")
    total_header = _TYPED_TOTAL_BAND_HEADER_RE.search(text)
    if total_header is not None:
        remainder = text[total_header.end() :]
        next_section = _TYPED_BAND_SECTION_RE.search(remainder)
        section = remainder if next_section is None else remainder[: next_section.start()]
        matches = list(_TYPED_BAND_GAP_RE.finditer(section))
    else:
        matches = list(_TYPED_BAND_GAP_RE.finditer(text))
    if len(matches) != 1:
        return None
    try:
        value = float(matches[0].group("value"))
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None
