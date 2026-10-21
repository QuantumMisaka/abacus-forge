from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
from pymatgen.analysis.elasticity import DeformedStructureSet, ElasticTensor, Strain, Stress
from pymatgen.core import Lattice, Structure

parser = argparse.ArgumentParser(description='Reconstruct elastic raw-strain evidence from raw-selected.tar.gz.')
parser.add_argument('--root', type=Path, required=True, help='directory extracted from raw-selected.tar.gz')
parser.add_argument('--output', type=Path, default=None, help='output per-strain JSON (default: ROOT/per-strain.json)')
args = parser.parse_args()
root = args.root
output = args.output or root / 'per-strain.json'

def read_stru(path: Path):
    lines = path.read_text(errors='replace').splitlines()
    def after(label):
        i = next(i for i,x in enumerate(lines) if x.strip() == label)
        return lines[i+1:]
    lc = float(after('LATTICE_CONSTANT')[0].split()[0])
    vec_lines = after('LATTICE_VECTORS')[0:3]
    cell_ang = np.array([[float(x) for x in line.split()[:3]] for line in vec_lines])
    # ABACUS stores LATTICE_VECTORS in Angstrom when LATTICE_CONSTANT is the Bohr conversion factor.
    return {'lattice_constant_bohr_per_angstrom': lc, 'cell_angstrom': cell_ang.tolist()}

def read_kpt(path: Path):
    lines = path.read_text(errors='replace').splitlines()
    i = next(i for i,x in enumerate(lines) if x.strip().upper() == 'K_POINTS')
    return [int(x) for x in lines[i+3].split()[:3]]

def read_collect(path: Path):
    x=json.loads(path.read_text())
    env=x['payload']['envelope']
    metrics={m['name']:m.get('value') for m in env['metrics']}
    checks={c['name']:c['status'] for c in env['checks']}
    return {
      'operation_id': x['payload']['operation_id'],
      'metrics': metrics,
      'checks': checks,
      'status': env['status'],
      'warnings': env.get('warnings', []),
    }

base_stru=read_stru(root/'input_stru/inputs/STRU')
base=np.array(base_stru['cell_angstrom'],float)
rows=[]
for d in ['input_stru'] + [f'deformed-stru-{i:03d}' for i in range(1,25)]:
    p=root/d
    initial=read_stru(p/'inputs/STRU')
    final=read_stru(p/'inputs/OUT.ABACUS/STRU_ION_D')
    col=read_collect(next((p/'reports/events').glob('*-collect.json')))
    stress=np.array(col['metrics']['stress'],float).reshape(3,3)
    if d=='input_stru':
        deformation=np.eye(3); strain=np.zeros((3,3)); label='input_stru'
    else:
        A_i=np.array(initial['cell_angstrom'],float)
        deformation=np.linalg.inv(base) @ A_i
        strain_obj=Strain.from_deformation(deformation)
        strain=np.asarray(strain_obj)
        label=d
    rows.append({
      'job': label,
      'kpt': read_kpt(p/'inputs/KPT'),
      'initial_input': initial,
      'final_structure': final,
      'deformation': deformation.tolist(),
      'strain': strain.tolist(),
      'converged': col['metrics'].get('converged'),
      'check_status': col['checks'],
      'stress_kbar': stress.tolist(),
      'stress_gpa': (-0.1*stress).tolist(),
      'energy_ev': col['metrics'].get('total_energy'),
      'relax_steps': col['metrics'].get('relax_steps'),
      'collect_status': col['status'],
      'collect_warnings': col['warnings'],
    })

eq_stress=Stress(-0.1*np.array(rows[0]['stress_kbar']))
# Reproduce the candidate's exact DeformedStructureSet ordering and matrices.
# Raw STRU-derived matrices are retained per-row as provenance, but rounded text
# can introduce tiny off-diagonal residue that trips pymatgen strain grouping.
_pym_structure=Structure(Lattice(base), ["Al"], [[0.0,0.0,0.0]])
_deformed_set=DeformedStructureSet(
    _pym_structure,
    symmetry=False,
    norm_strains=[factor * 0.01 for factor in (-1.0, -0.5, 0.5, 1.0)],
    shear_strains=[factor * 0.01 for factor in (-1.0, -0.5, 0.5, 1.0)],
)
deformations=list(_deformed_set.deformations)
for r,d in zip(rows[1:],deformations):
    r['candidate_expected_deformation']=np.asarray(d).tolist()
strains=[Strain.from_deformation(d) for d in deformations]
stresses=[Stress(-0.1*np.array(r['stress_kbar'])) for r in rows[1:]]
tensor=ElasticTensor.from_independent_strains(strains,stresses,eq_stress=eq_stress,vasp=False)
bv,gv=tensor.k_voigt,tensor.g_voigt
fit={
 'bulk_modulus': float(bv),
 'shear_modulus': float(gv),
 'young_modulus': float(9*bv*gv/(3*bv+gv)),
 'poisson_ratio': float((3*bv-2*gv)/(6*bv+2*gv)),
 'tensor_GPa': tensor.voigt.tolist(),
}
out={'schema_version':'elastic-al-fcc-per-strain-attribution/v1','source':{'sai_job_id':'1886152','run_id':'bm-20261021-044215-1886152','work_root':'/org/pku-jianghong/liuzhaoqing/paimon-bench-20261020/runs/elastic_Al-FCC/work/elastic_al-fcc_step1-005'},'base_input':base_stru,'reconstructed_fit':fit,'rows':rows}
output.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'fit':fit},indent=2))
print('\njob  kpt        strain_xx   strain_yy   strain_zz   strain_yz   strain_xz   strain_xy  stress_yz stress_xz stress_xy')
for r in rows:
 s=np.array(r['strain']); st=np.array(r['stress_gpa'])
 print(f"{r['job']:17s} {'x'.join(map(str,r['kpt'])):9s} " + ' '.join(f'{s[i,j]:+10.6f}' for i,j in [(0,0),(1,1),(2,2),(1,2),(0,2),(0,1)]) + ' ' + ' '.join(f'{st[i,j]:+8.3f}' for i,j in [(1,2),(0,2),(0,1)]))
