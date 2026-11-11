# Forge 三类任务展开：本地交付证据

2026-11-05。执行用户“任务单元展开优先、资源分配后续接入”的授权与[实施清单](../../plans/2026-11-05-forge-task-expansion.md)。Forge 本体已交付声子、弹性、振动的独立单元消费与显式汇总；Paimon adapter、平台资源和真实 ABACUS 验收未纳入本轮。

## 代码与包绑定

- repo：`git@github.com:QuantumMisaka/abacus-forge`；checkout：`/home/james/work/sidereus/workplace/abacus-forge`；branch：`main`；package：`0.1.0`。
- 实施基线：`7b54d28`；实现与构建提交：`82af7d53e4646b61d7b9d0bf3591dcadc4cd8fcd`。后续证据提交不改变 runtime 或 tests。
- 通过 `git archive` 导出该提交后构建 sdist，再从 sdist 构建 wheel。原有未跟踪的 `worktree-retention-20261024/` 未纳入构建或提交。
- 源码验证：`/home/james/scratch/forge-followup-20261105/venv`，pytest 通过仓库 conftest 加载当前 `src/`。
- 新安装环境：`/home/james/scratch/forge-task-expansion-20261105/installed-venv`，Python 3.12.13，`include-system-site-packages=false`，新 wheel 非 editable 安装。依赖含 pytest 8.4.2、phonopy 4.9.0、ASE 3.29.0；见[完整依赖](requirements.txt)。
- [verification.json](verification.json) 记录 site-packages 导入路径、direct URL、CLI 输出与制品校验。wheel 全部 78 个包文件、sdist 中 1522 个已跟踪文件逐一匹配该提交。

| 本地制品 | SHA-256 |
| --- | --- |
| `abacus_forge-0.1.0-py3-none-any.whl` | `49525424f803d4063b3631de9e54600f1bd1c8be9270be70a2d687989e296ff8` |
| `abacus_forge-0.1.0.tar.gz` | `618ad54ee3ea5d69de27208187424b2874043da05714067f02cbe08ee940bf60` |

制品目录为 `/home/james/scratch/forge-task-expansion-20261105/dist/`；二进制未加入 Git。本地候选未推送、未跑远端 CI，也未发布 PyPI。

## 已验证的交付行为

