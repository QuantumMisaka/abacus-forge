"""ABACUS-Forge minimal execution substrate."""

from abacus_forge.api import UnitModifyResult, UnitModifySpec, UnitPrepareResult, UnitSpec, collect, collect_unit, execute, execute_unit, export, modify_unit, prepare, prepare_unit, run
from abacus_forge.band_data import BandData
from abacus_forge.contracts import ArtifactRecord, ArtifactRef, CapabilityDescriptor, CheckRecord, ForgeErrorEnvelope, ForgeRequest, ForgeResultEnvelope, MetricRecord, Observation, OperationOutcome, OperationRef, OperationStatus, ScfCollectRequest, ScfExecuteRequest, ScfModifyRequest, ScfPrepareRequest
from abacus_forge.discovery import capabilities_document, request_schema_document
from abacus_forge.cube import CubeData, add_cubes, planar_average, subtract_cubes
from abacus_forge.dos_data import DOSData, DOSFamilyData, LocalDOSData, PDOSData
from abacus_forge.modify import modify_input, modify_kpt, modify_stru
from abacus_forge.perturbation import perturb_structure
from abacus_forge.pyatb import collect_pyatb, prepare_pyatb_band, run_pyatb
from abacus_forge.result import CollectionResult, RunResult, TaskResult
from abacus_forge.services import (
    CollectService,
    ExecuteService,
    ForgeServices,
    ModifyService,
    PrepareService,
    ScfCollectService,
    ScfExecuteService,
    ScfModifyService,
    ScfPrepareService,
    ScfServiceSet,
)
from abacus_forge.runner import LocalRunner
from abacus_forge.structure import AbacusStructure
from abacus_forge.tasks import run_band, run_band_sequence, run_cell_relax, run_dos, run_dos_sequence, run_md, run_relax, run_scf, run_task
from abacus_forge.workspace import Workspace

__all__ = [
    "AbacusStructure",
    "ArtifactRecord",
    "ArtifactRef",
    "CapabilityDescriptor",
    "BandData",
    "CollectionResult",
    "CheckRecord",
    "CubeData",
    "DOSData",
    "DOSFamilyData",
    "ForgeRequest",
    "ForgeErrorEnvelope",
    "ForgeResultEnvelope",
    "ForgeServices",
    "CollectService",
    "ExecuteService",
    "LocalDOSData",
    "LocalRunner",
    "MetricRecord",
    "ModifyService",
    "Observation",
    "OperationOutcome",
    "OperationRef",
    "OperationStatus",
    "PDOSData",
    "PrepareService",
    "RunResult",
    "ScfCollectRequest",
    "ScfExecuteRequest",
    "ScfModifyRequest",
    "ScfPrepareRequest",
    "ScfCollectService",
    "ScfExecuteService",
    "ScfModifyService",
    "ScfPrepareService",
    "ScfServiceSet",
    "TaskResult",
    "UnitModifyResult",
    "UnitModifySpec",
    "UnitPrepareResult",
    "UnitSpec",
    "Workspace",
    "add_cubes",
    "collect",
    "capabilities_document",
    "collect_pyatb",
    "collect_unit",
    "execute",
    "execute_unit",
    "export",
    "modify_input",
    "modify_kpt",
    "modify_stru",
    "modify_unit",
    "planar_average",
    "perturb_structure",
    "prepare",
    "prepare_pyatb_band",
    "prepare_unit",
    "run",
    "run_band",
    "run_band_sequence",
    "run_cell_relax",
    "run_dos",
    "run_dos_sequence",
    "run_md",
    "run_pyatb",
    "run_relax",
    "run_scf",
    "run_task",
    "request_schema_document",
    "subtract_cubes",
]

__version__ = "0.1.0"
