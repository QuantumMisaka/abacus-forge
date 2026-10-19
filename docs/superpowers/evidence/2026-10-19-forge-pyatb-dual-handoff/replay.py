"""Run installed Forge PyATB operations on two explicitly produced SCF workspaces."""
import argparse
import hashlib
import importlib.metadata as metadata
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--track', choices=['develop', 'lts'], action='append')
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pyatb', type=Path, required=True)
    args = parser.parse_args()
    import abacus_forge
    assert Path(abacus_forge.__file__).is_relative_to(sys.prefix)
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    executable = args.pyatb.resolve(strict=True)
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MPLBACKEND='Agg')
    summary = {'forge_version': metadata.version('abacus-forge'),
               'forge_module': abacus_forge.__file__, 'python': sys.executable,
               'pyatb_executable': str(executable), 'pyatb_executable_sha256': digest(executable), 'tracks': {}}
    for track, names in [('develop', ['hrs1_nao.csr', 'sr_nao.csr', 'rr.csr']),
                         ('lts', ['data-HR-sparse_SPIN0.csr', 'data-SR-sparse_SPIN0.csr', 'data-rR-sparse.csr'])]:
        if args.track and track not in args.track:
            continue
        candidates = [p for p in (args.sources / track).glob('*/typed-lcao-smoke') if not p.parent.is_symlink()]
        assert len(candidates) == 1
        producer = candidates[0]
        event = json.loads(next((producer / 'reports/events').glob('*-collect.json')).read_text())
        assert event['payload']['envelope']['status']['collection'] == 'complete'
        fermi = [m for m in event['payload']['envelope']['metrics'] if m['name'] == 'fermi_energy']
        assert len(fermi) == 1 and fermi[0]['unit'] == 'eV'
        workspace = root / track
        (workspace / 'source').mkdir(parents=True)
        source_paths = [producer / 'inputs/STRU'] + [producer / 'inputs/OUT.ABACUS' / n for n in names]
        source_hashes = {}
        for source in source_paths:
            dest = workspace / 'source' / source.name
            shutil.copyfile(source, dest)
            source_hashes[source.name] = digest(source)
            assert digest(dest) == source_hashes[source.name]
        base = {'schema_version': 'forge.request/v1', 'capability': 'pyatb-band', 'workspace_rel': '.'}
        requests = [
            ('prepare', {'structure_path_rel': 'source/STRU', 'hr_paths_rel': ['source/' + names[0]],
             'sr_path_rel': 'source/' + names[1], 'rr_path_rel': 'source/' + names[2],
             'fermi_energy': fermi[0]['value'], 'nspin': 1, 'line_segments': 5, 'max_kpoint_num': 100,
             'line_kpoints': [{'coords': [0, 0, 0], 'label': 'G'}, {'coords': [0.5, 0, 0.5], 'label': 'X'}],
             'handoff_mode': 'copy'}),
            ('execute', {'executable': str(executable), 'mpi_ranks': 1, 'omp_threads': 1,
             'timeout_seconds': 180, 'dry_run': False}),
            ('collect', {'band_info_path_rel': 'inputs/Out/Band_Structure/band_info.dat',
             'band_data_paths_rel': ['inputs/Out/Band_Structure/band.dat'],
             'band_picture_paths_rel': ['inputs/Out/Band_Structure/band.pdf']})]
        outcomes = {}
        for operation, fields in requests:
            request = {**base, 'operation': operation, 'operation_id': str(uuid.uuid4()), **fields}
            (workspace / f'{operation}-request.json').write_text(json.dumps(request, indent=2)+'\n')
            process = subprocess.run([sys.executable, '-I', '-m', 'abacus_forge.cli', 'operation', operation, '--stdin'],
                input=json.dumps(request), text=True, capture_output=True, cwd=workspace, env=env, timeout=240)
            (workspace / f'{operation}-response.json').write_text(process.stdout)
            (workspace / f'{operation}-stderr.txt').write_text(process.stderr)
            assert process.returncode == 0, (track, operation, process.stdout, process.stderr)
            payload = json.loads(process.stdout)
            envelope = payload['envelope']
            assert envelope['status']['scientific'] == 'unassessed'
            if operation == 'execute':
                assert envelope['status']['execution'] == 'completed'
            if operation == 'collect':
                assert envelope['status']['collection'] == 'complete'
                gaps = [m['value'] for m in envelope['metrics'] if m['name'] == 'band_gap']
                assert len(gaps) == 1 and math.isfinite(gaps[0])
            for artifact in envelope['artifacts']:
                relative = Path(artifact['path_rel'])
                assert not relative.is_absolute() and '..' not in relative.parts
                path = (workspace / relative).resolve(strict=True)
                assert path.is_relative_to(workspace)
                assert path.stat().st_size == artifact['size_bytes'] and digest(path) == artifact['sha256']
            audit = json.loads((workspace / 'reports/events' / f"{request['operation_id']}-{operation}.json").read_text())
            assert audit['payload'] == payload
            refs = envelope['diagnostics']['artifact_refs']
            assert {r['artifact_id'] for r in refs} == {a['id'] for a in envelope['artifacts']}
            outcomes[operation] = {'status': envelope['status'], 'artifacts': len(envelope['artifacts']), 'metrics': envelope['metrics']}
        assert len(list((workspace / 'reports/events').glob('*.json'))) == 3
        for source in source_paths:
            assert digest(source) == digest(workspace / 'source' / source.name) == source_hashes[source.name]
        summary['tracks'][track] = {'source_workspace': str(producer), 'source_sha256': source_hashes,
            'fermi_energy_eV': fermi[0]['value'], 'operations': outcomes, 'source_unchanged': True, 'audit_events': 3}
    (root / 'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
