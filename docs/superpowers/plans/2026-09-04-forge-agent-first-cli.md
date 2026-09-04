# ABACUS-Forge Agent-first CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver the Stage 3 v1 machine CLI for the current typed SCF unit-operation slice, with request-file/stdin ingestion, honest capability and request-schema discovery, one-envelope output, stable exit classes, and API/CLI parity while preserving every legacy CLI behavior.

**Spec:** `docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html` and `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html` (approved; the latter governs Service/Status, v1 CLI, error/exit, and compatibility details).

**Architecture:** Route only the new `operation`, `schema`, and `capabilities` top-level commands through a focused machine adapter; all existing commands continue through the unchanged legacy parser/dispatcher. The machine adapter decodes one typed request, calls one per-operation service, and renders the returned immutable envelope. SCF is the only advertised v1 capability in this stage and remains `experimental` until the typed machine path has its own real-smoke/release evidence. Scientific judgment, multi-operation orchestration, retry/continuation, scheduler/platform integration, and TUI remain outside Forge.

**Tech Stack:** Python 3.10+, standard-library `argparse`, `dataclasses`, `json`, `pathlib`, `typing.Protocol`; existing Forge contracts/services/runner; pytest process tests.

## Global Constraints

- Preserve legacy command names, arguments, stdout/stderr, exit behavior, `--json`, Python API, compatibility files, and task-pack behavior. Do not silently wrap legacy results in v1 envelopes.
- The v1 machine grammar is `abacus-forge operation <prepare|modify|execute|collect|postprocess|export> (--request FILE | --stdin) [--format json|text] [--pretty]`, `abacus-forge capabilities`, and `abacus-forge schema <capability> <operation>`. `--request` and `--stdin` are mutually exclusive. The process current working directory is the service `workspace_root`; `workspace_rel` remains the portable request field.
- `postprocess` and `export` are recognized operation names because the SPEC freezes that command surface, but Stage 3 does not invent their request/service contracts. Until Stage 4 supplies and advertises them, invoking them returns one `forge.error/v1` envelope with `request.invalid` and exit 2; discovery does not claim support.
- Default v1 operation stdout contains exactly one JSON document: either `forge.operation-outcome/v1` or `forge.error/v1`. `--pretty` changes JSON whitespace only. `--format text` projects the same envelope and never calls a different service or derives a different status. Controlled diagnostics may be written to stderr; no traceback, prompt, TTY sniffing, or natural-language stdout prefix is allowed.
- Exit 0 means the service delivered facts without an execution failure. Exit 2 covers `request.invalid`, `request.schema`, `request.path`, and `operation.conflict`; exit 3 covers `precondition.missing`; exit 4 is only an `OperationOutcome` whose execution status is `failed` after process start; exit 5 covers `persistence.failure` and `internal.failure`. Never pass through the ABACUS return code as the v1 process exit code.
- Request decoding uses phase-specific typed exceptions, never exception-message parsing: malformed JSON/top-level shape/operation mismatch is `request.invalid`; unknown schema or invalid/missing typed fields is `request.schema`; invalid workspace/request-source paths are `request.path`.
- Extend `ScfExecuteRequest` with only the explicit local process fields already present on the legacy execute CLI and required for API/CLI parity: `executable`, `mpi_ranks`, `omp_threads`, and `timeout_seconds`, in addition to `dry_run`. They map directly to `LocalRunner` configuration. Do not add launcher/shell strings, extra argv, scheduler fields, platform IDs, environment-secret payloads, retry, or continuation policy.
- Converge the first-slice facade before binding the CLI: new code consumes per-operation protocols/concrete services. `ForgeServices` remains only as a source-compatible delegating shim for existing Stage 2 callers and holds no orchestration state.
- Consolidate artifact-ref injection to one result-construction point when services are refactored. Do not change the frozen `ForgeResultEnvelope` key set or add observations to it.
- Capability/schema discovery is descriptive and side-effect free. Stage 3 advertises only capability `scf`, maturity `experimental`, engine `abacus`, and implemented operations `prepare`, `modify`, `execute`, `collect`; legacy relax/MD/PyATB/property packs are not promoted to the v1 surface. Promotion to `stable` requires a separately recorded typed-path real-smoke/release gate, not inference from legacy tests.
- Unknown `schema` capability/operation selectors return one `ForgeErrorEnvelope(error_class="request.invalid")` and exit 2. They are invalid discovery invocations, not malformed typed request schemas; discovery never reaches a service or writes the filesystem.
- Preserve the existing top-level `abacus-forge --help` output together with the legacy parser. It therefore does not list the separately routed machine commands in Stage 3. `README.md` must name `operation`, `schema`, and `capabilities` explicitly, while each new command provides its own `--help`.
- No AiiDA, ATP/MCP, scheduler/platform, `abacus-agent-tools`, or `abacustest` imports in `src/abacus_forge`. Add an AST-based import boundary gate; leave clean-environment install/import verification for Stage 5.
- Default tests remain deterministic and offline. No TUI, Paimon adapter, Stage 4 capability migration, scientific acceptance, or workflow engine is implemented by this plan.

