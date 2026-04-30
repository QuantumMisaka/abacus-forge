from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from ase import Atoms

from abacus_forge.tasks import run_band, run_dos, run_scf, run_task


def test_run_scf_executes_prepare_run_collect_and_export(tmp_path: Path) -> None:
    executable = _write_fake_abacus(
        tmp_path / "fake-abacus",
        stdout_lines=[
            "TOTAL ENERGY = -8.4",
            "FERMI ENERGY = 2.1",
            "SCF CONVERGED",
        ],
    )
    export_path = tmp_path / "scf-result.json"
    structure = Atoms(symbols=["Si"], positions=[[0.0, 0.0, 0.0]])

    result = run_scf(
        tmp_path / "scf-case",
        structure=structure,
        ensure_pbc=True,
        executable=str(executable),
        export_destination=export_path,
    )

    assert result.status == "completed"
    assert result.metrics["total_energy"] == -8.4
    assert result.diagnostics["task"] == "scf"
    assert result.inputs_snapshot["INPUT"]["calculation"] == "scf"
    assert json.loads(export_path.read_text(encoding="utf-8"))["metrics"]["total_energy"] == -8.4


def test_run_task_rejects_band_without_explicit_line_kpoints(tmp_path: Path) -> None:
    structure = Atoms(symbols=["Si"], positions=[[0.0, 0.0, 0.0]])

    with pytest.raises(ValueError, match="explicit line-mode KPT points"):
        run_task(tmp_path / "band-case", task="band", structure=structure)


def test_run_band_writes_line_mode_kpt_and_collects(tmp_path: Path) -> None:
    executable = _write_fake_abacus(
        tmp_path / "fake-band",
        stdout_lines=[
            "TOTAL ENERGY = -9.2",
            "BAND GAP = 1.3",
            "SCF CONVERGED",
        ],
        extra_writes={
            "outputs/BANDS_1.dat": "0.0 -1.0 0.5\n1.0 -0.9 0.8\n",
        },
    )
    structure = Atoms(
        symbols=["Si", "Si"],
        positions=[[0.0, 0.0, 0.0], [1.3, 1.3, 1.3]],
        cell=[[5.2, 0.0, 0.0], [0.0, 5.2, 0.0], [0.0, 0.0, 5.2]],
        pbc=[True, True, True],
    )

    result = run_band(
        tmp_path / "band-case",
        structure=structure,
        executable=str(executable),
        line_segments=24,
        line_kpoints=[
            {"coords": [0.0, 0.0, 0.0], "label": "Gamma"},
            {"coords": [0.5, 0.0, 0.0], "label": "X"},
        ],
    )

    assert result.status == "completed"
    assert result.inputs_snapshot["INPUT"]["calculation"] == "nscf"
    assert result.inputs_snapshot["INPUT"]["out_band"] == "1"
    assert result.inputs_snapshot["KPT_PARSED"]["mode"] == "line"
    assert result.inputs_snapshot["KPT_PARSED"]["segments"] == 24
    assert result.metrics["band_summary"]["num_points"] == 2


def test_run_dos_enables_pdos_outputs_in_same_task(tmp_path: Path) -> None:
    executable = _write_fake_abacus(
        tmp_path / "fake-dos",
        stdout_lines=[
            "TOTAL ENERGY = -7.8",
            "SCF CONVERGED",
        ],
        extra_writes={
            "outputs/DOS1_smearing.dat": "-5.0 0.1\n0.0 1.2\n",
            "outputs/PDOS": "# species projected DOS\nFe 0.6\nO 0.4\n",
            "outputs/TDOS": "# total DOS\n-1.0 0.1\n0.0 1.0\n",
        },
    )
    structure = Atoms(
        symbols=["Fe", "O"],
        positions=[[0.0, 0.0, 0.0], [1.5, 1.5, 1.5]],
        cell=[[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0]],
        pbc=[True, True, True],
    )

    result = run_dos(
        tmp_path / "dos-case",
        structure=structure,
        executable=str(executable),
    )

    assert result.status == "completed"
    assert result.inputs_snapshot["INPUT"]["out_dos"] == "1"
    assert result.inputs_snapshot["INPUT"]["out_pdos"] == "1"
    assert result.metrics["dos_summary"]["points"] == 2
    assert result.metrics["pdos_summary"]["pdos_file"].endswith("PDOS")


def _write_fake_abacus(
    path: Path,
    *,
    stdout_lines: list[str],
    extra_writes: dict[str, str] | None = None,
) -> Path:
    extra_writes = extra_writes or {}
    body = [
        "#!/usr/bin/env python3",
        "from pathlib import Path",
        "import sys",
        "args = sys.argv[1:]",
        "input_dir = Path('.')",
        "if '--input-dir' in args:",
        "    input_dir = Path(args[args.index('--input-dir') + 1])",
        "workspace = input_dir.parent",
    ]
    for relative_path, content in extra_writes.items():
        literal_path = repr(relative_path)
        literal_content = repr(content)
        body.extend(
            [
                f"path = workspace / {literal_path}",
                "path.parent.mkdir(parents=True, exist_ok=True)",
                f"path.write_text({literal_content}, encoding='utf-8')",
            ]
        )
    body.extend([f"print({line!r})" for line in stdout_lines])
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path
