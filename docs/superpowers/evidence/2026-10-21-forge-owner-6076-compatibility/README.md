# Paimon `6076ad0` → Forge `4106f33` 兼容性审计

日期：2026-10-21。范围：静态升级兼容性审计，不运行 50 例 Benchmark，也不修改
Paimon owner 的分支或冻结 kit。

## 当前身份

- Paimon owner：`app-tools-forge@17c45161a`
- Paimon 固定 Forge：`6076ad0c84fe24acad6ea3a2db9663aa58392b4a`
- owner 固定 wheel：`3647ccc2d69ddf4c82c290749b468e107202f079efbe256db211f617a2cba902`
- Forge 新候选：`4106f33505b552f1dee837c6f2e6bf24e514cf83`
- 新候选 wheel：`ae3705aa8d801a969f80ae7b3c418ec546e7fa66ba46a65094b80140cc393ad1`

## Runtime 差异

`6076ad0 → 4106f33` 的生产源码只改两个文件：

- `src/abacus_forge/discovery.py`
- `src/abacus_forge/pyatb_cohp.py`

`pyproject.toml`、CI workflow 和依赖声明无变化。行为差异限于：

1. `capabilities.contracts["pyatb-cohp"].result` 新增 pair convention/factor 说明；
   现有字段不删除、不改名。
2. 实验性 `pyatb-cohp/collect` 对 orbital-map、重复轨道、pair convention/factor
   增加严格校验。这会让 malformed/inconsistent legacy metadata fail-closed，
   不改变合法 PyATB 候选输出的数值。

## Owner 兼容结论

当前 tracked Paimon 产品与 benchmark runner 没有 `pyatb-cohp` 引用；Benchmark
使用的 Forge capability 不经过本次收紧的 collect 路径。因此：

- 当前 Benchmark 结果不因升级到 `4106f33` 自动失效；
- 仅为了当前 Benchmark 不需要全量重跑；
- 当前 Benchmark 也不需要立刻重绑 Forge；
- 若 Paimon 要消费 direct NAO COHP，建议重绑 `4106f33`，并按 owning entry
  验证 `pyatb-cohp/prepare → execute → collect`。

## 边界

本记录是静态兼容性审计，不替代 Paimon owner 决策、50 例重跑、平台验收或科学
验收。owner 后续状态变化时需重新审计。
