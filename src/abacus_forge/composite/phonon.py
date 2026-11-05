"""Finite-displacement phonon preparation and explicit force-set analysis.

These experimental helpers expose the independent ABACUS workspaces.  They do
not allocate resources or schedule the displacements.
"""

from __future__ import annotations

import hashlib
import math
import shutil
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from abacus_forge.composite.common import (
    ensure_root,
    require_prepared_inputs,
    run_subtasks,
    write_subtask,
    write_task_result,
)
from abacus_forge.result import TaskResult
from abacus_forge.structure import AbacusStructure
from abacus_forge.workspace import Workspace


def prepare_phonon(
    workspace: str | Path,
    *,
    phonopy: str = "phonopy",
    setting_file: str = "setting.conf",
    supercell: tuple[int, int, int] | list[int] | None = None,
    displacement_stepsize: float = 0.01,
) -> TaskResult:
    """Generate real displacement units and a relocatable plan.

    Supplying ``supercell`` uses the optional phonopy Python library directly.
    Omitting it retains the setting-file/executable interface, run in an isolated
    staging directory so previous ``STRU-*`` files cannot enter a new plan.
    """
    root = Workspace(ensure_root(workspace).root.expanduser().resolve())
    if (root.reports_dir / "phonon_plan.json").exists():
        raise FileExistsError("phonon plan already exists; use a new workspace")
    input_params, structure, kpt_payload = require_prepared_inputs(root)
    _species_labels(structure)
    # Match the atom order written to the ABACUS units (STRU groups species).
    structure = AbacusStructure.from_input(structure.to_stru(), structure_format="stru")
    distance = _positive_stepsize(displacement_stepsize)
    diagnostics: dict[str, Any] = {"phonopy": phonopy, "setting_file": setting_file}
    if supercell is None:
        if shutil.which(phonopy) is None:
            return TaskResult(
                task="phonon", workspace=root.root, status="degraded",
                summary={"count": 0},
                diagnostics={**diagnostics, "optional_dependency_missing": "phonopy"},
            )
        model = _prepare_with_cli(root, structure, phonopy, setting_file, diagnostics)
        if model is None:
            return TaskResult(
                task="phonon", workspace=root.root, status="failed",
                summary={"count": 0}, diagnostics=diagnostics,
            )
        matrix = np.asarray(model.supercell_matrix, dtype=int).tolist()
        displacement_lengths = [np.linalg.norm(item["displacement"]) for item in model.dataset["first_atoms"]]
        distance = float(displacement_lengths[0]) if displacement_lengths and np.allclose(displacement_lengths, displacement_lengths[0]) else None
    else:
        matrix = list(_supercell(supercell))
        model = _new_phonopy(structure, matrix)
        model.generate_displacements(distance=distance)
        diagnostics["method"] = "phonopy-python-finite-displacement"

    from abacus_forge.composite.plan import load_plan, save_plan

    displaced_cells = model.supercells_with_displacements
    if not displaced_cells:
        raise RuntimeError("phonopy did not generate any displacement units")
    parameters = {**input_params, "calculation": "scf", "cal_force": 1}
    parameters.pop("stru_file", None)
    threshold = float(parameters.get("scf_thr", 1e-7))
    if not math.isfinite(threshold) or threshold <= 0:
        raise ValueError("INPUT scf_thr must be finite and positive")
    parameters["scf_thr"] = min(threshold, 1e-7)
    subtasks = []
    for index, cell in enumerate(displaced_cells):
        metadata = {"task": "phonon", "displacement_index": index}
        subtask = write_subtask(
            root,
            f"phonon/ABACUS-{index + 1:03d}",
            input_params=parameters,
            structure=_displaced_structure(structure, cell),
            kpt_payload=kpt_payload,
            metadata=metadata,
            copy_reference_outputs=False,
        )
        subtasks.append({"workspace": str(subtask.root), "displacement_index": index})
    phonopy_file = "reports/phonopy_displacements.yaml"
    model.save(
        filename=root.root / phonopy_file,
        settings={"force_sets": False, "force_constants": False},
    )
    plan_path = save_plan(
        root, "phonon", subtasks,
        phonopy_file=phonopy_file,
        phonopy_file_sha256=hashlib.sha256((root.root / phonopy_file).read_bytes()).hexdigest(),
        supercell=matrix,
        displacement_stepsize=distance,
        supercell_atom_count=len(model.supercell),
        length_unit="angstrom",
        force_unit="eV/angstrom",
        force_constants_unit="eV/angstrom^2",
        diagnostics=diagnostics,
    )
    normalized = load_plan(root, "phonon")["subtasks"]
    return TaskResult(
        task="phonon", workspace=root.root, status="prepared", subtasks=normalized,
        summary={"count": len(normalized), "supercell_atom_count": len(model.supercell)},
        artifacts={str(plan_path.relative_to(root.root)): str(plan_path), phonopy_file: str(root.root / phonopy_file)},
        diagnostics=diagnostics,
    )


