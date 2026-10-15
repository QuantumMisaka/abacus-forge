# COHP IAO 安装消费证据

2026-10-15 用户要求在状态核查后继续推进。本轮完成当前 COHP 切片的安装后消费与有界数值等价检查；Forge 生产代码、公共契约和默认依赖保持 `43f5d4a274bb7106f1572dcaab122f7f29c7456b` 不变。

## 当前结果

- 从当前 Forge 源构建 wheel，SHA-256 `e2379f04974a63e46f5c25d9abf1aaaf6e444d81019df4904737628c28eb8e93`；提供 `ABACUS_FORGE_WHEEL` 后 `test_package_contract.py` 和 `test_package_metadata_drift.py` 为 **16 passed**。
- Python 3.13.13 无 system-site venv 离线安装 67 包，兼容性检查通过。Forge 实际从 venv 的 site-packages 加载；`ABACUS_FORGE_ROOT`、`PYTHONPATH` 未设置，两个旧包不存在。
- Paimon `bab7d380d385960f87eba01b67e1f8cdb36b895f` 的 ZIP（SHA-256 `545d2ec2308e14469d9d2fd41c46f7c1a72e810b5d31052f0a7ce57becd75663`）调用真实 Forge machine CLI 子进程完成 Si fixture 的 IAO 后处理，产物与 Paimon evidence 完整。
- 与同一输入的迁移前 Paimon IAO kernel 对比，曲线最大绝对差 **0.0**，ICOHP **-5.316876660330825 eV**；键、基组、费米能、诊断及 bond-images JSON 一致。irregular-k-grid warning 如实保留。
- Paimon 回归暴露并修复校验后续产物失败时提前复制前面产物的问题；修复前 6 failed / 16 passed，最终 COHP suite 23 passed，独立审查无阻断发现。

## 验收边界

公共 worker 首轮回放因本机没有 `abacus --check-input` 失败；离线回放仅注入这一步预检查，并禁止 SCF 补跑。Forge 后处理、子进程和交付均实际执行。这证明当前安装态后处理交接，不证明真实引擎预检查或平台运行。

安装态 package runtime 为 PASS；default-route 门禁保持预期 PARTIAL（8 条默认链通过、PyATB explicit-only）。这是本切片 clean-route 验收，不是完整专业依赖闭包。Si IAO 等价不替代 `abacus-cohp-lcao` legacy parity、其他材料或科学接受性；全部 typed capability 继续 experimental。

## 证据归属

跨仓证据由 Paimon owner 维护，位于 `app-tools-forge/toolbox/ABACUS/`：

- `docs/reports/2026-10-15-paimon-cohp-installed-closeout.md`：验收报告、复现命令和完整局限。
- `docs/superpowers/evidence/2026-10-15-paimon-cohp-installed-closeout/`：lock、kit manifest、门禁 JSON/退出码、RED/GREEN 原始日志、回放脚本及数值摘要。
- 本地候选与环境：`~/scratch/forge-cohp-closeout-20261015/`。

原 W1 [离线证据](2026-10-15-forge-cohp-postprocess.md)保持历史候选绑定；本轮不重新标记其为全量安装或发布通过。kit 已本地生成，未传输或发布。W3/W4 剩余工作继续由迁移总表维护。
