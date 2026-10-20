"""Explicit PyATB direct NAO COHP file handoff and output validation."""

from __future__ import annotations

import json
import math
from pathlib import Path

from abacus_forge.contracts import ArtifactRecord, ForgeResultEnvelope, MetricRecord, OperationStatus
from abacus_forge.errors import ForgeRequestError
from abacus_forge.pyatb_cohp_contracts import PyatbCohpCollectRequest, PyatbCohpPrepareRequest
from abacus_forge.pyatb_typed import (
    _parse_typed_stru, _sha256_file, _stage_typed_file, _typed_destination,
    _typed_output_artifact_id, _typed_workspace_source,
)
from abacus_forge.workspace import Workspace

_STRU_HEADERS = {
    "ATOMIC_SPECIES", "NUMERICAL_ORBITAL", "LATTICE_CONSTANT",
    "LATTICE_CONSTANT_UNIT", "LATTICE_VECTORS", "ATOMIC_POSITIONS",
    "NUMERICAL_DESCRIPTOR", "ABFS_ORBITAL", "PAW_FILES",
}


def _section(text: str, name: str) -> list[str]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.split("#", 1)[0].strip().upper() != name:
            continue
        rows = []
        for next_line in lines[index + 1:]:
            clean = next_line.split("#", 1)[0].strip()
            if clean.upper() in _STRU_HEADERS:
                break
            if clean:
                rows.append(clean)
        return rows
    return []


def _orbital_names(stru_path: Path) -> tuple[str, ...]:
    text = stru_path.read_text(encoding="utf-8")
    species = [row.split()[0] for row in _section(text, "ATOMIC_SPECIES")]
    orbitals = _section(text, "NUMERICAL_ORBITAL")
    if not species or len(set(species)) != len(species) or len(orbitals) != len(species):
        raise ForgeRequestError("STRU numerical orbitals must map one-to-one to species")
    names = []
    for row in orbitals:
        tokens = row.split()
        if len(tokens) != 1 or tokens[0] in (".", "..") or Path(tokens[0]).name != tokens[0] or "\\" in tokens[0]:
            raise ForgeRequestError("STRU contains an unsafe numerical orbital reference")
        names.append(tokens[0])
    if len(names) != len(set(names)):
        raise ForgeRequestError("STRU numerical orbital names must be unique")
    return tuple(names)


def _fmt(value: float | int) -> str:
    return format(float(value), ".16g")


def _render_input(request: PyatbCohpPrepareRequest, lattice: object,
                  hr_names: tuple[str, ...], sr_name: str) -> str:
    rows = ["INPUT_PARAMETERS", "{", f"    nspin  {request.nspin}",
            "    package  ABACUS", f"    fermi_energy  {_fmt(request.fermi_energy)}",
            "    fermi_energy_unit  eV",
            f"    HR_route  {' '.join('pyatb_sources/' + name for name in hr_names)}",
            f"    SR_route  pyatb_sources/{sr_name}", "    HR_unit  Ry",
            "    sparse_format  1",
            f"    max_kpoint_num  {request.max_kpoint_num}", "}", "",
            "LATTICE", "{", "    lattice_constant  1.0",
            "    lattice_constant_unit  Angstrom", "    lattice_vector"]
    for vector in lattice:  # type: ignore[union-attr]
        rows.append("    " + "  ".join(_fmt(value) for value in vector))
    rows.extend(["}", "", "COHP", "{", "    stru_file  STRU",
                 "    orbital_dir  .", f"    atom_i_index  {request.atom_i_index}",
                 f"    atom_j_index  {request.atom_j_index}",
                 f"    atom_i_orbs  {request.atom_i_orbs}",
                 f"    atom_j_orbs  {request.atom_j_orbs}",
                 "    method  COHP", f"    spin  {request.spin}",
                 f"    e_range  {'  '.join(_fmt(v) for v in request.e_range)}",
                 f"    de  {_fmt(request.de)}", f"    sigma  {_fmt(request.sigma)}",
                 f"    invert  {int(request.invert)}",
                 f"    shift_to_efermi  {int(request.shift_to_efermi)}",
                 "    output_prefix  COHP", "    kpoint_mode  direct",
                 f"    kpoint_num  {len(request.kpoints)}", "    kpoint_direct_coor"])
    rows.extend("    " + "  ".join(_fmt(v) for v in point) for point in request.kpoints)
    rows.extend(["    kpoint_weights  " + "  ".join(_fmt(v) for v in request.kpoint_weights),
                 "}", ""])
    return "\n".join(rows)