def run_phonon(workspace: str | Path, **kwargs: Any) -> TaskResult:
    """Run only the units explicitly listed in the prepared plan."""
    from abacus_forge.composite.plan import load_plan

    root = Workspace(ensure_root(workspace).root.expanduser().resolve())
    units = load_plan(root, "phonon")["subtasks"]
    return run_subtasks("phonon", root, [unit["workspace"] for unit in units], **kwargs)


def post_phonon(
    workspace: str | Path,
    *,
    phonopy: str = "phonopy",
    setting_file: str = "setting.conf",
    only_plot: bool = False,
    results: Iterable[dict[str, Any]] | None = None,
    qpoints: Iterable[Iterable[float]] | None = None,
) -> TaskResult:
    """Analyze an explicit, complete force collection without running ABACUS.

    With ``results`` omitted, the compatibility convenience path collects each
    planned workspace first.  ``only_plot=True`` explicitly invokes the legacy
    CPU plotting command on existing artifacts, without collection or ABACUS
    execution, and cannot be combined with results or q-points.  Analysis uses
    reduced q-points rather than a post-specific setting file.
    Frequencies are THz at explicit reduced q-points (Gamma by default).
    """
    if only_plot:
        if results is not None or qpoints is not None:
            raise ValueError("only_plot cannot be combined with explicit results or qpoints")
        root = Workspace(ensure_root(workspace).root.expanduser().resolve())
        return _plot_existing(root, phonopy, setting_file)
    if setting_file != "setting.conf":
        raise ValueError("post setting_file is unsupported; supply explicit qpoints for analysis")
    from abacus_forge.composite.plan import collect_subtask, gather_subtasks, load_plan

    root = Workspace(ensure_root(workspace).root.expanduser().resolve())
    plan = load_plan(root, "phonon")
    selected_qpoints = _qpoints(qpoints)
    units = plan["subtasks"]
    if results is None:
        results = [collect_subtask(root, "phonon", unit["unit_id"]) for unit in units]
    gathered = gather_subtasks(root, "phonon", results)
    if gathered.status != "completed":
        return gathered
    invalid: list[str] = []
    forces = []
    natoms = plan["supercell_atom_count"]
    for row in gathered.subtasks:
        metrics = row["metrics"]
        try:
            force = np.asarray(metrics.get("force"), dtype=float).reshape((-1, 3))
            valid = (
                metrics.get("normal_end") is True
                and metrics.get("converge") is True
                and force.shape == (natoms, 3)
                and np.isfinite(force).all()
            )
        except (TypeError, ValueError):
            valid = False
        if not valid:
            invalid.append(row["unit_id"])
        else:
            forces.append(force)
    if invalid:
        gathered.status = "degraded"
        gathered.diagnostics["invalid_force_units"] = invalid
        return gathered

    from phonopy import load
    from phonopy.file_IO import write_FORCE_CONSTANTS

    phonopy_path = root.resolve_relative(plan["phonopy_file"])
    if hashlib.sha256(phonopy_path.read_bytes()).hexdigest() != plan.get("phonopy_file_sha256"):
        raise ValueError("phonopy displacement dataset changed since preparation")
    model = load(phonopy_path, produce_fc=False)
    if len(model.supercells_with_displacements) != len(units):
        raise ValueError("phonopy displacement count differs from the prepared plan")
    # Shared gather returns plan order, not execution completion order.
    for expected_index, unit in enumerate(units):
        if unit.get("displacement_index") != expected_index:
            raise ValueError("phonopy displacement indexes differ from the prepared plan")
    model.forces = forces
    model.produce_force_constants()
    constants = np.asarray(model.force_constants)
    if constants.size == 0 or not np.isfinite(constants).all():
        raise RuntimeError("phonopy produced invalid force constants")
    model.run_qpoints(selected_qpoints)
    frequencies = np.asarray(model.qpoints.frequencies)
    if frequencies.shape != (len(selected_qpoints), 3 * len(model.primitive)) or not np.isfinite(frequencies).all():
        raise RuntimeError("phonopy produced invalid frequencies")
    force_constants_file = root.reports_dir / "FORCE_CONSTANTS"
    write_FORCE_CONSTANTS(constants, filename=force_constants_file)
    model_file = root.reports_dir / "phonopy_force_constants.yaml"
    model.save(filename=model_file, settings={"force_constants": True})
    summary = {
        "subtask_count": len(units),
        "completed_subtasks": len(gathered.subtasks),
        "qpoints": selected_qpoints,
        "frequencies_THz": frequencies.tolist(),
        "force_constant_shape": list(constants.shape),
        "method": "phonopy-finite-displacement",
    }
    metrics_file = write_task_result(root, "reports/metrics_phonon.json", summary)
    return TaskResult(
        task="phonon", workspace=root.root, status="completed", subtasks=gathered.subtasks,
        summary=summary,
        artifacts={
            **gathered.artifacts,
            **{str(path.relative_to(root.root)): str(path) for path in (force_constants_file, model_file, metrics_file)},
        },
        diagnostics={"phonopy": phonopy, "setting_file": setting_file, "only_plot": only_plot,
                     "scientific_assessment": "unassessed", "symmetrize_force_constants": False},
    )


