# ABACUS-Forge Test Portfolio Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `abacus-forge` 的现有测试治理为分层、可解释、可复现的质量门禁，保留真实科学计算契约，补齐 Agent-first CLI 与迁移兼容证据，并把真实 ABACUS smoke/benchmark 从默认离线回归中明确隔离。

**Spec:** none - requirements supplied directly by the user and constrained by `../AGENTS.md` plus this repository's `AGENTS.md`; the user explicitly confirmed large-scale test governance and requested TDD plus subagent-driven execution.

**Architecture:** 保持生产 API 的既有稳定行为，只增加向后兼容的 `prepare --json` 输出。测试通过 `pytest` marker 分成 core、integration、cli、compat、pyatb、composite、experimental、real_smoke、benchmark 层；默认回归仍离线且确定性，真实 ABACUS 与 Paimon v1.2/abacustest 证据通过显式开关运行。重复的 fake executable、参考 workspace 和进程调用收敛到 `tests/support/`，测试断言保留在各自最近的公共边界。

**Tech Stack:** Python 3.10+, pytest 7-8, `subprocess.run`, existing `abacus_forge` public API/CLI, Hatchling package entrypoint, `conda run -n paimon` verification environment.

## Global Constraints

- Forge 运行时不得重新依赖 `abacus-agent-tools`、`abacus-test`、AiiDA、Bohrium、DPDispatcher 或 Slurm；参考 fixture 只能作为测试数据。
- `prepare`、`modify-*`、`execute`、`collect`、`export` 的既有 Python API、目录布局、结果字段和默认 CLI 用法保持向后兼容；新增 `prepare --json` 必须不改变未传该选项时的路径输出。
- 默认 `pytest -q` 不得访问网络、调度器、真实集群或用户工作目录；真实计算只能由 `--run-real-smoke` 与显式环境变量启用。
- 只有经过真实 ABACUS smoke 的能力才可以被标记为稳定科学能力；仅有 mock/fixture 的 property pack 保持 `experimental`，不得进入 Paimon v1.3 稳定能力面。
- 保留 ABACUS 固定宽度输出 fixture 的原始字节（包括行尾空格）；fixture 不进入安装后的 `abacus_forge` 包。
- 新增或改变生产可观察行为必须记录 RED、GREEN、REFACTOR；纯测试移动/抽取/标记不伪造生产 RED，但必须先保存基线、逐批回归，并对删除/合并项执行真实 mutation 检查。
- 测试预期值必须来自手工核对或独立 fixture，不得调用被测实现来计算 expected；不得保留只验证源码文本、测试 mock 存在或覆盖率数字的断言。
- 工作只在 `test-governance/2026-09-01` 隔离分支完成；未经用户另行要求不合并、push 或发布。

---

### Task 1: Establish test taxonomy, selection gates, and warning policy

**Files:**
- Modify: `pyproject.toml:37-40` to register strict pytest markers and the external-warning policy.
- Modify: `tests/conftest.py:1-8` to attach markers by owning test file/path and to expose the opt-in command flags used by later tasks.
- Create: `tests/README.md` documenting each layer, its evidence boundary, and the exact local/CI commands.
- Modify: `AGENTS.md:13-21` to make the marker gates, mutation rule, and warning policy part of the Forge development contract.

**Test strategy:**
- Behavior boundary: test selection itself must distinguish stable deterministic tests from experimental, benchmark, and real-smoke evidence without changing production behavior.
- Existing suite to extend: `tests/conftest.py` and the existing 14 `tests/test_*.py` files; do not create a test that merely asserts marker constants.
- New test file justification: none; pytest collection output is the verification boundary for test infrastructure.
- Temporary probes: none.

**Interfaces:**
- Consumes: current pytest discovery from `pyproject.toml` and the existing test filenames.
- Produces: registered markers `core`, `integration`, `cli`, `compat`, `pyatb`, `composite`, `experimental`, `real_smoke`, and `benchmark`; later tasks use `--run-real-smoke` and `--run-benchmark` options registered here.

- [ ] **Step 1: Record the clean baseline before test-only refactoring**

