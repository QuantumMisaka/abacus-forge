# Forge 测试分层与门禁

默认测试集离线运行。Portfolio marker 标记测试能证明的行为边界；新增根目录测试文件在 `tests/conftest.py` 中归类，其他测试须显式标记。收集时会报出未归类用例，避免正向 `-m` 选择静默遗漏。

| Marker | 行为与证据边界 | 用途 |
| --- | --- | --- |
| `core` | 输入/结构/数据算法、请求记录与包元数据等局部契约 | 确定性 PR 回归 |
| `integration` | prepare/execute/collect、service、workspace 审计与文件交接 | 确定性 PR 回归 |
| `cli` | CLI 解码、派发及进程输出 | 确定性 PR 回归 |
| `compat` | ABACUS/abacustest 兼容及可选解析器迁移约束 | 迁移证据 |
| `pyatb` | PyATB handoff、manifest、typed operation | 启用 PyATB 桥接时必跑 |
| `composite` | 本地复合任务与属性计算接线 | 确定性回归，不证明物理结果 |
| `experimental` | 仅有 mock/fixture 的 property pack | 非稳定能力证据 |
| `real_smoke` | 调用方提供引擎和工作区的真实进程 | 显式启用的操作发布证据 |
| `benchmark` | 规范化迁移投影与 parser parity | 显式启用的迁移证据 |

通用 Python 开发环境（Python 3.10 或更新版本）：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
```

以下是维护者现用的 `paimon` conda 环境命令；从仓库根目录运行：

```bash
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -m 'not experimental and not real_smoke and not benchmark'
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -m experimental
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider --run-benchmark -m benchmark
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider --run-real-smoke -m real_smoke
```

默认回归收集全部测试，但跳过 `real_smoke` 和 `benchmark`；正向 marker 选择不替代完整离线回归。真实计算的输入准备、逐项命令、环境变量、结果范围及已知版本差异统一见 [real-smoke 指南](real_smoke/README.md)。`ABACUS_FORGE_ABACUSLITE_REQUIRE_FULL_MATRIX=1` 是双轨发布门禁的既有例外：即使没有 `--run-real-smoke`，对应测试也不会因缺少外部输入而跳过，会明确失败；普通默认回归不要设置它。

`benchmark/test_abacuslite_canonical_parity.py` 的 Stage 0 对照默认使用已安装的 `abacuslite` 作为 oracle（`pip install '.[abacuslite]'`，当前 pin `1.1.0`）。也可以显式指定源码目录，此时 `ABACUS_FORGE_CANONICAL_ABACUSLITE` 指向包含 `abacuslite` 包的目录（例如独立仓 `abacuslite` 的 `src/`）。canonical 日志由 abacuslite 的 test fixture 提供：`ABACUS_FORGE_CANONICAL_ABACUSLITE_FIXTURES` 指向 `testfiles` 目录；历史布局 `abacuslite/io/testfiles` 仍然兼容。发布 wheel 不带这些日志，所以安装态运行必须显式给 fixtures 路径。

```bash
export ABACUS_FORGE_CANONICAL_ABACUSLITE_FIXTURES=/absolute/path/to/abacuslite/tests/fixtures/io/testfiles
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  python -m pytest -q -p no:cacheprovider --run-benchmark \
  tests/benchmark/test_abacuslite_canonical_parity.py
```

其中 `test_canonical_oracle_binds_the_declared_abacuslite_pin` 断言 oracle 版本等于 `pyproject.toml` 声明的 exact pin，避免用旧包或旧 checkout 冒充。它比较 SCF、relax、cell-relax、MD 的 `legacyio`/`latestio` 事实及版本隔离、并发和审计边界。这项离线 parity 不替代 native/optional parser 双轨真实计算门禁。

要在已安装 wheel（而不是源码 checkout）上跑测试，显式设置 `ABACUS_FORGE_INSTALLED_PACKAGE_ONLY=1`：conftest 不再把 `src/` 插入 `sys.path`，并在 `abacus_forge` 仍解析到本仓源码时直接失败。该模式不能替代带真实引擎的双轨发布证据。

## 按变更选择 owning tests

- 改动版本记录、workspace 持久化或跨 operation artifact 时，运行 `tests/test_contracts.py tests/test_workspace.py tests/test_result_contract.py tests/test_units.py tests/test_service_status.py`，并加入对应 API/result tests。`test_contracts.py` 管记录验证，`test_workspace.py` 管 append-only manifest/event，后面三项管结果投影和服务错误映射。
- 改动机器 CLI transport 时，同时运行 `tests/test_machine_cli.py tests/test_cli_process.py`。前者管进程内解码/发现/派发，后者管 stdout/stderr/退出码与 API/进程一致性。
- `tests/test_architecture.py` 管生产代码导入边界与当前用户指南中的机器 CLI 示例；示例仍通过实际 CLI 解析和执行 dry-run。`tests/fixtures/abacus-native-md` 是本地格式 fixture，不能充当真实执行或科学判断。

typed SCF/Relax service tests 保持执行、收集事实与科学判断分离：`scientific` 为 `unassessed`；`dry_run` 必须显式请求；typed 执行不会根据旧 `NORMAL END` 推断跳过。`run_many(skip_completed=True)` 属于 legacy composite 兼容接口，不属于 typed status 协议。

删除或合并测试前，须记录具名 production mutation 和剩余测试仍失败的证据。测试通过数量不能替代行为证据。上述 marker 本身都不证明物理收敛或 HPC 调度正确性。
