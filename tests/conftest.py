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
    "test_api.py": ("integration",),
    "test_tasks.py": ("integration",),
    "test_units.py": ("integration",),
    "test_cli.py": ("cli",),
    "test_cli_process.py": ("cli",),
    "test_machine_cli.py": ("cli",),
    "test_result_contract.py": ("integration",),
    "test_service_status.py": ("integration",),
    "test_collect_abacus_reference.py": ("compat",),
    "test_pyatb.py": ("pyatb",),
    "test_composite.py": ("composite",),
    "test_maturation_packs.py": ("experimental",),
}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-real-smoke",
        action="store_true",
        default=False,
        help="run tests marked real_smoke against the supplied ABACUS workspace",
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
                item.add_marker(pytest.mark.skip(reason="pass --run-real-smoke to run real ABACUS smoke tests"))
            elif not all(
                os.environ.get(name)
                for name in (
                    "ABACUS_FORGE_REAL_SMOKE_WORKSPACE",
                    "ABACUS_FORGE_ABACUS_EXECUTABLE",
                )
            ):
                item.add_marker(
                    pytest.mark.skip(
                        reason="set ABACUS_FORGE_REAL_SMOKE_WORKSPACE and ABACUS_FORGE_ABACUS_EXECUTABLE"
                    )
                )
        if "benchmark" in relative_parts and not config.getoption("--run-benchmark"):
            item.add_marker(pytest.mark.skip(reason="pass --run-benchmark to run benchmark tests"))
