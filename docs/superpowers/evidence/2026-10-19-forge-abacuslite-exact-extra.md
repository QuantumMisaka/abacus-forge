# abacuslite 1.1.0 exact extra 与安装态四 capability parity

状态：已执行（本地）。2026-10-19 由项目主 Agent 依据工作区夜间协调计划（`docs/coordination/`，不入本仓）授权，仅本地修改与验证；未 push、未清理分支/worktree、未改 Paimon 配置。本文只支持其中列出的候选、环境与行为范围。

## 身份绑定

| 对象 | 身份 |
| --- | --- |
| abacuslite 发布版 | `1.1.0`（PyPI 当前唯一版本），tag `v1.1.0` = `94a26e4c7f31ed817eac36c871ff74a7b7abe418` |
| wheel | `abacuslite-1.1.0-py3-none-any.whl`，47,295 B，SHA-256 `c3e4504e9c9f5bceb69f70c79290e7843037ca72f625c5f66258e14d110f0ff3`，上传 2026-10-17T17:58:00Z（+08 为 10-18 01:58） |
| sdist | `abacuslite-1.1.0.tar.gz`，165,419 B，SHA-256 `79a85f09a37e68ca97ba35f0a620bc888ace092bfd0fdfc533320498d46956e3` |
| 发布物与源码 | wheel 内 8 个运行时 `.py` 与 tag `v1.1.0` 的 `src/abacuslite` 逐字节相同（8/8） |
| 元数据 | `License-Expression: LGPL-3.0-only`，含 `LICENSE`；`Requires-Python >=3.10`；依赖 `ase<4,>=3.28`、`numpy<3,>=1.26`、`seekpath<3,>=2.2` |
| Forge 候选 | 基线 `43f5d4a`，`src/` 到 `ce30899` 未变；wheel `abacus_forge-0.1.0-py3-none-any.whl`，277,141 B，SHA-256 `c06eb0abbd24b10658660d77efc1ef508a0d448283b1022134894b9209c83459` |

完整机器可读记账见 [provenance](2026-10-19-forge-abacuslite-1.1.0-package-provenance.json)。2026-09-14 的 local-oracle-only 记录保持冻结，不重写。

## 变更

- `pyproject.toml`：声明 `[project.optional-dependencies] abacuslite = ["abacuslite==1.1.0"]`；默认依赖集合不变。
- `tests/benchmark/test_abacuslite_canonical_parity.py`：oracle 改为“环境变量指定的包目录 → 已安装 `abacuslite` 包”，canonical 日志改由 `ABACUS_FORGE_CANONICAL_ABACUSLITE_FIXTURES` 提供（兼容历史 `abacuslite/io/testfiles`）；新增 `test_canonical_oracle_binds_the_declared_abacuslite_pin`，断言 oracle 版本等于 `pyproject.toml` 的 exact pin。ABACUS 已删除 vendored 插件，旧的 `interfaces/ASE_interface` oracle 路径不再可用。
- `tests/conftest.py`：新增 `ABACUS_FORGE_INSTALLED_PACKAGE_ONLY=1`，该模式下不把 `src/` 插入 `sys.path`，并在 `abacus_forge` 仍解析到本仓源码时直接失败，防止用源码 checkout 冒充已安装包。
- `tests/test_package_contract.py`：新增发布物 provenance 绑定断言（版本、tag、wheel/sdist 哈希、extra 与 pin 一致、默认依赖不含 abacuslite、候选 wheel 哈希、1.2.0 rebind 记账）；旧测试被替换，删除前已记录 mutation 证据（见下）。
- `docs/superpowers/README.md`、`ROADMAP.md`、`README.md`、`docs/reference.md`、`tests/README.md`：更新 extra 安装方式、oracle 运行方式和 Engine/Version Policy 状态。

## 验证

### 离线全量

```bash
python -m pip wheel --no-deps --no-build-isolation -w /tmp/fw .
# abacus_forge-0.1.0-py3-none-any.whl  sha256 c06eb0abbd24b10658660d77efc1ef508a0d448283b1022134894b9209c83459
ABACUS_FORGE_WHEEL=/tmp/fw/abacus_forge-0.1.0-py3-none-any.whl \
  python -m pytest -q -p no:cacheprovider
# 1479 passed, 33 skipped in 99.06s
```

### 新门禁的 mutation 证据

替换旧 provenance 测试前，对新增断言做了两处真实 mutation，均先失败、恢复后通过：

- registry wheel SHA-256 改为全零 → `test_published_abacuslite_release_provenance_binds_the_declared_extra` FAILED。
- `pyproject.toml` pin 从 `1.1.0` 改为 `1.1.1` → 同一测试 FAILED。
- 恢复后 → 1 passed。

