#!/usr/bin/env python3
"""Reproduce typed PyATB band handoff through installed Forge/PyATB wheels."""
import hashlib
import argparse
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
from urllib.parse import unquote, urlparse

import numpy as np

ROOT = Path(__file__).resolve().parent
SAVED = Path('/home/james/scratch/pyatb-sidereus-validation-20261019/forge-replay')
OUT = ROOT
VENV = ROOT / 'venv'
CLI = VENV / 'bin/abacus-forge'
PYATB = VENV / 'bin/pyatb'
FORGE_WHEEL = ROOT / 'wheels/abacus_forge-0.1.0-py3-none-any.whl'
PYATB_WHEEL = Path('/home/james/scratch/forge-pyatb-wheel-20261019/repaired/pyatb-1.1.2.dev0+5f7e132-cp312-cp312-manylinux_2_39_x86_64.whl')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def contained_file(work, rel):
    assert isinstance(rel, str) and rel and not Path(rel).is_absolute(), rel
    target = (work / rel).resolve()
    target.relative_to(work.resolve())
    assert target.is_file(), target
    return target


def validate_wheel_binding(distribution, wheel):
    record = json.loads(metadata.distribution(distribution).read_text('direct_url.json'))
    assert record['archive_info']['hashes']['sha256'] == sha(wheel)
    url = urlparse(record['url'])
    assert url.scheme == 'file' and Path(unquote(url.path)).resolve() == wheel
    return record


def check_artifacts(work, response):
    assert response['schema_version'] == 'forge.operation-outcome/v1'
    env = response['envelope']
    assert env['schema_version'] == 'forge.result/v1'
    assert env['status']['scientific'] == 'unassessed'
    assert env['workspace_rel'] == '.'
    for record in env['artifacts']:
        path = contained_file(work, record['path_rel'])
        assert record['availability'] == 'available'
        assert record['size_bytes'] == path.stat().st_size
        assert record['sha256'] == sha(path)
        assert record['role'] in {'input', 'output', 'runtime_log', 'provenance_manifest'}
    return env


def check_manifest(work, env):
    manifest = env['diagnostics'].get('pyatb_manifest')
    if manifest is None:
        return None
    assert manifest['schema_version'] == 'forge.pyatb-manifest/v1'
    assert manifest['missing'] == []
    artifact_by_id = {a['id']: a for a in env['artifacts']}
    for entry in manifest['inputs'] + manifest['outputs']:
        path = contained_file(work, entry['path_rel'])
        assert entry['artifact_id'] in artifact_by_id
        assert entry['path_rel'] == artifact_by_id[entry['artifact_id']]['path_rel']
        assert entry['sha256'] == sha(path)
        assert entry['size_bytes'] == path.stat().st_size
        assert entry['kind'] in {'structure', 'matrix_hr', 'matrix_sr', 'matrix_rr', 'pyatb_input', 'kpoint_path', 'band_info', 'band_data', 'band_plot'}
        assert entry['spin'] in {'shared', 'up', 'down', 'total', 'unknown'}
        if 'source_path_rel' in entry:
            source = contained_file(work, entry['source_path_rel'])
            assert entry['handoff_mode'] == 'copy'
            assert entry['source_sha256'] == sha(source) == entry['sha256']
    return manifest


def run_operation(work, name, request):
    write(work / f'{name}-request.json', request)
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    command = [str(CLI), 'operation', name, '--request', f'{name}-request.json']
    proc = subprocess.run(command, cwd=work,
                          env=env, text=True, capture_output=True, timeout=300)
    invocation = {'command': command, 'cwd': str(work), 'returncode': proc.returncode,
                  'pythonpath_unset': 'PYTHONPATH' not in env}
    write(work / f'{name}-invocation.json', invocation)
    (work / f'{name}-stdout.json').write_text(proc.stdout)
    (work / f'{name}-stderr.txt').write_text(proc.stderr)
    assert proc.returncode == 0, (name, proc.returncode, proc.stdout, proc.stderr)
    response = json.loads(proc.stdout)
    write(work / f'{name}-response.json', response)
    assert response['operation_id'] == request['operation_id']
    return response, invocation


