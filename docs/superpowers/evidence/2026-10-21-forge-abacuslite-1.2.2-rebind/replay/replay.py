"""Offline Forge parser replay of eight previously executed ABACUS workspaces.

Run after both installed environments exist:

  OLD=/home/james/scratch/forge-closeout-20261021/candidate-env/bin/python
  NEW=/home/james/scratch/forge-abacuslite-122-20261021/venv/bin/python
  "$OLD" -I replay.py run --old-python "$OLD" --new-python "$NEW"

Only old, already generated real logs are parsed. This script never executes
ABACUS. It snapshots each source workspace and verifies file hashes before and
after all parser calls. Each worker runs under an installed Python with -I.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
MATRIX = Path("/home/james/scratch/forge-dual-track-atst230-20261019/matrix-run/matrix.json")
SOURCES = Path("/home/james/scratch/forge-dual-track-atst230-20261019/matrix-run/pytest/test_native_and_abacuslite_col0")
CAPABILITIES = ("scf", "relax", "cell-relax", "md")
TRACKS = ("develop", "lts")
TOL_ENERGY_EV = 5e-3
TOL_FORCE_EV_ANG = 1e-3
TOL_STRESS_KBAR = 1e-3


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite": str(value)}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "tolist"):
        return _json_safe(value.tolist())
    return str(value)


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest(root: Path) -> dict[str, dict]:
    return {path.relative_to(root).as_posix(): {"sha256": _sha(path), "size_bytes": path.stat().st_size}
            for path in sorted(root.rglob("*")) if path.is_file()}


def _projection(capability: str, result: Any, workspace_rel: str) -> Any:
    from abacus_forge import collection_results, md_results, relax_results

    if capability in ("relax", "cell-relax"):
        return relax_results.collection_envelope(result, workspace_rel)
    if capability == "md":
        return md_results.collection_envelope(result, workspace_rel)
    return collection_results.collection_envelope(result, workspace_rel)


def _worker(args: argparse.Namespace) -> int:
    from abacus_forge.collection import collect_contained
    from abacus_forge.workspace import Workspace

    workspace = args.workspace.resolve()
    before = _manifest(workspace)
    result = collect_contained(
        Workspace(workspace), parser_backend=args.backend,
        output_version=args.output_version if args.backend == "abacuslite" else None,
    )
    envelope = _projection(args.capability, result, workspace.name)
    after = _manifest(workspace)
    if before != after:
        raise AssertionError("collector or another process changed snapshot files")
    try:
        forge_version = importlib.metadata.version("abacus-forge")
    except importlib.metadata.PackageNotFoundError:
        forge_version = None
    try:
        abacuslite_version = importlib.metadata.version("abacuslite")
    except importlib.metadata.PackageNotFoundError:
        abacuslite_version = None
    payload = {
        "source_kind": "offline_replay_of_existing_real_ABACUS_logs",
        "interpreter": sys.executable,
        "isolated": sys.flags.isolated == 1,
        "forge_version": forge_version,
        "abacuslite_version": abacuslite_version,
        "workspace": str(workspace),
        "capability": args.capability,
        "requested_backend": args.backend,
        "requested_output_version": args.output_version if args.backend == "abacuslite" else None,
        "collection_result": result.to_dict(),
        "typed_envelope": envelope.to_dict(),
        "snapshot_manifest": before,
        "snapshot_unchanged": True,
    }
    _write(args.out, payload)
    return 0


def _matrix() -> list[dict]:
    cases = json.loads(MATRIX.read_text(encoding="utf-8"))
    if len(cases) != 8:
        raise AssertionError(f"expected 8 matrix entries, got {len(cases)}")
    observed = [(case.get("track"), case.get("capability")) for case in cases]
    expected = [(track, capability) for track in TRACKS for capability in CAPABILITIES]
    if observed != expected:
        raise AssertionError(f"matrix order changed: {observed}")
    return cases


def _snapshot_sources(cases: list[dict], output: Path) -> list[dict]:
    snapshots = output / "snapshots"
    snapshots.mkdir()
    report = []
    for index, case in enumerate(cases):
        capability = case["capability"]
        source = SOURCES / f"{index}-{capability}-native"
        if not source.is_dir():
            raise FileNotFoundError(f"missing prior executed workspace: {source}")
        destination = snapshots / f"{index}-{case['track']}-{capability}"
        shutil.copytree(source, destination, symlinks=False)
        source_manifest = _manifest(source)
        copied_manifest = _manifest(destination)
        if source_manifest != copied_manifest:
            raise AssertionError(f"snapshot copy differs from original: {source}")
        report.append({"case_index": index, "track": case["track"], "capability": capability,
                       "engine_version_of_existing_log": case["version"],
                       "engine_executable_sha256_from_matrix": case["executable_sha256"],
                       "input_identity_from_matrix": case["input_identity"],
                       "original_workspace": str(source), "snapshot_workspace": str(destination),
                       "manifest": copied_manifest})
    return report


def _tolerance(name: str) -> float:
    lower = name.lower()
    if "force" in lower:
        return TOL_FORCE_EV_ANG
    if "stress" in lower or lower in ("pressure", "pressures", "virial", "virials"):
        return TOL_STRESS_KBAR
    if any(token in lower for token in ("energy", "fermi", "etot")):
        return TOL_ENERGY_EV
    return 0.0


def _recursive_diff(a: Any, b: Any, path: str, tolerance: float, differences: list[dict], counts: dict) -> None:
    if isinstance(a, dict) or isinstance(b, dict):
        if not isinstance(a, dict) or not isinstance(b, dict):
            differences.append({"path": path, "left": a, "right": b, "reason": "type"})
            return
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                differences.append({"path": f"{path}.{key}", "left": a.get(key), "right": b.get(key), "reason": "presence"})
            else:
                _recursive_diff(a[key], b[key], f"{path}.{key}", tolerance, differences, counts)
        return
    if isinstance(a, list) or isinstance(b, list):
        if not isinstance(a, list) or not isinstance(b, list) or len(a) != len(b):
            differences.append({"path": path, "left_shape": len(a) if isinstance(a, list) else None,
                                "right_shape": len(b) if isinstance(b, list) else None, "reason": "shape"})
            return
        for index, (left, right) in enumerate(zip(a, b)):
            _recursive_diff(left, right, f"{path}[{index}]", tolerance, differences, counts)
        return
    if isinstance(a, bool) or isinstance(b, bool):
        counts["fields"] += 1
        if a is not b:
            differences.append({"path": path, "left": a, "right": b, "reason": "boolean"})
        return
    if isinstance(a, (int, float)) or isinstance(b, (int, float)):
        counts["numeric_values"] += 1
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            differences.append({"path": path, "left": a, "right": b, "reason": "type"})
            return
        difference = abs(a - b)
        if difference > tolerance:
            differences.append({"path": path, "left": a, "right": b,
                                "abs_difference": difference, "tolerance": tolerance, "reason": "numeric"})
        return
    counts["fields"] += 1
    if a != b:
        differences.append({"path": path, "left": a, "right": b, "reason": "value"})


def _artifact_signature(envelope: dict) -> dict:
    return {item["path_rel"]: {key: item.get(key) for key in ("role", "stage", "availability", "media_type", "sha256", "size_bytes")}
            for item in envelope.get("artifacts", [])}


def _metric_records(envelope: dict) -> dict:
    return {item["name"]: item for item in envelope.get("metrics", [])}


def _stable_diagnostics(envelope: dict) -> dict:
    diagnostics = dict(envelope.get("diagnostics", {}))
    for name in ("parser", "native_final_energy_markers", "legacy_metrics"):
        diagnostics.pop(name, None)
    return diagnostics


def _compare(left: dict, right: dict, label: str) -> dict:
    lhs = left["typed_envelope"]
    rhs = right["typed_envelope"]
    differences: list[dict] = []
    counts = {"numeric_values": 0, "fields": 0}
    for name in ("status", "checks", "warnings"):
        _recursive_diff(lhs.get(name), rhs.get(name), f"envelope.{name}", 0.0, differences, counts)
    _recursive_diff(_stable_diagnostics(lhs), _stable_diagnostics(rhs), "envelope.stable_diagnostics", 0.0, differences, counts)
    _recursive_diff(_artifact_signature(lhs), _artifact_signature(rhs), "artifacts", 0.0, differences, counts)
    left_metrics, right_metrics = _metric_records(lhs), _metric_records(rhs)
    _recursive_diff(sorted(left_metrics), sorted(right_metrics), "metric_names", 0.0, differences, counts)
    for name in sorted(set(left_metrics) & set(right_metrics)):
        a, b = left_metrics[name], right_metrics[name]
        for key in ("kind", "unit", "source_artifact_id"):
            _recursive_diff(a.get(key), b.get(key), f"metric.{name}.{key}", 0.0, differences, counts)
        _recursive_diff(a.get("value"), b.get("value"), f"metric.{name}.value", _tolerance(name), differences, counts)
    # Complex forces/stresses and MD frame series live in CollectionResult
    # metrics, while the typed envelope places them in legacy_metrics. Compare
    # the raw metric map so array/frame shape and every value are covered.
    raw_left = left["collection_result"].get("metrics", {})
    raw_right = right["collection_result"].get("metrics", {})
    _recursive_diff(sorted(raw_left), sorted(raw_right), "raw_metric_names", 0.0, differences, counts)
    for name in sorted(set(raw_left) & set(raw_right)):
        _recursive_diff(raw_left[name], raw_right[name], f"raw_metric.{name}",
                        _tolerance(name), differences, counts)
    for name in ("status", "inputs_snapshot", "structure_snapshot", "final_structure_snapshot"):
        _recursive_diff(left["collection_result"].get(name), right["collection_result"].get(name),
                        f"collection.{name}", 0.0, differences, counts)
    # The raw nested result also exposes MD thermodynamic series and all
    # forces/stresses; metric names missing in one backend remain differences.
    return {"pair": label, "equivalent": not differences, "compared": counts,
            "left_backend": left["requested_backend"], "right_backend": right["requested_backend"],
            "left_abacuslite_version": left["abacuslite_version"],
            "right_abacuslite_version": right["abacuslite_version"],
            "left_collection_status": lhs["status"], "right_collection_status": rhs["status"],
            "metric_names_left": sorted(left_metrics), "metric_names_right": sorted(right_metrics),
            "differences": differences}


def _summarize(case_reports: list[dict], comparisons: list[dict]) -> str:
    lines = ["# abacuslite 1.2.0 → 1.2.2 offline real-log replay", "",
             "These are previously executed ABACUS v3.11.0-beta8 / v3.10.1 logs, not new engine executions.",
             "Each of eight source workspaces was copied and hash checked before/after collection.",
             "The four parser combinations per cell ran with installed Python `-I`.", "",
             "| Cell | Track | Capability | Old/new native | Old/new abacuslite | New native/1.2.2 | Status |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for case in case_reports:
        index = case["index"]
        pairs = [item for item in comparisons if item["case_index"] == index]
        by_label = {item["pair"]: item for item in pairs}
        def state(name: str) -> str:
            item = by_label[name]
            return "same" if item["equivalent"] else f"DIFF ({len(item['differences'])})"
        lines.append(f"| {index} | {case['track']} | {case['capability']} | {state('old-native:new-native')} | "
                     f"{state('old-optional:new-optional')} | {state('new-native:new-optional')} | "
                     f"{case['new_optional_status']} |")
    lines.extend(["", "Numerical tolerances mirror the prior real parity gate: energy/Fermi 0.005 eV, "
                  "force 0.001 eV/Å, stress/pressure 0.001 kbar. Structure and status are exact.",
                  "Full collection results, typed envelopes, commands, stdout/stderr, file hashes, and "
                  "field-level differences are in this directory's JSON files.",
                  "This replay does not establish compatibility with newly executed ABACUS, different basis/spin, "
                  "or scientific acceptance."])
    return "\n".join(lines) + "\n"


def _run(args: argparse.Namespace) -> int:
    # Preserve the venv/bin/python path. Resolving its symlink can escape the
    # virtual environment and silently select the system interpreter.
    old_python, new_python = args.old_python.absolute(), args.new_python.absolute()
    for interpreter in (old_python, new_python):
        if not interpreter.is_file():
            raise FileNotFoundError(f"installed interpreter missing: {interpreter}")
    if args.output.exists():
        raise FileExistsError(f"output directory must be new: {args.output}")
    cases = _matrix()
    args.output.mkdir(parents=True)
    snapshots = _snapshot_sources(cases, args.output)
    _write(args.output / "source-matrix.json", cases)
    _write(args.output / "source-snapshot-manifests.json", snapshots)
    case_reports: list[dict] = []
    comparisons: list[dict] = []
    for index, case in enumerate(cases):
        snapshot = Path(snapshots[index]["snapshot_workspace"])
        case_dir = args.output / "results" / f"{index}-{case['track']}-{case['capability']}"
        case_dir.mkdir(parents=True)
        versions: dict[str, dict] = {}
        for label, interpreter, backend in (
            ("old-native", old_python, "native"),
            ("old-optional", old_python, "abacuslite"),
            ("new-native", new_python, "native"),
            ("new-optional", new_python, "abacuslite"),
        ):
            result_file = case_dir / f"{label}.json"
            command = [str(interpreter), "-I", str(Path(__file__).resolve()), "worker",
                       "--workspace", str(snapshot), "--capability", case["capability"],
                       "--backend", backend, "--output-version", case["version"],
                       "--out", str(result_file)]
            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            process = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=120)
            (case_dir / f"{label}.stdout.txt").write_text(process.stdout, encoding="utf-8")
            (case_dir / f"{label}.stderr.txt").write_text(process.stderr, encoding="utf-8")
            _write(case_dir / f"{label}.command.json", {"argv": command, "exit_code": process.returncode})
            if process.returncode or not result_file.is_file():
                raise RuntimeError(f"{case['track']}/{case['capability']} {label} failed; see {case_dir}")
            versions[label] = json.loads(result_file.read_text(encoding="utf-8"))
            if versions[label]["snapshot_manifest"] != snapshots[index]["manifest"]:
                raise AssertionError(f"{label} changed or saw different workspace files")
        if versions["old-optional"]["abacuslite_version"] != "1.2.0":
            raise AssertionError("old optional interpreter is not abacuslite 1.2.0")
        if versions["new-optional"]["abacuslite_version"] != "1.2.2":
            raise AssertionError("new optional interpreter is not abacuslite 1.2.2")
        for pair in ("old-native:new-native", "old-optional:new-optional",
                     "old-native:old-optional", "new-native:new-optional"):
            left, right = pair.split(":")
            compared = _compare(versions[left], versions[right], pair)
            compared.update(case_index=index, track=case["track"], capability=case["capability"])
            comparisons.append(compared)
        case_reports.append({"index": index, "track": case["track"], "capability": case["capability"],
                             "engine_version_of_existing_log": case["version"],
                             "old_optional_status": versions["old-optional"]["typed_envelope"]["status"],
                             "new_optional_status": versions["new-optional"]["typed_envelope"]["status"],
                             "old_forge_version": versions["old-native"]["forge_version"],
                             "new_forge_version": versions["new-native"]["forge_version"]})
    _write(args.output / "comparisons.json", comparisons)
    _write(args.output / "case-report.json", case_reports)
    report = _summarize(case_reports, comparisons)
    (args.output / "report.md").write_text(report, encoding="utf-8")
    print(report, end="")
    return 0 if all(item["equivalent"] for item in comparisons) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    run = commands.add_parser("run")
    run.add_argument("--old-python", type=Path, required=True)
    run.add_argument("--new-python", type=Path, required=True)
    run.add_argument("--output", type=Path, default=HERE / "run-001")
    worker = commands.add_parser("worker")
    worker.add_argument("--workspace", type=Path, required=True)
    worker.add_argument("--capability", choices=CAPABILITIES, required=True)
    worker.add_argument("--backend", choices=("native", "abacuslite"), required=True)
    worker.add_argument("--output-version", required=True)
    worker.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        return _worker(args) if args.mode == "worker" else _run(args)
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
