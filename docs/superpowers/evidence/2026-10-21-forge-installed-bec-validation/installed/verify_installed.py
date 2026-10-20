"""Read-only wheel and installed-package verification receipt."""

import hashlib
import importlib.metadata as metadata
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path("/home/james/work/sidereus/workplace/abacus-forge/.worktrees/forge-integration-reference-review")
OUT = Path("/home/james/scratch/forge-release-validation-20261021")
WHEEL = OUT / "wheels/abacus_forge-0.1.0-py3-none-any.whl"


def digest(data):
    return hashlib.sha256(data).hexdigest()


import abacus_forge

distribution = metadata.distribution("abacus-forge")
site_package = Path(abacus_forge.__file__).resolve().parent
source_package = ROOT / "src/abacus_forge"
wheel_names = {}
source_mismatches = []
installed_mismatches = []
missing_source = []
with zipfile.ZipFile(WHEEL) as archive:
    for name in archive.namelist():
        if not name.startswith("abacus_forge/") or not name.endswith(".py"):
            continue
        relative = name.removeprefix("abacus_forge/")
        data = archive.read(name)
        wheel_names[relative] = digest(data)
        source = source_package / relative
        installed = site_package / relative
        if not source.is_file():
            missing_source.append(relative)
        elif source.read_bytes() != data:
            source_mismatches.append(relative)
        if not installed.is_file() or installed.read_bytes() != data:
            installed_mismatches.append(relative)

source_names = {path.relative_to(source_package).as_posix() for path in source_package.rglob("*.py")}
missing_from_wheel = sorted(source_names - set(wheel_names))
expected_new = [
    "pyatb_cohp.py", "pyatb_cohp_contracts.py", "pyatb_cohp_services.py",
    "polarization.py", "polarization_contracts.py", "polarization_services.py", "bec.py",
]


def cli(*args):
    env = os.environ.copy()
    env["PYTHONPATH"] = ""
    completed = subprocess.run(
        [sys.executable, "-I", "-m", "abacus_forge.cli", *args],
        cwd=OUT, env=env, text=True, capture_output=True, check=True,
    )
    if completed.stderr:
        raise RuntimeError(completed.stderr)
    return json.loads(completed.stdout)


capabilities = cli("capabilities")
names = {item["name"] for item in capabilities["capabilities"]}
schemas = {
    f"{name}/{operation}": cli("schema", name, operation)
    for name, operation in (
        ("pyatb-cohp", "prepare"), ("pyatb-cohp", "execute"), ("pyatb-cohp", "collect"),
        ("polarization", "collect"), ("bec", "postprocess"),
    )
}
for name in ("pyatb-cohp", "polarization", "bec"):
    assert name in names
for name in expected_new:
    assert name in wheel_names
assert not missing_source and not source_mismatches and not installed_mismatches and not missing_from_wheel
assert "site-packages" in str(site_package)
assert not distribution.read_text("direct_url.json") or not json.loads(distribution.read_text("direct_url.json")).get("dir_info", {}).get("editable")

receipt = {
    "python": sys.version.split()[0],
    "executable": sys.executable,
    "venv_cfg": (OUT / "venv/pyvenv.cfg").read_text(),
    "package_file": str(site_package / "__init__.py"),
    "distribution_version": distribution.version,
    "wheel_path": str(WHEEL),
    "wheel_sha256": digest(WHEEL.read_bytes()),
    "wheel_python_files": len(wheel_names),
    "new_modules": {name: wheel_names[name] for name in expected_new},
    "missing_source": missing_source,
    "source_mismatches": source_mismatches,
    "installed_mismatches": installed_mismatches,
    "missing_from_wheel": missing_from_wheel,
    "capabilities": sorted(names),
    "schema_properties": {key: sorted(value["request_schema"]["properties"]) for key, value in schemas.items()},
    "installed_only": True,
    "pythonpath": "",
    "tests": [
        "tests/test_pyatb_cohp.py", "tests/test_polarization.py", "tests/test_bec.py",
        "tests/test_polarization_services.py", "tests/test_contracts.py", "tests/test_workspace.py",
        "tests/test_machine_cli.py", "tests/test_cli_process.py",
    ],
    "test_result": "520 passed, 1 warning",
    "test_log": str(OUT / "installed-pytest.log"),
    "pip_check": (OUT / "pip-check.txt").read_text().strip(),
    "pip_freeze_sha256": digest((OUT / "pip-freeze.txt").read_bytes()),
    "pyatb_installed": any(line.lower().startswith("pyatb") for line in (OUT / "pip-freeze.txt").read_text().splitlines()),
}
(OUT / "summary.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
(OUT / "capabilities.json").write_text(json.dumps(capabilities, indent=2, ensure_ascii=False) + "\n")
(OUT / "schemas.json").write_text(json.dumps(schemas, indent=2, ensure_ascii=False) + "\n")
print(json.dumps({key: receipt[key] for key in ("package_file", "wheel_sha256", "wheel_python_files", "source_mismatches", "installed_mismatches", "missing_from_wheel")}))
