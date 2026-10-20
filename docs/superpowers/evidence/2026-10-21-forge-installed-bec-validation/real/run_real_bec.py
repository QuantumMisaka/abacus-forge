"""Bounded local MgO validation. Run under installed Forge, with toolchain sourced."""
import argparse, hashlib, json, os, shutil, subprocess, sys, time, uuid
from pathlib import Path
from ase import Atoms
from abacus_forge import prepare, execute
from abacus_forge.runner import LocalRunner
from abacus_forge.workspace import Workspace
ROOT=Path(__file__).resolve().parent
ENGINE=Path('/home/james/work/sidereus/workplace/abacus-packages/abacus-develop/build-mpi-lcao/install/bin/abacus_std_para')
PP_SOURCE=Path('/home/james/work/sidereus/workplace/app-tools-forge/toolbox/ABACUS/deps/abacus-pp-orb/PP')
PP=ROOT/'pp'
A=4.24584

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,obj): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,indent=2)+'\n')
def assets():
    PP.mkdir(exist_ok=True)
    for name in ('Mg.PD04.PBE.UPF','O.upf'):
        target=PP/name
        if not target.exists(): shutil.copy2(PP_SOURCE/name,target)
        assert sha(target)==sha(PP_SOURCE/name)
    dump(ROOT/'provenance.json',{'engine':str(ENGINE),'engine_sha256':sha(ENGINE),'pp':{n:sha(PP/n) for n in ('Mg.PD04.PBE.UPF','O.upf')},'a_angstrom':A,'cell_angstrom':[[0,A/2,A/2],[A/2,0,A/2],[A/2,A/2,0]],'species':['Mg','O'],'positions_fractional':[[0,0,0],[.5,.5,.5]],'source_ase_displaced_atom_index':2,'serialized_stru_displaced_atom_index':1,'serialized_stru_species':['O','Mg'],'direction':'x','ecutwfc_Ry':80,'nspin':1,'xc':'PBE','timeout_per_stage_seconds':300,'threads':1,'max_step_fraction':.25,'sensitivity_tolerance_e':.1,'python':sys.executable})
def operation(work,payload,label):
    payload={'schema_version':'forge.request/v1','operation_id':str(uuid.uuid4()),'workspace_rel':'.',**payload}
    dump(work/f'{label}-request.json',payload)
    proc=subprocess.run([sys.executable,'-I','-m','abacus_forge.cli','operation',payload['operation'],'--stdin'],input=json.dumps(payload),capture_output=True,text=True,cwd=work,timeout=30)
    (work/f'{label}-response.json').write_text(proc.stdout)
    (work/f'{label}-stderr.txt').write_text(proc.stderr)
    assert proc.returncode==0,(proc.stdout,proc.stderr)
    response=json.loads(proc.stdout)
    assert response['envelope']['status']['collection']=='complete',response
    return response

def stage(case, displacement, gdir, mesh):
    tag=f'd{displacement:+.4f}'
    root=ROOT/case/tag/('scf' if gdir==0 else f'g{gdir}')
    if (root/'success.json').exists(): return Workspace(root)
    assert not root.exists(), f'Inspect incomplete stage before retry: {root}'
    atoms=Atoms('MgO',scaled_positions=[[0,0,0],[.5,.5,.5]],cell=[[0,A/2,A/2],[A/2,0,A/2],[A/2,A/2,0]],pbc=True)
    atoms.positions[1,0]+=displacement
    params={'basis_type':'pw','ecutwfc':80,'nspin':1,'dft_functional':'PBE','symmetry':-1,'scf_thr':1e-10,'scf_nmax':100,'smearing_method':'fixed','nbands':4,'out_chg':1 if not gdir else 0,'out_band':0,'out_dos':0}
    k=[mesh]*3
    overrides={}
    if gdir:
        k[gdir-1]=2*mesh
        overrides={'calculation':'nscf','berry_phase':1,'gdir':gdir,'init_chg':'file','pw_diag_thr':1e-11}
    ws=prepare(root,structure=atoms,task='scf',parameters=params,input_overrides=overrides,kpoints=k,pseudo_path=PP,asset_mode='copy')
    if gdir:
        source=ROOT/case/tag/'scf/inputs/OUT.ABACUS/ABACUS-CHARGE-DENSITY.restart'
        dest=ws.inputs_dir/'OUT.ABACUS'/source.name
        dest.parent.mkdir(exist_ok=True)
        shutil.copy2(source,dest)
        dump(root/'charge-handoff.json',{'source':str(source.relative_to(ROOT)),'destination':str(dest.relative_to(ROOT)),'source_sha256':sha(source),'destination_before_execute_sha256':sha(dest),'timing':'copied before engine launch'})
    start=time.monotonic()
    result=execute(ws,runner=LocalRunner(executable=str(ENGINE),timeout_seconds=300,env_overrides={'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'}))
    elapsed=time.monotonic()-start
    dump(root/'run.json',{'returncode':result.returncode,'elapsed_seconds':elapsed})
    assert result.returncode==0,(root,result)
    if gdir:
        receipt=json.loads((root/'charge-handoff.json').read_text())
        receipt['destination_after_execute_sha256']=sha(dest)
        receipt['source_after_execute_sha256']=sha(source)
        assert receipt['source_after_execute_sha256']==receipt['source_sha256']
        dump(root/'charge-handoff.json',receipt)
    native=ws.inputs_dir/'OUT.ABACUS'/('running_nscf.log' if gdir else 'running_scf.log')
    log=native.read_text()
    assert 'Total  Time' in log, f'No normal finish {native}'
    if not gdir:
        assert '#SCF IS CONVERGED#' in log, f'No SCF convergence {native}'
    else:
        assert 'Read electron density from file' in log, f'No charge read marker {native}'
        operation(root,{'capability':'polarization','operation':'collect','log_path_rel':str(native.relative_to(root)),'structure_path_rel':'inputs/STRU','input_path_rel':'inputs/INPUT','output_path_rel':'facts/polarization.json'},'collect')
    dump(root/'success.json',{'elapsed_seconds':elapsed,'native_log_sha256':sha(native)})
    print(json.dumps({'case':case,'displacement':displacement,'gdir':gdir,'seconds':round(elapsed,2),'status':'success'}),flush=True)
    return ws
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',default='mesh4');p.add_argument('--mesh',type=int,default=4);p.add_argument('--displacement',type=float,default=0);p.add_argument('--gdir',type=int,default=0);args=p.parse_args()
    assets();stage(args.case,args.displacement,args.gdir,args.mesh)
