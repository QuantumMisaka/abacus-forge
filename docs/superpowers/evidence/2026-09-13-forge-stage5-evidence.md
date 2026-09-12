# Forge Stage 5 evidence record

**状态：** provisional / candidate evidence；不构成稳定能力或 Paimon v1.3
backend 发布决定。

**候选 HEAD：** `9c21f51efc8cb3f6f17a2e2e6919550b72be4037`（包含生产代码归因修复
及其回归测试）。

**证据文档基线提交：** `87eda1fe6b3e59da73965d4dee92cf2e876d5054`；后续
`5806d1c`、`5930607` 为文档校正，不改变候选代码。

**规范源：**
`docs/superpowers/specs/2026-09-01-forge-contract-first-rearchitecture-design.html`
与 `docs/superpowers/specs/2026-09-02-forge-service-status-migration-design.html`。

## 1. 当前 typed capability manifest

以下内容由候选提交的 `capabilities_document()` 直接输出；九项均保持
`experimental`。artifact role 只记录实际 descriptor，不推断未实现的角色。

| capability | operations | engine | artifact roles |
| --- | --- | --- | --- |
| `scf` | `prepare`, `modify`, `execute`, `collect` | `abacus` | `input`, `provenance_manifest`, `output` |
| `relax` | `prepare`, `modify`, `execute`, `collect` | `abacus` | `input`, `provenance_manifest`, `output` |
| `cell-relax` | `prepare`, `modify`, `execute`, `collect` | `abacus` | `input`, `provenance_manifest`, `output` |
| `md` | `prepare`, `modify`, `execute`, `collect`, `postprocess` | `abacus` | `input`, `provenance_manifest`, `output` |
| `band` | `postprocess` | `abacus` | `input`, `output` |
| `dos` | `postprocess` | `abacus` | `input`, `output` |
| `pyatb-band` | `prepare`, `execute`, `collect` | `pyatb` | `input`, `provenance_manifest`, `output` |
| `export` | `export` | `forge` | `output` |
| `atst-neb` | `prepare`, `execute`, `postprocess` | `atst-tools` | `input`, `output` |

Legacy property packs（包括 `convergence`、cube、BEC、Bader、workfunc、vacancy
等）不纳入本 typed manifest，继续保持 `experimental`；它们需要各自的
SPEC/PLAN 和真实操作证据后，才能由上层评估是否消费。

## 2. Deterministic and migration gates

执行环境为 conda `paimon`（Python 3.11.15），工作目录为候选 worktree。

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider
1346 passed, 10 skipped in 112.66s (0:01:52)

conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider \
  tests/test_architecture.py tests/test_contracts.py tests/test_workspace.py
344 passed in 10.14s

conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-benchmark -m benchmark
6 passed, 1350 deselected in 3.59s

git diff --check
passed (no output)
```

本证据/计划提交自身的 `git diff --check` 通过，placeholder scan 无匹配。

`benchmark` 当前是既有 fixture/collection 事实矩阵；它不是全链路执行等价、
科学正确性或稳定 maturity 证据。

代码候选提交的 discovery/import 检查输出为：

```text
0.1.0
['scf', 'relax', 'cell-relax', 'atst-neb', 'md', 'band', 'dos', 'pyatb-band', 'export']
```

architecture gate 同时覆盖生产 import 边界和禁止运行时依赖的 AST 检查。

## 3. Clean package and dependency isolation

环境：Linux 6.18.33.2-microsoft-standard-WSL2 x86_64、Python 3.13.13；以下是实际
执行的最小重现命令（`stage5_tmp` 是临时目录）：

```bash
stage5_tmp=$(mktemp -d /tmp/forge-stage5-build-XXXXXX)
python -m venv "$stage5_tmp/venv"
"$stage5_tmp/venv/bin/python" -m pip install --quiet hatchling
"$stage5_tmp/venv/bin/python" -m pip wheel --no-deps --no-build-isolation \
  --wheel-dir "$stage5_tmp/wheels" .
"$stage5_tmp/venv/bin/python" -m pip install --no-deps \
  "$stage5_tmp/wheels/abacus_forge-0.1.0-py3-none-any.whl"
