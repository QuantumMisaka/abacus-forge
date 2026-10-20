import hashlib, itertools, json, os, shutil, subprocess, sys, uuid
from pathlib import Path
import numpy as np
base = Path('/home/james/scratch/forge-pyatb-installed-20261019')
reference = Path('/home/james/scratch/pyatb-cohp-validation-20261019/si-v3')
output = Path('/home/james/scratch/forge-consumption-20261021/native-r2')
output.mkdir(exist_ok=False)
orbital = reference/'develop-COHP-narrow0-ranks1/Si_gga_7au_100Ry_2s2p1d.orb'
summary = {}
for track in ['develop', 'lts']:
    work = output/track
    shutil.copytree(base/track/'source',work/'source')
    shutil.copyfile(orbital,work/'source'/orbital.name)
    hashes = {str(p.relative_to(work)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (work/'source').iterdir()}
    old=json.loads((base/track/'prepare-request.json').read_text())
    common={'schema_version':'forge.request/v1','capability':'pyatb-cohp','workspace_rel':'.'}
    prepare={**common, 'structure_path_rel':'source/STRU','hr_paths_rel':old['hr_paths_rel'], 'sr_path_rel':old['sr_path_rel'], 'orbital_paths_rel':['source/'+orbital.name], 'fermi_energy':old['fermi_energy'], 'atom_i_index':1,'atom_j_index':1,'atom_i_orbs':'s','atom_j_orbs':'p','kpoints':list(itertools.product([0.,.5],repeat=3)),'kpoint_weights':[1.]*8,'e_range':[-15.,25.],'max_kpoint_num':3}
    responses={}
    for operation,request in [('prepare',prepare),('execute',{**common,'executable':str(base/'venv/bin/pyatb'),'timeout_seconds':120}),('collect',common)]:
        request={**request,'operation':operation,'operation_id':str(uuid.uuid4())}
        (work/f'{operation}-request.json').write_text(json.dumps(request,indent=2)+'\n')
        run=subprocess.run([sys.executable,'-m','abacus_forge.cli','operation',operation,'--stdin'],input=json.dumps(request),text=True,cwd=work,capture_output=True,env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'},timeout=150)
        (work/f'{operation}-response.json').write_text(run.stdout)
        (work/f'{operation}-stderr.log').write_text(run.stderr)
        assert run.returncode==0,(track,operation,run.stdout,run.stderr)
        responses[operation]=json.loads(run.stdout)
        status=responses[operation]['envelope']['status']
        if operation=='execute': assert status['execution']=='completed',status
        if operation=='collect': assert status['collection']=='complete',status
    actual=work/'inputs/Out/COHP'
    oldout=reference/f'{track}-COHP-narrow0-ranks1/Out/COHP'
    a,b=np.loadtxt(actual/'COHP.dat'),np.loadtxt(oldout/'COHP.dat')
    np.testing.assert_allclose(a,b,atol=1e-8,rtol=1e-8)
    meta=json.loads((actual/'COHP.meta.json').read_text())
    oldmeta=json.loads((oldout/'COHP.meta.json').read_text())
    np.testing.assert_allclose(meta['occupied_integral']['raw_value'],oldmeta['occupied_integral']['raw_value'],atol=1e-10,rtol=1e-10)
    assert hashes=={str(p.relative_to(work)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (work/'source').iterdir()}
    assert len(list((work/'reports/events').glob('*.json')))==3
    summary[track]={'samples':len(a),'max_spectrum_delta':float(np.max(np.abs(a-b))),'occupied_integral':meta['occupied_integral'],'source_sha256':hashes,'events':3,'status':responses['collect']['envelope']['status']}
(output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