## Frozen Stage 3 discovery records

`abacus-forge capabilities` returns this outer shape, with descriptor ordering and every list deterministic:

```json
{
  "schema_version": "forge.capabilities/v1",
  "capabilities": [
    {
      "schema_version": "forge.capability/v1",
      "name": "scf",
      "maturity": "experimental",
      "engine": "abacus",
      "operations": ["prepare", "modify", "execute", "collect"],
      "inputs": {
        "prepare": ["structure"],
        "modify": ["prepared_workspace"],
        "execute": ["prepared_workspace"],
        "collect": ["workspace_outputs"]
      },
      "artifact_roles": ["input", "provenance_manifest", "output"],
      "optional_dependencies": []
    }
  ]
}
```

`abacus-forge schema scf <operation>` returns:

```json
{
  "schema_version": "forge.schema-discovery/v1",
  "capability": "scf",
  "operation": "prepare",
  "request_schema": {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "ScfPrepareRequest",
    "type": "object",
    "additionalProperties": false
  }
}
```

The real `request_schema` must additionally contain the exact `properties`, `required`, constants/enums, scalar bounds, array item types, and defaults represented by the corresponding `Scf*Request`. It is a static transport description maintained beside the decoder; runtime validation remains owned by the typed request constructor, so no JSON Schema runtime dependency is added.

## File map

| Path | Responsibility |
| --- | --- |
| `src/abacus_forge/contracts.py` | Complete typed execute configuration and add the versioned capability descriptor. |
| `src/abacus_forge/services.py` | Per-operation SCF services, compatibility facade delegation, runner construction, single artifact-ref injection. |
| `src/abacus_forge/discovery.py` | Stable capability registry and static request-schema discovery documents. |
| `src/abacus_forge/machine_cli.py` | Isolated machine parser, request decoding, service dispatch, rendering, and exit mapping. |
| `src/abacus_forge/cli.py` | Route only the three new top-level commands to `machine_cli`; retain the legacy parser and dispatcher. |
| `src/abacus_forge/__init__.py` | Re-export the versioned per-operation Python services and discovery contracts. |
| `tests/test_contracts.py` | Execute request and capability descriptor round trips/validation. |
| `tests/test_service_status.py` | Per-operation service behavior, facade parity, runner mapping, and artifact-ref regression. |
| `tests/test_machine_cli.py` | In-process machine decoding, discovery, rendering, dispatch, and exit mapping. |
| `tests/test_cli_process.py` | Real subprocess stdout/stderr/exit and API/CLI parity, plus legacy compatibility. |
| `tests/test_architecture.py` | AST import-boundary gate. |
| `tests/conftest.py`, `tests/README.md` | Marker registration and machine CLI gate ownership. |
| `README.md` | Current v1 machine CLI usage, supported capability, and boundary. |

### Task 1: Complete the typed execute request for reproducible local invocation

**Files:**
- Modify: `src/abacus_forge/contracts.py`
- Modify: `tests/test_contracts.py`

**Test strategy:** Round-trip every local execution field; reject empty executable/argv entries, booleans masquerading as integers, non-positive thread/rank counts, non-positive/non-finite timeout, unknown fields, and non-JSON data. Existing minimal `ScfExecuteRequest(operation_id, workspace_rel)` remains valid with current defaults.

**Interfaces:** Extend `ScfExecuteRequest` with `executable: str = "abacus"`, `mpi_ranks: int = 1`, `omp_threads: int = 1`, and `timeout_seconds: float | None = None`. Serialize all fields deterministically in `to_dict()`. Do not add `launcher`, `extra_args`, `env_overrides`, shell mode, scheduler resources, or scientific fields.