"$stage5_tmp/venv/bin/python" -m pip install ase dpdata matplotlib numpy pymatgen

"$stage5_tmp/venv/bin/abacus-forge" schema scf execute \
  | "$stage5_tmp/venv/bin/python" -c \
  'import json,sys; d=json.load(sys.stdin); print("schema_ok", d["schema_version"], d["capability"], d["operation"])'
"$stage5_tmp/venv/bin/python" -c \
  'from abacus_forge.machine_cli import decode_operation_request; r=decode_operation_request("execute", {"schema_version":"forge.request/v1","operation":"execute","operation_id":"123e4567-e89b-42d3-a456-426614174123","workspace_rel":"fixture","dry_run":True}); print("decode_ok", type(r).__name__, r.operation, r.workspace_rel, r.dry_run)'
```

随后执行 `import`、console、schema 和最小 typed decoder 探针。构建结果：

```text
abacus_forge-0.1.0-py3-none-any.whl
sha256=1310f9a036d58a932a60d259007cbbde119f331537a26ea33489cc5b370a4be2
```

安装后的检查结果：

```text
import_ok 0.1.0
capabilities ['scf', 'relax', 'cell-relax', 'atst-neb', 'md', 'band', 'dos', 'pyatb-band', 'export']
cli_ok forge.capabilities/v1 9
forbidden_absent {'abacus_agent_tools': True, 'abacustest': True, 'aiida': True, 'atst_tools': True}
schema_ok forge.schema-discovery/v1 scf execute
decode_ok ScfExecuteRequest execute fixture True
```

该 gate 证明的是当前代码候选 wheel 的安装、import、console entry point、discovery 和
legacy runtime isolation；不证明 ABACUS/PyATB/ATST 的真实运行，也不包含任何
科学接受判断。

ATP/MCP、调度器和平台包不通过运行时探针判断；它们由同一候选提交的
architecture/AST forbidden-import gate 覆盖，避免把可选外部工具误写成 Forge 安装依赖。

## 4. Real-process evidence

在当前环境未提供真实 ABACUS executable 或 prepared workspace。精确选择命令为：

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-real-smoke -m real_smoke
4 skipped, 1352 deselected in 2.43s
```

该结果是 `unproven`，不是 pass，也不是科学或稳定性证据。现有
`tests/real_smoke/test_abacus_smoke.py` 已分别覆盖 typed SCF、Relax/cell-relax
和 MD 的 machine-CLI execute/collect；待外部提供无历史 generated output 的
workspace 与 executable 后再运行。`normal_end` 仅作为独立日志 observation，
不会被转换为 scientific status。当前归因规则只接受前缀未变的新增后缀 marker；
旧 marker 在截断、同尺寸改写或前缀改写中一律视为歧义并省略。

`atst-tools` 外部仓当前记录为 `main@9318177`、版本 `2.2.4`；Forge 的本地
adapter/process contract smoke 已有历史记录，但真实 NEB workflow、版本/API 锁定
和环境隔离仍为 `unproven`。Forge 不启动 Slurm，也不复制 atst 的链路编排。

## 5. 发布判断与未决条件

- 所有九个 typed capability 继续为 `experimental`；property packs 也继续为
  `experimental`。
- Forge core 的职责仍限于单 operation 的 prepare/modify/execute/collect/
  postprocess/export、事实型观察和 artifact 引用。
- 科学验证与接受判断、跨 operation 编排、重试/续算、资源选择、平台/调度和
  Paimon v3 thin adapter 均在 Forge 外部。
- 当前 clean package、离线契约、architecture 和 benchmark 门禁已形成候选证据；
  real ABACUS/PyATB/ATST workspace 与上层 Paimon v1.2 全链路 parity 尚未齐全。
- 因此本记录不能宣称 Stage 5“证据齐全”，不能把 capability 改为 `stable`，也
  不能宣称 Forge 已是 Paimon v1.3 stable backend。后续由外部上层提供真实输入、
  benchmark harness 和独立发布决定。