Run from the repository root:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest --collect-only -q -p no:cacheprovider > /tmp/forge-test-governance-baseline.collect
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider > /tmp/forge-test-governance-baseline.run
```

Expected: collection lists 114 tests; the run exits 0 with `114 passed` and the known third-party `spglib` deprecation warnings. Preserve these files until the task is reviewed; they are temporary evidence outside the repository.

- [ ] **Step 2: Register markers and strict collection**

Update `pyproject.toml` so the pytest section is exactly:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "--strict-markers"
markers = [
    "core: pure input, structure, transformation, and data contracts",
    "integration: prepare/execute/collect/unit/task integration contracts",
    "cli: in-process CLI dispatch contracts",
    "compat: ABACUS and abacustest compatibility fixtures",
    "pyatb: optional PyATB bridge contracts",
    "composite: local composite task-pack contracts",
    "experimental: mock/fixture-only property-pack contracts",
    "real_smoke: opt-in execution against a supplied real ABACUS workspace",
    "benchmark: opt-in compatibility benchmark projections",
]
```

Extend `tests/conftest.py` with this deterministic file-to-marker mapping and option registration:

```python
from __future__ import annotations

from pathlib import Path

import pytest


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
    "test_result_contract.py": ("integration",),
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
        if "real_smoke" in relative_parts and not config.getoption("--run-real-smoke"):
            item.add_marker(pytest.mark.skip(reason="pass --run-real-smoke to run real ABACUS smoke tests"))
        if "benchmark" in relative_parts and not config.getoption("--run-benchmark"):
            item.add_marker(pytest.mark.skip(reason="pass --run-benchmark to run benchmark tests"))
```

- [ ] **Step 3: Add the repository test map and gate commands**

Create `tests/README.md` with the following policy:

```markdown
# Forge test portfolio

The default suite is deterministic and offline. Markers describe evidence,
not implementation ownership:

| Marker | Evidence boundary | Release role |
| --- | --- | --- |
| `core` | INPUT/STRU/KPT, structures, transformations, DOS data | required PR gate |
| `integration` | prepare/execute/collect/unit/task boundaries | required PR gate |
| `cli` | in-process CLI dispatch | required PR gate |
| `compat` | ABACUS/abacustest output compatibility | required migration gate |
| `pyatb` | PyATB mapping and collection | required when PyATB bridge is enabled |
| `composite` | local composite pack wiring | deterministic regression, not physics proof |
| `experimental` | mock/fixture-only property packs | non-stable evidence |
| `real_smoke` | supplied real ABACUS workspace | opt-in release evidence |
| `benchmark` | normalized migration projections | opt-in migration evidence |

Commands:

```bash
conda run -n paimon python -m pytest -q
conda run -n paimon python -m pytest -q -m 'not experimental and not real_smoke and not benchmark'
conda run -n paimon python -m pytest -q -m experimental
conda run -n paimon python -m pytest -q --run-benchmark -m benchmark
conda run -n paimon python -m pytest -q --run-real-smoke -m real_smoke
```

Deleting or merging a test requires a named production mutation that the
remaining test still catches. A passing count alone is not evidence.
```

- [ ] **Step 4: Document the test contract in `AGENTS.md`**

Add to the testing section:

```markdown
- `tests/README.md` 是测试分层和门禁的唯一入口；新增测试先选择最近的行为边界和 marker。
- 默认回归不得访问真实集群；`real_smoke` 与 `benchmark` 只能通过显式 pytest 选项运行。
- 删除或合并测试前必须记录真实 mutation 及剩余测试的失败证据；不得以测试数量或覆盖率替代行为证据。
- 第三方 warning 只能按精确模块与消息过滤；项目自身 warning 应修复，不得静默。
```

- [ ] **Step 5: Verify the test infrastructure without changing production code**