def prepare_pyatb_cohp(workspace: Workspace, request: PyatbCohpPrepareRequest) -> tuple[dict[str, object], ...]:
    """Validate every source and target before writing the self-contained handoff."""
    root = workspace.root.resolve()
    source_specs: list[tuple[str, str, str]] = [
        ("structure", request.structure_path_rel, "inputs/STRU"),
        *(("hr", rel, "inputs/pyatb_sources/" + Path(rel).name) for rel in request.hr_paths_rel),
        ("sr", request.sr_path_rel, "inputs/pyatb_sources/" + Path(request.sr_path_rel).name),
        *(("orbital", rel, "inputs/" + Path(rel).name) for rel in request.orbital_paths_rel),
    ]
    destinations = [dest for _, _, dest in source_specs] + ["inputs/Input", "forge-unit.json"]
    if len(destinations) != len(set(destinations)):
        raise ForgeRequestError("PyATB source basenames or targets collide")
    reserved_directories = (Path("inputs/pyatb_sources"), Path("inputs/Out"))
    for destination in map(Path, destinations):
        if destination in reserved_directories or any(
            destination in other.parents for other in map(Path, destinations) if other != destination
        ):
            raise ForgeRequestError("PyATB file target collides with a generated directory")
    for _, _, rel in source_specs:
        if any(char.isspace() or char in ",{}#" for char in Path(rel).name):
            raise ForgeRequestError("PyATB source basenames must be single input tokens")

    staged = []
    for role, source_rel, dest_rel in source_specs:
        source = _typed_workspace_source(root, source_rel, role)
        dest = _typed_destination(root, dest_rel, role)
        if dest.exists() or dest.is_symlink():
            raise ForgeRequestError(f"PyATB destination already exists: {dest_rel}")
        staged.append((role, source_rel, dest_rel, source, dest, _sha256_file(source)))
    target = _typed_destination(root, "inputs/Input", "Input")
    if target.exists() or target.is_symlink():
        raise ForgeRequestError("PyATB destination already exists: inputs/Input")
    manifest_target = _typed_destination(root, "forge-unit.json", "forge unit")
    if manifest_target.exists() or manifest_target.is_symlink():
        raise ForgeRequestError("PyATB destination already exists: forge-unit.json")
    stru_source = staged[0][3]
    structure = _parse_typed_stru(stru_source)
    expected_orbitals = _orbital_names(stru_source)
    supplied_orbitals = tuple(Path(rel).name for rel in request.orbital_paths_rel)
    if len(supplied_orbitals) != len(set(supplied_orbitals)) or set(expected_orbitals) != set(supplied_orbitals):
        raise ForgeRequestError("orbital_paths_rel must exactly match STRU NUMERICAL_ORBITAL")
    if max(request.atom_i_index, request.atom_j_index) > len(structure.atoms):
        raise ForgeRequestError("COHP atom index is absent from STRU")
    input_text = _render_input(request, structure.atoms.cell.array,
                               tuple(Path(rel).name for rel in request.hr_paths_rel),
                               Path(request.sr_path_rel).name)
    workspace.ensure_layout()
    records = []
    for role, source_rel, dest_rel, source, dest, digest in staged:
        _stage_typed_file(source, dest, mode="copy")
        records.append(dict(role=role, source=source_rel, destination=dest_rel,
                            mode="copy", source_sha256=digest,
                            destination_sha256=_sha256_file(dest)))
    target.write_text(input_text, encoding="utf-8")
    return tuple(records)