- `composite/plan.py` 复用现有 Workspace/runner/result/contracts：保存相对路径与科学参数，列出单元，单项 execute/collect，按 ID gather。不同单元可同时运行；同单元使用现有 workspace guard。每次结果/事件与 gather 快照独立保留。
- 乱序、失败、缺失、重复 ID、输入变更和目录迁移均有行为回归。单项普通异常保留失败记录；成功项不被吞掉。重试由调用方显式选择，不内建恢复调度器。写结果本身失败仍可能抛错。
- 三个 `post(results=...)` 与 CLI `post --results` 不隐式执行/采集；缺事实不发布伪完成物性。无显式结果的便利入口沿用 collect，但也校验输入配对。
- 声子实际调用 phonopy Python 和 CLI，检查等价物理位移下的晶胞、力常数和频率；弹性用实际生成 STRU 的非立方/斜胞应变回推应力；振动以合成谐响应检查 Hessian、频率和 ZPE。引擎执行使用受控 executable，不是真实 ABACUS 计算。
- CPU 汇总可在新根目录完成：声子仅需 plan、位移 YAML、力记录；弹性需 plan、应力；振动另需 eq 输入。文件交接用法见[指南](../../../guide.md#composite-and-property-packs)。

## 验证结果

| 检查 | 实际结果 | 原始输出 |
| --- | --- | --- |
| 最终源码默认全离线 | **1742 passed / 35 skipped / 509 warnings**，163.21 s | [full-accepted.txt](full-accepted.txt) |
| 新 wheel installed-only：三类展开、CLI、workspace、contracts、result、service、包与上手示例 | **750 passed / 390 warnings**，62.83 s | [installed-tests.txt](installed-tests.txt) |
| 构建及安装 | sdist → wheel 成功，新 venv 安装成功 | [build.txt](build.txt)、[install-wheel.txt](install-wheel.txt) |
| 安装态 CLI/API/包内容 | `--version`、`doctor --json`、`capabilities`、`schema scf execute`、三个 pack 新命令 help、ScfExecuteRequest launcher/env、`pip check` 全部成功 | [verification.json](verification.json) |
| 文档回写后相对链接 | 2 passed | [documentation-links.txt](documentation-links.txt) |

默认回归未开启 real_smoke/benchmark；源码运行未设置 wheel 文件变量，安装态明确设置。warning 保留 ASE/NumPy shape 弃用提示及 workspace 并发测试的 Python fork 提示，未新增过滤。测试数量只表示上述范围，不证明材料结果、资源分配或 Paimon 全量替代。

复跑时将下方 `SOURCE_PYTHON` 和 `CHECK_ROOT` 指向对应环境；在 Forge checkout 根目录运行：

```bash
SOURCE_PYTHON=/home/james/scratch/forge-followup-20261105/venv/bin/python
CHECK_ROOT=/home/james/scratch/forge-task-expansion-20261105
"$SOURCE_PYTHON" -m pytest -q -p no:cacheprovider

PYTHONPATH='' ABACUS_FORGE_INSTALLED_PACKAGE_ONLY=1 \
ABACUS_FORGE_WHEEL="$CHECK_ROOT/dist/abacus_forge-0.1.0-py3-none-any.whl" \
"$CHECK_ROOT/installed-venv/bin/python" -m pytest -q -p no:cacheprovider \
  tests/test_composite_plan.py tests/test_elastic_vibration_expansion.py \
  tests/test_phonon_expansion.py tests/test_composite.py tests/test_composite_elastic_fit.py \
  tests/test_contracts.py tests/test_workspace.py tests/test_result_contract.py \
  tests/test_units.py tests/test_service_status.py tests/test_cli.py \
  tests/test_package_contract.py tests/test_package_metadata_drift.py \
  tests/test_installed_package_mode.py tests/test_diagnostics.py tests/test_getting_started.py
"$CHECK_ROOT/installed-venv/bin/python" -m pip check
"$CHECK_ROOT/installed-venv/bin/python" scripts/release_validate.py \
  verify-distributions --dist-dir "$CHECK_ROOT/dist"
```

## 同轮独立审查与修复

同家族独立 reviewer `/root/contract_review` 审查实现 diff、文件 SHA 与原始测试输出；没有开启第二轮泛化审查。原 5 项关闭后，复核进一步发现参考 OUT 过滤对旧 property restart 的兼容回归；收窄并核实 RED/GREEN 后，最终结论为“本轮独立终审通过，无剩余阻断项”。主代理随后检查最终全量与安装态结果。

| 发现 | 实际修复与回归 |
| --- | --- |
| phonopy ABACUS CLI 的 Bohr 被当作 Å | 归一晶胞和位移，恢复质量及 Å/eV 力常数约定；实际 CLI/Python 在 0.02 Å 位移下对拍 2I 力常数与频率。 |
| 默认 post 绕过输入配对 | 三类默认 post 均通过 `collect_subtask`；非参考单元 INPUT 改变会在 collect 前拒绝。 |
| ASE 行向量晶胞的应变乘法错误 | 使用 `cell @ (I+strain).T`；从矩形/斜胞实际 STRU 回推应力，检验弹性张量。 |
| 声子质量及自定义 species 丢失 | 保留单 species/元素的 label、质量、PP/ORB；同元素多种 species 在展开前明确拒绝。 |
| `kpoint_file` 未绑定实际 KPT | 读取真实选择文件，生成时归一 KPT，摘要按实际 selector 计算。 |
| 过滤参考 OUT 导致旧 charge-density restart 丢失 | 默认仍复制，只在三类新展开中显式关闭；旧 restart 保留与新单元不继承参考结果两项同时通过。 |

审查修复的原始反例：[声子](phonon-review-red.txt)、[默认 post 与晶胞](elastic-vibration-review-p2-red.txt)、[KPT/参考输出](kpt-output-red.txt)；修复后[专项 72 passed](review-green.txt)。最后一项兼容收窄有独立 [RED 1 failed](restart-compat-red.txt) / [GREEN 2 passed](restart-compat-green.txt)，随后才取得上述最终全量和安装态结果。最初新增消费接口也保留 [plan RED](plan-red.txt) 与 [CLI RED](cli-red.txt)。日志入仓仅去除行尾空白，未改写结果。

## 适用边界与后续

[专项 report 第 7 节](../2026-11-05-forge-architecture-replacement-audit/phonon-elastic-vibration-parallel-report.md#7-用户授权后的-forge-实现接续) 逐项更新 PAR-01–06：Forge 的单元消费层已落实，Paimon adapter/ATP/Flow 接线未做，真实 allocation 留后续。旧 `run_many` 批次异常语义及 runner timeout 后代残留仍在原边界，未借本轮新增接口宣称已修复。

三类 pack 仍为 experimental。Forge 弹性是 13 单元，Paimon 原方法是 25 单元；振动只覆盖 Hessian/频率/ZPE，声子新分析覆盖力常数/q 点频率，未补齐所有热力学/谱图产品能力。声子同元素多 species 暂不支持。INPUT/STRU/KPT 摘要不是完整 PP/ORB/环境身份。下一步应在最新 Paimon 基线上消费这些阶段接口，再验证平台资源和科学/Benchmark parity；本轮不宣称可以直接替代现役全部能力。