- [ ] **Step 1: Write failing contract tests**

```python
def test_scf_execute_request_round_trips_local_runner_configuration() -> None:
    request = ScfExecuteRequest(
        operation_id="123e4567-e89b-42d3-a456-426614174000",
        workspace_rel="scf",
        executable="/opt/abacus/bin/abacus",
        mpi_ranks=4,
        omp_threads=2,
        timeout_seconds=120.0,
    )
    assert ScfExecuteRequest.from_dict(request.to_dict()) == request


@pytest.mark.parametrize("field,value", [("mpi_ranks", 0), ("omp_threads", True), ("timeout_seconds", float("inf"))])
def test_scf_execute_request_rejects_invalid_runner_configuration(field: str, value: object) -> None:
    payload = valid_execute_request_dict()
    payload[field] = value
    with pytest.raises(ValueError):
        ScfExecuteRequest.from_dict(payload)
```

- [ ] **Step 2: Run RED**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py`

Expected: FAIL because the execution fields are not accepted or serialized.

- [ ] **Step 3: Implement strict typed fields**

Use explicit validators; remember that `bool` is an `int` subclass and must be rejected for numeric resource fields. Use `math.isfinite()` for timeout. Preserve the existing request schema version and default construction behavior.

- [ ] **Step 4: Run GREEN**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_service_status.py`

Expected: all pass; existing service callers require no changes.

- [ ] **Step 5: Commit**

```bash
git add src/abacus_forge/contracts.py tests/test_contracts.py
git commit -m "feat: complete typed execute request"
```

### Task 2: Converge the SCF facade to per-operation services

**Files:**
- Modify: `src/abacus_forge/services.py`
- Modify: `src/abacus_forge/__init__.py`
- Modify: `tests/test_service_status.py`

**Test strategy:** Test each narrow method through its protocol, verify execute constructs a `LocalRunner` exactly from `ScfExecuteRequest`, verify injected fake runner support, verify the legacy facade returns an identical serialized result, and catch duplicate artifact-ref injection.

**Interfaces:** Add runtime-checkable `PrepareService`, `ModifyService`, `ExecuteService`, and `CollectService` protocols with exactly `prepare`, `modify`, `execute`, and `collect`. Add concrete `ScfPrepareService`, `ScfModifyService`, `ScfExecuteService`, and `ScfCollectService` sharing only a private workspace/error/persistence context. Add `ScfServiceSet.default(workspace_root=".", runner_factory=LocalRunner)`. `ForgeServices` delegates its existing `*_scf` methods to this set and remains source compatible. `ScfExecuteService.execute()` builds the default runner from the request fields; a test-only/integration injection may supply a runner factory, but the CLI does not branch around the request.

- [ ] **Step 1: Write failing narrow-interface tests**

```python
def test_execute_service_maps_request_to_runner_once(tmp_path: Path) -> None:
    factory = RecordingRunnerFactory(successful_run_result())
    services = ScfServiceSet.default(workspace_root=tmp_path, runner_factory=factory)
    result = services.execute.execute(configured_execute_request())
    assert isinstance(result, OperationOutcome)
    assert factory.calls == [expected_local_runner_kwargs()]


def test_legacy_forge_services_is_a_serialization_equivalent_shim(tmp_path: Path) -> None:
    direct, facade = build_isolated_equivalent_service_scenarios(tmp_path)
    assert direct.to_dict() == facade.to_dict()


def test_outcome_contains_each_artifact_ref_once(tmp_path: Path) -> None:
    outcome = collect_through_narrow_service(tmp_path)
    refs = outcome.envelope.to_dict()["diagnostics"]["artifact_refs"]
    assert refs == list({(ref["operation_id"], ref["artifact_id"]): ref for ref in refs}.values())
```

- [ ] **Step 2: Run RED**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py`

Expected: FAIL because the per-operation protocols and concrete services do not exist.

- [ ] **Step 3: Refactor without changing domain behavior**

Move the four method bodies behind the narrow concrete services. Keep common workspace containment, typed error mapping, admission, persistence, and observation construction in one private context rather than copying them. Construct/inject artifact refs only immediately before `OperationOutcome` creation; remove the earlier injection from `_with_workspace`. Do not change event ownership, compatibility writes, or error classes.

- [ ] **Step 4: Run GREEN and compatibility regression**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py tests/test_contracts.py tests/test_workspace.py tests/test_result_contract.py tests/test_units.py`