def _artifact(path: Path, path_rel: str, media_type: str) -> ArtifactRecord:
    return ArtifactRecord(id=_typed_output_artifact_id(path_rel), path_rel=path_rel,
                          role="output", stage="collect", media_type=media_type,
                          sha256=_sha256_file(path), size_bytes=path.stat().st_size)


def _spectrum(path: Path) -> tuple[int, str]:
    previous = -math.inf
    count = 0
    header = None
    for row in path.read_text(encoding="utf-8").splitlines():
        if row.lstrip().startswith("#"):
            if header is None:
                header = row.lstrip()[1:].strip()
            continue
        if not row.strip():
            continue
        parts = row.split()
        if len(parts) != 2:
            raise ValueError("spectrum must contain exactly two columns")
        energy, value = map(float, parts)
        if not math.isfinite(energy) or not math.isfinite(value) or energy <= previous:
            raise ValueError("spectrum energy must increase and both columns must be finite")
        previous = energy
        count += 1
    if count < 2 or header not in ("energy_eV COHP", "energy_eV -COHP"):
        raise ValueError("spectrum must contain at least two samples")
    return count, header.split()[1]


def _metadata(path: Path, spectrum: Path, root: Path) -> dict[str, object]:
    meta = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(meta, dict):
        raise ValueError("COHP metadata must be an object")
    def finite_json(value: object) -> bool:
        if isinstance(value, float):
            return math.isfinite(value)
        if isinstance(value, list):
            return all(finite_json(item) for item in value)
        if isinstance(value, dict):
            return all(isinstance(key, str) and finite_json(item) for key, item in value.items())
        return value is None or isinstance(value, (str, int, bool))
    if not finite_json(meta):
        raise ValueError("COHP metadata contains non-finite or unsupported JSON values")
    files = meta.get("files")
    reference = files.get("spectrum") if isinstance(files, dict) else None
    if not isinstance(reference, str) or not reference or Path(reference).is_absolute():
        raise ValueError("metadata.files.spectrum must identify the declared spectrum")
    resolved = (path.parent / reference).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("metadata spectrum reference escapes workspace") from error
    if resolved != spectrum.resolve(strict=False):
        raise ValueError("metadata spectrum reference differs from declared spectrum")
    if meta.get("method") != "COHP" or meta.get("spectrum_unit") != "dimensionless":
        raise ValueError("metadata method or spectrum unit is not COHP")
    invert = meta.get("invert")
    if not isinstance(invert, bool) or meta.get("spectrum_label") != ("-COHP" if invert else "COHP"):
        raise ValueError("metadata COHP sign facts are inconsistent")
    if meta.get("sign_convention") != ("negative population" if invert else "raw population"):
        raise ValueError("metadata sign convention is inconsistent")
    for field in ("energy_shifted_to_efermi",):
        if not isinstance(meta.get(field), bool):
            raise ValueError(f"metadata {field} must be boolean")
    for field in ("fermi_energy_eV", "pair_factor"):
        val = meta.get(field)
        if isinstance(val, bool) or not isinstance(val, (float, int)) or not math.isfinite(val):
            raise ValueError(f"metadata {field} must be finite")
    if meta["pair_factor"] <= 0 or meta.get("spin") not in ("sum", "up", "down"):
        raise ValueError("metadata pair factor or spin is invalid")
    if meta.get("kpoint_weight_mode") != "explicit_normalized":
        raise ValueError("metadata does not confirm explicit normalized k weights")
    broadening = meta.get("broadening")
    if not isinstance(broadening, dict) or isinstance(broadening.get("sigma_eV"), bool) or not isinstance(broadening.get("sigma_eV"), (int, float)) or not math.isfinite(broadening["sigma_eV"]) or broadening["sigma_eV"] <= 0:
        raise ValueError("metadata Gaussian broadening is invalid")
    for field in ("atom_i_orbitals", "atom_j_orbitals"):
        values = meta.get(field)
        if not isinstance(values, list) or not values or any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in values):
            raise ValueError(f"metadata {field} is invalid")
    integral = meta.get("occupied_integral")
    if not isinstance(integral, dict) or integral.get("method") != "ICOHP" or integral.get("unit") != "eV" or integral.get("occupation") != "E <= EF (zero temperature)":
        raise ValueError("metadata occupied integral facts are invalid")
    for field in ("raw_value", "value", "spin_degeneracy"):
        val = integral.get(field)
        if isinstance(val, bool) or not isinstance(val, (float, int)) or not math.isfinite(val):
            raise ValueError(f"metadata occupied_integral.{field} is invalid")
    if integral["spin_degeneracy"] <= 0 or integral.get("label") != ("-ICOHP" if invert else "ICOHP"):
        raise ValueError("metadata occupied integral sign is invalid")
    if not math.isclose(integral["value"], -integral["raw_value"] if invert else integral["raw_value"], rel_tol=1e-8, abs_tol=1e-8):
        raise ValueError("metadata raw and displayed ICOHP disagree")
    return meta


