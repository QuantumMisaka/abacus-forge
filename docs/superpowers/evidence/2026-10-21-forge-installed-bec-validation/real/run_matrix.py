"""Sequential, bounded scientific validation orchestration outside Forge core."""
import runpy
from pathlib import Path
m=runpy.run_path(str(Path(__file__).with_name('run_real_bec.py')))
m['assets']()
for d in (0.,-.01,.01):
    for g in (0,1,2,3): m['stage']('mesh4',d,g,4)
