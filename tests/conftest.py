from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


_FILE_MARKERS: dict[str, tuple[str, ...]] = {
    "test_input_io.py": ("core",),
    "test_structure.py": ("core",),
    "test_modify.py": ("core",),
    "test_perturbation.py": ("core",),
    "test_dos_data.py": ("core",),
    "test_dos_postprocess.py": ("core",),
    "test_cube.py": ("core",),
    "test_api.py": ("integration",),
    "test_tasks.py": ("integration",),
    "test_units.py": ("integration",),
    "test_cli.py": ("cli",),
    "test_cli_process.py": ("cli",),
    "test_machine_cli.py": ("cli",),
    "test_export_machine_cli.py": ("cli",),
    "test_export_services.py": ("integration",),
    "test_md_machine_cli.py": ("cli",),
    "test_result_contract.py": ("integration",),
    "test_service_status.py": ("integration",),
    "test_typed_calculation_guards.py": ("integration",),
    "test_md_contracts.py": ("integration",),
    "test_md_services.py": ("integration",),
    "test_md_postprocess_contracts.py": ("integration",),
    "test_md_postprocess_algorithms.py": ("core",),
    "test_md_postprocess_services.py": ("integration",),
    "test_md_postprocess_machine_cli.py": ("cli",),
    "test_atst_neb.py": ("integration",),
    "test_collect_abacus_reference.py": ("compat",),
    "test_pyatb.py": ("pyatb",),
    "test_composite.py": ("composite",),
    "test_maturation_packs.py": ("experimental",),
    "test_property_manifest.py": ("experimental",),
    "test_architecture.py": ("core",),
}

_REAL_SMOKE_ENV_BY_TEST: dict[str, tuple[str, ...]] = {
    "test_real_abacus_scf_execute_and_collect": (
        "ABACUS_FORGE_REAL_SMOKE_WORKSPACE",
        "ABACUS_FORGE_ABACUS_EXECUTABLE",
    ),
    "test_typed_scf_machine_execute_and_collect": (
        "ABACUS_FORGE_REAL_SMOKE_WORKSPACE",
        "ABACUS_FORGE_ABACUS_EXECUTABLE",
    ),
    "test_typed_md_machine_execute_and_collect": (
        "ABACUS_FORGE_MD_SMOKE_WORKSPACE",
        "ABACUS_FORGE_ABACUS_EXECUTABLE",
    ),
    "test_typed_relax_machine_execute_and_collect": (
        "ABACUS_FORGE_RELAX_SMOKE_WORKSPACE",
        "ABACUS_FORGE_ABACUS_EXECUTABLE",
    ),
    "test_typed_lcao_scf_machine_execute_and_collect": (
        "ABACUS_FORGE_LCAO_SMOKE_WORKSPACE",
        "ABACUS_FORGE_ABACUS_EXECUTABLE",
    ),
    "test_typed_lcao_nspin2_machine_execute_and_collect": (
        "ABACUS_FORGE_LCAO_NSPIN2_SMOKE_WORKSPACE",
        "ABACUS_FORGE_ABACUS_EXECUTABLE",
    ),
    "test_typed_lcao_matrices_machine_execute_and_collect": (
        "ABACUS_FORGE_LCAO_MATRICES_SMOKE_WORKSPACE",
        "ABACUS_FORGE_ABACUS_EXECUTABLE",
    ),
    "test_typed_pyatb_band_machine_process_smoke": (
        "ABACUS_FORGE_PYATB_SMOKE_WORKSPACE",
        "ABACUS_FORGE_PYATB_EXECUTABLE",
        "ABACUS_FORGE_PYATB_SMOKE_FERMI_ENERGY",
    ),
    "test_atst_neb_machine_process_smoke": ("ABACUS_FORGE_ATST_EXECUTABLE",),
    "test_native_and_abacuslite_collect_real_output_parity": (
        "ABACUS_FORGE_ABACUSLITE_DUAL_TRACK_MATRIX",
        "ABACUS_FORGE_ABACUSLITE_PATH",
    ),
}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-real-smoke",
        action="store_true",
        default=False,
        help="run tests marked real_smoke against supplied external engine/workspace inputs",
    )
    parser.addoption(
        "--run-benchmark",
        action="store_true",
        default=False,
        help="run tests marked benchmark",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        filename = Path(str(item.fspath)).name
        for marker_name in _FILE_MARKERS.get(filename, ()):
            item.add_marker(getattr(pytest.mark, marker_name))
        relative_parts = Path(str(item.fspath)).parts
        if "real_smoke" in relative_parts:
            if not config.getoption("--run-real-smoke"):
                item.add_marker(pytest.mark.skip(reason="pass --run-real-smoke to run real process smoke tests"))
            else:
                required_env = _REAL_SMOKE_ENV_BY_TEST.get(
                    item.name,
                    (
                        "ABACUS_FORGE_REAL_SMOKE_WORKSPACE",
                        "ABACUS_FORGE_ABACUS_EXECUTABLE",
                    ),
                )
                missing_env = tuple(name for name in required_env if not os.environ.get(name))
                if missing_env:
                    item.add_marker(
                        pytest.mark.skip(
                            reason="set " + " and ".join(missing_env)
                        )
                    )
        if "benchmark" in relative_parts and not config.getoption("--run-benchmark"):
            item.add_marker(pytest.mark.skip(reason="pass --run-benchmark to run benchmark tests"))
