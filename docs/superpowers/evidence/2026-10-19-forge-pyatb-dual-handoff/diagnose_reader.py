"""Isolate the installed PyATB reader from Forge and from file naming."""
import argparse
import hashlib
import importlib.metadata as metadata
import inspect
import json
from pathlib import Path
import shutil
import tempfile
from pyatb.io.abacus_read_xr import abacus_readHR

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--develop-hr', type=Path, required=True)
parser.add_argument('--lts-hr', type=Path, required=True)
args = parser.parse_args()
reader = Path(inspect.getfile(abacus_readHR))
report = {'pyatb_version': metadata.version('pyatb'), 'reader': str(reader),
          'reader_sha256': hashlib.sha256(reader.read_bytes()).hexdigest(), 'cases': {}}
for name, source in [('develop', args.develop_hr), ('lts', args.lts_hr)]:
    with tempfile.TemporaryDirectory() as temporary:
        renamed = Path(temporary) / 'data-HR-sparse_SPIN0.csr'
        shutil.copyfile(source, renamed)
        assert renamed.read_bytes() == source.read_bytes()
        try:
            abacus_readHR(nspin=1, HR_route=str(renamed), HR_unit='Ry')
            result = {'success': True}
        except Exception as error:
            result = {'success': False, 'error_type': type(error).__name__, 'error': str(error)}
        report['cases'][name] = {**result, 'source': str(source),
            'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'tested_filename': renamed.name}
assert report['cases']['lts']['success']
assert report['cases']['develop']['error_type'] == 'IndexError'
print(json.dumps(report, indent=2))
