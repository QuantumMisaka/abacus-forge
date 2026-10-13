# 仓库示例输入

`NiO_inputs/` 保存一份 ABACUS NiO 输入样例。三个文件各有自己的来源和用途：

| 文件 | 内容与边界 |
| --- | --- |
| [`INPUT`](NiO_inputs/INPUT) | 旧的单次 ABACUS 输入样例，配置为 `cell-relax`、`nspin=2`、`device=gpu`、PBE、LCAO、`ecutwfc=100`、`scf_thr=1e-7`、`relax_nmax=200`、`force_thr_ev=0.01`、`stress_thr=0.5` 等。它的 `pseudo_dir`、`orbital_dir` 是原使用者机器上的绝对路径，不能直接在别的机器使用。 |
| [`STRU`](NiO_inputs/STRU) | NiO 起始结构，含两枚 Ni 的反平行初始磁矩以及 PP/数值轨道的文件名引用。它可独立作为 Forge `prepare --structure` 的结构输入；准备过程会生成新的 `INPUT` 和 `STRU`，不会自动复制旁边的 `INPUT`。 |
| [`gpu_abacus.sbatch`](NiO_inputs/gpu_abacus.sbatch) | SAI 站点专用的 Slurm 外层脚本，包含 `4V100` partition、站点 QOS、`/opt/sai_config` MPS 映射脚本和特定 ABACUS module。它不是可直接移植的 Forge 命令，也不属于 Forge 的调度功能。 |

该目录不含 PP/ORB 资源文件或 ABACUS executable。原始文件保持原样。`tests/test_structure.py` 直接读取 `NiO_inputs/STRU`，验证 Forge 可解析其中的 Ni/O 原子标签；该测试不验证 `INPUT`、GPU/Slurm 配置、赝势或轨道文件，也不执行 ABACUS。

## 本地 prepare 与 execute dry-run

先按[根 README 的安装说明](../README.md#install)安装 Forge 及其依赖，再从仓库根目录运行以下命令。它在系统临时目录创建全新的 workspace，使用仓内结构生成输入，并用 typed `operation execute` 的 `dry_run: true` 请求检查执行请求边界：

```bash
repo_root=$(git rev-parse --show-toplevel)
scratch=$(mktemp -d "${TMPDIR:-/tmp}/abacus-forge-nio.XXXXXX")
cd "$scratch"

PYTHONPATH="$repo_root/src" python -m abacus_forge.cli prepare NiO \
  --task cell-relax \
  --structure "$repo_root/examples/NiO_inputs/STRU" \
  --structure-format stru \
  --parameter device=gpu \
  --parameter nspin=2 \
  --parameter basis_type=lcao \
  --parameter dft_functional=pbe \
  --parameter ecutwfc=100 \
  --parameter scf_thr=1e-7 \
  --parameter relax_nmax=200 \
  --parameter relax_method=cg \
  --parameter force_thr_ev=0.01 \
  --parameter stress_thr=0.5 \
  --parameter kspacing=0.14 \
  --parameter pseudo_dir=/path/to/compatible-PP \
  --parameter orbital_dir=/path/to/compatible-ORB \
  --json

cat > request.json <<'JSON'
{
  "schema_version": "forge.request/v1",
  "capability": "cell-relax",
  "operation": "execute",
  "operation_id": "123e4567-e89b-42d3-a456-426614174901",
  "workspace_rel": "NiO",
  "dry_run": true
}
JSON

PYTHONPATH="$repo_root/src" python -m abacus_forge.cli operation execute --request request.json
```

`/path/to/compatible-PP` 和 `/path/to/compatible-ORB` 是待替换的路径占位符；上面的 dry-run 不检查它们是否存在。此处显式重述了示例 `INPUT` 中与 cell-relax、LCAO 和计算参数有关的部分，Forge 不会从 `NiO_inputs/INPUT` 读取这些设置。`prepare` 只保留 `STRU` 引用的 PP/ORB 文件名；只有提供匹配的外部文件、实际可用路径及 ABACUS executable 后，workspace 才适合真实运行。

当前顶层 legacy `execute` 命令没有 `--dry-run` 选项。上例使用 machine operation 请求字段 `dry_run: true`；预期结果是 `execution=skipped`，不会启动 ABACUS。它只验证本地结构解析、输入准备及请求/结果路径，不证明 PP/ORB 可用、ABACUS 可运行、GPU/Slurm 配置可用、计算收敛或科学结果可接受。当前 discovery 中 `cell-relax` capability 的 maturity 为 `experimental`，示例不会改变该状态。

真实 ABACUS 验证必须另行准备与本机 ABACUS 版本兼容的 PP/ORB、配置可执行文件和匹配的运行环境；它不属于以上本地 dry-run。不要把 SAI `gpu_abacus.sbatch` 当作通用提交脚本。
