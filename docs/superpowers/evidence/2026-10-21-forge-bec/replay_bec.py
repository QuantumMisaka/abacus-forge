"""Synthetic source-shaped CLI/API handoff demonstration; no ABACUS execution."""
import json, os, runpy, subprocess, sys, uuid
from pathlib import Path
import numpy as np
from abacus_forge import BecPostprocessRequest, BecServiceSet
from abacus_forge.structure import BOHR_TO_ANG
repo=Path('/home/james/work/sidereus/workplace/abacus-forge/.worktrees/forge-integration-reference-review')
work=Path('/home/james/scratch/forge-bec-20261021/cli-replay')
work.mkdir(exist_ok=False)
generator=runpy.run_path(str(repo/'tests/test_polarization_services.py'))['_write_native_sources']
env={**os.environ,'PYTHONPATH':str(repo/'src'),'PYTHONDONTWRITEBYTECODE':'1'}
responses=[]
def operation(payload,label):
    payload={'schema_version':'forge.request/v1','operation_id':str(uuid.uuid4()),'workspace_rel':'.',**payload}
    (work/f'{label}-request.json').write_text(json.dumps(payload,indent=2)+'\n')
    result=subprocess.run([sys.executable,'-m','abacus_forge.cli','operation',payload['operation'],'--stdin'],input=json.dumps(payload),text=True,capture_output=True,cwd=work,env=env,timeout=20)
    (work/f'{label}-response.json').write_text(result.stdout)
    (work/f'{label}-stderr.txt').write_text(result.stderr)
    assert result.returncode==0,(label,result.stdout,result.stderr)
    response=json.loads(result.stdout)
    assert response['envelope']['status']['collection']=='complete',response
    responses.append(response)
    return payload,response
samples=[]
delta=.1*BOHR_TO_ANG
for index,displacement in enumerate([-delta,0.,delta]):
    paths=[]
    for gdir in (1,2,3):
        scalar=[-.02,0.,.02][index] if gdir==1 else 0.
        log,stru,inp=generator(work,displacement,gdir,scalar)
        out=f'facts/s{index}-g{gdir}.json'
        operation({'capability':'polarization','operation':'collect','log_path_rel':log,'structure_path_rel':stru,'input_path_rel':inp,'output_path_rel':out},f'collect-{index}-{gdir}')
        paths.append(out)
    samples.append({'displacement_angstrom':displacement,'polarization_paths_rel':paths})
request,response=operation({'capability':'bec','operation':'postprocess','columns':[{'atom_index':1,'direction':'x','samples':samples}],'branch_mode':'auto','max_step_fraction':.2,'output_path_rel':'outputs/bec-cli.json'},'bec')
api_request=BecPostprocessRequest.from_dict({**request,'operation_id':str(uuid.uuid4()),'output_path_rel':'outputs/bec-api.json'})
api=BecServiceSet.default(workspace_root=work).postprocess.postprocess(api_request)
assert api.envelope.status.collection=='complete',api
left=json.loads((work/'outputs/bec-cli.json').read_text())
right=json.loads((work/'outputs/bec-api.json').read_text())
assert left==right
np.testing.assert_allclose(left['computed_columns'][0]['values'],[.2,0,0],atol=1e-6,rtol=0)
assert left['requested_complete'] and not left['full_tensor_complete']
assert len(list((work/'reports/events').glob('*.json')))==11
summary={'fixture':'synthetic source-shaped, not ABACUS run','collect_cli_operations':9,'bec_cli_operations':1,'bec_python_operations':1,'events':11,'cli_api_results_equal':True,'column_e':left['computed_columns'][0]['values'],'requested_complete':left['requested_complete'],'full_tensor_complete':left['full_tensor_complete'],'scientific':left['scientific']}
(work/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
