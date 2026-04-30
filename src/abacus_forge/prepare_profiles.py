"""Task-aware defaults for single-workspace prepares."""

from __future__ import annotations

from typing import Any

from abacus_forge.structure_recognition import StructureMetadata

TASK_DEFAULTS: dict[str, dict[str, Any]] = {
    "scf": {"calculation": "scf"},
    "relax": {"calculation": "relax", "cal_force": 1, "cal_stress": 1},
    "cell-relax": {"calculation": "cell-relax", "cal_force": 1, "cal_stress": 1},
    "band": {"calculation": "nscf", "out_band": 1},
    "dos": {"calculation": "nscf", "out_dos": 1, "out_pdos": 1},
    "pdos": {"calculation": "nscf", "out_dos": 1, "out_pdos": 1},
}


def build_task_parameters(
    task: str | None,
    *,
    metadata: StructureMetadata | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged = dict(TASK_DEFAULTS.get((task or "scf").lower(), {}))
    if metadata is not None:
        if metadata.structure_class == "layer" and "dip_cor_flag" not in merged:
            merged["dip_cor_flag"] = 1
        if metadata.structure_class in {"cluster", "cubic_cluster"} and "gamma_only" not in merged:
            merged["gamma_only"] = 1
    if parameters:
        merged.update(parameters)
    return merged
