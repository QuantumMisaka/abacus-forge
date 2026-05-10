"""PyATB prepare/run/collect helpers for ABACUS LCAO outputs."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from abacus_forge.api import collect
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
