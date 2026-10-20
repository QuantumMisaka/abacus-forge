"""Replay CI run blocks locally; checkout/setup-python are supplied locally."""
import io,json,os,pathlib,shutil,subprocess,sys,tarfile
import yaml
ROOT=pathlib.Path('/home/james/work/sidereus/workplace/abacus-forge/.worktrees/forge-integration-reference-review')
BASE=pathlib.Path(__file__).parent
version=sys.argv[1]; interpreter=sys.argv[2];out=BASE/version;out.mkdir();src=out/'source';src.mkdir();venv=out/'venv'
archive=subprocess.check_output(['git','archive','HEAD'],cwd=ROOT)
with tarfile.open(fileobj=io.BytesIO(archive)) as t:t.extractall(src,filter='data')
for name in ['.github/workflows/ci.yml','tests/README.md']:shutil.copy2(ROOT/name,src/name)
subprocess.run([interpreter,'-m','venv',str(venv)],check=True)
workflow=yaml.safe_load((src/'.github/workflows/ci.yml').read_text());steps=workflow['jobs']['installed-package']['steps']
env=dict(os.environ,PATH=str(venv/'bin')+os.pathsep+os.environ['PATH'],GITHUB_WORKSPACE=str(src),GITHUB_OUTPUT=str(out/'github-output'),GITHUB_ENV=str(out/'github-env'),PYTHONDONTWRITEBYTECODE='1');env.pop('ABACUS_FORGE_CANONICAL_ABACUSLITE',None)
receipts=[]
for i,step in enumerate(steps):
 if 'run' not in step:
  if step.get('with',{}).get('repository')=='QuantumMisaka/abacuslite':
   commit=dict(line.split('=',1) for line in (out/'github-output').read_text().splitlines())['commit'];target=src/'.ci-abacuslite';target.mkdir()
   b=subprocess.check_output(['git','archive',commit,'tests/fixtures/io/testfiles'],cwd='/home/james/work/sidereus/workplace/abacuslite/.worktrees/public-api-contract')
   with tarfile.open(fileobj=io.BytesIO(b)) as t:t.extractall(target,filter='data')
   receipts.append({'fixture_source_commit':commit,'checkout':'local git archive of the declared commit; not a hosted Actions execution'})
  continue
 step_env=dict(env)
 for k,v in step.get('env',{}).items():step_env[k]=v.replace('${{ github.workspace }}',str(src))
 script=out/f'{i}.sh';script.write_text(step['run']);subprocess.run(['bash','-n',str(script)],check=True)
 log=out/f'{i}.log'
 with log.open('w') as f:result=subprocess.run(['bash','--noprofile','--norc','-eo','pipefail',str(script)],cwd=src,env=step_env,stdout=f,stderr=subprocess.STDOUT)
 receipts.append({'name':step['name'],'script':script.name,'log':log.name,'exit_code':result.returncode});(out/'commands.json').write_text(json.dumps(receipts,indent=2)+'\n');print(version,step['name'],result.returncode,flush=True)
 if result.returncode:sys.exit(result.returncode)
 if (out/'github-env').exists():env.update(dict(line.split('=',1) for line in (out/'github-env').read_text().splitlines()))
with (out/'requirements.txt').open('w') as f:subprocess.run([str(venv/'bin/python'),'-m','pip','freeze'],stdout=f,check=True)
