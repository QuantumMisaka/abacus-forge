# Forge Engine/Version Policy Stage 0 evidence

日期：2026-09-14

Forge candidate：`cb988adf13dd8199aced31db463121b571652943`

Canonical source checkout：`abacus-develop` `94576a80169de36e02e637edc2a0963fba9e1838`

Canonical package root：`abacus-develop/interfaces/ASE_interface`

## Canonical checkout parity

命令：

```bash
ABACUS_FORGE_CANONICAL_ABACUSLITE=/home/james/work/sidereus/workplace/abacus-develop/interfaces/ASE_interface \
conda run --no-capture-output -n abacus-env env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
python -m pytest -q --run-benchmark -m benchmark \
tests/benchmark/test_abacuslite_canonical_parity.py
```

输出为 `15 passed in 0.93s`，原始 stdout transcript SHA256 为
`2474a6233c25a55303cfdbee51446b3dd78e70c0a33fd0b4121caf79f39c5c00`。

这 15 项覆盖 `legacyio`/`latestio` 两个版本分支及 SCF、relax、cell-relax、MD
四个 capability，并覆盖完整日志、截断日志、非收敛日志、output-only（没有
INPUT/eig_occ/MD_dump）、歧义日志、越界软链接、同进程版本交替、并发 workspace、
只读领域文件和追加式审计。比较的事实是 total energy、Fermi、forces、stresses，
保持 Forge 的单位和符号约定；测试没有执行 ABACUS，也没有作科学接受判断。

## Local source-wheel smoke

为验证 canonical source 当前可构建且 Forge 能通过实际安装包导入，使用
`abacus-develop/interfaces/ASE_interface` 构建了本地 wheel
`abacuslite-1.0.0-py3-none-any.whl`（SHA256
`8dd81ccf5736f5299a013ea593c91578b98b0681cfbe92d170657961deec5130`），安装到
fresh venv `/tmp/forge-abacuslite-fresh` 后预加载已安装的 `legacyio`/`latestio`，再运行同一
15 项 fixture 集合，结果为 `15 passed in 0.41s`。该 smoke 证明本地构建包的导入和
Forge adapter 路由可用；direct oracle 与 adapter 在该进程共享同一个已安装 wheel，故不替代
上面的 checkout-to-adapter 独立 parity，也不替代发布仓库中的 exact-package 验收。

## 离线实现门禁

默认 Forge 回归命令：

```bash
conda run --no-capture-output -n abacus-env pytest -q
```

在修复 LocalRunner 绝对 `PATH` 预检失败语义并恢复候选分支的 release-gate/postprocess 回归后，结果为 `1401 passed, 31 skipped`
（156 warnings，均为已有 ASE 第三方弃用警告）。`tests/test_service_status.py` 的
generated `mpirun` preflight 回归单独为 `1 passed`。

实现包含：

- native 默认路径和 legacy `collect()` 保持不变；
- ServiceSet 的 keyword-only `parser_backend`/`output_version`，仅 collect 消费；
- CLI 的 collect-only 参数和请求错误优先级；
- 纯版本正规化及 `legacyio`/`latestio` 局部分发，不使用 global IO switch；
- abacuslite 缺包、版本冲突、缺失事实不 fallback 的 fail-closed 语义；
- PyATB 新旧 CSR 名称及 nspin 1/2/4 角色回归、`STEP OF RELAXATION : N` 解析和既有 final 候选规则。

## 未关闭的 Stage 1/D 门

当前 `pip index versions abacuslite` 返回 `No matching distribution found for abacuslite`，
因此本地 wheel 证据和 canonical checkout 证据都不能替代可安装发布包。默认 wheel 的 optional extra、fresh
environment 的真实 package import、native/abacuslite × LTS/develop 四 capability 双轨
发布矩阵，以及 app-tools 的 Paimon 工具矩阵/旧依赖清零/Agent Benchmark/生产 E2E，均
继续保持未验收状态。Forge 仍不宣称 Engine/Version Policy 发布完成。
