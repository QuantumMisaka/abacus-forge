#!/bin/bash
#SBATCH --job-name=v12_elas_hist
#SBATCH --partition=8V100V0
#SBATCH --qos=improper-gpu
#SBATCH --account=pku-jianghong
#SBATCH --ntasks=1
#SBATCH --gres=gpu:1
#SBATCH --time=02:00:00
set -o pipefail
R=/org/pku-jianghong/liuzhaoqing/paimon-bench-20261020
RR=$R/runs/v12-equivalent-elastic-Al-FCC-20261022
PY=$RR/venv-historical/bin/python
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:-}"
export LD_PRELOAD="${LD_PRELOAD:-}"
set +u
source /opt/sai_config/mps_mapping.d/${SLURM_JOB_PARTITION}.bash 2>/dev/null || true
source /opt/modules/lmod/9.2.4/init/bash
module use /opt/modules/modulefiles/devtools /opt/modules/modulefiles/apps
module load abacus/LTSv3.10.1-sm70-auto
export ABACUS_PP_ORB_ROOT=$R/pporb/pporb
export ABACUSAGENT_MODEL=test
export ABACUSAGENT_SUBMIT_TYPE=local
export ABACUS_COMMAND="OMP_NUM_THREADS=4 abacus"
export PYTHONPATH=$RR/code:$RR/code-agent/src
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
cd "$RR"
"$PY" - <<"PY" 2>&1 | tee "$RR/logs/historical-scf-replay.log"
import json, pathlib
from abacusagent.modules.elastic import abacus_cal_elastic
source=pathlib.Path("/org/pku-jianghong/liuzhaoqing/paimon-bench-20261020/runs/v12-equivalent-elastic-Al-FCC-20261022/input/historical-source/000000")
out=abacus_cal_elastic(abacus_inputs_dir=source, norm_strain=0.01, shear_strain=0.01)
pathlib.Path("historical-scf-result.json").write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps(out,indent=2))
if "message" in out:
    raise SystemExit(1)
PY
status=$?
echo replay_exit=$status | tee -a "$RR/logs/historical-scf-replay.log"
sacct -j "${SLURM_JOB_ID:-0}" --format=JobID,State,ExitCode,Elapsed -n >> "$RR/logs/historical-scf-replay.log" 2>&1 || true
exit $status
