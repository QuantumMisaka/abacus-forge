# Forge 完整 SCF 输入与真实 NEB 验收

本轮由用户于 2026-10-15 授权，执行范围见[计划](../plans/2026-10-15-forge-real-evidence-followup.md)。Forge 生产代码和公共契约保持 `43f5d4a274bb7106f1572dcaab122f7f29c7456b`；改动仅包含文档及外层验收脚本/证据。所有 capability 仍为 experimental。

## 候选与运行环境

- Forge wheel：`abacus_forge-0.1.0-py3-none-any.whl`，SHA-256 `e2379f04974a63e46f5c25d9abf1aaaf6e444d81019df4904737628c28eb8e93`，复用[安装验收](2026-10-15-forge-cohp-installed-consumption.md)的候选；[身份核对](2026-10-15-forge-real-evidence/wheel-source-identity.json)确认全部 68 个 Python 文件逐字节等于当前生产源码。
- COHP：无 system-site 的 Python 3.13.13 venv，清除 `PYTHONPATH`/`ABACUS_FORGE_ROOT`，以安装包的 machine CLI 执行。
- NEB：ATST 源码 `45d8c78de8a605c127cd4c36742d0c9525a0a6b6` 构建的 2.2.8 wheel，SHA-256 `bf9ba9a9af15d89e9800693156e16dd1f1ee257e505460997bf4b3d63688a825`。与 Forge wheel 解包至独立 `pythonlib`，通过 `PYTHONPATH` 置于既有 `adam-abacus-min` Python 3.12 依赖环境之上；不改写共享环境。这项运行证明指定 wheel 的执行，不作为 fresh dependency closure 验收。
- 本地工作文件：`~/scratch/forge-real-evidence-20261015/`；SAI 根目录：`/org/galileo-group/galileouser02/forge-real-evidence-20261015/`。

## 完整 Si SCF 上的 COHP

输入来自 2026-10-13 SAI job `1760372` 的真实 LTSv3.10.1 GPU SCF，目录为 `/org/galileo-group/galileouser02/cohp-iao-9f6411c64-sai-20261013/cohp-iao-b3ffff102-current-0b5f`。本轮复用既有计算，没有重跑 SCF。原始说明由 Paimon 仓 `toolbox/ABACUS/docs/reports/2026-10-13-candidate-tool-sai-cohp-iao-real-scf-smoke.md` 维护。

输入共 126 个文件，含完整 36 k 点 H/S/WFC 与稀疏 S(R)，时间反演展开为 64 k 点。远端与下载后的逐文件 SHA-256 全部相同，见 [manifest](2026-10-15-forge-real-evidence/cohp-scf-sha256.json)。外层[回放脚本](2026-10-15-forge-real-evidence/cohp_replay.py)在五个独立 workspace 各执行一次 postprocess，检查输入未变、所有 v1 ArtifactRecord 的文件大小/哈希/相对路径、追加审计事件及科学状态。

| Si 1–2 轨道选择 | ICOHP / eV |
| --- | ---: |
| all / all | −3.0224776506888595 |
| s / s | −0.04897334039345078 |
| s / p | −0.6040196341992011 |
| p / s | −0.6045951883997248 |
| p / p | −1.764889487696483 |

原始 IAO 总 ICOHP 为 −3.0224776506888587 eV；全曲线最大绝对差 `4.773959005888173e-15`，四组 s/p ICOHP 求和残差 `0.0 eV`。每组生成 5 个声明产物和 1 个审计事件，collection 为 `complete`，execution 为 `not_run`，scientific 为 `unassessed`。原参考 meta/曲线、五组请求/响应/审计及[数值摘要](2026-10-15-forge-real-evidence/cohp-summary.json)已归档。

这证明完整真实输入上的 IAO 后处理迁移等价和轨道分解一致性，不等于 legacy `abacus-cohp-lcao` parity、多材料验收或 Paimon 完整平台链验收。分数占据等原始诊断继续保留。

复现时将完整 SCF 下载至本地，使用包含当前 Forge wheel 与 NumPy 的环境；`--output` 必须为不存在的新目录：

```bash
python docs/superpowers/evidence/2026-10-15-forge-real-evidence/cohp_replay.py \
  --python /absolute/path/to/installed-venv/bin/python \
  --scf /absolute/path/to/full-scf \
  --reference "$PWD/docs/superpowers/evidence/2026-10-15-forge-real-evidence/cohp-reference" \
  --output /absolute/path/to/new-replay-directory
```

## 真实 ATST NEB

使用 ATST `examples/01_neb_Li-Si` 的 65 原子、5 图像输入和 `config_parallel_smoke.yaml`：保留 100 Ry、2×2×2 k 点、`scf_thr=1e-6`、FIRE、普通 NEB 1 步 + CI-NEB 1 步及 `fmax=0.05 eV/Å`；串行消费 1 个 V100，1 MPI/1 OMP，显式 `endpoint_singlepoint=always` 重新计算端点。外层只将 pseudo/orbital 路径映射到独立运行目录、指定 GPU，并关闭图像并行；计算编排仍属于 ATST。

[配置](2026-10-15-forge-real-evidence/neb-workflow.yaml)、[提交脚本](2026-10-15-forge-real-evidence/neb.sbatch)和[验收脚本](2026-10-15-forge-real-evidence/neb_run.py)独立于 Forge core。执行从已有示例链开始，本次不覆盖 Forge `prepare`；后续显式传入实际 `neb.traj` 做 summary/postprocess。

