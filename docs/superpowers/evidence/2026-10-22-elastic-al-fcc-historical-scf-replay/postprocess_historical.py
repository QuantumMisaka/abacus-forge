import json, pathlib, sys
import numpy as np
from abacustest.lib_collectdata.collectdata import RESULT
from pymatgen.analysis.elasticity import ElasticTensor, Strain, Stress

work=pathlib.Path(sys.argv[1]).resolve()

def collect(path):
    result=RESULT(fmt="abacus", path=path)
    return {k:result[k] for k in ["normal_end","converge","scf_steps","energy","stress"]}

def to_stress(values):
    a=np.asarray(values,dtype=float)
    return Stress(-0.1*np.array([a[0:3],a[3:6],a[6:]]))

from abacusagent.modules.elastic import prepare_deformed_stru
input_dir=work/"input_stru"
deformed=prepare_deformed_stru(input_dir,0.01,0.01)
strains=[Strain.from_deformation(d) for d in deformed.deformations]
rows=[]
input_metrics=collect(input_dir)
eq=to_stress(input_metrics["stress"])
rows.append({"job":"input_stru","metrics":input_metrics,"stress_kbar":input_metrics["stress"],"stress_gpa":(-0.1*np.asarray(input_metrics["stress"])).tolist()})
deformed_stresses=[]
for i,d in enumerate(deformed,1):
    p=work/f"deformed-stru-{i:03d}"
    m=collect(p)
    s=to_stress(m["stress"])
    deformed_stresses.append(s)
    rows.append({"job":p.name,"metrics":m,"stress_kbar":m["stress"],"stress_gpa":(-0.1*np.asarray(m["stress"])).tolist()})
tensor=ElasticTensor.from_independent_strains(strains,deformed_stresses,eq_stress=eq,vasp=False)
bv,gv=tensor.k_voigt,tensor.g_voigt
fit={
    "bulk_modulus":float(bv),
    "shear_modulus":float(gv),
    "young_modulus":float(9*bv*gv/(3*bv+gv)),
    "poisson_ratio":float((3*bv-2*gv)/(6*bv+2*gv)),
    "tensor_GPa":tensor.voigt.tolist(),
}
out={
    "schema_version":"v12-historical-scf-elastic-replay/v1",
    "source_commit":"abacus-agent-tools@e81c5d1",
    "work_dir":str(work),
    "calculation":"scf",
    "kpt":[20,20,20],
    "fit":fit,
    "rows":rows,
    "compatibility_patch":"pymatgen/dpdata serialization only: vasp/poscar -> poscar",
}
path=work.parent/"historical-scf-replay-parsed.json"
path.write_text(json.dumps(out,indent=2,default=str)+"\n")
print(json.dumps({
    "path":str(path),
    "fit":fit,
    "all_converged":all(r["metrics"]["converge"] is True for r in rows),
    "all_normal_end":all(r["metrics"]["normal_end"] is True for r in rows),
    "row_count":len(rows),
},indent=2))