def main():
    global OUT, SAVED, VENV, CLI, PYATB, FORGE_WHEEL, PYATB_WHEEL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT,
                        help='fresh output directory for replay workspaces')
    parser.add_argument('--saved', type=Path, default=SAVED,
                        help='saved replay with source and request JSON')
    parser.add_argument('--venv', type=Path, default=VENV,
                        help='fresh wheel-installed virtual environment')
    parser.add_argument('--forge-wheel', type=Path, default=FORGE_WHEEL,
                        help='exact Forge wheel used for this install')
    parser.add_argument('--pyatb-wheel', type=Path, default=PYATB_WHEEL,
                        help='exact native PyATB wheel used for this install')
    args = parser.parse_args()
    OUT, SAVED, VENV = args.output.resolve(), args.saved.resolve(), args.venv.resolve()
    FORGE_WHEEL, PYATB_WHEEL = args.forge_wheel.resolve(), args.pyatb_wheel.resolve()
    CLI, PYATB = VENV / 'bin/abacus-forge', VENV / 'bin/pyatb'
    OUT.mkdir(parents=True, exist_ok=True)
    import abacus_forge
    import pyatb
    assert Path(sys.executable).resolve() == (VENV / 'bin/python').resolve()
    assert Path(abacus_forge.__file__).resolve().is_relative_to(VENV / 'lib/python3.12/site-packages')
    assert Path(pyatb.__file__).resolve().is_relative_to(VENV / 'lib/python3.12/site-packages')
    assert PYATB.is_file()
    forge_install = validate_wheel_binding('abacus-forge', FORGE_WHEEL)
    pyatb_install = validate_wheel_binding('pyatb', PYATB_WHEEL)
    summary = {
        'forge_commit': 'be1c0bc7ccf3d966288b59cafd890e8db4eb03ee',
        'python': sys.executable,
        'forge_module': str(Path(abacus_forge.__file__).resolve()),
        'pyatb_module': str(Path(pyatb.__file__).resolve()),
        'forge_wheel': str(FORGE_WHEEL),
        'forge_wheel_sha256': sha(FORGE_WHEEL),
        'pyatb_wheel': str(PYATB_WHEEL),
        'pyatb_wheel_sha256': sha(PYATB_WHEEL),
        'forge_install_direct_url': forge_install,
        'pyatb_install_direct_url': pyatb_install,
        'pyatb_executable': str(PYATB),
        'pyatb_executable_sha256': sha(PYATB),
        'tracks': {},
    }
    for track in ('develop', 'lts'):
        prior = SAVED / track
        work = OUT / track
        assert not work.exists(), f'fresh replay required: {work}'
        work.mkdir()
        shutil.copytree(prior / 'source', work / 'source')
        source_before = {p.name: sha(p) for p in (work / 'source').iterdir() if p.is_file()}
        assert source_before == {p.name: sha(p) for p in (prior / 'source').iterdir() if p.is_file()}
        details = {'source_sha256': source_before, 'operations': {}}
        prior_event_bytes = {}
        for name in ('prepare', 'execute', 'collect'):
            request = json.loads((prior / f'{name}-request.json').read_text())
            request['operation_id'] = str(uuid.uuid4())
            if name == 'execute':
                request['executable'] = str(PYATB)
            result, invocation = run_operation(work, name, request)
            env = check_artifacts(work, result)
            manifest = check_manifest(work, env)
            expected = {'prepare': ('not_run', 'not_collected'), 'execute': ('completed', 'not_collected'), 'collect': ('not_run', 'complete')}[name]
            assert (env['status']['execution'], env['status']['collection']) == expected
            if name == 'prepare':
                assert [e['kind'] for e in manifest['inputs']] == ['structure', 'matrix_hr', 'matrix_sr', 'matrix_rr', 'pyatb_input', 'kpoint_path']
                assert all(e['spin'] == 'shared' for e in manifest['inputs'])
            if name == 'collect':
                assert [e['kind'] for e in manifest['outputs']] == ['band_info', 'band_data', 'band_plot']
                assert all(e['spin'] == 'unknown' for e in manifest['outputs'])
            audit_now = json.loads((work / 'reports/forge-workspace.json').read_text())
            assert [e['operation'] for e in audit_now['events']] == list(('prepare', 'execute', 'collect')[:len(details['operations']) + 1])
            for event_path, old_bytes in prior_event_bytes.items():
                assert event_path.read_bytes() == old_bytes, f'prior event mutated: {event_path}'
            prior_event_bytes = {contained_file(work, e['path_rel']): contained_file(work, e['path_rel']).read_bytes()
                                 for e in audit_now['events']}
            assert len(prior_event_bytes) == len(details['operations']) + 1
            details['operations'][name] = {'operation_id': request['operation_id'], 'status': env['status'],
                                            'artifacts': len(env['artifacts']), 'metrics': env['metrics'],
                                            'invocation': invocation}
        audit = json.loads((work / 'reports/forge-workspace.json').read_text())
        assert audit['schema_version'] == 'forge.workspace/v1'
        assert [e['operation'] for e in audit['events']] == ['prepare', 'execute', 'collect']
        assert len(list((work / 'reports/events').glob('*.json'))) == 3
        for event in audit['events']:
            event_file = contained_file(work, event['path_rel'])
            payload = json.loads(event_file.read_text())
            assert payload['id'] == event['id']
            assert payload['operation'] == event['operation']
            assert payload['payload']['operation_id'] == event['id']
            assert payload['payload'] == json.loads((work / f"{event['operation']}-response.json").read_text())
        source_after = {p.name: sha(p) for p in (work / 'source').iterdir() if p.is_file()}
        assert source_after == source_before
        new_band = np.loadtxt(work / 'inputs/Out/Band_Structure/band.dat')
        old_band = np.loadtxt(prior / 'inputs/Out/Band_Structure/band.dat')
        assert new_band.shape == old_band.shape
        max_abs_diff = float(np.max(np.abs(new_band - old_band)))
        assert np.allclose(new_band, old_band, rtol=1e-7, atol=1e-5), max_abs_diff
        details['band_shape'] = list(new_band.shape)
        details['band_max_abs_diff_eV'] = max_abs_diff
        details['audit_events'] = len(audit['events'])
        details['source_unchanged'] = True
        summary['tracks'][track] = details
        write(OUT / 'replay-summary.json', summary)
        print(f'{track}: prepare/execute/collect passed; band max diff {max_abs_diff:.3g} eV', flush=True)
    write(OUT / 'replay-summary.json', summary)


if __name__ == '__main__':
    main()
