"""Stage candidate PyATB Python source with an installed native runtime.

Run with the Python interpreter from the existing PyATB environment.
This does not build or install a wheel and does not modify that environment.
"""
import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import shutil
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True, help='Candidate src/pyatb directory')
parser.add_argument('--output', type=Path, required=True, help='New runtime directory')
args = parser.parse_args()
source = args.source.resolve(strict=True)
root = args.output.resolve()
root.mkdir(parents=True, exist_ok=False)
distribution = metadata.distribution('pyatb')
installed = Path(distribution.locate_file('pyatb'))
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
shutil.copytree(source, root/'pyatb', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
natives = list(installed.glob('interface_python*.so'))
assert len(natives) == 1
shutil.copyfile(natives[0], root/'pyatb'/natives[0].name)
shutil.copytree(installed.parent/'pyatb.libs', root/'pyatb.libs')
launcher = root/'pyatb-candidate'
launcher.write_text('#!'+sys.executable+'\nimport sys\nsys.path.insert(0, '+repr(str(root))+')\nfrom pyatb.main import main\nsys.exit(main())\n')
launcher.chmod(0o755)
binding = {'kind': 'complete candidate Python source with reused native extension; not a rebuilt wheel',
    'installed_version': distribution.version, 'python': sys.executable,
    'source_files': {str(p.relative_to(source)): sha(p) for p in source.rglob('*.py')},
    'native_extension_sha256': sha(natives[0]),
    'bundled_libraries': {p.name: sha(p) for p in (root/'pyatb.libs').iterdir() if p.is_file()},
    'launcher': str(launcher), 'launcher_sha256': sha(launcher)}
(root/'binding.json').write_text(json.dumps(binding, indent=2)+'\n')
print(launcher)