Run:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest --collect-only -q -p no:cacheprovider -m core
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest --collect-only -q -p no:cacheprovider -m 'not experimental and not real_smoke and not benchmark'
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
```

Expected: all commands exit 0; no `PytestUnknownMarkWarning`; the default run still reports 114 passing tests. Existing `spglib` warnings may remain until Task 5's precise warning policy is applied.

- [ ] **Step 6: Commit the taxonomy-only change**

```bash
git add pyproject.toml tests/conftest.py tests/README.md AGENTS.md
git commit -m "test: classify forge test portfolio"
```

### Task 2: Consolidate deterministic test support and remove duplicate fake runners

**Files:**
- Create: `tests/support/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/support/fake_executables.py`
- Create: `tests/support/workspaces.py`
- Modify: `tests/test_api.py`, `tests/test_cli.py`, `tests/test_composite.py`, `tests/test_pyatb.py`, `tests/test_tasks.py`, `tests/test_units.py` to import shared helpers and delete local `_write_fake_*` definitions.

**Test strategy:**
- Behavior boundary: test-only refactor; fake executables must preserve the same workspace-relative writes, stdout, exit codes, OMP reporting, matrix artifacts, and PyATB artifacts currently exercised by the six owning suites.
- Existing suite to extend: the six files listed above; no new production test file.
- New test file justification: `tests/support/` is test infrastructure, not a test boundary.
- Temporary probes: none committed; use a temporary copy of one helper script only for mutation evidence.

**Interfaces:**
- Consumes: `Workspace`, `prepare`, and the existing fake-script behaviors in the current tests.
- Produces: `write_fake_abacus`, `write_fake_abacus_with_matrix`, `write_fake_pyatb`, and `write_fake_lcao_scf_workspace` for later CLI/process and smoke tests.

- [ ] **Step 1: Preserve the baseline and name the mutations**

Before editing, run the six owning suites and save their collection output. The refactor must catch these mutations if temporarily applied and then reverted: changing fake ABACUS's workspace root from `Path.cwd().parent` to `Path.cwd()`, removing a requested artifact write, and changing the fake executable's exit code from 0 to 1.

- [ ] **Step 2: Create the shared executable helpers**

Create `tests/support/fake_executables.py` with this public implementation shape:

```python
from __future__ import annotations

import os
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path


def _make_executable(path: Path, body: Sequence[str]) -> Path:
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def write_fake_abacus(
    path: Path,
    *,
    stdout_lines: Sequence[str],
    extra_writes: Mapping[str, str] | None = None,
    returncode: int = 0,
    include_omp_line: bool = False,
) -> Path:
    body = ["#!/usr/bin/env python3", "from pathlib import Path", "import os", "workspace = Path.cwd().parent"]
    if include_omp_line:
        body.append("print(f\"OMP = {os.environ.get('OMP_NUM_THREADS', 'missing')}\")")
    for relative_path, content in (extra_writes or {}).items():
        body.extend(
            [
                f"path = workspace / {relative_path!r}",
                "path.parent.mkdir(parents=True, exist_ok=True)",
                f"path.write_text({content!r}, encoding='utf-8')",
            ]
        )
    body.extend(f"print({line!r})" for line in stdout_lines)
    body.append(f"raise SystemExit({int(returncode)})")
    return _make_executable(path, body)


def write_fake_abacus_with_matrix(path: Path) -> Path:
    return write_fake_abacus(
        path,
        stdout_lines=["TOTAL ENERGY = -9.2", "FERMI ENERGY = 3.2", "SCF CONVERGED"],
        extra_writes={
            "inputs/OUT.ABACUS/data-HR-sparse_SPIN0.csr": "hr",
            "inputs/OUT.ABACUS/data-SR-sparse_SPIN0.csr": "sr",
            "inputs/OUT.ABACUS/data-rR-sparse.csr": "rr",
        },
    )


def write_fake_pyatb(path: Path) -> Path:
    return _make_executable(
        path,
        [
            "#!/usr/bin/env python3",
            "from pathlib import Path",
            "out = Path.cwd() / 'Out' / 'Band_Structure'",
            "out.mkdir(parents=True, exist_ok=True)",
            "(out / 'band_info.dat').write_text('Band gap is 2.5\\n', encoding='utf-8')",
            "(out / 'band.png').write_text('fake image', encoding='utf-8')",
            "print('pyatb done')",
        ],
    )
```

Remove unused imports (`stat` and local helper-only imports) from the six owning suites after switching to these functions. Preserve each test's explicit stdout and `extra_writes` values at the call site so the behavior being exercised remains readable.

- [ ] **Step 3: Move the reusable fake LCAO workspace setup**

Create `tests/support/workspaces.py`:

```python
from __future__ import annotations

from pathlib import Path

from ase import Atoms

from abacus_forge.api import prepare
from abacus_forge.workspace import Workspace


def write_fake_lcao_scf_workspace(path: Path) -> Workspace:
    workspace = prepare(
        path,
        task="scf",
        structure=Atoms(symbols=["Si"], positions=[[0.0, 0.0, 0.0]], cell=[4.0, 4.0, 4.0], pbc=True),
        parameters={"basis_type": "lcao", "suffix": "ABACUS", "nspin": 1},
    )
    workspace.write_text("outputs/stdout.log", "FERMI ENERGY = 3.2\nSCF CONVERGED\n")
    workspace.write_text("inputs/OUT.ABACUS/data-HR-sparse_SPIN0.csr", "hr")
    workspace.write_text("inputs/OUT.ABACUS/data-SR-sparse_SPIN0.csr", "sr")
    workspace.write_text("inputs/OUT.ABACUS/data-rR-sparse.csr", "rr")
    return workspace
