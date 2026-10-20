# Forge optional parser 升级至 abacuslite 1.2.2

2026-10-21 用户要求优先升级 abacuslite。本轮将 exact extra 从 1.2.0 更新为
1.2.2，接替[前一候选](2026-10-21-forge-integration-candidate-closeout.md)的暂留决定。
默认 parser 仍为 native，abacuslite 仍是可选依赖；Forge 公共接口和运行代码未修改。
执行入口为[既有版本计划](../plans/2026-09-13-forge-engine-version-policy.md)。

## 包与来源

- [PyPI 1.2.2](https://pypi.org/project/abacuslite/1.2.2/) 的 wheel 和 sdist 已实际下载并核验摘要；8 个运行文件与发布 tag `v1.2.2`（commit `f8c8b045fa3a76ad4c2fdd92c828fda5155f6f34`）逐字节相同。
- `latestio` / `legacyio` 中 Forge 调用的能量、力、应力 reader，含 latestio 导入的 legacy 能量函数，均与 1.2.0 实现相同。
- 新 Forge wheel 为 `abacus_forge-0.1.0-py3-none-any.whl`，SHA256 `516fcbda179964e652ba44dade698604c03b021b7c2080c7820fc0710c215441`。其 76 个 Python 模块与基线 `a68f32a` 及安装目录逐字节一致；打包元数据的实际差异是 optional pin。
- [provenance](2026-10-21-forge-abacuslite-1.2.2-package-provenance.json) 明确记录基线及元数据差异，不声称新包完全等于改动前的 Git 提交。旧 1.2.0 provenance 保留原样。

候选位于 `/home/james/scratch/forge-abacuslite-122-20261021/artifacts/`；独立环境为
同级 `venv/`（CPython 3.12，无 system-site）。安装方式：

```bash
python -m pip install '/home/james/scratch/forge-abacuslite-122-20261021/artifacts/abacus_forge-0.1.0-py3-none-any.whl[abacuslite]'
```

## 验证

- fresh venv 安装 `[dev,abacuslite]`，`pip check` 通过。
- 安装态 package/metadata/canonical parity：**32 passed**，包括实际 wheel 的 optional dependency 和 license 门禁；canonical fixture 来自 v1.2.2 tag，四类能力为 SCF、relax、cell-relax、MD。
- 全离线安装态回归：**1534 passed、33 skipped、176 warnings**，120.45 s，exit 0。相比上一轮 1532/35，本轮显式提供 wheel，两个包门禁也执行通过。
- 留存真实输出 8 格 × 4 种组合，共 32 份 collection 结果；新旧 native、新旧 optional、新版 native/optional 等 32 次比较均通过既有数值容差。覆盖能量、Fermi、力/应力及 MD 序列、结构与状态。LTS relax/cell-relax 仍为 partial，其他六格 complete；原始输入和回放副本前后 hash 不变。

[完整回归](2026-10-21-forge-abacuslite-1.2.2-rebind/installed-offline.log)、[实际验证命令](2026-10-21-forge-abacuslite-1.2.2-rebind/commands.json)、[安装收据](2026-10-21-forge-abacuslite-1.2.2-rebind/installed.json)、[package parity](2026-10-21-forge-abacuslite-1.2.2-rebind/package-parity.log)、[回放报告](2026-10-21-forge-abacuslite-1.2.2-rebind/replay/report.md)、[逐项比较](2026-10-21-forge-abacuslite-1.2.2-rebind/replay/comparisons.json)及同目录全部原始结果可核验。新旧环境依赖清单仅 Forge wheel 和 abacuslite 版本不同。

这次双轨回放复用 10-19 保存的 develop `v3.11.0-beta8` / LTS `v3.10.1` 输出。
它验证升级后的解析兼容性，不是重新运行 ABACUS；不会把旧引擎记录改标为
1.2.2 实算，也不扩大材料、自旋或科学收敛声明。

## 当前仍在途

1. **Paimon 消费新候选及完整 demo/Benchmark。** 本轮只读刷新到 `app-tools-forge@368d694e6`，owner 已补事实字段映射和 STRU 行内注释解析；配置仍绑定 Forge `20dc2eb6` / wheel `2fbc50ee…` 与 abacuslite 1.2.0。owner 需按实际需要换用新包，并统一 kit 产品 ZIP 与 harness，再完成包含 prepare 的实际入口、完整 50 例 Benchmark 和平台验收。没有发现已证实的 Forge 库级阻断。
2. **科学覆盖扩展。** direct NAO COHP 的更多材料/自旋、BEC 全张量与收敛等仍待具体需求推进；现有 MgO 证据仅覆盖一个 O_x 响应，typed capabilities 仍为 experimental。
3. **远程交付。** `main` `714fea2` 已推送并触发托管 CI 通过（run
   `39477565615`）；wheel/sdist artifact 已生成。PyPI 发布仍未执行。

完整 Contract System 与 property manifest 的 Draft 未获准实施，不列为正在施工或本轮完成条件。
Paimon owner 的工作树保持原状；其配置、kit 和 Benchmark 不在本轮改写范围。

## 收口

独立审查通过，无实质问题。最终源码包含当前 pin、测试与 provenance；从它构建的
wheel 与安装态验证候选相同，见[构建收据](2026-10-21-forge-abacuslite-1.2.2-rebind/final-build.json)。
193 个文档相对链接核对通过，staged diff 格式检查通过。按既有授权交付到本地 main，
开发 worktree 保留。远程推送与 CI 已接续完成；PyPI 发布和 Paimon 候选替换仍未执行。
