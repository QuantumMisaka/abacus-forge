from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from ase import Atoms
from ase.io import write as ase_write

from abacus_forge.cli import main
from abacus_forge.input_io import read_input, read_kpt
from abacus_forge.structure import AbacusStructure
from abacus_forge.workspace import Workspace


def test_cli_prepare_collect_and_export(tmp_path: Path, capsys) -> None:
    structure = Atoms(symbols=["Si"], positions=[[0.0, 0.0, 0.0]])
    structure_path = tmp_path / "Si.xyz"
    ase_write(structure_path, structure)
    workspace = tmp_path / "cli-case"

    assert (
        main(
            [
                "prepare",
                str(workspace),
                "--structure",
                str(structure_path),
                "--structure-format",
                "xyz",
                "--task",
                "relax",
                "--ensure-pbc",
                "--parameter",
                "ecutwfc=70",
                "--kpoint",
                "3",
                "--kpoint",
                "3",
                "--kpoint",
                "1",
            ]
        )
        == 0
    )
    capsys.readouterr()

    (workspace / "outputs").mkdir(exist_ok=True)
    (workspace / "outputs" / "stdout.log").write_text("TOTAL ENERGY = -6.4\nSCF CONVERGED\n", encoding="utf-8")
    (workspace / "outputs" / "stderr.log").write_text("", encoding="utf-8")

    assert main(["collect", str(workspace), "--json"]) == 0
    collect_out = capsys.readouterr().out
    payload = json.loads(collect_out)
    assert payload["status"] == "completed"
    assert payload["structure_snapshot"] is not None
    assert payload["inputs_snapshot"]["INPUT"]["calculation"] == "relax"

    export_path = tmp_path / "cli-result.json"
    assert main(["export", str(workspace), "--output", str(export_path)]) == 0
    capsys.readouterr()
    assert json.loads(export_path.read_text(encoding="utf-8"))["metrics"]["total_energy"] == -6.4


