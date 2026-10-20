"""Audit completed stages and compare the three predeclared sensitivity cases."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
configs=[('mesh4',.01,'analysis-mesh4-002'),('mesh4',.005,'analysis-mesh4-half'),('mesh5',.01,'analysis-mesh5-001')]
results=[]
for case,delta,folder in configs:
    d=json.loads((R/folder/'summary.json').read_text())
    result=json.loads((R/folder/'auto-result.json').read_text())
    assert result['requested_complete'] and not result['full_tensor_complete']
    assert result['scientific']=='unassessed'
    assert d['auto_column_e'][0]<0 and d['max_auto_explicit_error_e']<2e-6 and d['max_explicit_manual_error_e']<2e-6
    results.append({'case':case,'delta_angstrom':delta,'column_e':d['auto_column_e'],'max_auto_explicit_error_e':d['max_auto_explicit_error_e'],'max_explicit_manual_error_e':d['max_explicit_manual_error_e'],'analysis':folder})
base=results[0]['column_e'][0]
for item in results:item['Zxx_difference_from_baseline_e']=abs(item['column_e'][0]-base)
records=[]
for stage in sorted(R.glob('mesh*/d*/*')):
    if not stage.is_dir():continue
    success=json.loads((stage/'success.json').read_text());run=json.loads((stage/'run.json').read_text())
    assert run['returncode']==0 and run['elapsed_seconds']<300
    scf=stage.name=='scf'
    log=stage/'inputs/OUT.ABACUS'/('running_scf.log' if scf else 'running_nscf.log')
    assert sha(log)==success['native_log_sha256']
    native=log.read_text();assert 'Total  Time' in native
    assert ('#SCF IS CONVERGED#' if scf else 'Read electron density from file') in native
    for pp in ('Mg.PD04.PBE.UPF','O.upf'):assert sha(stage/'inputs'/pp)==sha(R/'pp'/pp)
    if not scf:
        receipt=json.loads((stage/'charge-handoff.json').read_text())
        before=receipt.get('destination_before_execute_sha256',receipt.get('destination_sha256'))
        assert receipt['source_sha256']==before==sha(R/receipt['source'])
        response=json.loads((stage/'collect-response.json').read_text())
        assert response['envelope']['status']['collection']=='complete'
    records.append({'stage':str(stage.relative_to(R)),'returncode':run['returncode'],'seconds':run['elapsed_seconds'],'kind':'scf' if scf else 'nscf','native_sha256':sha(log)})
assert len(records)==32
assert sum(x['kind']=='nscf' for x in records)==24
summary={'wheel_sha256':'c70e71a698ea6fc6d697495845e45c8cb9a95876636e54705074ce2967a02180','engine_runs':len(records),'polarization_collections':24,'bec_cli_operations_in_final_analyses':6,'all_runs_exit_zero':True,'all_scf_converged':True,'all_stage_pp_match':True,'all_charge_handoff_before_hashes_match_and_scf_sources_unchanged':True,'all_native_logs_match_success_hash':True,'cases':results,'predeclared_sensitivity_tolerance_e':.1,'limited_sensitivity_within_tolerance':all(x['Zxx_difference_from_baseline_e']<.1 for x in results),'scientific':'unassessed','full_tensor_complete':False,'records':records}
(R/'validation-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='records'},indent=2))
