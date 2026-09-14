# Forge Stage 1 package gate

日期：2026-09-14

本记录只覆盖 SPEC 的 exact installable `abacuslite` package gate。它不把
canonical source checkout 或本地构建 wheel 写成公开发布版本。

## 发布可用性检查

在 `abacus-env` 中执行：

```bash
conda run --no-capture-output -n abacus-env \
  python -m pip index versions abacuslite
```

结果为：

```text
ERROR: No matching distribution found for abacuslite
```

因此当前没有可以写入 Forge optional dependency 的公开 exact version。
`pyproject.toml` 继续不声明 `abacuslite` extra，也不写 git 或本地路径依赖。

canonical checkout 的事实仍绑定到：

```text
repository: abacus-develop/interfaces/ASE_interface
commit:     94576a80169de36e02e637edc2a0963fba9e1838
version:    abacuslite 1.0.0
```

该 checkout 构建出的本地 source wheel 为
`abacuslite-1.0.0-py3-none-any.whl`，SHA-256 为
`8dd81ccf5736f5299a013ea593c91578b98b0681cfbe92d170657961deec5130`。
它仅用于本地 smoke 和 adapter 验证，不能替代发布仓库中的 installable exact
package。Forge 候选 wheel 的 SHA-256 为
`809cec1e83cc021ce12b250ee4caae0b265a4e9c5101987a25fb71dc267b9906`，对应
Forge revision `edda0618f68863da5a516a06269e2ca489338d55`。两者的 canonical
commit、构建命令、文件名和 SHA-256 已写入可执行 provenance record
[`2026-09-14-forge-stage1-package-provenance.json`](./2026-09-14-forge-stage1-package-provenance.json)，
测试会拒绝缺字段、命名/version 不一致或非 64 位 SHA。相同 wheel 文件名的另一次
构建必须作为新的 artifact 记录其自身 SHA 和 source commit，不能沿用本记录。

## 可执行 package-contract 门禁

源码元数据门禁：

```bash
conda run --no-capture-output -n abacus-env \
  pytest -q tests/test_package_contract.py
```

结果为 `2 passed, 1 skipped`。没有声明 extra 时，skip 是有意的发布候选门；
测试仍验证默认 dependencies 不包含 `abacuslite`。

对具体 wheel 的生成元数据检查：

```bash
ABACUS_FORGE_WHEEL=/tmp/forge-stage1-wheel/abacus_forge-0.1.0-py3-none-any.whl \
conda run --no-capture-output -n abacus-env \
  pytest -q tests/test_package_contract.py
```

结果为 `2 passed`。本次候选 wheel SHA-256 为
`809cec1e83cc021ce12b250ee4caae0b265a4e9c5101987a25fb71dc267b9906`。该
opt-in 检查直接读取候选 wheel 的 `dist-info/METADATA`：
默认依赖不得包含 `abacuslite`；若未来声明 optional dependency，必须恰好是
`abacuslite==<实际发布版本>` 并带 extra marker。它不会允许 source
`pyproject.toml` 与最终 wheel 元数据出现边界漂移。

## 未关闭门

Stage 1 仍未完成。必须等 canonical 项目提供可从包索引安装的实际版本后，才可：

1. 将 `pyproject.toml` 的 extra 写成该实际版本的 exact pin；
2. 在无预装 parser 的 fresh environment 中安装 Forge[extra] 及其依赖；
3. 运行 SCF、relax、cell-relax、MD 四 capability 的 native/abacuslite 双轨
   parity，并绑定 Forge、ABACUS executable 和 parser package 的版本/hash。

在这些证据产生前，Stage 0 checkout parity 和本地 source-wheel smoke 不得升级为
Stage 1 发布结论。


## 源码与构建产物一致性补强（2026-09-14）

候选 wheel 门禁现在对比当前源码与生成元数据的项目 Name/Version、完整
`Provides-Extra` 集合，以及 `abacuslite` 的存在性、exact pin 和所属 extra。
源码未声明 parser extra 时，wheel 也必须不声明该 parser 依赖。默认依赖中的
parser 和非单一 extra marker 均被拒绝。这不证明包索引有可安装的发布版本。

新增合成 wheel 回归先在旧实现观察到 `5 failed, 1 passed`：新增/缺失 parser、
pin 漂移、extra 名称漂移、Version 漂移均未被旧实现拒绝；默认依赖污染原已拒绝。
修复并加入一致声明/无 parser 声明正例后，三个 owning suites 为
`12 passed, 1 skipped`；给定真实候选 wheel 后为 `13 passed`：

```bash
conda run --no-capture-output -n abacus-env python -m pip wheel --no-deps . \
  --wheel-dir /home/james/scratch/forge-package-drift-wheel
ABACUS_FORGE_WHEEL=/home/james/scratch/forge-package-drift-wheel/abacus_forge-0.1.0-py3-none-any.whl \
conda run --no-capture-output -n abacus-env pytest -q \
  tests/test_package_contract.py tests/test_package_metadata_drift.py \
  tests/test_abacuslite_release_gate.py
```

此 wheel 从 Forge `3371971cf35e7ec091265331fce567666f2c9694` 加本次仅测试/文档
增量的工作树构建，SHA-256 为
`6717a403bc6f51602f0a6757edf936f17b3135e66e3cda1619925605fc46b08a`。
首次关闭 build isolation 的构建因环境缺少 hatchling 失败；正常隔离构建成功。
历史 provenance record 保持原 artifact 绑定；本次未安装或发布 `abacuslite`。
exact published package、fresh-extra install 和发布包四 capability parity 继续开放。

独立审查补修：Core Metadata header 名称不区分大小写；旧门禁按大小写敏感行前缀
读取 Name/Requires-Dist，会漏掉小写的默认 parser 依赖。新增小写及混合大小写
污染负例在修复前 `2 failed`；统一使用 email Parser 的 `get_all` 读取 header 后，
加入混合大小写的合法 optional 声明正例，真实 wheel owning suites 为 `16 passed`。
重新从 `c516d12` 加本次测试修复构建到
`/home/james/scratch/forge-package-header-wheel/abacus_forge-0.1.0-py3-none-any.whl`，
SHA-256 仍为 `6717a403bc6f51602f0a6757edf936f17b3135e66e3cda1619925605fc46b08a`；
测试修改未改变 wheel 包内容。历史 provenance 与外部 Stage 1 门状态不变。

后续 Minor 修复：读取 Requires-Dist 后先展开合法 continuation whitespace，再执行
精确依赖和 marker 检查。折行 optional parser 正例先出现 `1 failed, 1 passed`，
修复后同一实际 wheel 的 owning suites 为 `17 passed`；未改变 wheel 内容或哈希，
未改变外部 published package/fresh-extra 门。