def test_cli_new_tasks_help_and_dry_run(tmp_path: Path, capsys) -> None:
    structure = Atoms(symbols=["Si"], positions=[[0.0, 0.0, 0.0]], cell=[4, 4, 4], pbc=True)
    structure_path = tmp_path / "Si.xyz"
    ase_write(structure_path, structure)

    with pytest.raises(SystemExit) as help_exit:
        main(["cell-relax", "--help"])
    assert help_exit.value.code == 0
    capsys.readouterr()

    assert (
        main(
            [
                "md",
                str(tmp_path / "md-dry-run"),
                "--structure",
                str(structure_path),
                "--structure-format",
                "xyz",
                "--dry-run",
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "dry-run"
    assert payload["inputs_snapshot"]["INPUT"]["calculation"] == "md"


def test_cli_composite_eos_prepare(tmp_path: Path, capsys) -> None:
    structure = Atoms(symbols=["Al"], positions=[[0.0, 0.0, 0.0]], cell=[4, 4, 4], pbc=True)
    structure_path = tmp_path / "Al.xyz"
    ase_write(structure_path, structure)
    workspace = tmp_path / "eos-cli"

    assert main(["prepare", str(workspace), "--structure", str(structure_path), "--structure-format", "xyz"]) == 0
    capsys.readouterr()
    assert main(["eos", "prepare", str(workspace), "--start", "0.975", "--end", "1.025", "--step", "0.025", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "prepared"
    assert payload["summary"]["count"] == 3


def test_cli_and_workflow_collection_payloads_are_mappable(tmp_path: Path, capsys) -> None:
    workspace = Workspace(tmp_path / "shared-case")
    workspace.ensure_layout()
    workspace.write_text("outputs/stdout.log", "TOTAL ENERGY = -5.0\nFERMI ENERGY = 1.1\nSCF CONVERGED\n")
    workspace.write_text("outputs/stderr.log", "")

    assert main(["collect", str(workspace.root), "--json"]) == 0
    cli_payload = json.loads(capsys.readouterr().out)

    from abacus_forge.api import collect

    workflow_payload = collect(workspace).to_dict()
    assert cli_payload["status"] == workflow_payload["status"]
    assert cli_payload["metrics"] == workflow_payload["metrics"]
    assert set(cli_payload["artifacts"]) == set(workflow_payload["artifacts"])


def test_cli_collect_supports_explicit_output_log_override(tmp_path: Path, capsys) -> None:
    workspace = Workspace(tmp_path / "cli-output-override")
    workspace.ensure_layout()
    workspace.write_text("inputs/INPUT", "INPUT_PARAMETERS\ncalculation scf\n")
    workspace.write_text("outputs/OUT.ABACUS/running_scf.log", "TOTAL ENERGY = -5.0\nSCF CONVERGED\n")
    workspace.write_text("outputs/stdout.log", "Atomic-orbital Based Ab-initio\ntotal 3.0\n")
    workspace.write_text("outputs/custom.log", "Atomic-orbital Based Ab-initio\ntotal 7.0\n")
    workspace.write_text("outputs/stderr.log", "")

    assert main(["collect", str(workspace.root), "--output-log", "outputs/custom.log", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["metrics"]["total_time"] == 7.0
    assert payload["diagnostics"]["output_log_reason"] == "override"


def test_cli_prepare_supports_element_level_magmoms(tmp_path: Path, capsys) -> None:
    structure = Atoms(
        symbols=["Fe", "Fe", "O"],
        positions=[[0.0, 0.0, 0.0], [1.4, 1.4, 1.4], [0.7, 0.7, 0.7]],
        cell=[[4.2, 0.0, 0.0], [0.0, 4.2, 0.0], [0.0, 0.0, 4.2]],
        pbc=[True, True, True],
    )
    structure_path = tmp_path / "FeO.cif"
    ase_write(structure_path, structure)
    workspace = tmp_path / "cli-magmom-case"

    assert (
        main(
            [
                "prepare",
                str(workspace),
                "--structure",
                str(structure_path),
                "--task",
                "scf",
                "--magmom",
                "Fe=3.0",
                "--magmom",
                "O=0.5",
            ]
        )
        == 0
    )
    capsys.readouterr()

    recovered = AbacusStructure.from_input(workspace / "inputs" / "STRU", structure_format="stru")
    assert recovered.atoms.get_chemical_symbols() == ["O", "Fe", "Fe"]
    assert recovered.atoms.get_initial_magnetic_moments().tolist() == [0.5, 3.0, 3.0]


def test_cli_modify_stru_supports_afm_and_site_magmoms(tmp_path: Path, capsys) -> None:
    structure = Atoms(
        symbols=["Fe", "Fe", "O"],
        positions=[[0.0, 0.0, 0.0], [1.4, 1.4, 1.4], [0.7, 0.7, 0.7]],
        cell=[[4.2, 0.0, 0.0], [0.0, 4.2, 0.0], [0.0, 0.0, 4.2]],
        pbc=[True, True, True],
    )
    source = tmp_path / "source.cif"
    output = tmp_path / "STRU.modified"
    ase_write(source, structure)

    assert (
        main(
            [
                "modify-stru",
                str(source),
                "--output",
                str(output),
                "--magmom",
                "Fe=3.0",
                "--magmom",
                "O=0.5",
                "--afm",
            ]
        )
        == 0
    )
    capsys.readouterr()

    recovered = AbacusStructure.from_input(output, structure_format="stru")
    assert recovered.atoms.get_chemical_symbols() == ["O", "Fe", "Fe"]
    assert recovered.atoms.get_initial_magnetic_moments().tolist() == [0.5, 3.0, -3.0]

    output_site = tmp_path / "STRU.site.modified"
    assert (
        main(
            [
                "modify-stru",
                str(source),
                "--output",
                str(output_site),
                "--site-magmoms",
                "1.0,1.5,-0.2",
            ]
        )
        == 0
    )
    capsys.readouterr()

    recovered_site = AbacusStructure.from_input(output_site, structure_format="stru")
    assert recovered_site.atoms.get_chemical_symbols() == ["O", "Fe", "Fe"]
    assert recovered_site.atoms.get_initial_magnetic_moments().tolist() == [-0.2, 1.0, 1.5]


def test_cli_modify_input_updates_and_removes_keys(tmp_path: Path, capsys) -> None:
    source = tmp_path / "INPUT"
    output = tmp_path / "INPUT.modified"
    source.write_text("INPUT_PARAMETERS\ncalculation scf\necutwfc 80\nsmearing_sigma 0.02\n", encoding="utf-8")

    assert (
        main(
            [
                "modify-input",
                str(source),
                "--output",
                str(output),
                "--set",
                "calculation=relax",
                "--set",
                "force_thr=1e-4",
                "--remove",
                "smearing_sigma",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert read_input(output) == {
        "calculation": "relax",
        "ecutwfc": "80",
        "force_thr": "1e-4",
    }


def test_cli_modify_input_rejects_invalid_assignment(tmp_path: Path) -> None:
    source = tmp_path / "INPUT"
    source.write_text("INPUT_PARAMETERS\ncalculation scf\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="invalid parameter"):
        main(
            [
                "modify-input",
                str(source),
                "--output",
                str(tmp_path / "INPUT.modified"),
                "--set",
                "bad-assignment",
            ]
        )


def test_cli_modify_kpt_supports_mesh_and_line_modes(tmp_path: Path, capsys) -> None:
    mesh_source = tmp_path / "KPT"
    mesh_source.write_text("K_POINTS\n0\nGamma\n2 2 2 0 0 0\n", encoding="utf-8")
    mesh_output = tmp_path / "KPT.mesh.modified"

    assert (
        main(
            [
                "modify-kpt",
                str(mesh_source),
                "--output",
                str(mesh_output),
                "--mode",
                "mesh",
                "--mesh",
                "6",
                "6",
                "1",
                "--shifts",
                "1",
                "1",
                "1",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert read_kpt(mesh_output) == {"mode": "mesh", "mesh": [6, 6, 1], "shifts": [1, 1, 1]}

    line_source = tmp_path / "KPT.line"
    line_source.write_text("K_POINTS\n10\nLine\n0.0 0.0 0.0 #Gamma\n0.5 0.0 0.0 #X\n", encoding="utf-8")
    line_output = tmp_path / "KPT.line.modified"

    assert (
        main(
            [
                "modify-kpt",
                str(line_source),
                "--output",
                str(line_output),
                "--mode",
                "line",
                "--segments",
                "20",
                "--point",
                "0,0,0:Gamma",
                "--point",
                "0.5,0.5,0:M",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert read_kpt(line_output) == {
        "mode": "line",
        "segments": 20,
        "points": [
            {"coords": [0.0, 0.0, 0.0], "label": "Gamma"},
            {"coords": [0.5, 0.5, 0.0], "label": "M"},
        ],
    }


def test_cli_scf_task_runs_end_to_end(tmp_path: Path, capsys) -> None:
    executable = _write_fake_abacus(
        tmp_path / "fake-scf",
        stdout_lines=[
            "TOTAL ENERGY = -6.8",
            "FERMI ENERGY = 1.5",
            "SCF CONVERGED",
        ],
    )
    structure = Atoms(symbols=["Si"], positions=[[0.0, 0.0, 0.0]])
    structure_path = tmp_path / "Si.xyz"
    ase_write(structure_path, structure)

    assert (
        main(
            [
                "scf",
                str(tmp_path / "scf-task"),
                "--structure",
                str(structure_path),
                "--structure-format",
                "xyz",
                "--ensure-pbc",
                "--executable",
                str(executable),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["metrics"]["total_energy"] == -6.8
    assert payload["diagnostics"]["task"] == "scf"


def test_cli_band_task_requires_explicit_points(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="explicit line-mode KPT points"):
        main(["band", str(tmp_path / "band-task")])


def test_cli_dos_task_enables_pdos_outputs_and_export(tmp_path: Path, capsys) -> None:
    executable = _write_fake_abacus(
        tmp_path / "fake-dos",
        stdout_lines=[
            "TOTAL ENERGY = -7.2",
            "SCF CONVERGED",
        ],
        extra_writes={
            "outputs/DOS1_smearing.dat": "-5.0 0.1\n0.0 1.3\n",
            "outputs/PDOS": "# species projected DOS\nFe 0.7\nO 0.3\n",
            "outputs/TDOS": "# total DOS\n-1.0 0.2\n0.0 1.0\n",
        },
    )
    structure = Atoms(
        symbols=["Fe", "O"],
        positions=[[0.0, 0.0, 0.0], [1.5, 1.5, 1.5]],
        cell=[[4.0, 0.0, 0.0], [0.0, 4.0, 0.0], [0.0, 0.0, 4.0]],
        pbc=[True, True, True],
    )
    structure_path = tmp_path / "FeO.cif"
    ase_write(structure_path, structure)
    export_path = tmp_path / "dos-task.json"

    assert (
        main(
            [
                "dos",
                str(tmp_path / "dos-task"),
                "--structure",
                str(structure_path),
                "--executable",
                str(executable),
                "--output",
                str(export_path),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "completed"
    assert payload["inputs_snapshot"]["INPUT"]["out_dos"] == "1"
    assert "out_pdos" not in payload["inputs_snapshot"]["INPUT"]
    assert payload["metrics"]["dos_family_summary"]["projected_dos"]["pdos_file"].endswith("PDOS")
    assert json.loads(export_path.read_text(encoding="utf-8"))["metrics"]["dos_summary"]["points"] == 2


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
        body.extend(
            [
                f"path = workspace / {relative_path!r}",
                "path.parent.mkdir(parents=True, exist_ok=True)",
                f"path.write_text({content!r}, encoding='utf-8')",
            ]
        )
    body.extend([f"print({line!r})" for line in stdout_lines])
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path