def collect_pyatb_cohp(workspace: Workspace, request: PyatbCohpCollectRequest) -> ForgeResultEnvelope:
    root = workspace.root.resolve()
    paths = (request.spectrum_path_rel, request.metadata_path_rel)
    artifacts = []
    missing = []
    malformed = []
    resolved = []
    for rel, media in zip(paths, ("text/plain", "application/json")):
        path = root / rel
        try:
            target = path.resolve(strict=True)
            target.relative_to(root)
            if not target.is_file():
                raise OSError("not a file")
            artifacts.append(_artifact(target, rel, media))
            resolved.append(target)
        except FileNotFoundError:
            missing.append(rel)
            resolved.append(None)
        except (OSError, RuntimeError, ValueError):
            malformed.append(rel)
            resolved.append(None)
    samples = None
    spectrum_label = None
    meta = None
    if resolved[0] is not None:
        try:
            samples, spectrum_label = _spectrum(resolved[0])
        except (OSError, UnicodeError, ValueError, OverflowError):
            malformed.append(paths[0])
    if resolved[1] is not None:
        try:
            meta = _metadata(resolved[1], root / paths[0], root)
            if spectrum_label is not None and meta["spectrum_label"] != spectrum_label:
                raise ValueError("spectrum header and metadata sign disagree")
        except (OSError, UnicodeError, ValueError, OverflowError, TypeError):
            malformed.append(paths[1])
    status = "complete" if not missing and not malformed else ("partial" if artifacts else "missing_output")
    metrics = ()
    if status == "complete" and meta is not None:
        integral = meta["occupied_integral"]
        metrics = (
            MetricRecord(name="icohp_raw", value=integral["raw_value"], unit="eV", kind="reported", source_artifact_id=artifacts[1].id),
            MetricRecord(name="icohp", value=integral["value"], unit="eV", kind="reported", source_artifact_id=artifacts[1].id),
        )
    return ForgeResultEnvelope(operation="collect", workspace_rel=request.workspace_rel,
        status=OperationStatus(execution="not_run", scientific="unassessed", collection=status),
        artifacts=tuple(artifacts), metrics=metrics,
        diagnostics={"capability": "pyatb-cohp", "engine": "pyatb", "method": "direct_nao",
                     "population": "COHP", "requested_output_paths_rel": list(paths),
                     "missing_output_paths_rel": missing, "malformed_output_paths_rel": malformed,
                     "spectrum_samples": samples, "metadata": meta if status == "complete" else None})