Expected: all pass and the facade/new service serialized results are equivalent.

- [ ] **Step 5: Commit**

```bash
git add src/abacus_forge/services.py src/abacus_forge/__init__.py tests/test_service_status.py
git commit -m "refactor: expose per-operation forge services"
```

### Task 3: Add honest capability and request-schema discovery

**Files:**
- Create: `src/abacus_forge/discovery.py`
- Modify: `src/abacus_forge/contracts.py`
- Modify: `src/abacus_forge/__init__.py`
- Modify: `tests/test_contracts.py`
- Create: `tests/test_machine_cli.py`
- Modify: `tests/conftest.py`

**Test strategy:** Round-trip and strictly validate `CapabilityDescriptor`; assert deterministic discovery shapes; assert every advertised operation has a strict schema matching its typed request serialization and dataclass fields; assert unsupported capability/operation pairs return `request.invalid`/exit 2 without filesystem changes; assert only SCF is advertised and its maturity remains experimental.

**Interfaces:** Add frozen `CapabilityDescriptor` with the exact fields shown above and strict `to_dict()/from_dict()`. Add `capabilities_document() -> dict[str, JSONValue]` and `request_schema_document(capability: str, operation: str) -> dict[str, JSONValue]`; the latter raises typed `ForgeRequestError` for an unknown selector so the machine adapter can map it to `request.invalid`. Static schemas cover all fields and constraints from the four SCF request classes, including the execute fields from Task 1. Discovery returns fresh JSON-safe values so callers cannot mutate registry state.

- [ ] **Step 1: Write failing descriptor and discovery tests**

```python
def test_capabilities_advertise_only_experimental_scf_operations() -> None:
    payload = capabilities_document()
    assert payload["schema_version"] == "forge.capabilities/v1"
    assert [item["name"] for item in payload["capabilities"]] == ["scf"]
    assert payload["capabilities"][0]["maturity"] == "experimental"
    assert payload["capabilities"][0]["operations"] == ["prepare", "modify", "execute", "collect"]
    assert payload["capabilities"][0]["artifact_roles"] == ["input", "provenance_manifest", "output"]


@pytest.mark.parametrize("operation", ["prepare", "modify", "execute", "collect"])
def test_request_schema_matches_contract_fields_and_wire_keys(operation: str) -> None:
    document = request_schema_document("scf", operation)
    schema = document["request_schema"]
    request_type = SCF_REQUEST_TYPES[operation]
    field_keys = {item.name for item in dataclasses.fields(request_type)} | {"operation"}
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == field_keys
    assert set(schema["properties"]) == set(valid_request(operation).to_dict())


@pytest.mark.parametrize("operation", ["prepare", "modify", "execute", "collect"])
def test_request_schema_freezes_required_constants_and_bounds(operation: str) -> None:
    schema = request_schema_document("scf", operation)["request_schema"]
    assert set(schema["required"]) == REQUIRED_WIRE_FIELDS[operation]
    assert schema["properties"]["schema_version"]["const"] == "forge.request/v1"
    assert schema["properties"]["operation"]["const"] == operation
    assert_numeric_bounds_match_contract(operation, schema)


@pytest.mark.parametrize("capability,operation", [("relax", "prepare"), ("scf", "postprocess")])
def test_unknown_schema_selector_is_request_invalid(capability: str, operation: str) -> None:
    with pytest.raises(ForgeRequestError):
        request_schema_document(capability, operation)
```

- [ ] **Step 2: Run RED**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_machine_cli.py`

Expected: FAIL because descriptor/discovery records are absent.

- [ ] **Step 3: Implement static, side-effect-free discovery**

Keep discovery independent of legacy task registries and optional imports. Do not list postprocess/export until their typed services exist. Derive the schema property-key expectation from `dataclasses.fields(request_type)` plus the computed `operation` property, and cross-check it against a representative request's real `to_dict()` keys; do not maintain a second hard-coded key helper. Keep `required` and semantic constraints explicit because dataclass defaults cannot represent wire requirements such as `structure_path_rel`'s non-empty sentinel. Register `test_machine_cli.py` with marker `cli` in `_FILE_MARKERS`.

- [ ] **Step 4: Run GREEN**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_contracts.py tests/test_machine_cli.py`

