#!/bin/bash
#SBATCH --job-name=forge-real-neb
#SBATCH --account=galileo-group
#SBATCH --partition=4V100
#SBATCH --qos=rush-1o2gpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus-per-node=1
#SBATCH --time=00:40:00
set -eo pipefail
source /opt/modules/lmod/9.2.4/init/bash
module use /opt/modules/modulefiles/devtools /opt/modules/modulefiles/apps
module load abacus/LTSv3.10.1-sm70-auto
source /opt/sai_config/mps_mapping.d/${SLURM_JOB_PARTITION}.bash
set -u
task_root=/org/galileo-group/galileouser02/forge-real-evidence-20261015
export PYTHONPATH="$task_root/pythonlib"
export PATH="$task_root/bin:$PATH"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLBACKEND=Agg
cd "$task_root/neb"
set +u
module list > modules.txt 2>&1
set -u
command -v abacus > executable.txt
abacus --version > abacus-version.txt 2>&1
nvidia-smi > gpu.txt
/org/galileo-group/galileouser02/adam-opencode-runs/conda-envs/adam-abacus-min/bin/python -u "$task_root/neb_run.py"
