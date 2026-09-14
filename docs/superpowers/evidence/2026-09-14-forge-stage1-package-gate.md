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
