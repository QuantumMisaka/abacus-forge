"""Task-aware defaults for single-workspace prepares."""

from __future__ import annotations

from typing import Any

from abacus_forge.structure_recognition import StructureMetadata

TASK_DEFAULTS: dict[str, dict[str, Any]] = {
    "scf": {"calculation": "scf"},
    "relax": {"calculation": "relax", "cal_force": 1, "cal_stress": 1},
    "cell-relax": {"calculation": "cell-relax", "cal_force": 1, "cal_stress": 1},
    "md": {
        "calculation": "md",
        "cal_force": 1,
        "md_type": "nve",
        "md_nstep": 10,
        "md_dt": 1.0,
        "md_tfirst": 300,
        "md_tlast": 300,
        "md_dumpfreq": 1,
    },
    "band": {"calculation": "nscf", "out_band": 1},
    "dos": {"calculation": "nscf", "out_dos": 1},
}

_FORBIDDEN_DOS_PARAMETERS = {"dos_scale", "dos_nche"}
_DOS_CONTROL_PARAMETERS = {
    "include_tdos",
    "include_pdos",
    "include_ldos",
    "pdos_mode",
    "pdos_atom_indices",
    "plot_emin",
    "plot_emax",
    "save_data",
    "save_plot",
    "suffix",
}


def build_task_parameters(
    task: str | None,
    *,
    metadata: StructureMetadata | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_task = (task or "scf").lower()
    if normalized_task not in TASK_DEFAULTS:
        raise ValueError(f"unsupported task: {normalized_task}")
    supplied = dict(parameters or {})
    if normalized_task == "dos":
        forbidden = sorted(_FORBIDDEN_DOS_PARAMETERS.intersection(supplied))
        if forbidden:
            raise ValueError(f"unsupported DOS parameter(s): {', '.join(forbidden)}")
    controls = {key: supplied.pop(key) for key in list(supplied) if key in _DOS_CONTROL_PARAMETERS}
    merged = dict(TASK_DEFAULTS[normalized_task])
    if metadata is not None:
        if metadata.structure_class == "layer" and "dip_cor_flag" not in merged:
            merged["dip_cor_flag"] = 1
        if metadata.structure_class in {"cluster", "cubic_cluster"} and "gamma_only" not in merged:
            merged["gamma_only"] = 1
    if supplied:
        merged.update(supplied)
    if normalized_task == "dos":
        include_tdos = _truthy(controls.get("include_tdos", True))
        include_pdos = _truthy(controls.get("include_pdos", True))
        include_ldos = _truthy(controls.get("include_ldos", False))
        if include_ldos:
            raise ValueError("LDOS is reserved but not implemented")
        if not include_tdos and not include_pdos:
            raise ValueError("dos task requires at least one of include_tdos/include_pdos")
        basis_type = str(merged.get("basis_type", "pw")).lower()
        merged["out_dos"] = 2 if include_pdos and basis_type == "lcao" else 1
    return merged


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)
