"""Public import compatibility and lightweight package import checks."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.core

SRC = Path(__file__).resolve().parents[1] / "src"

# Frozen from the original eager package imports. Keep this independent of the lazy map.
EXPECTED_EXPORTS = (
    'AbacusStructure',
    'ArtifactRecord',
    'ArtifactRef',
    'ExportDocument',
    'ExportRequest',
    'EXPORT_SCHEMA_VERSION',
    'ExportService',
    'ExportServiceProtocol',
    'ExportServiceSet',
    'AtstNebExecuteRequest',
    'AtstNebPostprocessRequest',
    'AtstNebPrepareRequest',
    'AtstNebExecuteService',
    'AtstNebPostprocessService',
    'AtstNebPrepareService',
    'AtstNebServiceSet',
    'BandPostprocessRequest',
    'BandPostprocessService',
    'CapabilityDescriptor',
    'BandData',
    'CollectionResult',
    'CheckRecord',
    'CohpPostprocessRequest',
    'CubeData',
    'DOSData',
    'DOSFamilyData',
    'DosPostprocessRequest',
    'CohpPostprocessService',
    'DosPostprocessService',
    'ForgeRequest',
    'ForgeErrorEnvelope',
    'ForgeResultEnvelope',
    'ForgeServices',
    'CollectService',
    'ExecuteService',
    'LocalDOSData',
    'LocalRunner',
    'MetricRecord',
    'ModifyService',
    'Observation',
    'OperationOutcome',
    'OperationRef',
    'OperationStatus',
    'PDOSData',
    'PyatbBandCollectRequest',
    'PyatbBandCollectService',
    'PyatbBandCollectServiceProtocol',
    'PyatbBandExecuteRequest',
    'PyatbBandExecuteService',
    'PyatbBandExecuteServiceProtocol',
    'PyatbBandPrepareRequest',
    'PyatbBandPrepareService',
    'PyatbBandPrepareServiceProtocol',
    'PyatbBandServiceSet',
    'PYATB_MANIFEST_SCHEMA_VERSION',
    'PyatbManifest',
    'PyatbManifestEntry',
    'PROPERTY_MANIFEST_SCHEMA_VERSION',
    'PropertyManifest',
    'PropertyManifestEntry',
    'classify_pyatb_output',
    'PostprocessService',
    'PostprocessServiceSet',
    'PrepareService',
    'RunResult',
    'RelaxCollectRequest',
    'RelaxExecuteRequest',
    'RelaxModifyRequest',
    'RelaxPrepareRequest',
    'RelaxServiceSet',
    'MdCollectRequest',
    'MdExecuteRequest',
    'MdModifyRequest',
    'MdPrepareRequest',
    'MdPostprocessRequest',
    'MdPostprocessService',
    'MdPostprocessServiceProtocol',
    'MdPostprocessServiceSet',
    'MdServiceSet',
    'ScfCollectRequest',
    'ScfExecuteRequest',
    'ScfModifyRequest',
    'ScfPrepareRequest',
    'ScfCollectService',
    'ScfExecuteService',
    'ScfModifyService',
    'ScfPrepareService',
    'ScfServiceSet',
    'TaskResult',
    'UnitModifyResult',
    'UnitModifySpec',
    'UnitPrepareResult',
    'UnitSpec',
    'Workspace',
    'add_cubes',
    'collect',
    'capabilities_document',
    'collect_pyatb',
    'collect_unit',
    'execute',
    'execute_unit',
    'export',
    'modify_input',
    'modify_kpt',
    'modify_stru',
    'modify_unit',
    'planar_average',
    'perturb_structure',
    'prepare',
    'prepare_pyatb_band',
    'prepare_unit',
    'run',
    'run_band',
    'run_band_sequence',
    'run_cell_relax',
    'run_dos',
    'run_dos_sequence',
    'run_md',
    'run_pyatb',
    'run_relax',
    'run_scf',
    'run_task',
    'request_schema_document',
    'subtract_cubes',
)

EXPECTED_MODULES = {
    'abacus_forge.structure': ('AbacusStructure',),
    'abacus_forge.contracts': ('ArtifactRecord', 'ArtifactRef', 'AtstNebExecuteRequest', 'AtstNebPostprocessRequest', 'AtstNebPrepareRequest', 'CapabilityDescriptor', 'CheckRecord', 'ForgeRequest', 'ForgeErrorEnvelope', 'ForgeResultEnvelope', 'MetricRecord', 'Observation', 'OperationOutcome', 'OperationRef', 'OperationStatus', 'ScfCollectRequest', 'ScfExecuteRequest', 'ScfModifyRequest', 'ScfPrepareRequest'),
    'abacus_forge.export_contracts': ('ExportDocument', 'ExportRequest', 'EXPORT_SCHEMA_VERSION'),
    'abacus_forge.export_services': ('ExportService', 'ExportServiceProtocol', 'ExportServiceSet'),
    'abacus_forge.atst_neb': ('AtstNebExecuteService', 'AtstNebPostprocessService', 'AtstNebPrepareService', 'AtstNebServiceSet'),
    'abacus_forge.postprocess_contracts': ('BandPostprocessRequest', 'CohpPostprocessRequest', 'DosPostprocessRequest'),
    'abacus_forge.postprocess_services': ('BandPostprocessService', 'CohpPostprocessService', 'DosPostprocessService', 'PostprocessService', 'PostprocessServiceSet'),
    'abacus_forge.band_data': ('BandData',),
    'abacus_forge.result': ('CollectionResult', 'RunResult', 'TaskResult'),
    'abacus_forge.cube': ('CubeData', 'add_cubes', 'planar_average', 'subtract_cubes'),
    'abacus_forge.dos_data': ('DOSData', 'DOSFamilyData', 'LocalDOSData', 'PDOSData'),
    'abacus_forge.services': ('ForgeServices', 'CollectService', 'ExecuteService', 'ModifyService', 'PrepareService', 'RelaxServiceSet', 'MdServiceSet', 'ScfCollectService', 'ScfExecuteService', 'ScfModifyService', 'ScfPrepareService', 'ScfServiceSet'),
    'abacus_forge.runner': ('LocalRunner',),
    'abacus_forge.pyatb_contracts': ('PyatbBandCollectRequest', 'PyatbBandExecuteRequest', 'PyatbBandPrepareRequest'),
    'abacus_forge.pyatb_services': ('PyatbBandCollectService', 'PyatbBandCollectServiceProtocol', 'PyatbBandExecuteService', 'PyatbBandExecuteServiceProtocol', 'PyatbBandPrepareService', 'PyatbBandPrepareServiceProtocol', 'PyatbBandServiceSet'),
    'abacus_forge.pyatb_manifest': ('PYATB_MANIFEST_SCHEMA_VERSION', 'PyatbManifest', 'PyatbManifestEntry', 'classify_pyatb_output'),
    'abacus_forge.property_manifest': ('PROPERTY_MANIFEST_SCHEMA_VERSION', 'PropertyManifest', 'PropertyManifestEntry'),
    'abacus_forge.relax_contracts': ('RelaxCollectRequest', 'RelaxExecuteRequest', 'RelaxModifyRequest', 'RelaxPrepareRequest'),
    'abacus_forge.md_contracts': ('MdCollectRequest', 'MdExecuteRequest', 'MdModifyRequest', 'MdPrepareRequest'),
    'abacus_forge.md_postprocess_contracts': ('MdPostprocessRequest',),
    'abacus_forge.md_postprocess_services': ('MdPostprocessService', 'MdPostprocessServiceProtocol', 'MdPostprocessServiceSet'),
    'abacus_forge.api': ('UnitModifyResult', 'UnitModifySpec', 'UnitPrepareResult', 'UnitSpec', 'collect', 'collect_unit', 'execute', 'execute_unit', 'export', 'modify_unit', 'prepare', 'prepare_unit', 'run'),
    'abacus_forge.workspace': ('Workspace',),
    'abacus_forge.discovery': ('capabilities_document', 'request_schema_document'),
    'abacus_forge.pyatb': ('collect_pyatb', 'prepare_pyatb_band', 'run_pyatb'),
    'abacus_forge.modify': ('modify_input', 'modify_kpt', 'modify_stru'),
    'abacus_forge.perturbation': ('perturb_structure',),
    'abacus_forge.tasks': ('run_band', 'run_band_sequence', 'run_cell_relax', 'run_dos', 'run_dos_sequence', 'run_md', 'run_relax', 'run_scf', 'run_task'),
}

def _isolated(code: str) -> Any:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run([sys.executable, "-c", code], env=env, text=True, capture_output=True, check=True)
    return json.loads(proc.stdout)

def test_input_io_import_does_not_load_unrelated_services_or_science_packages() -> None:
    result = _isolated("""
