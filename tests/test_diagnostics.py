"""Read-only installed-environment diagnostics and CLI entry behavior."""

from __future__ import annotations

import json
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from abacus_forge.cli import main

pytestmark = pytest.mark.cli


def test_doctor_default_human_and_json_need_no_engine(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert main(["doctor"]) == 0
    human = capsys.readouterr()
    assert "Forge environment" in human.out
    assert "No external engine is required" in human.out
    assert human.err == ""
    assert list(tmp_path.iterdir()) == []
    assert main(["doctor", "--json"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert document["schema_version"] == "forge.environment/v1"
    assert document["status"] == "ready"
    assert document["python"]["version"]
    assert document["distribution"]["name"] == "abacus-forge"
    assert {item["name"] for item in document["dependencies"]} >= {"ase", "dpdata", "matplotlib", "numpy", "pymatgen"}
    assert document["executables"] == []
    assert document["assets"] == []
    assert list(tmp_path.iterdir()) == []


def test_doctor_explicit_program_and_assets_are_read_only(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    program = tmp_path / "engine"
    program.write_text("#!/bin/sh\nprintf bad > should-not-run\n", encoding="utf-8")
    program.chmod(0o755)
    asset = tmp_path / "Si.upf"
    asset.write_text("pseudo", encoding="utf-8")
    before = sorted(path.name for path in tmp_path.iterdir())
    assert main(["doctor", "--json", "--executable", str(program), "--asset", str(asset)]) == 0
    document = json.loads(capsys.readouterr().out)
    assert document["executables"][0]["status"] == "present"
    assert document["assets"][0]["status"] == "present"
    assert sorted(path.name for path in tmp_path.iterdir()) == before
    assert not (tmp_path / "should-not-run").exists()

    assert main(["doctor", "--json", "--executable", "not-a-real-engine-987654", "--asset", "missing.upf"]) == 3
    document = json.loads(capsys.readouterr().out)
    assert document["status"] == "missing"
    assert document["executables"][0]["status"] == "missing"
    assert document["assets"][0]["status"] == "missing"
    assert all(item["suggestion"] for item in (*document["executables"], *document["assets"]))
    assert sorted(path.name for path in tmp_path.iterdir()) == before


def test_doctor_core_dependency_missing_exits_three(capsys, monkeypatch):
    import abacus_forge.diagnostics as diagnostics

    original = diagnostics.metadata.version
    def missing_numpy(name):
        if name == "numpy":
            raise diagnostics.metadata.PackageNotFoundError(name)
        return original(name)
    monkeypatch.setattr(diagnostics.metadata, "version", missing_numpy)
    assert main(["doctor", "--json"]) == 3
    document = json.loads(capsys.readouterr().out)
    assert next(item for item in document["dependencies"] if item["name"] == "numpy")["status"] == "missing"


def test_doctor_bad_options_return_two(capsys):
    assert main(["doctor", "--unknown"]) == 2
    assert "unrecognized arguments" in capsys.readouterr().err
    assert main(["doctor", "--asset"]) == 2
    assert "expected one argument" in capsys.readouterr().err


def test_version_and_stdlib_entry_without_numpy_import(capsys, tmp_path):
    assert main(["--version"]) == 0
    assert "0.1.0" in capsys.readouterr().out
    script = (
        "import builtins,json; original=builtins.__import__; "
        "builtins.__import__=lambda name,*a,**k: "
        "(_ for _ in ()).throw(ImportError('blocked numpy')) if name=='numpy' else original(name,*a,**k); "
        "from abacus_forge.cli import main; raise SystemExit(main(['doctor','--json']))"
    )
    env = os.environ.copy()
    installed_only = env.get("ABACUS_FORGE_INSTALLED_PACKAGE_ONLY") == "1"
    env["PYTHONPATH"] = "" if installed_only else str(Path(__file__).parents[1] / "src")
    command = [sys.executable, *(["-I"] if installed_only else []), "-c", script]
    completed = subprocess.run(command, cwd=tmp_path, env=env,
                               text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["schema_version"] == "forge.environment/v1"


def test_top_level_help_discovers_new_entrypoints_without_legacy_imports(capsys, monkeypatch):
    cli_module = importlib.import_module("abacus_forge.cli")
    monkeypatch.setattr(cli_module, "_load_legacy_dependencies", lambda: (_ for _ in ()).throw(AssertionError("legacy loaded")))
    with pytest.raises(SystemExit) as help_exit:
        main(["--help"])
    assert help_exit.value.code == 0
    help_text = capsys.readouterr().out
    assert "doctor" in help_text
    assert "--version" in help_text
    assert main(["doctor", "--help"]) == 0
    assert "--asset" in capsys.readouterr().out


def test_machine_discovery_dispatches_without_legacy_loader(capsys, monkeypatch):
    cli_module = importlib.import_module("abacus_forge.cli")
    monkeypatch.setattr(cli_module, "_load_legacy_dependencies", lambda: (_ for _ in ()).throw(AssertionError("legacy loaded")))
    assert main(["capabilities"]) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == "forge.capabilities/v1"
    assert main(["schema", "bec", "postprocess"]) == 0
    assert json.loads(capsys.readouterr().out)["capability"] == "bec"
