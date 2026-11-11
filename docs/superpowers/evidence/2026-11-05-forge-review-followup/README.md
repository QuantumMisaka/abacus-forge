# Forge 2026-11-05 复审接续

本轮只完成 Forge 的本地开发与安装态验收，接续 [SCF 计划 Task 11](../../plans/2026-10-29-forge-scf-consumer-chain.md)。不改变收缩后的架构边界。

## 源码与环境

- repo：`git@github.com:QuantumMisaka/abacus-forge`。
- checkout：`/home/james/work/sidereus/workplace/abacus-forge`，branch `main`，package `0.1.0`。
- 先 fast-forward 到远端 `f6957ba26cafdb62c039473dd20ded3c0e824598`，再以 `2d3344c` 合入已有并发回归分支 `f18c8c9`；该合并只增加测试与证据。
- 修复／构建提交：`2dfcae89f73a5e128f7f12dae585d99607c93597`。随后文档提交不改变运行代码。
- 新环境：`/home/james/scratch/forge-followup-20261105/venv`，Python 3.12.13，`include-system-site-packages = false`，安装当前 wheel 的 `[dev,abacuslite,phonon]`。
- RED/GREEN 使用既有 `abacus-env`（pytest 9.0.3）；正式全离线与安装态验收使用新环境及项目声明的 pytest `<9`。日常 editable 导入仍指向 canonical checkout，随 main 同步获得新代码。

## 修复与审查

- `read_input_tokens` 仅将参数名转小写；值和 whitespace-token 注释语义保留。新增 parser 回归及四个 uppercase/mixed-case runtime-K service 反例。
- `_string_sequence` 恢复 scalar str/bytes 拒绝；constructor/from_dict 覆盖原来被拆成字符数组的输入及空标量。deque/generator 兼容与 launcher 专用数组校验保持。
- 同家族独立 reviewer 核对 `2dfcae8` 完整六文件 diff 与原始 RED/GREEN 输出，结论：两个 P2 闭合，无阻断项。
- 独立文档 reviewer 核对本轮文档 diff、日志、候选／发布边界与新旧 venv 配置，结论：无阻断项；文档链接检查 2 passed。入仓日志只清理行尾空格，原始输出仍保留在上述 scratch 目录。

## 验证

| 检查 | 结果 | 原始结果 |
| --- | --- | --- |
| 新增反例，修复前 | 15 failed / 13 passed / 542 deselected | [RED](red.txt) |
| contracts/workspace/result/units/service/input/CLI | 729 passed / 5 warnings | [GREEN](green.txt) |
| 干净环境默认全离线 | 1676 passed / 33 skipped / 176 warnings | [full](full.txt) |
| wheel installed-only 回归 | 595 passed | [installed](installed-tests.txt) |
| CLI、API、pip check、消费者 stub 与源码绑定 | 通过 | [verification.json](verification.json) |

新环境使用 pytest 8.4.2；完整安装依赖见 [requirements.txt](requirements.txt)。本轮未启用 real_smoke/benchmark；全量运行的 176 条 warning 来自 ASE 对 NumPy 2.5 数组 shape 赋值的弃用提示，未添加过滤。安装态验证确认非 editable，包来自新 venv 的 site-packages。

在修复提交 `2dfcae8` 的 checkout 根目录复跑，`python` 使用 Python 3.12，制品写入独立目录：

