"""One bounded sensitivity case per invocation, all stages sequential."""
import argparse,runpy
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('kind',choices=['half-displacement','denser-mesh']);a=p.parse_args()
m=runpy.run_path(str(Path(__file__).with_name('run_real_bec.py')))
if a.kind=='half-displacement':
    case,mesh,ds='mesh4',4,(-.005,.005)
else:
    case,mesh,ds='mesh5',5,(0.,-.01,.01)
for d in ds:
    for g in (0,1,2,3): m['stage'](case,d,g,mesh)
