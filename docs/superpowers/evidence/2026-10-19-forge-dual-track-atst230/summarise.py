import hashlib, importlib.metadata as md, json, re, tarfile
from pathlib import Path
from abacus_forge.collection import collect_contained
from abacus_forge import collection_results,relax_results,md_results
root=Path('/home/james/scratch/forge-dual-track-atst230-20261019')
run=root/'matrix-run'
evidence=Path('/home/james/work/sidereus/workplace/abacus-forge/.worktrees/forge-integration-reference-review/docs/superpowers/evidence/2026-10-19-forge-dual-track-atst230')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
with tarfile.open(evidence/'real-inputs-and-logs.tar.gz','w:gz') as archive:
 archive.add(run/'sources',arcname='sources')
 for i,case in enumerate(json.loads((run/'matrix.json').read_text())):
  cap=case['capability'];p=run/'pytest/test_native_and_abacuslite_col0'/f'{i}-{cap}-native'
  log=p/'inputs/OUT.ABACUS'/f'running_{cap}.log'
  text=log.read_text(); version=re.search(r'ABACUS\s+(v\S+)',text)[1];commit=re.search(r'Commit:\s+(\S+)',text)[1]
  assert version==case['version'],(version,case)
  outputs={}
  for backend in ['native','abacuslite']:
   r=collect_contained(p,parser_backend=backend,**({'output_version':case['version']} if backend=='abacuslite' else {}))
   module=relax_results if cap in ['relax','cell-relax'] else md_results if cap=='md' else collection_results
   env=module.collection_envelope(r,p.name)
   outputs[backend]={'status':env.status.to_dict(),'legacy_status':r.status,'energy':r.metrics.get('total_energy'),'normal_end':r.metrics.get('normal_end'),'converged':r.metrics.get('converged'),'final_structure_selection_ambiguous':r.diagnostics.get('final_structure_selection_ambiguous'),'parser':r.diagnostics['parser']}
  rows.append({'track':case['track'],'capability':cap,'actual_log_version':version,'actual_log_commit':commit,'executed_input_sha256':sha(p/'inputs/INPUT'),'log_sha256':sha(log),'outputs':outputs})
  archive.add(log,arcname=f'logs/{i}-{cap}/{log.name}')
  archive.add(p/'inputs/INPUT',arcname=f'logs/{i}-{cap}/INPUT')
summary={'matrix_cells':rows,'wheels':{p.name:sha(p) for p in (root/'wheels').glob('*.whl')},'archive_sha256':sha(evidence/'real-inputs-and-logs.tar.gz'),'versions':{d.metadata['Name']:d.version for d in md.distributions()},'scope':'real PW single-process nspin=1 parser parity, not scientific convergence or all-engine compatibility'}
assert summary['wheels']['abacuslite-1.2.0-py3-none-any.whl']=='3e5e245c0a03e8182c2c726d7ccad1c800c20250641abd4b81a8e22e892bc4a0'
(evidence/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
for row in rows: print(row['track'],row['capability'],row['outputs']['native']['status'])
