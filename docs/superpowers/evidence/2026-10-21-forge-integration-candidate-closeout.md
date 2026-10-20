# Forge 本地 main 与候选交付收口

本轮按用户确认顺序完成已实现增量集成、候选范围和实际消费缺口核查。
[执行计划](../plans/2026-10-21-forge-integration-candidate-closeout.md)。

## 已集成内容与验证

实现提交 **5f38349d7fcdb925af742b05bb2bd8bab061392c** 已 fast-forward 合入本地 main。
包含直接 NAO/PyATB COHP、有限 discovery contracts、manifest 消费示例、
polarization/BEC typed operations 及各自规范、测试和真实证据。代码契约未因收口改变。

- main 集成后全离线 **1532 passed、35 skipped**，121.75 s，exit 0。
- main 源码构建 sdist，再从 sdist 构建 wheel，均成功；wheel 与前轮已验证的
  c70e71a… **完全相同**，因此既有520项安装态和真实MgO证据继续适用。
- 新 CPython 3.12 venv 安装候选 `[dev,abacuslite]`，无 system-site；安装态
  package/metadata/canonical parity **30 passed**。初始缺 wheel 环境变量跳过的
  两项已显式指定本候选补验，**2 passed**；`pip check` 通过。
- 安装、wheel 与 main 源码的76个Python模块逐字节一致；结构化CLI可发现新增能力。

[机器收据](2026-10-21-forge-integration-candidate-closeout/candidate.json)、
[实际命令](2026-10-21-forge-integration-candidate-closeout/commands.json)、
[main 回归](2026-10-21-forge-integration-candidate-closeout/main-offline.log)、
[可选解析器回归](2026-10-21-forge-integration-candidate-closeout/candidate-package-tests.log)、
[实际 wheel 门禁](2026-10-21-forge-integration-candidate-closeout/candidate-wheel-tests.log)。

## 本地候选包

版本仍为开发版本 **0.1.0**；本候选通过源码提交与产物摘要识别，未推送远程、未发布PyPI。
文件位于 `/home/james/scratch/forge-closeout-20261021/artifacts/`：

| 产物 | SHA256 |
| --- | --- |
| `abacus_forge-0.1.0-py3-none-any.whl` | `c70e71a698ea6fc6d697495845e45c8cb9a95876636e54705074ce2967a02180` |
| `abacus_forge-0.1.0.tar.gz` | `ee210de2b94739b9e55451e92419b6f4673d266fd5982c2501da79dfe7f0c746` |

本机安装方式（选择新环境，避免覆盖其他工作的运行环境）：

```bash
python -m pip install /home/james/scratch/forge-closeout-20261021/artifacts/abacus_forge-0.1.0-py3-none-any.whl
# 需要可选 abacuslite parser 时：
python -m pip install '/home/james/scratch/forge-closeout-20261021/artifacts/abacus_forge-0.1.0-py3-none-any.whl[abacuslite]'
abacus-forge capabilities
```

sdist 用于构建，已实际从它产出相同 wheel；现有 sdist ignore 策略不包含原生 `.log`，
完整原始验证材料在本地 main 的已跟踪 evidence 中。源码检验/历史恢复使用 Git 工作树。
当前主工作树干净且已集成；开发工作树保留，供脚本路径和后续迭代使用。

## 依赖与范围裁决

| 项目 | 本候选选择与边界 |
| --- | --- |
| 默认依赖 | 继续 ASE、dpdata、matplotlib、NumPy、pymatgen；不引入旧 abacus-agent-tools / abacustest 运行时依赖 |
| abacuslite | 保留 optional exact `1.2.0`；本候选重新验证安装与canonical parity，原有双轨证据仍按原版本有效 |
| PyATB / ATST | 外部 executable/产物交接，不打入 Forge wheel；旧真实证据各自保留其指定输入/引擎范围 |
| Python/平台 | 元数据声明Python≥3.10；本候选实测CPython3.12/Linux。PyATB原生wheel另有限定CPython3.12/glibc≥2.39的既有范围 |
| 成熟度 | typed capabilities 仍experimental，scientific=unassessed；不由安装通过晋升stable |

Ruling：**不在本候选升级 abacuslite pin**。已核对发布tag差异和
[PyPI 1.2.2](https://pypi.org/project/abacuslite/1.2.2/)；1.2.1增加无熵能量元数据，
1.2.2修复文件型ASE calculator的非共线磁矩传递，均未改变Forge当前使用的
latestio/legacyio能量、力、应力读取函数。未发现当前demo需要新增字段，因此保留
已验证pin。实际消费者需要新能力时另做rebind、provenance和兼容验证，不以版本号
新旧替代效果判断。此裁决不否定1.2.2已发布或可用。

## 实际 demo/Benchmark 交接

只读核查 Paimon owner 工作树 `app-tools-forge@89fe8edc5`，该工作树有未提交内容，
本轮未修改其代码、配置、kit或授权记录。当前未找到有复现依据的Forge库级阻断。

- Paimon仍绑定旧Forge `20dc2eb6` / wheel `2fbc50ee…`；本次Forge新候选尚未接入
  该产品，不把现有Paimon结果说成已验收5f38349。
- 新产品ZIP为 `4f000960…`，runtime gate PASS；默认路由14/15的PARTIAL来自
  PyATB band按设计只允许显式调用，不是新增失败。
- replay已注入backend=forge；89fe8edc5已补齐band_info-derived Fermi/VBM/CBM。
  Si band四项指标均在0.05 eV阈值内，旧“执行器未接线/边缘事实未补”不再列待办。

下一实际工作由Paimon owner承接：

1. 统一候选kit：已提交manifest的app ZIP和authorization candidate_lock仍是
   `d7a10a80…`，追加benchmark段却指向`4f000960…`；按当前产品和harness重新整理
   一致的3.12/3.13 kit、绑定与门禁。旧锁与新产品不一致需由owner核对既有授权的
   实际适用范围，不能仅根据hash变化推断必须重新请求授权。
2. 若采用本轮Forge候选，将其wheel/源码版本显式重绑定，并验收受影响的实际入口。
3. 接续canary和完整Benchmark。CoF3固定输入能量对照已通过，但绕过prepare；
   prepare参数策略对等仍属于Paimon产品判断，不能归咎为未证实的Forge缺陷。

核查来源（工作区相对本仓根）：
`../app-tools-forge/toolbox/ABACUS/docs/superpowers/evidence/2026-10-20-paimon-benchmark-candidate-3313b4c1c/README.md`、
`.../2026-10-20-paimon-benchmark-kit/manifest.json`、
`.../2026-10-20-paimon-benchmark-sai-canary/README.md`，以及
`tests/benchmark/candidate_runner.py`、`config/configure.json`。
只读审计发现的缺口记录于此，不占用或改写并行owner状态。

## 交付状态

本轮Forge集成与候选范围已落实；完整Paimon Benchmark、生产发布和进一步科学
收敛不由这些局部结果关闭。独立收口审查通过，构建/安装/上层交接结论均与原始
证据一致，无实质问题；164项文档相对文件链接及diff格式检查通过。