Expected: all pass with stable ordering and exact schemas.

- [ ] **Step 5: Commit**

```bash
git add src/abacus_forge/contracts.py src/abacus_forge/discovery.py src/abacus_forge/__init__.py tests/test_contracts.py tests/test_machine_cli.py tests/conftest.py
git commit -m "feat: add forge capability discovery"
```

### Task 4: Build the isolated v1 machine adapter

**Files:**
- Create: `src/abacus_forge/machine_cli.py`
- Modify: `tests/test_machine_cli.py`

**Test strategy:** Exercise request-file and stdin as mutually exclusive sources; malformed UTF-8/JSON/top-level data; operation mismatch; schema/path errors; all service result classes; JSON/pretty/text rendering; unsupported postprocess/export; and dependency-injected services proving exactly one call.

**Interfaces:** Implement `run_machine_cli(argv: Sequence[str], *, stdin: TextIO, stdout: TextIO, stderr: TextIO, cwd: Path, services: ScfServiceSet | None = None) -> int`. Use a machine-only parser whose usage errors are converted to `ForgeErrorEnvelope`, leaving the legacy parser untouched. Implement `decode_scf_request(operation, payload)` with an explicit decoder map to the four `Scf*Request.from_dict()` methods. Preflight `schema_version`, `operation`, and workspace path in distinct typed phases; do not inspect exception text. Implement `exit_code_for(result)` and renderers as pure functions.

- [ ] **Step 1: Write failing adapter tests**

```python
def test_machine_adapter_calls_one_service_and_writes_one_json_document() -> None:
    services = RecordingScfServices(success_outcome())
    completed = invoke_machine(["operation", "collect", "--stdin"], stdin=valid_collect_json(), services=services)
    assert completed.exit_code == 0
    assert json.loads(completed.stdout) == success_outcome().to_dict()
    assert services.calls == [("collect", valid_collect_request())]


@pytest.mark.parametrize("capability,operation", [("relax", "prepare"), ("scf", "postprocess")])
def test_unknown_schema_selector_returns_one_request_invalid_envelope(capability: str, operation: str) -> None:
    completed = invoke_machine(["schema", capability, operation])
    assert completed.exit_code == 2
    assert json.loads(completed.stdout)["error"]["class"] == "request.invalid"


@pytest.mark.parametrize(
    "result,expected",
    [
        (error("request.schema"), 2),
        (error("precondition.missing"), 3),
        (started_failure_outcome(), 4),
        (error("internal.failure"), 5),
    ],
)
def test_machine_exit_mapping_is_semantic(result: object, expected: int) -> None:
    assert exit_code_for(result) == expected
```

- [ ] **Step 2: Run RED**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_machine_cli.py`

Expected: FAIL because the machine adapter does not exist.

- [ ] **Step 3: Implement decoding, dispatch, rendering, and exit mapping**

Read at most one JSON value and require EOF except whitespace. For an invalid request, preserve a canonical UUIDv4/workspace only if safely extractable; otherwise serialize null as allowed by the SPEC. Use `json.dumps(..., allow_nan=False, sort_keys=True)` and one trailing newline. `--format text` may display schema, operation/error class, operation ID, execution/collection, artifact paths, and message drawn directly from the envelope; it must not add convergence/acceptance conclusions. `--pretty` is rejected with text format as `request.invalid`.

- [ ] **Step 4: Run GREEN**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_machine_cli.py tests/test_service_status.py`

Expected: all pass and every operation test records one service call.

- [ ] **Step 5: Commit**

```bash
git add src/abacus_forge/machine_cli.py tests/test_machine_cli.py
git commit -m "feat: add agent-first machine adapter"
```

### Task 5: Route the public CLI and prove process/API parity

**Files:**
- Modify: `src/abacus_forge/cli.py`
- Modify: `tests/support/process.py`
- Modify: `tests/test_cli_process.py`

**Test strategy:** Run real subprocesses for request-file/stdin and discovery. Assert exactly one parseable stdout document, diagnostics-only stderr, no prompt with `stdin=DEVNULL`, exits 0/2/3/4/5, started nonzero/timeout/signal as exit 4 outcomes, and serialized parity with direct API calls. Re-run existing legacy process assertions unchanged.

