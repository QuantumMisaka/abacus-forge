# Local validation commands

Each engine-driving shell sourced:
`source /home/james/work/sidereus/workplace/abacus-develop/toolchain/install/setup`

Installed Python:
`/home/james/scratch/forge-release-validation-20261021/venv/bin/python`

All scripts executed using this Python with `-I` and `PYTHONDONTWRITEBYTECODE=1`.
Initial probes: `run_real_bec.py --gdir 0`, then `run_real_bec.py --gdir 1`.
The SCF engine exited 0; first script validation asserted the wrong normal-end
and convergence marker strings. They were corrected from the retained log;
the original successful SCF was independently checked and marked successful.
No engine rerun or source-log rewrite was used to address the assertion.

Baseline: `run_matrix.py > matrix.log 2>&1`, exit 0.
Sensitivity (each internally sequential; these two independent cases concurrent):
`run_sensitivity.py half-displacement > half-displacement.log 2>&1`
`run_sensitivity.py denser-mesh > denser-mesh.log 2>&1`

Every ABACUS invocation uses Forge prepare/execute plus LocalRunner, one rank,
one OMP/OpenBLAS thread and a 300-second timeout. Collector and BEC are separate
installed CLI `python -I -m abacus_forge.cli operation ... --stdin` calls; exact
request/response and analysis argv/cwd/env receipts are retained in each folder.

Both sensitivity driver invocations completed with exit 0.
Final analysis invocations (all exit 0):
`analyze_real_bec.py --case mesh4 --delta 0.01 --output-dir /home/james/scratch/forge-real-bec-20261021/analysis-mesh4-002`
`analyze_real_bec.py --case mesh4 --delta 0.005 --output-dir /home/james/scratch/forge-real-bec-20261021/analysis-mesh4-half`
`analyze_real_bec.py --case mesh5 --delta 0.01 --output-dir /home/james/scratch/forge-real-bec-20261021/analysis-mesh5-001`
`summarize_validation.py` completed with exit 0 and audited all 32 runs, 24 collections and six BEC calls.
