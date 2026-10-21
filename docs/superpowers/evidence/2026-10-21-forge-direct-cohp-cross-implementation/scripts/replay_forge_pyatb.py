import json,os,shutil,subprocess,sys,uuid
from pathlib import Path
base=Path('/home/james/scratch/forge-direct-cohp-cross-20261021/pyatb')
scf=Path('/home/james/scratch/forge-real-evidence-20261015/cohp-iao-b3ffff102-current-0b5f')
pyatb=Path('/home/james/scratch/forge-pyatb-installed-20261019/venv/bin/pyatb')
forge=Path('/home/james/work/sidereus/workplace/abacus-forge')
if base.exists():
    raise SystemExit('output exists')
source=base/'source'; source.mkdir(parents=True)
files=['STRU','Si_gga_6au_100Ry_2s2p1d.orb']
for name in files: shutil.copy2(scf/name,source/name)
shutil.copy2(scf/'OUT.ABACUS/data-HR-sparse_SPIN0.csr',source/'data-HR-sparse_SPIN0.csr')
shutil.copy2(scf/'OUT.ABACUS/data-SR-sparse_SPIN0.csr',source/'data-SR-sparse_SPIN0.csr')
# actual full 36-point k mesh and weights from OUT.ABACUS/kpoints
kpts=[]; weights=[]
lines=(scf/'OUT.ABACUS/kpoints').read_text().splitlines()
start=next(i for i,line in enumerate(lines) if 'K-POINTS DIRECT COORDINATES' in line)
for line in lines[start+2:]:
    row=line.split()
    if len(row)!=5 or not row[0].isdigit(): break
    kpts.append([float(row[1]),float(row[2]),float(row[3])])
    weights.append(float(row[4]))
assert len(kpts)==36,len(kpts)
common={'schema_version':'forge.request/v1','capability':'pyatb-cohp','workspace_rel':'.'}
prepare={**common,'structure_path_rel':'source/STRU','hr_paths_rel':['source/data-HR-sparse_SPIN0.csr'],'sr_path_rel':'source/data-SR-sparse_SPIN0.csr','orbital_paths_rel':['source/Si_gga_6au_100Ry_2s2p1d.orb'],'fermi_energy':15.9268620439,'atom_i_index':1,'atom_j_index':1,'atom_i_orbs':'s','atom_j_orbs':'p','kpoints':kpts,'kpoint_weights':weights,'e_range':[-15.0,25.0],'de':0.05,'sigma':0.15,'max_kpoint_num':4000}
responses={}
for op,request in [('prepare',prepare),('execute',{**common,'executable':str(pyatb),'timeout_seconds':600}),('collect',common)]:
    request={**request,'operation':op,'operation_id':str(uuid.uuid4())}
    (base/f'{op}-request.json').write_text(json.dumps(request,indent=2)+'\n')
    env=os.environ.copy(); env['PYTHONPATH']=str(forge/'src'); env['PYTHONNOUSERSITE']='1'
    run=subprocess.run(['/home/james/apps/miniforge3/envs/paimon/bin/python','-m','abacus_forge.cli','operation',op,'--stdin'],input=json.dumps(request),text=True,cwd=base,capture_output=True,env=env,timeout=650)
    (base/f'{op}-response.json').write_text(run.stdout)
    (base/f'{op}-stderr.log').write_text(run.stderr)
    assert run.returncode==0,(op,run.stdout,run.stderr)
    response=json.loads(run.stdout); responses[op]=response
    status=response['envelope']['status']
    if op=='execute': assert status['execution']=='completed',status
    if op=='collect': assert status['collection']=='complete',status
meta=json.loads((base/'inputs/Out/COHP/COHP.meta.json').read_text())
summary={'kpoint_count':len(kpts),'kpoint_weights':weights,'pair_factor':meta['pair_factor'],'pair_convention':meta['pair_convention'],'occupied_integral':meta['occupied_integral'],'status':responses['collect']['envelope']['status']}
(base/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