```

Update `tests/test_cli.py` to import this function and delete its local implementation.

- [ ] **Step 4: Refactor the six suites without changing assertions**

Use these imports at the owning boundaries (the new `tests/__init__.py` prevents collisions with an unrelated installed `tests` package):

```python
from tests.support.fake_executables import write_fake_abacus, write_fake_abacus_with_matrix, write_fake_pyatb
from tests.support.workspaces import write_fake_lcao_scf_workspace
```

Keep the tests' existing expected values and artifact paths; only replace helper calls and remove duplicated helper bodies. `test_api.py`'s OMP test must pass `include_omp_line=True`; `test_pyatb.py`'s matrix sequence must use `write_fake_abacus_with_matrix`.

- [ ] **Step 5: Run the owning suites and mutation checks**

Run:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_api.py tests/test_cli.py tests/test_composite.py tests/test_pyatb.py tests/test_tasks.py tests/test_units.py
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
```

Expected: both commands exit 0 and preserve the pre-refactor test count. During the temporary mutation checks, the owning tests must fail for the changed workspace root/artifact/exit-code behavior; restore the helper before the final run.

- [ ] **Step 6: Commit the test-only refactor**

```bash
git add tests/support tests/test_api.py tests/test_cli.py tests/test_composite.py tests/test_pyatb.py tests/test_tasks.py tests/test_units.py
git commit -m "test: centralize forge execution fixtures"
```

### Task 3: Add an Agent-first CLI process contract and backward-compatible `prepare --json`

**Files:**
- Create: `tests/support/process.py`
- Create: `tests/test_cli_process.py`
- Modify: `src/abacus_forge/cli.py:69-94,224-281,826-827` to accept `prepare --json` and emit a structured prepared-workspace payload while preserving legacy path output.

**Test strategy:**
- Behavior boundary: an external agent invoking `python -m abacus_forge.cli` receives machine-readable stdout, stable process exit codes, separated stderr, no prompts, and a structured `prepare --json` result.
- Existing suite to extend: `tests/test_cli.py` remains the in-process dispatch suite; the new file is justified because subprocess stdout/stderr/exit behavior cannot be proven with `main()` plus `capsys` alone.
- New test file justification: `tests/test_cli_process.py` owns the independent OS-process boundary.
- Temporary probes: none.

**Interfaces:**
- Consumes: `tests.support.fake_executables.write_fake_abacus`, `abacus_forge.api.prepare`, and the installed module entrypoint.
- Produces: `abacus-forge prepare --json` and `abacus-forge prepare --pyatb --json` payloads of the form `{"status": "prepared", "workspace": "<path>"}`; legacy `prepare` remains a bare path.

- [ ] **Step 1: Write the focused RED tests first**

Create `tests/support/process.py`:

```python
from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_cli(*args: str | Path, cwd: Path | None = None, env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    source_path = str(PROJECT_ROOT / "src")
    merged_env["PYTHONPATH"] = source_path + os.pathsep + merged_env.get("PYTHONPATH", "")
    if env:
        merged_env.update(env)
    command: Sequence[str] = [sys.executable, "-m", "abacus_forge.cli", *(str(arg) for arg in args)]
    return subprocess.run(command, cwd=cwd, env=merged_env, text=True, capture_output=True)
```

Create `tests/test_cli_process.py` with these focused tests:

```python
from __future__ import annotations

import json
from pathlib import Path

from abacus_forge.api import prepare
from tests.support.fake_executables import write_fake_abacus
from tests.support.process import run_cli


def test_prepare_json_is_machine_readable(tmp_path: Path) -> None:
    workspace = tmp_path / "prepare-json"
    result = run_cli("prepare", workspace, "--json")
    assert result.returncode == 0
    assert result.stderr == ""
    assert json.loads(result.stdout) == {"status": "prepared", "workspace": str(workspace)}


def test_prepare_without_json_keeps_legacy_path_output(tmp_path: Path) -> None:
    workspace = tmp_path / "prepare-legacy"
    result = run_cli("prepare", workspace)
    assert result.returncode == 0
    assert result.stdout.strip() == str(workspace)


def test_execute_process_emits_json_and_zero_exit(tmp_path: Path) -> None:
    workspace = prepare(tmp_path / "execute", task="scf")
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["TOTAL ENERGY = -3.2", "SCF CONVERGED"])
    result = run_cli("execute", workspace.root, "--executable", executable)
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert result.stderr == ""
    assert payload["status"] == "completed"
    assert payload["returncode"] == 0


def test_execute_missing_executable_returns_structured_failure_and_127(tmp_path: Path) -> None:
    workspace = prepare(tmp_path / "missing", task="scf")
    result = run_cli("execute", workspace.root, "--executable", tmp_path / "missing-abacus")
    payload = json.loads(result.stdout)
    assert result.returncode == 127
    assert payload["returncode"] == 127
    assert payload["diagnostics"]["failure_class"] == "missing_executable"


def test_help_is_a_noninteractive_process_contract() -> None:
    help_result = run_cli("--help")
    assert help_result.returncode == 0
    assert help_result.stderr == ""
    assert "usage:" in help_result.stdout


def test_parser_error_has_nonzero_exit_and_empty_stdout() -> None:
    error_result = run_cli("not-a-forge-command")
    assert error_result.returncode == 2
    assert error_result.stdout == ""
    assert "invalid choice" in error_result.stderr
```

Run only the new file before changing production code:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_cli_process.py
```

Expected RED: only `test_prepare_json_is_machine_readable` fails because the current parser rejects `--json`; the other five process tests pass. Any additional failure is a test setup defect and must be corrected before changing production code.

- [ ] **Step 2: Implement the minimal CLI behavior**

In `src/abacus_forge/cli.py`:

1. Add `prepare_parser.add_argument("--json", action="store_true", help="print a structured result to stdout")` beside the existing prepare options.
2. Import `Workspace` from `abacus_forge.workspace`.
3. Add this helper immediately before `main`:

```python
def _print_prepared_workspace(workspace: Workspace, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps({"status": "prepared", "workspace": str(workspace.root)}, sort_keys=True))
    else:
        print(workspace.root)
```

4. In both `prepare` branches (including `--pyatb`), replace the direct `print(workspace.root)` with `_print_prepared_workspace(workspace, as_json=args.json)` and keep `return 0` unchanged.

- [ ] **Step 3: Verify GREEN and run the owning suites**

Run:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_cli_process.py
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_cli.py tests/test_api.py tests/test_tasks.py tests/test_units.py
```

Expected: the focused file passes all five tests, the owning suites pass, and legacy in-process prepare tests still receive a bare path.

- [ ] **Step 4: Refactor only after GREEN**

Keep process invocation in `tests/support/process.py`, keep expected JSON literals in `tests/test_cli_process.py`, and do not add assertions on parser source text. Remove any temporary RED probe before committing.

- [ ] **Step 5: Commit the CLI contract**

```bash
git add src/abacus_forge/cli.py tests/support/process.py tests/test_cli_process.py
git commit -m "feat: add structured prepare cli output"
```

### Task 4: Make collector compatibility and serialized result contracts explicit

**Files:**
- Create: `tests/support/reference_workspaces.py`
- Create: `tests/test_result_contract.py`
- Create: `tests/benchmark/test_abacustest_compatibility.py`
- Create: `tests/fixtures/abacustest-abacus-scf/KPT`
- Create: `tests/fixtures/abacustest-abacus-scf/STRU`
- Modify: `tests/test_collect_abacus_reference.py` to use the shared reference workspace builder without changing its hand-checked metrics.

**Test strategy:**
- Behavior boundary: collector compatibility must retain force/stress/pressure/virial/timing/log-selection behavior, and `CollectionResult`, `RunResult`, and unit preparation payloads must remain JSON-serializable with stable top-level fields.
- Existing suite to extend: `tests/test_collect_abacus_reference.py` owns parser compatibility; the result contract file is justified as a distinct serialization boundary; the benchmark file owns opt-in migration projection.
- New test file justification: result serialization and benchmark selection are independent boundaries not covered by the current collector tests.
- Temporary probes: none.

**Interfaces:**
- Consumes: `Workspace`, `collect`, `prepare`, `run`, `prepare_unit`, `UnitSpec`, and the existing ABACUSTest fixture.
- Produces: `copy_abacustest_scf_workspace(root: Path) -> Workspace`; a benchmark projection with literal expected status/metric values; no production schema change.

- [ ] **Step 1: Add complete reusable reference inputs**

Create `tests/fixtures/abacustest-abacus-scf/KPT` with:

