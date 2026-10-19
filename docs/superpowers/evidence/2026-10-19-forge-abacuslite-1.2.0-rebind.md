# abacuslite 1.2.0 rebind 与安装态四 capability parity

状态：已执行（本地）。2026-10-19 按上一轮 provenance 记录的单轮 rebind 约定完成；只推 feature 分支并开 PR，未直接改 main、未改 Paimon 配置、未发布。

## 身份绑定

| 对象 | 身份 |
| --- | --- |
| abacuslite 发布版 | `1.2.0`（PyPI），tag `v1.2.0` = `7e6761d2ff656f11f54abc613ac7bdad6ef6dec4`，<https://pypi.org/project/abacuslite/1.2.0/> |
| wheel | `abacuslite-1.2.0-py3-none-any.whl`，48,301 B，SHA-256 `3e5e245c0a03e8182c2c726d7ccad1c800c20250641abd4b81a8e22e892bc4a0`，上传 2026-10-19T03:41:48Z（+08 11:41） |
| sdist | `abacuslite-1.2.0.tar.gz`，188,270 B，SHA-256 `61a238197879136ee59d99651242921850834a3954b8a8b475a34b109a077fe0` |
| 发布物与源码 | wheel 内 8 个运行时 `.py` 与 tag `v1.2.0` 的 `src/abacuslite` 逐字节相同（8/8） |
| 元数据 | `Requires-Python >=3.10`；依赖 `ase<4,>=3.28`、`numpy<3,>=1.26`、`seekpath<3,>=2.2`（与 1.1.0 相同） |
| Forge 候选 | 基线 `f97b798`，`src/` 未变；wheel `abacus_forge-0.1.0-py3-none-any.whl`，SHA-256 `2fbc50eef8a75368832c94fbaa3a3635d89728367897cc3b427dfd98d62c821e` |

机器可读记账见 [1.2.0 provenance](2026-10-19-forge-abacuslite-1.2.0-package-provenance.json)。[1.1.0 provenance](2026-10-19-forge-abacuslite-1.1.0-package-provenance.json) 与 [2026-09-14 local-oracle 记录](2026-09-14-forge-stage1-package-provenance.json) 保持冻结，不重写。

## 变更

- `pyproject.toml`：exact extra 从 `abacuslite==1.1.0` 改为 `abacuslite==1.2.0`（`change_kind: changed`）；默认依赖列表未变。
- 新增 1.2.0 provenance，并把 `history.supersedes` 指向 1.1.0 记录。
- `tests/test_package_contract.py`：活动记录切到 1.2.0（版本、tag、PyPI URL、wheel/sdist 哈希）；同时冻结断言 1.1.0 记录与 local-oracle 记录不变；`rebind` 断言改为 `status: applied`、`from 1.1.0 → to 1.2.0`。
- `README.md`、`docs/reference.md`、`tests/README.md`、`ROADMAP.md`、`docs/superpowers/README.md`：pin 与状态更新到 1.2.0。

## 验证

- RED：改 pin 后、更新 provenance 前，`test_published_abacuslite_release_provenance_binds_the_declared_extra` 失败（声明的 `abacuslite==1.2.0` 与仍为 1.1.0 的 provenance 不一致）。
- GREEN：`tests/test_package_contract.py` + `tests/test_package_metadata_drift.py` → 14 passed, 2 skipped。
- 离线全量（含 `ABACUS_FORGE_WHEEL`）：**1490 passed, 33 skipped**，95.93s。
- 安装态四 capability parity（fresh `python3.13` venv、无 system-site、`--no-cache-dir` 从本地 wheel 安装 `[abacuslite]`）：`abacus-forge 0.1.0`、`abacuslite 1.2.0`、`ase 3.29.0`、`numpy 2.5.4`、`seekpath 2.2.2`、`pymatgen 2026.9.24`；`pip check` → `No broken requirements found`；`abacus_forge`/`abacuslite` 均解析到 venv site-packages。canonical 日志取自 tag `v1.2.0`（`git archive v1.2.0 tests/fixtures/io/testfiles`），`--run-benchmark` → **16 passed**（scf/relax/cell-relax/md × legacyio@v3.10.1 / latestio@v3.11.0-beta8+56，外加 oracle 版本绑定、截断/非收敛、output-only、同进程交替版本、并发隔离、只读域文件）。
- 缺包 fail-closed（同一 venv 卸载 abacuslite 后）：`abacuslite package is required for parser_backend=abacuslite`，不回退 native。

## 证据边界

1. **canonical checkout parity（历史，未重跑）**：2026-09-14/15 以 `abacus-develop` checkout 为 oracle 的 15 项 benchmark；该路径已被上游删除 vendored 插件取代。
2. **安装态 package parity（本文）**：以已发布 `abacuslite 1.2.0` 同时作为实现与直接 oracle，验证 Forge 字段投影；它不证明“发布包与某个 checkout 相同”，后者由 8/8 文件哈希单独给出。
3. **双轨真实发布证据（未做）**：`tests/real_smoke/test_abacuslite_dual_track.py` 需 develop/LTS 真实引擎、8 格 matrix 与 executable SHA-256，属显式 `--run-real-smoke` 门禁。

1.2.0 的 PP/ORB env fallback 属 abacuslite 新增功能；本轮 parity 覆盖的是 collect 所需的 reader 面，不把新功能当作已验证的 Forge 能力。不证明科学可接受性、真实 ABACUS 收敛或 Paimon 侧消费。

## 风险与提示

- wheel SHA-256 随 pin 与构建工具链变化：本次 `2fbc50ee…`，1.1.0 期为 `c06eb0ab…`。消费者（含 Paimon kit）重建后必须重新记录自己的 SHA。
- `abacuslite` 1.2.0 仍会新增 `seekpath` 依赖；Paimon W3 的 lock/kit 影响由其 owner 确认，本批未改其配置。
- 下一 pin 未定；abacuslite 再发版时另起一轮 rebind，不复用本文哈希。
