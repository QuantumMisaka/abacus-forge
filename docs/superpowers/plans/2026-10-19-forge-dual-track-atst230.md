# 发布 parser 双轨与 ATST 2.3.0 交接验证

授权：用户在分支与文档收口后确认继续。沿用 Engine/Version Policy 和 ATST adapter 的既有规范，不新增公共接口，不修改 dpdata 默认依赖。基线 `1cc82ab`；复用隔离工作树，新分支 `codex/forge-dual-track-atst230`。

## 顺序与范围

- [x] 核对本机两轨 ABACUS 与原始 smoke 源目录。共享 Conda ATST 为 2.2.8，不更改共享环境。
- [x] 从当前源码构建 Forge wheel；新建隔离环境安装 PyPI abacuslite 1.2.0 与 ATST 2.3.0，记录来源与依赖。
- [x] 重建可复现矩阵：develop/LTS × PW SCF/relax/cell-relax/MD，单进程实际执行后比较 native/abacuslite 的 typed 投影、状态与产物。使用现有 `test_abacuslite_dual_track.py`，完整矩阵不得 skip。
- [x] 用已安装 ATST 2.3.0 执行现有 make/dry-run/summary/post 进程门禁；单列有限步真实 NEB 的剩余条件，不以 dry-run 代替实际执行。
- [x] 修复安装态 CLI 子进程隔离，更新 owning 文档与证据；独立 reviewer 核对通过，无阻断问题。

本轮双轨使用已有明确版本的本地引擎，不表示追踪最新上游 HEAD。测试复制原始输入，不覆盖既有结果；输入变换、引擎哈希、包安装身份与失败原样保留。科学收敛、平台发布、所有配置覆盖不在本次结论范围。

## 本轮结果

八格真实运行 parity 与 ATST 安装态进程门禁已通过，见[实测记录](../evidence/2026-10-19-forge-dual-track-atst230.md)。新增安装态 CLI 子进程隔离回归先 2 failed 后通过；CLI/architecture 共 51 passed。独立 reviewer 核对 69 个 Forge wheel Python 文件与源码相同、三个 wheel 哈希、输入/日志归档及安装态 ATST executable；无阻断问题。125 个修改文档中的本地链接目标均存在，diff whitespace 检查通过。候选供本地 main 集成，保留分支与工作树，不推送或发布。