### 安装态四 capability parity（fresh venv）

环境：全新 `python3.13 -m venv`，无 system-site，`--no-cache-dir` 从本地 wheel 安装 `abacus_forge-0.1.0-py3-none-any.whl[abacuslite]` 与 `pytest`。安装结果：`abacus-forge 0.1.0`、`abacuslite 1.1.0`、`ase 3.29.0`、`numpy 2.5.4`、`seekpath 2.2.2`、`pymatgen 2026.9.24`、`matplotlib 3.11.2`、`dpdata 1.1.0`；`pip check` 为 `No broken requirements found`；`abacus_forge` 与 `abacuslite` 均解析到 venv 的 site-packages。

canonical 日志取自 abacuslite `v1.1.0` tag（`git archive v1.1.0 tests/fixtures/io/testfiles`），未使用任何 Forge 源码路径：

```bash
env -u PYTHONPATH -u ABACUS_FORGE_ROOT MPLBACKEND=Agg \
  ABACUS_FORGE_INSTALLED_PACKAGE_ONLY=1 \
  ABACUS_FORGE_CANONICAL_ABACUSLITE_FIXTURES=/tmp/fx/tests/fixtures/io/testfiles \
  /tmp/fv/bin/python -m pytest -q -p no:cacheprovider --run-benchmark \
  tests/benchmark/test_abacuslite_canonical_parity.py
# 16 passed in 0.79s
```

覆盖 8 个 capability/版本单元（scf / relax / cell-relax / md × `legacyio`@v3.10.1 / `latestio`@v3.11.0-beta8+56），以及 oracle 版本绑定、截断/非收敛、output-only、同进程交替版本、并发隔离、只读域文件与 append-only 审计。

### 缺包 fail-closed（fresh venv，无 extra）

同一 wheel 在另一个 fresh venv 中不带 extra 安装，`abacuslite` 不存在；显式请求 `parser_backend=abacuslite`：

```
MISSING_PACKAGE_FAIL_CLOSED: abacuslite package is required for parser_backend=abacuslite
```

即未安装可选包时按既有 `precondition.missing` 失败，不回退 native。

## 证据边界

三类 parity 必须分开读：

1. **canonical checkout parity（历史）**：2026-09-14/09-15 以 `abacus-develop` 的 `interfaces/ASE_interface` checkout 为 oracle 的 15 项 benchmark；记录在 [版本政策设计复核](2026-09-13-forge-engine-version-policy-review.md)与 [Stage 0](2026-09-14-forge-engine-version-policy-stage0.md)。该路径已被上游删除 vendored 插件取代。
2. **安装态 package parity（本文）**：以已发布 `abacuslite 1.1.0` 同时作为实现与直接 oracle，验证 Forge 的字段投影；它证明“已发布 1.1.0 的 reader 结果与 Forge 投影一致”，不证明“发布包与某个 checkout 相同”。后者由上文 8/8 文件哈希给出（离线、可复算）。
3. **双轨真实发布证据（未做）**：`tests/real_smoke/test_abacuslite_dual_track.py` 需要 develop/LTS 两台真实引擎、8 格 matrix、executable SHA-256 与 input identity，属显式 `--run-real-smoke` 门禁，本次未运行。

本文不证明：科学可接受性、ABACUS 真实运行收敛、Paimon 侧消费与平台验收、其他材料或输出格式。

## 观察与风险

- **wheel 哈希随工具链变化**：Forge `src/` 自 `43f5d4a` 未变，但本次 wheel 为 `c06eb0ab…`，与 2026-10-15 的 `e2379f04…` 不同（构建环境/hatchling 版本不同）。任何消费者重新构建都必须重新记录自己的 wheel SHA-256，不能复用旧值。
- **一次负载下的测试超时**：并行做其他构建时，全量回归出现 2 个 `tests/test_cli_process.py` 子进程 30s 超时；单独重跑该文件 41 passed（58.66s），随后干净全量 1479 passed。判定为负载相关偶发，不作为产品失败，但发布候选验收应在无并发负载时重跑。
- **extra 名是跨仓接口**：`abacus-forge[abacuslite]` 已在 pyproject 落地；Paimon W3 的 lock/kit 需自行确认新增 `seekpath` 等依赖的影响，本批未改其配置。

## 1.2.0 rebind 记账（未执行）

目标 pin 为 `abacuslite==1.2.0`（PP/ORB env fallback 属新增功能，不是 1.1.x 补丁）。1.2.0 发布后在同一轮内完成：更新 `pyproject.toml` exact pin、本 provenance、oracle 版本断言与 README/reference 说明，重跑四 capability parity 与缺包门禁，并重新绑定发布物哈希。不重复推导中间版本，不把 1.2.0 的新功能回写成 1.1.x。