```text
K_POINTS
0
Gamma
5 5 2 0 0 0
```

Create `tests/fixtures/abacustest-abacus-scf/STRU` with the exact structure currently embedded in `tests/test_collect_abacus_reference.py`:

```text
ATOMIC_SPECIES
Si 28.085500 Si.upf

LATTICE_CONSTANT
1.0
LATTICE_CONSTANT_UNIT
Angstrom

LATTICE_VECTORS
8.3004 0.0 0.0
0.0 8.3004 0.0
0.0 0.0 25.362243471279523

ATOMIC_POSITIONS
Direct
Si
0.0
1
0.0 0.0 0.0 m 1 1 1
```

- [ ] **Step 2: Extract the reference workspace builder**

Create `tests/support/reference_workspaces.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from abacus_forge.workspace import Workspace


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "abacustest-abacus-scf"


def copy_abacustest_scf_workspace(root: Path) -> Workspace:
    workspace = Workspace(root).ensure_layout()
    for relative_path in ("INPUT", "KPT", "STRU"):
        workspace.write_text(f"inputs/{relative_path}", (FIXTURE_ROOT / relative_path).read_text(encoding="utf-8"))
    workspace.write_text("outputs/OUT.ABACUS/running_scf.log", (FIXTURE_ROOT / "OUT.ABACUS" / "running_scf.log").read_text(encoding="utf-8"))
    workspace.write_text("outputs/out.log", (FIXTURE_ROOT / "out.log").read_text(encoding="utf-8"))
    workspace.write_text("outputs/OUT.ABACUS/INPUT", (FIXTURE_ROOT / "OUT.ABACUS" / "INPUT").read_text(encoding="utf-8"))
    workspace.write_text("outputs/stderr.log", "")
    workspace.write_json("outputs/OUT.ABACUS/time.json", json.loads((FIXTURE_ROOT / "time.json").read_text(encoding="utf-8")))
    return workspace
```

Refactor `tests/test_collect_abacus_reference.py` to call this helper and delete its inline `STRU`/`KPT`/log copying. Keep the existing force, stress, pressure, virial, timing, and log-selection expected values as independent assertions.

- [ ] **Step 3: Add serialized result contract tests**

Create `tests/test_result_contract.py` with these tests:

```python
from __future__ import annotations

import json
from pathlib import Path

from abacus_forge import LocalRunner
from abacus_forge.api import UnitSpec, collect, prepare, prepare_unit, run
from tests.support.fake_executables import write_fake_abacus


def test_collection_result_to_dict_has_stable_agent_fields(tmp_path: Path) -> None:
    workspace = prepare(tmp_path / "collect-contract", task="scf")
    workspace.write_text("outputs/stdout.log", "TOTAL ENERGY = -5.0\nSCF CONVERGED\n")
    workspace.write_text("outputs/stderr.log", "")
    payload = collect(workspace).to_dict()
    assert set(payload) == {
        "workspace",
        "status",
        "metrics",
        "artifacts",
        "diagnostics",
        "inputs_snapshot",
        "structure_snapshot",
        "final_structure_snapshot",
    }
    assert payload["status"] == "completed"
    json.dumps(payload, allow_nan=False)


def test_run_result_to_dict_serializes_paths_and_exit_status(tmp_path: Path) -> None:
    workspace = prepare(tmp_path / "run-contract", task="scf")
    executable = write_fake_abacus(tmp_path / "fake-abacus", stdout_lines=["TOTAL ENERGY = -3.2", "SCF CONVERGED"])
    payload = run(workspace, runner=LocalRunner(executable=str(executable))).to_dict()
    assert payload["workspace"] == str(workspace.root)
    assert isinstance(payload["returncode"], int)
    assert payload["stdout_path"].endswith("stdout.log")
    assert payload["stderr_path"].endswith("stderr.log")


def test_unit_prepare_payload_matches_manifest_contract(tmp_path: Path) -> None:
    result = prepare_unit(UnitSpec(task="scf", unit="default", workdir=tmp_path / "unit-contract"))
    payload = result.to_dict()
    assert set(payload) == {"workspace", "task", "unit", "engine", "manifest"}
    assert payload["task"] == "scf"
    assert payload["unit"] == "default"
    assert payload["engine"] == "abacus"
    assert payload["manifest"]["prepared"] is True
```

The expected values remain literal and the test exercises the public result boundary; no source-text assertion or implementation-derived expected value is permitted.

