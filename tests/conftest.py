from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
INSTALLED_PACKAGE_ONLY_ENV = "ABACUS_FORGE_INSTALLED_PACKAGE_ONLY"


def _uses_installed_package_only() -> bool:
    """Opt-in mode for proving a built wheel, not the source checkout, is tested."""
    return os.environ.get(INSTALLED_PACKAGE_ONLY_ENV) == "1"


if not _uses_installed_package_only() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


_FILE_MARKERS: dict[str, tuple[str, ...]] = {
    "test_assets.py": ("core",),
    "test_input_io.py": ("core",),
    "test_structure.py": ("core",),
    "test_modify.py": ("core",),
    "test_perturbation.py": ("core",),
    "test_dos_data.py": ("core",),
    "test_dos_postprocess.py": ("core",),
    "test_cube.py": ("core",),
    "test_contracts.py": ("core",),
    "test_export_contracts.py": ("core",),
    "test_package_contract.py": ("core",),
    "test_package_metadata_drift.py": ("core",),
    "test_installed_package_mode.py": ("core",),
    "test_postprocess_algorithms.py": ("core",),
    "test_cohp_iao.py": ("core",),
    "test_api.py": ("integration",),
    "test_tasks.py": ("integration",),
    "test_units.py": ("integration",),
    "test_workspace.py": ("integration",),
    "test_export_io.py": ("integration",),
    "test_postprocess_services.py": ("integration",),
    "test_real_smoke_freshness.py": ("integration",),
    "test_cli.py": ("cli",),
    "test_cli_process.py": ("cli",),
    "test_machine_cli.py": ("cli",),
    "test_export_machine_cli.py": ("cli",),
    "test_export_services.py": ("integration",),
    "test_md_machine_cli.py": ("cli",),
    "test_postprocess_machine_cli.py": ("cli",),
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
    "test_abacuslite_release_gate.py": ("compat",),
    "test_parser_backend.py": ("compat",),
    "test_pyatb.py": ("pyatb",),
    "test_pyatb_manifest.py": ("pyatb",),
    "test_pyatb_typed.py": ("pyatb",),
    "test_composite.py": ("composite",),
    "test_composite_elastic_fit.py": ("composite",),
    "test_maturation_packs.py": ("experimental",),
    "test_property_manifest.py": ("experimental",),
    "test_architecture.py": ("core",),
}

_PORTFOLIO_MARKERS = frozenset({
    "core", "integration", "cli", "compat", "pyatb", "composite",
    "experimental", "real_smoke", "benchmark",
})

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
    "test_vacancy_pack_machine_execute_and_collect": (
        "ABACUS_FORGE_VACANCY_SMOKE_WORKSPACE",
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

_DUAL_TRACK_TEST_NAME = "test_native_and_abacuslite_collect_real_output_parity"
_DUAL_TRACK_RELEASE_GATE_ENV = "ABACUS_FORGE_ABACUSLITE_REQUIRE_FULL_MATRIX"


def pytest_configure(config: pytest.Config) -> None:
    if not _uses_installed_package_only():
        return
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support.installed_package import (
        NotWheelInstalledError,
        validate_wheel_install,
    )

    import abacus_forge

    try:
        validate_wheel_install(abacus_forge)
    except NotWheelInstalledError as error:
        raise pytest.UsageError(
            f"{INSTALLED_PACKAGE_ONLY_ENV}=1 requires a wheel install: {error}"
        ) from error


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
    dual_track_release_gate = os.environ.get(_DUAL_TRACK_RELEASE_GATE_ENV) == "1"
    unclassified: list[str] = []
    for item in items:
        path = Path(str(item.fspath))
        filename = path.name
        is_root_test = path.parent == ROOT / "tests"
        # The file map covers root-level suites. Nested suites classify their
        # own tests, so a reused basename cannot silently inherit a boundary.
        for marker_name in _FILE_MARKERS.get(filename, ()) if is_root_test else ():
            item.add_marker(getattr(pytest.mark, marker_name))
        if path.is_relative_to(ROOT / "tests") and not any(
            marker.name in _PORTFOLIO_MARKERS for marker in item.iter_markers()
        ):
            unclassified.append(item.nodeid)
        relative_parts = path.parts
        if "real_smoke" in relative_parts:
            is_dual_track_release_gate = (
                dual_track_release_gate and item.name == _DUAL_TRACK_TEST_NAME
            )
            if not config.getoption("--run-real-smoke") and not is_dual_track_release_gate:
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
                if missing_env and not is_dual_track_release_gate:
                    item.add_marker(
                        pytest.mark.skip(
                            reason="set " + " and ".join(missing_env)
                        )
                    )
        if "benchmark" in relative_parts and not config.getoption("--run-benchmark"):
            item.add_marker(pytest.mark.skip(reason="pass --run-benchmark to run benchmark tests"))
    if unclassified:
        raise pytest.UsageError(
            "tests without a portfolio marker (classify in tests/conftest.py "
            "or explicitly on the test):\n" + "\n".join(unclassified[:20])
            + (f"\n... and {len(unclassified) - 20} more" if len(unclassified) > 20 else "")
        )
