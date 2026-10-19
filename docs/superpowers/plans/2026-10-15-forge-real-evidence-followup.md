# Forge 真实输入与执行验收推进

授权：2026-10-15 用户确认按“文档收尾 → COHP 完整真实数据 → 真实 NEB，并调查 abacuslite 发布包”推进。工作流 L3，复用 `codex/cohp-install-closeout-20261015` 工作区；本轮包含本地 main 集成，不包含推送、发布或 experimental 晋级。

规范依据：[COHP W1](../specs/2026-10-15-forge-cohp-postprocess-design.md)、[Stage 5](2026-09-13-forge-stage5-evidence-gates.md)、[版本政策](2026-09-13-forge-engine-version-policy.md)和[ATST adapter](2026-09-09-forge-atst-neb-adapter.md)。保持单 operation、显式产物与追加审计契约；外层验收脚本拥有运行顺序和站点设置。

2026-10-19 状态接续：本页的发布包查询保留 10-15 历史事实；`abacuslite==1.2.0` 已完成 [exact extra 与安装态验收](../evidence/2026-10-19-forge-abacuslite-1.2.0-rebind.md)，不再等待首次发布。ATST 2.3.0 已完成[安装态 CLI 与上游真实轨迹消费回放](../evidence/2026-10-19-forge-atst-upstream-replay.md)，按用户决定不默认重复上游 NEB；本页原始新算证据仍绑定 2.2.8。

## 交付清单

- [x] 补 COHP 接口参考并核对 discovery；上轮 `016d337` 文档与本轮记录作为同一已审查分支进入本地 main 集成。
- [x] 核对既有 SAI Si SCF 完整产物和来源；以当前 Forge 独立 machine CLI 执行 IAO 后处理并比较数值/产物。既有 SCF 可作为显式输入，不伪称本轮新算；按可用输入扩展轨道选择。
- [x] 用真实 ATST + ABACUS 执行有界 NEB，核对进程、轨迹、summary、postprocess 和 audit。ATST 2.2.8 + LTSv3.10.1 实际计算 65 原子/5 图像，普通与 CI 阶段各 1 步；两者未收敛。batch 因 harness 参数错误失败，纠正后仅重试 postprocess 成功，三次 operation 审计完整保留。
- [x] 查询 canonical abacuslite 发布包。PyPI JSON 返回 404，显式索引查询返回无匹配分发；保存原始收据，保留 native 默认。exact pin/fresh-extra 继续等待发布包，不以 checkout wheel 冒充发布包。
- [x] 运行适用离线门禁、核对原始证据并完成独立审查：100 项文档/机器 CLI 检查与 67 项 owning tests 通过，最终 reviewer 无剩余阻断项。集成采用本地 fast-forward，不包含推送。

Ruling：本轮不实施 Draft BEC/Contract System、不删除默认依赖 — 它们需要独立设计或依赖所有权决策 — 避免将运行验收扩展为公共契约变更。

完成证据见[本轮运行记录](../evidence/2026-10-15-forge-real-evidence.md)。审查修正一处产物描述（实际输出 CIF，无 postprocess STRU），并独立重算轨迹位移、核对全部 operation 及 84 项归档哈希。本轮验收包含失败后恢复，不是整段 batch 一次成功；COHP 多材料/legacy parity、NEB 科学收敛与 parser 发布包门仍保持各自边界。
