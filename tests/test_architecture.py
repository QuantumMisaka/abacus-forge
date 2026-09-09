from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from tests.support.process import run_cli


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src" / "abacus_forge"
README = ROOT / "README.md"

# These are upper-layer integrations.  Forge may provide compatibility
# fixtures for some of them under tests, but production source must not import
# them or any of their submodules.
FORBIDDEN_ROOTS = frozenset(
    {
        "aiida",
        "abacustest",
        "abacus_agent_tools",
        "abacusagent",
        "atp",
        "atst_tools",
        "mcp",
        "fastmcp",
        "asterfire",
        "bohrium",
        "dpdispatcher",
        "dflow",
        "slurm",
        "sacct",
        "salloc",
        "sbatch",
        "scancel",
        "scontrol",
        "sinfo",
        "srun",
        "sstat",
        "squeue",
        "pbs",
        "qdel",
        "qsub",
        "qstat",
        "bjobs",
        "bkill",
        "bsub",
        "lsf",
    }
)


def forbidden_imports(source_root: Path, forbidden_roots: set[str] | frozenset[str]) -> list[str]:
    """Return deterministic path:line:module violations for Python source."""
    violations: list[str] = []
    for path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                if module.split(".", 1)[0] in forbidden_roots:
                    violations.append(f"{path.as_posix()}:{node.lineno}:{module}")
    return sorted(violations)


def test_production_modules_do_not_import_forbidden_upper_layers() -> None:
    violations = forbidden_imports(SOURCE_ROOT, FORBIDDEN_ROOTS)
    assert violations == []


def test_machine_help_exposes_frozen_commands() -> None:
    operation_help = run_cli("operation", "--help")
    assert operation_help.returncode == 0
    assert operation_help.stderr == ""
    assert "--request" in operation_help.stdout
    assert "--stdin" in operation_help.stdout
    for operation in ("prepare", "modify", "execute", "collect", "postprocess", "export"):
        assert operation in operation_help.stdout
    for command in ("schema", "capabilities"):
        command_help = run_cli(command, "--help")
        assert command_help.returncode == 0
        assert command_help.stderr == ""
        assert "usage:" in command_help.stdout


def test_forbidden_imports_reports_import_forms_in_sorted_path_order(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    (source_root / "b.py").write_text("import mcp.server\n", encoding="utf-8")
    (source_root / "a.py").write_text("from aiida.orm import Node\n", encoding="utf-8")
    (tmp_path / "outside.py").write_text("import aiida\n", encoding="utf-8")

    violations = forbidden_imports(source_root, FORBIDDEN_ROOTS)

    assert violations == [
        f"{(source_root / 'a.py').as_posix()}:1:aiida.orm",
        f"{(source_root / 'b.py').as_posix()}:1:mcp.server",
    ]


def test_machine_discovery_advertises_experimental_scf_relax_and_atst_neb() -> None:
    result = run_cli("capabilities")
    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert [item["name"] for item in payload["capabilities"]] == ["scf", "relax", "cell-relax", "atst-neb"]
    for capability in payload["capabilities"][:3]:
        assert capability["maturity"] == "experimental"
        assert capability["engine"] == "abacus"
        assert capability["operations"] == ["prepare", "modify", "execute", "collect"]
        assert capability["artifact_roles"] == ["input", "provenance_manifest", "output"]
    atst = payload["capabilities"][3]
    assert atst["maturity"] == "experimental"
    assert atst["engine"] == "atst-tools"
    assert atst["operations"] == ["prepare", "execute", "postprocess"]
    assert atst["artifact_roles"] == ["input", "output"]


def test_readme_machine_request_examples_parse_through_real_cli(tmp_path: Path) -> None:
    text = README.read_text(encoding="utf-8")
    section_match = re.search(r"^## Agent-first CLI\n(?P<section>.*?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    assert section_match is not None
    section = section_match.group("section")
    assert "operation execute --request request.json" in section
    assert "operation execute --stdin" in section

    examples = re.findall(r"```json\n(?P<payload>\{.*?\})\n```", section, flags=re.DOTALL)
    assert len(examples) == 2
    for index, example in enumerate(examples):
        payload = json.loads(example)
        request = json.dumps(payload)
        if index == 0:
            request_file = tmp_path / "request.json"
            request_file.write_text(request, encoding="utf-8")
            result = run_cli("operation", "execute", "--request", request_file, cwd=tmp_path)
        else:
            result = run_cli("operation", "execute", "--stdin", cwd=tmp_path, input_text=request)
        assert result.returncode == 0
        assert result.stderr == ""
        assert json.loads(result.stdout)["envelope"]["operation"] == "execute"
