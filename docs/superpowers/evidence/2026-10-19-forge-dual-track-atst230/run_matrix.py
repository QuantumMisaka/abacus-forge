"""Run the existing real-output parity gate with two explicit engine binaries.

Source directories are copied before use; --output must be a new directory.
Source the engine toolchain environment before invoking this with an installed
Forge/abacuslite environment. This harness does not submit cluster jobs.
"""
import argparse
import hashlib
import importlib.metadata as md
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--develop', type=Path, required=True)
    parser.add_argument('--lts', type=Path, required=True)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    import abacus_forge, abacuslite
    assert md.version('abacuslite') == '1.2.0'
    for module in (abacus_forge, abacuslite):
        assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    inputs = {}
    for capability, name in [('scf','pw-scf'),('relax','pw-cell-relax'),('cell-relax','pw-cell-relax'),('md','pw-md')]:
        source = args.source_root / name
        # Accept only the small, reviewed input/asset set, never old outputs.
        files = {p.relative_to(source).as_posix():p for p in source.rglob('*') if p.is_file()}
        assert set(files) == {'inputs/INPUT','inputs/STRU','inputs/KPT','pseudos/Si.upf'}, files
        target = root/'sources'/capability
        shutil.copytree(source,target,symlinks=False)
        manifest = {name:digest(target/name) for name in sorted(files)}
        inputs[capability] = {'workspace':str(target),'files':manifest,'identity':hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()}
    matrix=[]
    for track,binary,version in [('develop',args.develop,'v3.11.0-beta8'),('lts',args.lts,'v3.10.1')]:
        binary = binary.resolve(strict=True)
        for capability,record in inputs.items():
            case={'track':track,'capability':capability,'version':version,'executable':str(binary),'executable_sha256':digest(binary),'basis':'pw','nspin':1,'input_identity':record['identity'],'workspace':record['workspace']}
            if capability=='relax':
                case.update(input_calculation='relax',rewrite_input_calculation=True)
            matrix.append(case)
    (root/'matrix.json').write_text(json.dumps(matrix,indent=2)+'\n')
    (root/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    receipt={'python':sys.executable,'forge':abacus_forge.__file__,'abacuslite':abacuslite.__file__,'versions':{n:md.version(n) for n in ('abacus-forge','abacuslite','atst-tools','pytest')},'repo_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=args.repo,text=True).strip()}
    env=os.environ.copy()
    env.pop('PYTHONPATH',None)
    env.update(ABACUS_FORGE_INSTALLED_PACKAGE_ONLY='1',ABACUS_FORGE_ABACUSLITE_PATH=str(Path(abacuslite.__file__).parent.parent),ABACUS_FORGE_ABACUSLITE_REQUIRE_FULL_MATRIX='1',ABACUS_FORGE_ABACUSLITE_DUAL_TRACK_MATRIX=json.dumps(matrix),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    command=[sys.executable,'-m','pytest','-q','--run-real-smoke','tests/real_smoke/test_abacuslite_dual_track.py','--basetemp',str(root/'pytest')]
    receipt['command']=command
    result=subprocess.run(command,cwd=args.repo,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (root/'pytest.log').write_text(result.stdout)
    receipt['exit_code']=result.returncode
    (root/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(result.stdout)
    return result.returncode

if __name__=='__main__':
    raise SystemExit(main())