import json, sys
import abacus_forge.input_io
print(json.dumps(sorted(sys.modules)))
""")
    modules = set(result)
    forbidden = (
        "abacus_forge.services", "abacus_forge.md_postprocess_services",
        "abacus_forge.pyatb_services", "abacus_forge.atst_neb",
        "abacus_forge.postprocess_services", "abacus_forge.md_postprocess",
        "abacus_forge.pyatb", "abacus_forge.cube", "abacus_forge.band_data",
        "numpy", "scipy", "matplotlib", "ase", "dpdata", "pyatb", "atst_tools",
    )
    assert not {name for name in modules if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)}

def test_package_exports_retain_order_and_source_object_identity() -> None:
    import abacus_forge as forge
    assert forge.__version__ == "0.1.0"
    assert tuple(forge.__all__) == EXPECTED_EXPORTS
    assert set(EXPECTED_EXPORTS) <= set(dir(forge))
    for module_name, names in EXPECTED_MODULES.items():
        module = importlib.import_module(module_name)
        for name in names:
            assert getattr(forge, name) is getattr(module, name), name

def test_lazy_exports_and_regular_submodule_imports_in_fresh_process() -> None:
    result = _isolated("""
import json, sys
import abacus_forge as forge
before = sorted(sys.modules)
from abacus_forge import input_io
from abacus_forge import UnitSpec, UnitModifySpec
after = sorted(sys.modules)
print(json.dumps({"before": before, "after": after, "submodule": input_io is sys.modules["abacus_forge.input_io"], "identity": UnitSpec.__module__ == "abacus_forge.api" and UnitModifySpec.__module__ == "abacus_forge.api"}))
""")
    assert "abacus_forge.services" not in result["before"]
    assert result["submodule"] and result["identity"]
    assert "abacus_forge.api" in result["after"]

def test_parallel_export_access_returns_same_objects() -> None:
    result = _isolated("""
import importlib, json
from concurrent.futures import ThreadPoolExecutor
import abacus_forge as forge
names = ('UnitSpec', 'ScfPrepareRequest', 'MdPostprocessServiceSet', 'AbacusStructure')
with ThreadPoolExecutor(max_workers=8) as pool:
    values = list(pool.map(lambda name: getattr(forge, name), names * 8))
sources = ('api', 'contracts', 'md_postprocess_services', 'structure')
ok = all(value is getattr(importlib.import_module('abacus_forge.' + sources[i % 4]), names[i % 4]) for i, value in enumerate(values))
print(json.dumps({'ok': ok, 'repeated': all(values[i] is values[i + 4] for i in range(28))}))
""")
    assert result == {"ok": True, "repeated": True}
