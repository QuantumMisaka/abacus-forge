"""Inspect built main candidate and its isolated optional-parser installation."""
import hashlib,importlib.metadata as md,json,subprocess,sys,tarfile,zipfile
from pathlib import Path
import abacus_forge
R=Path('/home/james/work/sidereus/workplace/abacus-forge')
O=Path('/home/james/scratch/forge-closeout-20261021')
wheel=O/'artifacts/abacus_forge-0.1.0-py3-none-any.whl'
sdist=O/'artifacts/abacus_forge-0.1.0.tar.gz'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
site=Path(abacus_forge.__file__).parent
with zipfile.ZipFile(wheel) as z:
 files={n:z.read(n) for n in z.namelist() if n.startswith('abacus_forge/') and n.endswith('.py')}
 assert len(files)==76
 for n,b in files.items():
  rel=n.removeprefix('abacus_forge/')
  assert b==(R/'src'/n).read_bytes()==(site/rel).read_bytes(),n
assert md.version('abacuslite')=='1.2.0'
proc=subprocess.run([sys.executable,'-I','-m','abacus_forge.cli','capabilities'],capture_output=True,text=True,check=True)
(O/'capabilities.json').write_text(proc.stdout)
with tarfile.open(sdist) as t:
 members=t.getnames();native_logs=sum(n.endswith('running_nscf.log') for n in members)
receipt={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'source_tree_clean':not subprocess.check_output(['git','status','--porcelain'],cwd=R,text=True).strip(),'version':md.version('abacus-forge'),'python':sys.version,'python_executable':sys.executable,'installed_path':str(site),'artifacts':{p.name:{'path':str(p),'size':p.stat().st_size,'sha256':sha(p)} for p in (wheel,sdist)},'wheel_built_from_sdist':True,'python_modules_equal_source_wheel_installed':len(files),'wheel_equal_previously_validated_candidate':sha(wheel)=='c70e71a698ea6fc6d697495845e45c8cb9a95876636e54705074ce2967a02180','optional_parser':'abacuslite=='+md.version('abacuslite'),'pip_check':(O/'pip-check.log').read_text().strip(),'sdist_native_berry_logs':native_logs,'sdist_scope':'build source; complete native evidence is tracked in Git main, not included by existing sdist ignore policy','tests':{'post_merge_offline':'1532 passed, 35 skipped','fresh_optional_install_parity_metadata':'30 passed; 2 wheel-gated tests initially skipped','explicit_candidate_wheel_gates':(O/'candidate-wheel-tests.log').read_text().strip()},'publication':'local candidate only; no remote push or PyPI publication'}
(O/'candidate.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