```bash
# 当前修复提交的构建与安装
CHECK_ROOT=/home/james/scratch/forge-followup-20261105-replay
python -m build --outdir "$CHECK_ROOT/dist"
python -m venv "$CHECK_ROOT/venv"
"$CHECK_ROOT/venv/bin/python" -m pip install "$CHECK_ROOT/dist/abacus_forge-0.1.0-py3-none-any.whl[dev,abacuslite,phonon]"
"$CHECK_ROOT/venv/bin/python" -m pip check

# 源码全离线及已安装包回归
ABACUS_FORGE_WHEEL="$CHECK_ROOT/dist/abacus_forge-0.1.0-py3-none-any.whl" \
  "$CHECK_ROOT/venv/bin/python" -m pytest -q -p no:cacheprovider
PYTHONPATH='' ABACUS_FORGE_INSTALLED_PACKAGE_ONLY=1 \
  ABACUS_FORGE_WHEEL="$CHECK_ROOT/dist/abacus_forge-0.1.0-py3-none-any.whl" \
  "$CHECK_ROOT/venv/bin/python" -m pytest -q -p no:cacheprovider \
  tests/test_input_io.py tests/test_contracts.py tests/test_service_status.py \
  tests/test_package_contract.py tests/test_package_metadata_drift.py \
  tests/test_diagnostics.py tests/test_getting_started.py

"$CHECK_ROOT/venv/bin/abacus-forge" --version
"$CHECK_ROOT/venv/bin/abacus-forge" doctor --json
"$CHECK_ROOT/venv/bin/abacus-forge" capabilities
"$CHECK_ROOT/venv/bin/abacus-forge" schema scf execute
python scripts/release_validate.py verify-distributions --dist-dir "$CHECK_ROOT/dist"
```

原始构建使用 `abacus-env/bin/python -m build`，venv 由同一 Python 3.12.13 创建；两个包的版本与元数据校验通过。wheel 中 77 个包文件逐一比对 Git 修复提交，sdist 中的已跟踪文件也全部匹配。

| 本地制品 | SHA-256 |
| --- | --- |
| `abacus_forge-0.1.0-py3-none-any.whl` | `dade7acf408bc61e945297caa8349ff94a660c9384ac69e1c40aa5899a3809ad` |
| `abacus_forge-0.1.0.tar.gz` | `9daca95c9b32c01dc15cffc2eb2f46a44455f2fec04edaa8b4921a6dfccfa74f` |

制品位于 `/home/james/scratch/forge-followup-20261105/dist/`；摘要与环境记录已入仓，二进制未加入 Git。

## 默认消费者检查

消费脚本来源为 `git@codeup-misaka.com:sidereus-ai/galileo-science-suite/science-suite-alpha/app-tools`，checkout `app-tools-forge-latest-main-sync`，branch `integration/paimon-v3-forge-replacement-20261030`，commit `586492ad3f453d776d824b91cb5a3196b555ea7c`；路径 `toolbox/ABACUS/scripts/verify_forge_scf_installed_consumer.py`，backend `forge`，toolbox `1.2.85`（`config/configure.json`）。本轮只读取现有脚本，没有修改 Paimon；不生成或验收部署 kit，运行依赖为上面的新 venv 清单。

```bash
"$CHECK_ROOT/venv/bin/python" -I \
  /home/james/work/sidereus/workplace/app-tools-forge-latest-main-sync/toolbox/ABACUS/scripts/verify_forge_scf_installed_consumer.py
```

结果为 exit 0：真实 default request/service factories，成功路径 execute→collect、resolved launch 可读、allocation observation 为 unknown；失败路径保留 envelope 且不 collect。仅引擎使用 executable stub。该单脚本检查不等于 Paimon full suite，也不等于最新 v2 基线的完整迁移验收。

## 发布边界

2026-11-05 只读查询 GitHub：`v0.1.0` 指向 `d5585f5d1d9dbcbca57ca9efea11280eb1b0adb8`，`publish.yml` 运行数为 0。旧 tag 与 CI 不覆盖本轮源码。新 wheel 是本地消费验证制品，远端 CI 尚未运行；不直接作为正式发布上传来源。后续依 [发行手册](../../../releasing.md) 取得同提交 CI 与制品，并由 owner 处理既有 tag／版本和 PyPI 上传。

本轮没有真实 ABACUS、SAI/GPU 或 Benchmark 运行。SCF stub 消费仅用于包与调用边界验证；Paimon 完整替代仍由其 owner 计划验收。
