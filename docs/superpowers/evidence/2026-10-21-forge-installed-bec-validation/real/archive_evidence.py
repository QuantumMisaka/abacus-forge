"""Copy bounded validation evidence, excluding venv and binary restart files."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DEST=Path('/home/james/work/sidereus/workplace/abacus-forge/.worktrees/forge-integration-reference-review/docs/superpowers/evidence/2026-10-21-forge-installed-bec-validation')
INSTALL=Path('/home/james/scratch/forge-release-validation-20261021')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def cp(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);assert sha(src)==sha(dst)
# Complete receipts for the initial matrix, loaded before receipt instrumentation.
for p in ROOT.glob('mesh*/d*/g*/charge-handoff.json'):
    assert (p.parent/'success.json').exists(),f'incomplete stage: {p.parent}'
    d=json.loads(p.read_text())
    if 'destination_sha256' in d:d['destination_before_execute_sha256']=d.pop('destination_sha256')
    d['timing']='copied before engine launch'
    d['destination_after_execute_sha256']=sha(ROOT/d['destination'])
    d['source_after_execute_sha256']=sha(ROOT/d['source'])
    assert d['source_after_execute_sha256']==d['source_sha256']==d['destination_before_execute_sha256']
    p.write_text(json.dumps(d,indent=2)+'\n')
for p in INSTALL.iterdir():
    if p.is_file():cp(p,DEST/'installed'/p.name)
for p in ROOT.iterdir():
    if p.is_file():cp(p,DEST/'real'/p.name)
for p in (ROOT/'pp').glob('*'):cp(p,DEST/'real'/'pp'/p.name)
for stage in ROOT.glob('mesh*/d*/*'):
    if not stage.is_dir():continue
    assert (stage/'success.json').exists(),f'incomplete stage: {stage}'
    for p in stage.rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(stage)
        if p.suffix=='.json' or p.suffix=='.log' or p.name in ('INPUT','STRU','KPT','INPUT.info','KPT.info','collect-stderr.txt'):
            cp(p,DEST/'real'/stage.relative_to(ROOT)/rel)
for name in ('analysis-mesh4-002','analysis-mesh4-half','analysis-mesh5-001'):
    folder=ROOT/name
    assert (folder/'summary.json').exists(),f'incomplete analysis: {name}'
    for p in folder.rglob('*'):
        if p.is_file():cp(p,DEST/'real'/p.relative_to(ROOT))
index={str(p.relative_to(DEST)):sha(p) for p in DEST.rglob('*') if p.is_file() and p.name!='archive-manifest.json'}
(DEST/'archive-manifest.json').write_text(json.dumps(index,indent=2,sort_keys=True)+'\n')
print(json.dumps({'files':len(index),'bytes':sum((DEST/p).stat().st_size for p in index),'all_source_copy_hashes_match':True}))
