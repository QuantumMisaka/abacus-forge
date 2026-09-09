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


def import_graph(source_root: Path) -> dict[str, set[str]]:
    """Resolve absolute and package-relative imports, including re-exports."""
    graph: dict[str, set[str]] = {}
    for path in sorted(source_root.rglob("*.py")):
        parts = path.relative_to(source_root).with_suffix("").parts
        module = ".".join(("abacus_forge", *parts))
        package = module.rsplit(".", 1)[0]
        if parts[-1] == "__init__":
            module = package
        imports: set[str] = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    parent = package.split(".")[:len(package.split(".")) - node.level + 1]
                    base = ".".join((*parent, *([base] if base else [])))
                # A named import can be either a symbol or a submodule.
                # Prefer the submodule when present, avoiding false traversal
                # of the package's compatibility facade for sibling imports.
                for alias in node.names:
                    candidate = f"{base}.{alias.name}"
                    relative = candidate.removeprefix("abacus_forge.").replace(".", "/")
                    if (source_root / f"{relative}.py").is_file() or (source_root / relative / "__init__.py").is_file():
                        imports.add(candidate)
                    else:
                        imports.add(base)
        graph[module] = imports
    return graph


def dependency_violations(
    graph: dict[str, set[str]], roots: set[str],
    forbidden_modules: frozenset[str] = frozenset({"abacus_forge.api"}),
) -> list[str]:
    violations: set[str] = set()
    for root in sorted(roots):
        pending = [(root,)]
        visited: set[str] = set()
        while pending:
            chain = pending.pop()
            module = chain[-1]
            if module in visited:
                continue
            visited.add(module)
            if module in forbidden_modules or module.split(".", 1)[0] in FORBIDDEN_ROOTS:
                violations.add(" -> ".join(chain))
                continue
            pending.extend((*chain, target) for target in sorted(graph.get(module, ())))
    return sorted(violations)


def test_typed_services_and_neutral_core_do_not_depend_on_legacy_api() -> None:
    graph = import_graph(SOURCE_ROOT)
    roots = {
        f"abacus_forge.{name}" for name in (
            "services", "atst_neb", "preparation", "collection",
            "service_support", "compatibility_records", "modify",
            "collection_results", "relax_results",
        )
    }
    assert roots <= graph.keys()
    assert dependency_violations(graph, roots) == []
    assert dependency_violations(
        graph, roots - {"abacus_forge.services"},
        frozenset({"abacus_forge.api", "abacus_forge.services"}),
    ) == []
    support = ast.parse((SOURCE_ROOT / "service_support.py").read_text(encoding="utf-8"))
    request_types = {
        alias.name for node in ast.walk(support) if isinstance(node, ast.ImportFrom)
        for alias in node.names if alias.name.endswith("Request")
    }
    assert request_types == set(), "generic support must not select capability request types"


def test_dependency_gate_follows_relative_reexports_and_forbidden_transitive_imports(tmp_path: Path) -> None:
    (tmp_path / "services.py").write_text("from . import bridge\n", encoding="utf-8")
    (tmp_path / "bridge.py").write_text("from abacus_forge.api import prepare\nimport mcp.server\n", encoding="utf-8")
    assert dependency_violations(import_graph(tmp_path), {"abacus_forge.services"}) == [
        "abacus_forge.services -> abacus_forge.bridge -> abacus_forge.api",
        "abacus_forge.services -> abacus_forge.bridge -> mcp.server",
    ]


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


def test_machine_discovery_advertises_experimental_scf_relax_atst_neb_md_and_postprocess() -> None:
    result = run_cli("capabilities")
    assert result.returncode == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert [item["name"] for item in payload["capabilities"]] == [
        "scf", "relax", "cell-relax", "atst-neb", "md", "band", "dos",
    ]
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
    md = payload["capabilities"][4]
    assert md["maturity"] == "experimental"
    assert md["engine"] == "abacus"
    assert md["operations"] == ["prepare", "modify", "execute", "collect"]
    assert md["artifact_roles"] == ["input", "provenance_manifest", "output"]


def test_machine_discovery_advertises_only_band_and_dos_postprocess_operations() -> None:
    payload = json.loads(run_cli("capabilities").stdout)
    descriptors = {item["name"]: item for item in payload["capabilities"]}
    assert descriptors["band"]["operations"] == ["postprocess"]
    assert descriptors["dos"]["operations"] == ["postprocess"]
    for name in ("band", "dos"):
        descriptor = descriptors[name]
        assert descriptor["engine"] == "abacus"
        assert descriptor["maturity"] == "experimental"
        assert descriptor["artifact_roles"] == ["input", "output"]
        assert set(descriptor["inputs"]) == {"postprocess"}


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