def _supercell(value: Any) -> tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("supercell must contain three positive integers")
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 1 for item in value):
        raise ValueError("supercell must contain three positive integers")
    return tuple(value)


def _positive_stepsize(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError("displacement_stepsize must be finite and positive")
    return float(value)


def _qpoints(value: Iterable[Iterable[float]] | None) -> list[list[float]]:
    points = np.asarray([[0.0, 0.0, 0.0]] if value is None else list(value), dtype=float)
    if points.ndim != 2 or points.shape[0] == 0 or points.shape[1] != 3 or not np.isfinite(points).all():
        raise ValueError("qpoints must be a non-empty finite N by 3 array")
    return points.tolist()


def _new_phonopy(structure: AbacusStructure, supercell: list[int]):
    from phonopy import Phonopy
    from phonopy.structure.atoms import PhonopyAtoms

    atoms = structure.atoms
    phonopy_atoms = PhonopyAtoms(
        symbols=atoms.get_chemical_symbols(),
        cell=np.asarray(atoms.cell),
        scaled_positions=atoms.get_scaled_positions(wrap=False),
        masses=atoms.get_masses(),
        magnetic_moments=atoms.get_initial_magnetic_moments() if atoms.has("initial_magmoms") else None,
    )
    return Phonopy(phonopy_atoms, supercell_matrix=supercell)


def _displaced_structure(source: AbacusStructure, cell) -> AbacusStructure:
    from ase import Atoms

    atoms = Atoms(numbers=cell.numbers, cell=cell.cell, scaled_positions=cell.scaled_positions, masses=cell.masses, pbc=True)
    labels = _species_labels(source)
    atoms.info["abacus_atom_labels"] = [labels[symbol] for symbol in atoms.get_chemical_symbols()]
    metadata = source.atoms.info.get("abacus_species_meta")
    if metadata is not None:
        atoms.info["abacus_species_meta"] = deepcopy(metadata)
    if cell.magnetic_moments is not None:
        atoms.set_initial_magnetic_moments(np.asarray(cell.magnetic_moments))
    return AbacusStructure(atoms, source_format=source.source_format)


def _species_labels(structure: AbacusStructure) -> dict[str, str]:
    symbols = structure.atoms.get_chemical_symbols()
    labels = structure.atoms.info.get("abacus_atom_labels", symbols)
    element_labels: dict[str, str] = {}
    for symbol, label in zip(symbols, labels, strict=True):
        if symbol in element_labels and element_labels[symbol] != label:
            raise ValueError("phonon expansion does not support different ABACUS species for the same element")
        element_labels[symbol] = label
    return element_labels


def _normalize_cli_model(model, structure: AbacusStructure):
    """Convert phonopy's ABACUS au/eV-per-A model to A/eV-per-A.

    Phonopy's ABACUS interface expresses both cell and displacements in bohr,
    with an au-specific THz conversion factor.  Rebuilding a default-unit model
    converts the geometry, dataset and frequency convention together.  Source
    masses are restored because the phonopy ABACUS reader does not read them.
    """
    from phonopy import Phonopy
    from phonopy.interface.calculator import get_calculator_physical_units
    from phonopy.structure.atoms import PhonopyAtoms

    physical_units = get_calculator_physical_units(model.calculator)
    distance_to_A = (
        physical_units.distance_to_A
        if hasattr(physical_units, "distance_to_A")
        else physical_units["distance_to_A"]
    )
    if not np.array_equal(model.unitcell.numbers, structure.atoms.numbers):
        raise ValueError("phonopy CLI atom order differs from the staged source structure")
    cell = PhonopyAtoms(
        numbers=model.unitcell.numbers,
        cell=np.asarray(model.unitcell.cell) * distance_to_A,
        scaled_positions=model.unitcell.scaled_positions,
        masses=structure.atoms.get_masses(),
        magnetic_moments=model.unitcell.magnetic_moments,
    )
    normalized = Phonopy(
        cell,
        supercell_matrix=model.supercell_matrix,
        primitive_matrix=model.primitive_matrix,
        symprec=model.symmetry.tolerance * distance_to_A,
    )
    dataset = deepcopy(model.dataset)
    if "first_atoms" not in dataset:
        raise ValueError("phonon task plans require finite-displacement phonopy datasets")
    for displacement in dataset["first_atoms"]:
        displacement["displacement"] = np.asarray(displacement["displacement"]) * distance_to_A
    normalized.dataset = dataset
    return normalized


def _prepare_with_cli(root, structure: AbacusStructure, executable: str, setting_file: str, diagnostics: dict[str, Any]):
    resolved_executable = Path(shutil.which(executable) or executable)
    # New phonopy distributions split calculator initialization into this
    # companion command; older distributions retain it in ``phonopy``.
    initializer = resolved_executable.with_name("phonopy-init")
    if resolved_executable.name == "phonopy" and initializer.is_file():
        executable = str(initializer)
    setting = Path(setting_file)
    if not setting.is_absolute():
        setting = root.root / setting
    if not setting.is_file():
        raise FileNotFoundError(f"phonopy setting file does not exist: {setting}")
    # Never scan previous root-level STRU-* files after a failed external call.
    with tempfile.TemporaryDirectory(prefix="phonopy-prepare-", dir=root.root) as directory:
        staging = Path(directory)
        # The external ABACUS writer assumes literal element labels.  The
        # single-species-per-element check makes this private relabeling safe;
        # generated Forge units restore the original labels and resources.
        staged = AbacusStructure.from_input(structure.atoms)
        labels = _species_labels(structure)
        staged.atoms.info["abacus_atom_labels"] = staged.atoms.get_chemical_symbols()
        metadata = structure.atoms.info.get("abacus_species_meta", {})
        staged.atoms.info["abacus_species_meta"] = {
            element: deepcopy(metadata[label]) for element, label in labels.items() if label in metadata
        }
        (staging / "STRU").write_text(staged.to_stru(), encoding="utf-8")
        completed = subprocess.run(
            [executable, str(setting.resolve()), "--abacus", "-d"],
            cwd=staging, capture_output=True, text=True, check=False,
        )
        diagnostics.update({
            "phonopy_prepare_command": [executable, str(setting.resolve()), "--abacus", "-d"],
            "phonopy_prepare_returncode": completed.returncode,
            "phonopy_prepare_stdout_tail": "\n".join(completed.stdout.splitlines()[-20:]),
            "phonopy_prepare_stderr_tail": "\n".join(completed.stderr.splitlines()[-20:]),
            "method": "phonopy-executable-finite-displacement",
        })
        if completed.returncode != 0:
            return None
        yaml_file = staging / "phonopy_disp.yaml"
        if not yaml_file.is_file():
            diagnostics["missing_output"] = "phonopy_disp.yaml"
            return None
        from phonopy import load

        return _normalize_cli_model(load(yaml_file, produce_fc=False), structure)


def _plot_existing(root: Workspace, executable: str, setting_file: str) -> TaskResult:
    command = [executable, "-p", setting_file, "--abacus", "-s"]
    diagnostics: dict[str, Any] = {
        "phonopy": executable,
        "only_plot": True,
        "command": command,
        "method": "phonopy-existing-artifact-plot",
        "scientific_assessment": "unassessed",
    }
    try:
        completed = subprocess.run(command, cwd=root.root, capture_output=True, text=True, check=False)
        returncode = completed.returncode
        stdout, stderr = completed.stdout, completed.stderr
    except OSError as error:
        returncode = None
        stdout, stderr = "", str(error)
        diagnostics["exception_type"] = type(error).__name__
    diagnostics.update(
        phonopy_post_returncode=returncode,
        phonopy_post_stdout_tail="\n".join(stdout.splitlines()[-20:]),
        phonopy_post_stderr_tail="\n".join(stderr.splitlines()[-20:]),
    )
    stdout_path = root.write_text("reports/phonopy_plot_stdout.log", stdout)
    stderr_path = root.write_text("reports/phonopy_plot_stderr.log", stderr)
    plot_artifacts = {
        path.name: str(path)
        for path in root.root.iterdir()
        if path.is_file() and path.suffix.lower() in {".pdf", ".png", ".svg", ".yaml", ".dat"}
    }
    summary = {"only_plot": True, "phonon_artifacts": sorted(plot_artifacts)}
    metrics_path = write_task_result(root, "reports/metrics_phonon_plot.json", {
        "summary": summary, "diagnostics": diagnostics,
    })
    return TaskResult(
        task="phonon", workspace=root.root, status="completed" if returncode == 0 else "failed",
        summary=summary, diagnostics=diagnostics,
        artifacts={
            **plot_artifacts,
            **{path.relative_to(root.root).as_posix(): str(path) for path in (stdout_path, stderr_path, metrics_path)},
        },
    )