- [ ] **Step 4: Add the opt-in compatibility benchmark projection**

Create `tests/benchmark/test_abacustest_compatibility.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from abacus_forge import collect
from tests.support.reference_workspaces import copy_abacustest_scf_workspace


@pytest.mark.benchmark
def test_abacustest_scf_projection_preserves_migration_metrics(tmp_path: Path) -> None:
    result = collect(copy_abacustest_scf_workspace(tmp_path / "benchmark"))
    assert result.status == "completed"
    assert len(result.metrics["force"]) == 81
    assert result.metrics["stress"] == pytest.approx([
        [-52.80278090212644, -0.20034687716893254, -0.16869734918889936],
        [-0.20034687716893204, -52.87869324794468, -0.45515956333833435],
        [-0.16869734918889878, -0.45515956333833385, -39.96544028144169],
    ])
    assert result.metrics["pressure"] == pytest.approx(-48.548971477133335)
    assert result.metrics["total_time"] == pytest.approx(932.927)
```

This is a compatibility projection, not a claim that one fixture proves the full Paimon benchmark. The full benchmark remains a later migration gate.

- [ ] **Step 5: Run the compatibility and contract suites**

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_collect_abacus_reference.py tests/test_result_contract.py
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider --run-benchmark -m benchmark
```

Expected: all selected tests pass; the benchmark is skipped without `--run-benchmark` and runs only with that explicit option.

- [ ] **Step 6: Commit the compatibility governance change**

```bash
git add tests/support/reference_workspaces.py tests/test_collect_abacus_reference.py tests/test_result_contract.py tests/benchmark tests/fixtures/abacustest-abacus-scf/KPT tests/fixtures/abacustest-abacus-scf/STRU
git commit -m "test: formalize collector compatibility contracts"
```

### Task 5: Add opt-in real ABACUS smoke evidence and make the default output clean

**Files:**
- Create: `tests/real_smoke/__init__.py`
- Create: `tests/real_smoke/test_abacus_smoke.py`
- Create: `tests/real_smoke/README.md`
- Modify: `tests/conftest.py:30-50` to skip `real_smoke` unless explicitly enabled and to require the two environment variables.
- Modify: `pyproject.toml:37-55` to ignore only the known external `spglib` warning while retaining project warning visibility.
- Modify: `tests/README.md` and `AGENTS.md` with the real-smoke invocation and evidence limits.

**Test strategy:**
- Behavior boundary: a supplied prepared Forge workspace can execute through the real ABACUS binary and collect a completed result without changing the user's source workspace; missing opt-in or environment is an explicit skip, not a silent pass.
- Existing suite to extend: `tests/test_units.py` and `tests/test_tasks.py` remain deterministic fake-runner suites; the new file owns the external executable boundary.
- New test file justification: real execution is a separate, opt-in boundary and must never contaminate default CI.
- Temporary probes: copy the supplied smoke workspace into `tmp_path`; never mutate the environment-designated source.

**Interfaces:**
- Consumes: `ABACUS_FORGE_REAL_SMOKE_WORKSPACE` (prepared Forge workspace path) and `ABACUS_FORGE_ABACUS_EXECUTABLE` (real ABACUS executable path), plus `execute_unit`/`collect_unit`.
- Produces: one explicit `real_smoke` evidence test and documented commands; no scheduler or platform code in Forge.

- [ ] **Step 1: Write the opt-in smoke test and verify the default skip**

Create `tests/real_smoke/test_abacus_smoke.py`:

```python
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from abacus_forge.api import UnitSpec, collect_unit, execute_unit


@pytest.mark.real_smoke
def test_real_abacus_scf_execute_and_collect(tmp_path: Path) -> None:
    source_value = os.environ.get("ABACUS_FORGE_REAL_SMOKE_WORKSPACE")
    executable = os.environ.get("ABACUS_FORGE_ABACUS_EXECUTABLE")
    if not source_value or not executable:
        pytest.skip("set ABACUS_FORGE_REAL_SMOKE_WORKSPACE and ABACUS_FORGE_ABACUS_EXECUTABLE")
    source = Path(source_value)
    if not source.is_dir():
        pytest.fail(f"ABACUS_FORGE_REAL_SMOKE_WORKSPACE is not a directory: {source}")
    if not shutil.which(executable) and not Path(executable).is_file():
        pytest.fail(f"ABACUS_FORGE_ABACUS_EXECUTABLE is not executable: {executable}")

    workspace = tmp_path / "real-smoke"
    shutil.copytree(source, workspace, symlinks=True)
    executed = execute_unit(UnitSpec(task="scf", unit="default", workdir=workspace, executable=executable))
    collected = collect_unit(UnitSpec(task="scf", unit="default", workdir=workspace))

    assert executed.returncode == 0
    assert collected.status == "completed"
    assert isinstance(collected.metrics.get("total_energy"), (int, float))
