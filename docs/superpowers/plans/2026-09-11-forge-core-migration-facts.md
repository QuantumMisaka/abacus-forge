# Forge Core Migration Fact Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\`- [ ]\`) syntax for tracking.

**Goal:** 为 v1.3 首批核心能力建立可重复的 SCF、relax、cell-relax、MD 迁移事实矩阵，证明 Forge 与既有 ABACUS/abacustest 操作在输入、解析和产物边界上的一致性，而不把科学验收、编排或调度引入 Forge。

**Spec:** \`docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html\`（R10、R11、Phase 4、首批稳定面）与 \`docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html\`（R2/R4、Stage 3/4、事实与解释边界）。

**Architecture:** 继续使用现有 \`collect()\` legacy projection 与 typed \`ScfServiceSet\`/\`RelaxServiceSet\`/\`MdServiceSet\`，在同一个隔离 workspace 上做事实投影比较。新增的 relax/cell-relax fixture 只作为 ABACUS 原生文件输入，不改变生产 parser、request、result、status 或 capability descriptor；benchmark 保持显式 opt-in，并把结果限定为迁移事实证据。

**Tech Stack:** Python 3.10+, pytest benchmark marker, existing \`Workspace\`, legacy \`collect\`, typed service sets, checked-in ABACUS text fixtures.

## Global Constraints

- Forge 运行时继续不依赖 \`abacus-agent-tools\`、\`abacustest\`、AiiDA、调度器或平台；参考仓库只用于人工核对 fixture 和字段来源。
- 矩阵只比较 INPUT/KPT/STRU profile、命令/进程事实、parser observations、workspace-relative artifact inventory、envelope/status 形状；不得比较能量物理正确性、收敛质量、轨迹质量或其他科学结论。
- \`scientific\` 必须保持 \`unassessed\`；benchmark 不能晋升 capability maturity，也不能代替 real-smoke 或上层 Paimon Agent Benchmark。
- 默认 \`pytest -q\` 不运行 benchmark；必须通过 \`--run-benchmark -m benchmark\` 显式运行。
- 新 fixture 不进入安装包，不复制 Paimon/AiiDA 状态字段，不引入 task/workflow/scheduler 语义。

---

### Task 1: Add Forge-owned Relax fixtures and the four-capability fact matrix

**Files:**
- Create: \`tests/fixtures/abacus-native-relax/INPUT\`
- Create: \`tests/fixtures/abacus-native-relax/KPT\`
- Create: \`tests/fixtures/abacus-native-relax/STRU\`
- Create: \`tests/fixtures/abacus-native-relax/OUT.ABACUS/running_relax.log\`
- Create: \`tests/fixtures/abacus-native-relax/OUT.ABACUS/STRU_FINAL\`
- Modify: \`tests/support/reference_workspaces.py\` to add \`NATIVE_RELAX_FIXTURE_ROOT\` and \`copy_native_relax_workspace(root, capability)\`.
- Create: \`tests/benchmark/test_core_capability_facts.py\`.

**Test strategy:**
- Behavior boundary: compare legacy and typed collection facts on four isolated copies; do not assert scientific acceptance.
- Existing suites: reuse \`tests/benchmark/test_abacustest_compatibility.py\`'s factual comparison convention and \`tests/test_collect_abacus_reference.py\`'s native MD fixture.
- New test file justification: the four-capability matrix is a separate opt-in migration gate, not a replacement for capability-specific parser/service tests.
- Temporary probes: none; expected values come from checked-in fixture text or the legacy projection of the same workspace.

**Interfaces:**
- Consumes: \`copy_abacustest_scf_workspace\`, \`copy_native_md_workspace\`, \`ScfServiceSet\`, \`RelaxServiceSet\`, \`MdServiceSet\`, and the four typed collect request classes.
- Produces: \`copy_native_relax_workspace\` and one benchmark test parametrized over \`scf\`, \`relax\`, \`cell-relax\`, and \`md\`.

- [ ] **Step 1: Add the hand-checked native Relax fixture**

Create the five fixture files with these exact contents:

~~~text
INPUT_PARAMETERS
calculation relax
basis_type pw
ecutwfc 20
~~~

~~~text
K_POINTS
0
Gamma
1 1 1 0 0 0
~~~

~~~text
ATOMIC_SPECIES
Si 28.085500 Si.upf

LATTICE_CONSTANT
1.0
LATTICE_CONSTANT_UNIT
Angstrom

LATTICE_VECTORS
4 0 0
0 4 0
0 0 4

ATOMIC_POSITIONS
Direct
Si
0
1
0 0 0 m 1 1 1
~~~

~~~text
ABACUS VERSION: 3.8.0
RELAX STEPS = 3
TOTAL ENERGY = -4.2 eV
SCF CONVERGED
NORMAL END
~~~

The \`STRU_FINAL\` file must be byte-identical to \`STRU\`. Keep the fixture intentionally small: it exercises native file naming and parser facts, not a physical relaxation claim.

- [ ] **Step 2: Add the workspace-copy helper**

Extend \`tests/support/reference_workspaces.py\` with this public helper:

~~~python
NATIVE_RELAX_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "abacus-native-relax"


def copy_native_relax_workspace(root: Path, capability: str = "relax") -> Workspace:
    if capability not in {"relax", "cell-relax"}:
        raise ValueError(f"unsupported Relax fixture capability: {capability}")
    workspace = Workspace(root).ensure_layout()
    input_text = (NATIVE_RELAX_FIXTURE_ROOT / "INPUT").read_text(encoding="utf-8")
    input_text = input_text.replace("calculation relax", f"calculation {capability}", 1)
    workspace.write_text("inputs/INPUT", input_text)
    for relative_path in ("KPT", "STRU"):
        workspace.write_text(
            f"inputs/{relative_path}",
            (NATIVE_RELAX_FIXTURE_ROOT / relative_path).read_text(encoding="utf-8"),
        )
    workspace.write_text(
        f"outputs/OUT.ABACUS/running_{capability}.log",
        (NATIVE_RELAX_FIXTURE_ROOT / "OUT.ABACUS" / "running_relax.log").read_text(encoding="utf-8"),
    )
    workspace.write_text(
        "outputs/OUT.ABACUS/STRU_FINAL",
        (NATIVE_RELAX_FIXTURE_ROOT / "OUT.ABACUS" / "STRU_FINAL").read_text(encoding="utf-8"),
    )
    workspace.write_text("outputs/stderr.log", "")
    return workspace
~~~

Do not import any code from \`paimon\` or \`abacustest\` at runtime.

- [ ] **Step 3: Write the failing matrix test**

Create \`tests/benchmark/test_core_capability_facts.py\`. The public test must have this shape:

~~~python
@pytest.mark.benchmark
@pytest.mark.parametrize("capability", ["scf", "relax", "cell-relax", "md"])
def test_core_capability_typed_projection_matches_legacy_facts(tmp_path: Path, capability: str) -> None:
    workspace = _copy_workspace(tmp_path / capability, capability)
    legacy = collect(workspace)
    typed = _typed_collect(tmp_path, workspace, capability)

    assert isinstance(typed, OperationOutcome)
    assert legacy.status == "completed"
    assert typed.envelope.status.collection == "complete"
    assert typed.envelope.status.execution == "not_run"
    assert typed.envelope.status.scientific == "unassessed"
    for name in _shared_metric_names(capability):
        assert name in legacy.metrics
        _assert_fact_equal(_metric_value(typed, name), legacy.metrics[name])
    assert _relative_artifact_paths(workspace, legacy) == {
        artifact.path_rel for artifact in typed.envelope.artifacts
    }
~~~

Implement the private helpers in the same file. \`_copy_workspace\` dispatches to the existing SCF/MD helpers or the new Relax helper. \`_typed_collect\` constructs the existing typed request class with \`workspace_rel=workspace.root.name\), a unique UUIDv4 operation ID, and dispatches only to the matching per-operation service. \`_shared_metric_names\` is exactly:

- SCF: \`("total_energy", "natom", "scf_steps")\`
- Relax/cell-relax: \`("total_energy", "relax_steps")\`
- MD: \`("total_energy", "md_last_total_energy", "md_last_potential_energy", "md_last_kinetic_energy", "md_last_temperature", "md_last_pressure", "md_dump_frames", "md_dump_steps")\`

\`_metric_value\` looks up \`MetricRecord.value\` by name. \`_relative_artifact_paths\` resolves each legacy artifact under \`workspace.root\` and returns POSIX relative paths, failing on an escaped path. \`_assert_fact_equal\` recursively compares dict/list facts and uses \`pytest.approx\` only for finite numeric leaves. Never calculate expected values with Forge code.

- [ ] **Step 4: Run the focused test to verify the expected RED**

Run:

~~~bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q tests/benchmark/test_core_capability_facts.py --run-benchmark
~~~

Expected before the helper/test is complete: collection or assertion failure identifying the missing matrix implementation, not a production-code failure.

- [ ] **Step 5: Complete the minimal test implementation and run it GREEN**

Finish only the test helper and fixture wiring; do not alter \`src/abacus_forge\`. Run the same command and expect \`4 passed\`.

- [ ] **Step 6: Run the owning migration gates**

Run:

~~~bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q tests/benchmark/test_core_capability_facts.py tests/benchmark/test_abacustest_compatibility.py --run-benchmark
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q tests/test_collect_abacus_reference.py tests/test_service_status.py tests/test_md_services.py tests/test_architecture.py
~~~

Expected: benchmark gate \`6 passed\`; owning offline gate passes with no new warning or unknown marker. The matrix remains opt-in and no stable descriptor is changed.

- [ ] **Step 7: Commit the fact-matrix task**

~~~bash
git add tests/fixtures/abacus-native-relax tests/support/reference_workspaces.py tests/benchmark/test_core_capability_facts.py
git commit -m "test: add core capability migration fact matrix"
~~~

### Task 2: Record the evidence boundary and correct developer-facing operation wording

**Files:**
- Modify: \`AGENTS.md:42-45\`.
- Modify: \`docs/superpowers/plans/2026-09-11-forge-maturity-gates-integration.md\` by adding a dated “Core migration fact matrix follow-up” section.
- Modify: \`docs/superpowers/plans/2026-09-01-forge-test-portfolio-governance.md\` completion/evidence notes to link the new benchmark file.

**Test strategy:**
- Behavior boundary: documentation only; no public API, schema, result, status, CLI or runtime change.
- Existing suite: \`tests/test_architecture.py\` and the benchmark command from Task 1 remain the evidence source.
- New test file justification: none.
- Temporary probes: none.

**Interfaces:**
- Consumes: Task 1's \`tests/benchmark/test_core_capability_facts.py\` and its \`4 passed\`/\`6 passed\` output.
- Produces: unambiguous developer wording that \`execute\` is canonical, \`run\` is compatibility-only, \`collect\` is observation-only, and \`postprocess\` is an independent typed operation; a dated evidence record that explicitly excludes science, scheduling, orchestration, and maturity promotion.

- [ ] **Step 1: Record the documentation baseline**

Run:

~~~bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q tests/test_architecture.py
~~~

Record the clean result in the SDD report. The documentation change must preserve the existing architecture checks.

- [ ] **Step 2: Update \`AGENTS.md\` operation boundaries**

Replace the Section 4 \`run\` paragraph with:

~~~markdown
- **\`execute\`**：只负责将指定目录与资源参数转换为一次本地进程执行，不负责前置准备、后置收集或科学分析；\`run\` 仅作为兼容别名。
- **\`collect\`**：只负责解析工作目录输出并返回标准化事实和 JSON，不负责落库、展示和平台化交付。
- **\`postprocess\`**：只负责对调用方显式提供的同一 workspace 产物执行一个独立后处理 operation；不隐式执行 prepare、execute、collect 或科学判定。
~~~

- [ ] **Step 3: Record the matrix without overclaiming**

In the integration plan, record the fixture scope, exact benchmark command and result, and this boundary sentence verbatim:

> The matrix proves only input/profile, process, parser-observation, artifact, and envelope compatibility for the four core capability names. It does not prove scientific correctness, convergence quality, workflow orchestration, scheduler integration, or stable maturity.

State that typed capabilities remain \`experimental\` until the approved SPEC's separate compat, real-smoke, clean-environment and release decision gates are satisfied.

- [ ] **Step 4: Link the matrix from the historical governance plan**

Add a short evidence link under the completion notes of \`2026-09-01-forge-test-portfolio-governance.md\`; do not rewrite its historical checklist or claim that the benchmark is a required default gate.

- [ ] **Step 5: Run documentation and owning checks**

Run:

~~~bash
git diff --check
python - <<'PY'
from pathlib import Path
from html.parser import HTMLParser

for path in Path("docs/superpowers/specs").glob("*.html"):
    HTMLParser().feed(path.read_text(encoding="utf-8"))
for path in (Path("AGENTS.md"), Path("docs/superpowers/plans/2026-09-11-forge-maturity-gates-integration.md"), Path("docs/superpowers/plans/2026-09-01-forge-test-portfolio-governance.md")):
    text = path.read_text(encoding="utf-8")
    assert "TBD" not in text and "TODO" not in text
PY
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q tests/test_architecture.py
~~~

Expected: all commands exit 0; architecture suite remains green.

- [ ] **Step 6: Commit the documentation task**

~~~bash
git add AGENTS.md docs/superpowers/plans/2026-09-11-forge-maturity-gates-integration.md docs/superpowers/plans/2026-09-01-forge-test-portfolio-governance.md
git commit -m "docs: record core migration fact boundary"
~~~

## Plan self-review

- SPEC coverage: the plan addresses the four-capability first stable surface, explicit benchmark layering, operation-independent typed services, and the fact-versus-science boundary. It does not promote a descriptor or alter a runtime contract.
- Shared-file scan: Task 1 owns only fixture/support/benchmark files; Task 2 owns only AGENTS and planning documents. No implementation task consumes a file written by another task except the documented benchmark evidence link.
- Type consistency: \`copy_native_relax_workspace\` returns \`Workspace\`; typed requests use the existing four \`*CollectRequest\` classes; artifact paths use the existing \`ArtifactRecord.path_rel\`; all commands use the repository's \`conda run -n paimon\` gate.
- No placeholders: the plan contains exact paths, fixture bytes, metric names, commands, and expected results. No \`TBD\`, \`TODO\`, or undefined interface remains.

