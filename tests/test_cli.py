from __future__ import annotations

import json
from pathlib import Path

from abacus_forge.cli import main


def test_cli_prepare_collect_and_export(tmp_path: Path, capsys) -> None:
    structure = tmp_path / "Si.stru"
    structure.write_text("ATOMIC_SPECIES\nSi 28.085 Si.upf\n", encoding="utf-8")
    workspace = tmp_path / "cli-case"

    assert main([
        "prepare",
        str(workspace),
        "--structure",
        str(structure),
        "--parameter",
        "calculation=scf",
        "--kpoint",
        "3",
        "--kpoint",
        "3",
        "--kpoint",
        "1",
    ]) == 0
    capsys.readouterr()

    (workspace / "outputs").mkdir(exist_ok=True)
    (workspace / "outputs" / "stdout.log").write_text("TOTAL ENERGY = -6.4\nSCF CONVERGED\n", encoding="utf-8")
    (workspace / "outputs" / "stderr.log").write_text("", encoding="utf-8")

    assert main(["collect", str(workspace), "--json"]) == 0
    collect_out = capsys.readouterr().out
    assert json.loads(collect_out)["status"] == "completed"

    export_path = tmp_path / "cli-result.json"
    assert main(["export", str(workspace), "--output", str(export_path)]) == 0
    capsys.readouterr()
    assert json.loads(export_path.read_text(encoding="utf-8"))["metrics"]["total_energy"] == -6.4