首次 job `1804117` 在 2 秒内因 harness 将 `check_input=True` 与 `dry_run=False` 同时传入而被 request schema 拒绝，未启动 ABACUS。现行契约要求 check_input 只用于 dry-run；修正 harness 为 `False` 后，以新 workspace 提交 `1804129`。保留失败目录，不覆盖该次请求/响应。

job `1804129` 在 `4v100n15` 上实际运行 5 分 42 秒，Forge execute 返回 `completed/not_collected/unassessed`，ATST 生成 10 帧、每帧 65 原子的真实轨迹。但 harness 误将总图像数 `5` 传给表示中间图像数的 `n_max`，第一次 postprocess 为 `failed/partial/unassessed`，因此 Slurm **FAILED，exit 1:0**；不能将整个 batch 写成成功。

核对 ATST `--help` 与 `select_post_neb_chain` 后，将 `n_max` 改为 `3`。随后以 `neb_run.py --resume-postprocess` 显式复用同一 `neb.traj`，在登录节点只做 CPU 后处理，退出码 0；没有重算 ABACUS。新 operation 使用 `neb-summary-corrected.json` / `neb-ts-corrected`，保留原失败 summary、请求、响应及事件。最终 postprocess 为 `completed/complete/unassessed`，11 个声明产物完整，包括 trajectory、summary、CIF、latest trajectory/extxyz、重启链、PDF 和日志。审计总数为 3（成功 execute、失败 postprocess、成功 postprocess），各事件和产物哈希均已核对。

ATST manifest 记录 warmup 与 CI-NEB 各 `actual_steps=1`，**两者 converged 均为 false**。最终投影 NEB 力为 `0.48562988494204895 eV/Å`，高于 `0.05 eV/Å` 阈值。summary 中的 `0.6969303030000447 eV` 仅是未收敛末链的能差观测，不能作为收敛迁移势垒。10 帧能量/力均有限，相对初始链的最大位置变化为 `0.013274570912692954 Å`。

因此本轮关闭**有限步真实 NEB execute + 显式 postprocess 操作证据**；完整收敛路径、多案例/并行配置与科学有效性仍未证明。两个 harness 错误和 Slurm 失败均保留，不以恢复成功覆盖失败历史。Forge 生产代码没有修改。

实际运行记录见 [acceptance](2026-10-15-forge-real-evidence/neb/acceptance.json)、[独立核对](2026-10-15-forge-real-evidence/neb-independent-verification.json)、[Slurm 收据](2026-10-15-forge-real-evidence/neb-platform/sacct.txt)及 [engine identity](2026-10-15-forge-real-evidence/neb-platform/engine-identity.json)。ABACUS 为 `v3.10.1`，executable SHA-256 `c29ff3096b9edf455e76e36e7055ef3937c56194bc0235ae9df5e8cfb8c3c303`；ATST 实际使用其 vendored abacuslite。原始日志在归档中加 `.txt` 后缀，字节与 artifact 哈希不变，映射见 `neb-archive-map.json`。

已提交的原始脚本保存在 `neb-platform/`，与 `staged-inputs-sha256.json` / `candidate-sha256.txt` 绑定；本目录顶层脚本是包含上述修正的复现入口。另有一项环境记录限制：原 batch 在 `set -u` 下调用 Lmod `module list`，`modules.txt` 仅记录 `LD_PRELOAD: unbound variable`，不是有效模块清单。实际引擎身份由 executable 路径、版本和哈希确定；复现脚本已在该记录命令前后切换 nounset。此文档/日志采集修正未重新提交 GPU 计算。

## abacuslite 发布包调查

2026-10-15 显式查询 `https://pypi.org/simple`：`python -m pip index versions abacuslite --index-url https://pypi.org/simple` 返回 1，提示无匹配分发；`https://pypi.org/pypi/abacuslite/json` 返回 HTTP 404。[查询收据](2026-10-15-forge-real-evidence/abacuslite-query.json)与原始响应已归档。该结论限于此索引与日期。

本地 canonical checkout 虽声明 1.0.0，不能代替已发布包；继续保留 native 默认，不添加虚构 exact extra。published package / fresh-extra 四 capability parity 仍等待可安装发布包。ATST 内部 vendored parser 的使用也不关闭 Forge optional parser 的发布门禁。

## 离线验证

- `tests/test_architecture.py tests/test_machine_cli.py`：100 passed，6.73 秒。
- `tests/test_atst_neb.py tests/test_postprocess_services.py tests/test_postprocess_machine_cli.py tests/test_cohp_iao.py`：67 passed，8.36 秒。

原始输出见 [docs-machine-tests.txt](2026-10-15-forge-real-evidence/docs-machine-tests.txt) 与 [owning-tests.txt](2026-10-15-forge-real-evidence/owning-tests.txt)。本轮没有改动生产代码或测试契约，不将这 167 项描述为新一次全量测试。

## 独立复核与集成

同族独立 reviewer 两次复核 COHP 与最终 NEB 证据，确认五组 COHP 产物、输入 manifest、三次 NEB operation 的身份/大小/哈希和 84 项归档映射一致，并重算轨迹位移。审查指出报告曾误写 postprocess 生成 STRU，已按实际 artifact 集合更正为 CIF；最终无剩余阻断项。文档链接、JSON、验收脚本语法及维护文本的 `git diff --check` 通过。原始引擎输出、提交收据和 YAML 含生产方行尾空白；归档保留原字节以维持哈希，不纳入格式清理，完整 diff 的空白提示不作为科学或运行失败。

本轮按用户批准集成本地 main；不含推送、发布或 capability 晋级。保留隔离工作树和原始 scratch/SAI 数据供后续追溯。
