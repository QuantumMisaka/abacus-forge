"""Helpers for writing sample ABACUS output artifacts into one workspace."""

from __future__ import annotations

import shutil
from pathlib import Path

from abacus_forge.band_data import write_sample_band_artifacts
from abacus_forge.dos_data import write_sample_dos_artifacts, write_sample_dos_family_artifacts
from abacus_forge.workspace import Workspace


def write_sample_analysis_outputs(
    workspace: Workspace,
    *,
    run_bands: bool = False,
    run_dos: bool = False,
    include_pdos: bool = False,
    relax_requested: bool = False,
    relax_workflow_goal: str = "relax",
    band_workflow_goal: str = "band",
    dos_workflow_goal: str = "dos",
    dos_family_workflow_goal: str = "dos",
    band_gap: float = 1.2,
    projected_species: list[str] | None = None,
    energy_window: tuple[float, float] = (-10.0, 10.0),
    fermi_energy: float = 3.2,
    relaxed_structure_placeholder: str = "Relaxed structure placeholder\n",
) -> None:
    duplicate_dir = workspace.outputs_dir / "OUT.ABACUS"
    if relax_requested:
        _write_relaxed_structure(
            workspace,
            placeholder=relaxed_structure_placeholder,
            workflow_goal=relax_workflow_goal,
        )
    if run_bands:
        write_sample_band_artifacts(workspace.outputs_dir, duplicate_dir=duplicate_dir)
        workspace.write_json(
            "reports/metrics_band.json",
            {
                "band_gap": band_gap,
                "cbm": {"energy": 0.6, "kpoint_index": 1},
                "vbm": {"energy": -0.6, "kpoint_index": 1},
                "workflow_goal": band_workflow_goal,
            },
        )
    if run_dos:
        if include_pdos:
            write_sample_dos_family_artifacts(workspace.outputs_dir, duplicate_dir=duplicate_dir)
        else:
            write_sample_dos_artifacts(workspace.outputs_dir, duplicate_dir=duplicate_dir)
        workspace.write_json(
            "reports/metrics_dos.json",
            {
                "energy_window": {"emin_ev": energy_window[0], "emax_ev": energy_window[1]},
                "fermi_energy": fermi_energy,
                "workflow_goal": dos_workflow_goal,
            },
        )
    if include_pdos:
        workspace.write_json(
            "reports/metrics_dos_family.json",
            {
                "projection_mode": "species",
                "species": list(projected_species or []),
                "workflow_goal": dos_family_workflow_goal,
            },
        )


def _write_relaxed_structure(workspace: Workspace, *, placeholder: str, workflow_goal: str) -> None:
    source_stru = workspace.inputs_dir / "STRU"
    target_stru = workspace.outputs_dir / "OUT.ABACUS" / "STRU_ION_D"
    target_stru.parent.mkdir(parents=True, exist_ok=True)
    if source_stru.exists():
        shutil.copyfile(source_stru, target_stru)
    else:
        workspace.write_text("outputs/OUT.ABACUS/STRU_ION_D", placeholder)
    workspace.write_json(
        "reports/metrics_relax.json",
        {
            "converged": True,
            "final_structure_available": True,
            "workflow_goal": workflow_goal,
        },
    )
