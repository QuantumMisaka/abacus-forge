import os,subprocess,json,pathlib,sys,hashlib,importlib.metadata as md,zipfile
p=pathlib.Path(__file__).parent;r=pathlib.Path('/home/james/work/sidereus/workplace/abacus-forge/.worktrees/forge-integration-reference-review');env=dict(os.environ);env.pop('ABACUS_FORGE_CANONICAL_ABACUSLITE',None);env.update(PYTHONPATH='',PYTHONDONTWRITEBYTECODE='1',ABACUS_FORGE_INSTALLED_PACKAGE_ONLY='1',ABACUS_FORGE_WHEEL=str(p/'artifacts/abacus_forge-0.1.0-py3-none-any.whl'),ABACUS_FORGE_CANONICAL_ABACUSLITE_FIXTURES=str(p/'fixtures/tests/fixtures/io/testfiles'));commands=[]
import abacus_forge
site=pathlib.Path(abacus_forge.__file__).parent;assert str(site).startswith(str(p/'venv/'));assert md.version('abacuslite')=='1.2.2'
with zipfile.ZipFile(env['ABACUS_FORGE_WHEEL']) as z:
 names=[n for n in z.namelist() if n.startswith('abacus_forge/') and n.endswith('.py')]
 for n in names:assert z.read(n)==(r/'src'/n).read_bytes()==(site/n.removeprefix('abacus_forge/')).read_bytes(),n
(p/'installed.json').write_text(json.dumps({'python':sys.version,'forge':md.version('abacus-forge'),'abacuslite':md.version('abacuslite'),'installed_path':str(site),'runtime_modules_equal':len(names),'wheel_sha256':hashlib.sha256(pathlib.Path(env['ABACUS_FORGE_WHEEL']).read_bytes()).hexdigest()},indent=2)+'\n')
for name,args in [('pip-check',['-m','pip','check']),('requirements',['-m','pip','freeze']),('package-parity',['-m','pytest','-q','-p','no:cacheprovider','--run-benchmark','tests/test_package_contract.py','tests/test_package_metadata_drift.py','tests/benchmark/test_abacuslite_canonical_parity.py']),('installed-offline',['-m','pytest','-q','-p','no:cacheprovider'])]:
 cmd=[sys.executable,*args]
 with (p/(name+'.log')).open('w') as f:result=subprocess.run(cmd,cwd=r,env=env,stdout=f,stderr=subprocess.STDOUT)
 commands.append({'command':cmd,'cwd':str(r),'env':{k:env[k] for k in ['PYTHONPATH','PYTHONDONTWRITEBYTECODE','ABACUS_FORGE_INSTALLED_PACKAGE_ONLY','ABACUS_FORGE_WHEEL','ABACUS_FORGE_CANONICAL_ABACUSLITE_FIXTURES']},'exit_code':result.returncode,'log':name+'.log'});(p/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(name,result.returncode,flush=True)
 if result.returncode:sys.exit(result.returncode)
