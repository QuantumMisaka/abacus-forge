# 退役与被替代的设计

2026-11-05 按用户要求清理不符合当前目标的设计。本目录保留原提案正文以便追溯，新增归档提示并修正相对链接；原状态、命令和待办均不作为当前执行依据。原 `docs/superpowers/specs/` URL 改为简短状态/后继指引，历史引用仍可查。

| 原设计 | 处置与当前依据 |
| --- | --- |
| [Contract System M1–M4](2026-09-29-forge-contract-system-design.html) | 未整体批准，退出当前开发目标。有限 discovery contracts map 继续按[10-21 有限消费规范](../../superpowers/specs/2026-10-21-forge-consumption-metadata-design.md)维护，不继承知识库/查询服务框架。 |
| [I/O Contract Knowledge Base](2026-09-29-forge-io-contract-knowledge-base-design.html) | 历史草案，不再作为前置建设。[收缩设计](../../superpowers/specs/2026-10-29-forge-computation-factory-target-architecture-design.md)要求在实际 owner 中按消费者补齐元数据。 |
| [09-29 Typed BEC](2026-09-29-forge-typed-bec-design.html) | 被[10-21 有界 BEC 规范](../../superpowers/specs/2026-10-21-forge-polarization-bec-design.md)替代，旧数值解释不作为实现依据。 |

有效的 Contract-First、Service/Status 及领域 SPEC 不因已实现而归档。现有 property manifest 有实际消费，保留其 provisional/experimental 范围；此次没有删除代码、接口、测试或原始运行证据。

当前入口：[设计与计划](../../superpowers/README.md)。