**Interfaces:** At the start of `cli.main`, inspect only the first argv token. For `operation`, `schema`, or `capabilities`, delegate the complete argv to `run_machine_cli`; otherwise invoke the existing parser and dispatch unchanged. Extend `run_cli()` test support with optional `input_text` while retaining `DEVNULL` by default.

- [ ] **Step 1: Write failing subprocess contracts**

```python
def test_operation_stdin_matches_direct_collect_api(tmp_path: Path) -> None:
    api_root, cli_root = prepare_equivalent_collect_roots(tmp_path)
    request = collect_request_for("scf")
    direct = ScfServiceSet.default(workspace_root=api_root).collect.collect(request)
    process = run_cli("operation", "collect", "--stdin", cwd=cli_root, input_text=json.dumps(request.to_dict()))
    assert process.returncode == 0
    assert json.loads(process.stdout) == direct.to_dict()


@pytest.mark.parametrize("scenario,exit_code", [("schema", 2), ("precondition", 3), ("nonzero", 4), ("internal", 5)])
def test_operation_process_uses_frozen_exit_classes(scenario: str, exit_code: int, tmp_path: Path) -> None:
    result = run_scenario_process(scenario, tmp_path)
    assert result.returncode == exit_code
    assert len(parse_concatenated_json_values(result.stdout)) == 1
```

- [ ] **Step 2: Run RED**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_cli_process.py`

Expected: new process tests FAIL because public routing is absent.

- [ ] **Step 3: Add additive top-level routing**

Do not add the new commands to the legacy `build_parser()` or alter its `ArgumentParser.error()` behavior. Use the request's execute configuration to create the local runner. For parity tests that would otherwise consume the same `operation_id`, use isolated copied workspaces or distinct IDs and compare protocol fields after normalizing only operation identity/event-path differences explicitly named by the test.

- [ ] **Step 4: Run GREEN and legacy regression**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_machine_cli.py tests/test_cli_process.py tests/test_cli.py tests/test_service_status.py`

Expected: all pass; the pre-existing parser-error and legacy output tests remain byte-compatible.

- [ ] **Step 5: Commit**

```bash
git add src/abacus_forge/cli.py tests/support/process.py tests/test_cli_process.py
git commit -m "feat: expose forge v1 operation cli"
```

### Task 6: Lock the architecture boundary and document the versioned machine surface

**Files:**
- Create: `tests/test_architecture.py`
- Modify: `tests/conftest.py`
- Modify: `tests/README.md`
- Modify: `README.md`

**Test strategy:** Parse every production Python module with `ast`; reject direct or submodule imports of `aiida`, `abacustest`, `abacus_agent_tools`, ATP/MCP packages, Bohrium, DPDispatcher, and scheduler bindings. Verify documented commands exist in `--help`, discovery names only SCF, and all README request examples parse through the real CLI.

**Interfaces and documentation:** Add a concise Agent-first CLI section showing one request-file example, one stdin example, discovery, stdout/error/exit rules, current SCF-only experimental v1 maturity, cwd-as-workspace-root, and the fact that scientific judgment/orchestration/scheduling remain caller-owned. Explicitly list `operation`, `schema`, and `capabilities` because the compatibility-preserved top-level legacy help does not advertise them; direct users to each new command's own `--help`. Update the earlier README sentence saying the Agent-first CLI is deferred. Update `tests/README.md` so machine unit/process parity and AST boundaries have explicit owners. Register `test_architecture.py` as `core`.

- [ ] **Step 1: Write the failing AST and documentation contract tests**

```python
def test_production_modules_do_not_import_forbidden_upper_layers() -> None:
    violations = forbidden_imports(Path("src/abacus_forge"), FORBIDDEN_ROOTS)
    assert violations == []


def test_machine_help_exposes_frozen_commands() -> None:
    result = run_cli("operation", "--help")
    assert result.returncode == 0
    assert "--request" in result.stdout
    assert "--stdin" in result.stdout
```

