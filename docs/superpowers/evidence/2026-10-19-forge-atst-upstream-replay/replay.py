"""Consume archived upstream NEB trajectories through installed Forge/ATST.

No execute operation, ABACUS calculation or scheduler submission is performed.
"""
import argparse
import hashlib
import importlib.metadata as md
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import uuid

ARCHIVE_SHA = '4565d61aa42e7ed1878b44d754728bc27e7d0f5148b129599fb3392a5e7bb3e7'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert sha(args.archive)==ARCHIVE_SHA
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=False)
    import abacus_forge,atst_tools,abacuslite
    for module in (abacus_forge,atst_tools,abacuslite):
        assert Path(module.__file__).is_relative_to(sys.prefix)
    assert md.version('atst-tools')=='2.3.0' and md.version('abacuslite')=='1.2.0'
    atst=Path(sys.executable).parent/'atst'
    assert atst.is_file()
    env=os.environ.copy();env.pop('PYTHONPATH',None)
    env['PATH']=str(atst.parent)+os.pathsep+env.get('PATH','')
    env['OMP_NUM_THREADS']='1';env['OPENBLAS_NUM_THREADS']='1'
    outcomes={}
    with tarfile.open(args.archive) as archive:
        for case in ('neb_serial','neb_parallel'):
            workspace=root/case;workspace.mkdir()
            files=['neb.traj',f'config_{case}.json','evidence.json','atst_artifacts.json',f'api_{case}.json']
            provenance={}
            for name in files:
                member=archive.getmember(f'harness/cases/{case}/{name}')
                assert member.isfile()
                target=workspace/name;target.write_bytes(archive.extractfile(member).read())
                provenance[name]=sha(target)
            original=json.loads((workspace/'evidence.json').read_text())
            images=original['checks']['image_count']
            request={'schema_version':'forge.request/v1','capability':'atst-neb','operation':'postprocess','workspace_rel':'.','operation_id':str(uuid.uuid4()),'trajectory_path_rel':'neb.traj','n_max':images-2,'summary_path_rel':'reports/atst/replay-summary.json','output_prefix':'outputs/atst/replay-ts','write_latest':True,'write_neb_init_chain':True,'plot':True}
            (workspace/'request.json').write_text(json.dumps(request,indent=2)+'\n')
            result=subprocess.run([sys.executable,'-I','-m','abacus_forge.cli','operation','postprocess','--stdin'],cwd=workspace,env=env,input=json.dumps(request),text=True,capture_output=True,timeout=120)
            (workspace/'response.json').write_text(result.stdout)
            (workspace/'stderr.txt').write_text(result.stderr)
            assert result.returncode==0,(case,result.stdout,result.stderr)
            response=json.loads(result.stdout);envelope=response['envelope']
            assert envelope['status']=={'execution':'completed','collection':'complete','scientific':'unassessed'}
            for record in envelope['artifacts']:
                relative=Path(record['path_rel']);assert not relative.is_absolute() and '..' not in relative.parts
                path=(workspace/relative).resolve(strict=True);assert path.is_relative_to(workspace)
                assert sha(path)==record['sha256'] and path.stat().st_size==record['size_bytes']
            replay_summary=json.loads((workspace/'reports/atst/replay-summary.json').read_text())
            assert replay_summary['status']['n_images']==images and replay_summary['status']['complete']
            band=original['checks']['persisted_band']
            assert len(band)==images
            for got,expected in zip(replay_summary['latest']['energies_eV'],[item['energy_ev'] for item in band],strict=True):
                assert math.isclose(got,expected,rel_tol=0,abs_tol=1e-10)
            for got,expected in zip(replay_summary['latest']['image_fmax_eV_per_A'],[item['force_max_ev_per_angstrom'] for item in band],strict=True):
                assert math.isclose(got,expected,rel_tol=0,abs_tol=1e-10)
            events=list((workspace/'reports/events').glob('*.json'));assert len(events)==1
            assert (workspace/'reports/forge-workspace.json').is_file()
            for name,digest in provenance.items():assert sha(workspace/name)==digest
            outcomes[case]={'status':envelope['status'],'input_sha256':provenance,'image_count':images,'n_max':images-2,'artifact_count':len(envelope['artifacts']),'audit_events':1,'source_unchanged':True,'summary_matches_upstream_energy_and_force':True,'upstream_checks':original['checks']}
    summary={'archive_sha256':ARCHIVE_SHA,'python':sys.executable,'atst_executable':str(atst),'versions':{n:md.version(n) for n in ('abacus-forge','atst-tools','abacuslite')},'no_engine_execution':True,'outcomes':outcomes}
    (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:{'status':v['status'],'artifacts':v['artifact_count']} for k,v in outcomes.items()},indent=2))

if __name__=='__main__':main()
