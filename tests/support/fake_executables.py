from __future__ import annotations

import os
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path


def _make_executable(path: Path, body: Sequence[str]) -> Path:
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def write_fake_abacus(
    path: Path,
    *,
    stdout_lines: Sequence[str],
    extra_writes: Mapping[str, str] | None = None,
    returncode: int = 0,
    include_omp_line: bool = False,
) -> Path:
    body = ["#!/usr/bin/env python3", "from pathlib import Path", "import os", "workspace = Path.cwd().parent"]
    if include_omp_line:
        body.append("print(f\"OMP = {os.environ.get('OMP_NUM_THREADS', 'missing')}\")")
    for relative_path, content in (extra_writes or {}).items():
        body.extend(
            [
                f"path = workspace / {relative_path!r}",
                "path.parent.mkdir(parents=True, exist_ok=True)",
                f"path.write_text({content!r}, encoding='utf-8')",
            ]
        )
    body.extend(f"print({line!r})" for line in stdout_lines)
    body.append(f"raise SystemExit({int(returncode)})")
    return _make_executable(path, body)


def write_fake_abacus_with_matrix(path: Path) -> Path:
    return write_fake_abacus(
        path,
        stdout_lines=["TOTAL ENERGY = -9.2", "FERMI ENERGY = 3.2", "SCF CONVERGED"],
        extra_writes={
            "inputs/OUT.ABACUS/data-HR-sparse_SPIN0.csr": "hr",
            "inputs/OUT.ABACUS/data-SR-sparse_SPIN0.csr": "sr",
            "inputs/OUT.ABACUS/data-rR-sparse.csr": "rr",
        },
    )


def write_fake_pyatb(path: Path) -> Path:
    return _make_executable(
        path,
        [
            "#!/usr/bin/env python3",
            "from pathlib import Path",
            "out = Path.cwd() / 'Out' / 'Band_Structure'",
            "out.mkdir(parents=True, exist_ok=True)",
            "(out / 'band_info.dat').write_text('Band gap is 2.5\\n', encoding='utf-8')",
            "(out / 'band.png').write_text('fake image', encoding='utf-8')",
            "print('pyatb done')",
        ],
    )