```

Run without opt-in:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider -m real_smoke
```

Expected: the test is skipped with the message requiring `--run-real-smoke`; no external executable is invoked.

- [ ] **Step 2: Add the explicit smoke gate and environment documentation**

Extend `pytest_collection_modifyitems` so every item whose path contains `real_smoke` receives the existing skip marker unless `--run-real-smoke` is set. Add `tests/real_smoke/README.md`:

```markdown
# Real ABACUS smoke

The smoke gate consumes a prepared Forge workspace and never edits the source
workspace. The workspace must contain valid `inputs/INPUT`, `inputs/STRU`,
`inputs/KPT`, and all pseudopotential/orbital assets required by its INPUT.

```bash
export ABACUS_FORGE_REAL_SMOKE_WORKSPACE=/absolute/path/to/prepared-forge-workspace
export ABACUS_FORGE_ABACUS_EXECUTABLE=/absolute/path/to/abacus
conda run -n paimon python -m pytest -q --run-real-smoke -m real_smoke
```

This gate proves Forge execution and collection integration only. It does not
replace convergence studies, platform validation, or the Paimon v1.2 benchmark.
```

- [ ] **Step 3: Suppress only the known third-party warning**

Add this to `[tool.pytest.ini_options]` after the marker list:

```toml
filterwarnings = [
    "ignore:Set OLD_ERROR_HANDLING to false and catch the errors directly\\.:DeprecationWarning:spglib\\..*",
]
```

Do not add a blanket `ignore::DeprecationWarning`; any warning from Forge code must remain visible.

- [ ] **Step 4: Verify the clean default suite and the opt-in boundary**

Run:

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider -m 'not real_smoke'
```

Expected: default deterministic tests pass with no warning summary; the real-smoke test remains skipped unless environment variables and `--run-real-smoke` are supplied. If the filter does not match the installed spglib module/message, adjust only the module/message regex and rerun; do not broaden it.

- [ ] **Step 5: Update the governance docs with release evidence**

Add to `tests/README.md` and `AGENTS.md`: deterministic tests are PR gates; `compat`/`benchmark` are migration evidence; `real_smoke` is release evidence; none of these alone proves physical convergence or HPC scheduler correctness.

- [ ] **Step 6: Commit the real-smoke and warning policy**

```bash
git add pyproject.toml tests/conftest.py tests/real_smoke tests/README.md AGENTS.md
git commit -m "test: add opt-in real abacus smoke gate"
```

## Completion Verification

After all tasks and reviews, run from the isolated repository root:

```bash
git diff --check
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider --run-benchmark -m benchmark
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider -m 'not experimental and not real_smoke and not benchmark'
```

Expected: all commands exit 0; the deterministic suite has no warning summary; benchmark projection passes only under its explicit flag; experimental and real-smoke tests are excluded from the stable gate unless explicitly selected. The final whole-branch review must also confirm that no runtime dependency or scheduler integration was introduced and that every removed helper/test has surviving mutation evidence.

## Plan Self-Review

- Coverage: Task 1 makes the test portfolio and gates explicit; Task 2 removes duplicate test infrastructure; Task 3 covers the Agent-first process boundary and the one backward-compatible CLI behavior; Task 4 protects collector migration and serialized result contracts; Task 5 adds real ABACUS evidence without contaminating default CI.
- Scope: no AiiDA, platform, scheduler, or runtime dependency changes; Paimon benchmark claims remain explicitly bounded to the available fixture projection.
- Placeholder scan: every task names its created files, marker names, environment variables, test commands, expected output, and concrete behavior; no unspecified implementation step remains.
- Type consistency: `write_fake_abacus`, `write_fake_abacus_with_matrix`, `write_fake_pyatb`, `write_fake_lcao_scf_workspace`, `run_cli`, and `copy_abacustest_scf_workspace` signatures are defined before later tasks consume them.
- Known ruling: test-only tasks do not invent RED cycles; Task 3 is the only planned production behavior change and must provide the mandatory RED/GREEN evidence.