- [ ] **Step 2: Run the focused gate before documentation edits**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_architecture.py tests/test_cli_process.py`

Expected: architecture code may already pass, but the new help/documentation contract remains incomplete; keep the RED evidence for the behavior being added rather than weakening the assertion.

- [ ] **Step 3: Implement AST matching and update current-state docs**

Match both `ast.Import` and `ast.ImportFrom` by root module name; report `path:line:module` deterministically. Do not scan tests/docs as production dependencies. Keep README usage factual and short; do not repeat the SPEC's rejected alternatives or add TUI/Paimon-v3 implementation instructions.

- [ ] **Step 4: Run focused and full verification**

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_architecture.py tests/test_contracts.py tests/test_service_status.py tests/test_machine_cli.py tests/test_cli_process.py tests/test_cli.py`

Expected: all pass.

Run: `conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider`

Expected: the complete deterministic suite passes; real smoke and benchmark remain opt-in/skipped.

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m abacus_forge.cli capabilities`

Expected: exit 0 and one JSON document advertising only experimental SCF prepare/modify/execute/collect.

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m abacus_forge.cli operation --help`

Expected: exit 0 with both mutually exclusive request inputs and all six frozen operation names visible.

- [ ] **Step 5: Commit**

```bash
git add tests/test_architecture.py tests/conftest.py tests/README.md README.md
git commit -m "docs: publish forge machine cli boundary"
```

## Final review gate

- [ ] Request an independent task-scoped code review against both approved SPECs and this PLAN.
- [ ] Resolve only verified Stage 3 gaps; reject requests that add orchestration, scientific policy, platform scheduling, TUI, Stage 4 operations, or Paimon adapter behavior.
- [ ] Re-run the focused machine/contract gate and the complete deterministic suite after review fixes.
- [ ] Confirm `git diff --check`, no unresolved placeholder markers in changed production/docs files, and a clean intended diff.
- [ ] Use `superpowers:verification-before-completion` before any completion claim and `superpowers:finishing-a-development-branch` before merge/PR/cleanup.

## Deliberately deferred after Stage 3

1. Stage 4 introduces independently evidenced relax/MD/postprocess/PyATB typed operation contracts and expands discovery only as each capability becomes real; SCF promotion from `experimental` to `stable` also requires its own typed machine-path real-smoke evidence.
2. Stage 5 creates the independent `paimon-v3` repository for the thin Agent adapter, benchmark parity, scientific interpretation, orchestration, and platform/scheduler integration.
3. A VASPKIT/AbacusCopilot-style TUI is optional and may be built only as a shell over the stable Python API or machine envelope.
4. Clean-environment wheel install/import verification and removal of legacy runtime dependencies remain Stage 5 release gates; the Stage 3 AST test prevents new forbidden source imports now.
5. `Workspace.claim_v1_operation` alias removal requires a fresh usage scan when workspace admission is next modified; Stage 3 does not touch that boundary solely for cleanup.

## Plan self-review

- **SPEC coverage:** Tasks 1–2 complete the shared typed-request/Python-service side of R1/R2 and remove the first-slice facade deviation from new consumers; Tasks 3–5 implement R3/R4, the frozen v1 command shape, envelope transport, exit classes, and API/CLI parity; Task 6 closes the recorded AST boundary debt and updates current-state documentation.
- **Scope discipline:** The plan does not implement scientific policy, workflow/retry, scheduling, TUI, Paimon adapters, or Stage 4 operations. Unsupported frozen verbs fail structurally rather than acquiring placeholder business logic.
- **Maturity discipline:** SCF is discoverable but `experimental`; the existing legacy real-smoke test is not misrepresented as typed machine-path release evidence.
- **Discovery fidelity:** Advertised artifact roles are exactly the current serialized values (`input`, `provenance_manifest`, `output`); stdout/stderr remain artifact IDs under role `output`. Unknown discovery selectors have one frozen class-2 response, and schema drift tests compare reflection, real serialization, and explicit semantic constraints.
- **Type consistency:** Every named production interface is introduced before use; the CLI consumes `ScfServiceSet`, typed requests, `OperationOutcome`, and `ForgeErrorEnvelope` directly, and discovery documents mirror rather than replace runtime typed validation.
- **Compatibility:** The only top-level routing change is gated by the three new command names; all pre-existing argv continues through the legacy parser, and focused plus full regressions protect its output and exit behavior.
- **Placeholder audit:** The plan contains no unresolved implementation placeholders; helper names in example tests are explicitly owned by their task and must be implemented with the test.
