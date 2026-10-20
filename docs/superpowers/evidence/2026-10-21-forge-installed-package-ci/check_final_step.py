import json,os,pathlib,subprocess,sys,yaml
base=pathlib.Path(__file__).parent; version=sys.argv[1]; out=base/version; src=out/'source'; repo=pathlib.Path('/home/james/work/sidereus/workplace/abacus-forge/.worktrees/forge-integration-reference-review')
workflow=yaml.safe_load((repo/'.github/workflows/ci.yml').read_text());step=next(s for s in workflow['jobs']['installed-package']['steps'] if s.get('name')=='Check installed metadata and four-capability parser parity')
env=dict(os.environ,PATH=str(out/'venv/bin')+os.pathsep+os.environ['PATH'],PYTHONDONTWRITEBYTECODE='1');env.pop('ABACUS_FORGE_CANONICAL_ABACUSLITE',None)
env.update(dict(line.split('=',1) for line in (out/'github-env').read_text().splitlines()))
for k,v in step['env'].items():env[k]=v.replace('${{ github.workspace }}',str(src))
script=out/'final-check.sh';script.write_text(step['run']);subprocess.run(['bash','-n',str(script)],check=True)
with (out/'final-check.log').open('w') as f:r=subprocess.run(['bash','--noprofile','--norc','-eo','pipefail',str(script)],cwd=src,env=env,stdout=f,stderr=subprocess.STDOUT)
(out/'final-check.json').write_text(json.dumps({'command':['bash','--noprofile','--norc','-eo','pipefail',str(script)],'cwd':str(src),'env':{k:env[k] for k in ['ABACUS_FORGE_WHEEL','ABACUS_FORGE_INSTALLED_PACKAGE_ONLY','ABACUS_FORGE_CANONICAL_ABACUSLITE_FIXTURES','PYTHONPATH']},'exit_code':r.returncode,'script':'final-check.sh','log':'final-check.log'},indent=2)+'\n');print(version,r.returncode);sys.exit(r.returncode)
