"""Outer acceptance harness; consumes an existing complete SCF, never runs ABACUS."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

import numpy as np


def manifest(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("python", "scf", "reference", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items()
           if k not in {"PYTHONPATH", "ABACUS_FORGE_ROOT"}}
    env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MPLBACKEND="Agg")
    source_manifest = manifest(args.scf)
    (args.output / "scf-sha256.json").write_text(json.dumps(source_manifest, indent=2))
    results = {}
    for left, right in (("all", "all"), ("s", "s"), ("s", "p"), ("p", "s"), ("p", "p")):
        name = left + "-" + right
        workspace = args.output / name
        shutil.copytree(args.scf, workspace / "scf")
        request = dict(schema_version="forge.request/v1", capability="cohp",
                       operation="postprocess", operation_id=str(uuid.uuid4()),
                       workspace_rel=".", method="iao", scf_dir_rel="scf",
                       atom_i_index=1, atom_j_index=2, atom_i_orbs=left,
                       atom_j_orbs=right, output_dir_rel="outputs/cohp")
        (workspace / "request.json").write_text(json.dumps(request, indent=2))
        process = subprocess.run([str(args.python), "-m", "abacus_forge.cli",
                                  "operation", "postprocess", "--stdin"],
                                 input=json.dumps(request), cwd=workspace, env=env,
                                 text=True, capture_output=True, timeout=300)
        (workspace / "response.json").write_text(process.stdout)
        (workspace / "stderr.txt").write_text(process.stderr)
        assert process.returncode == 0, process.stdout + process.stderr
        body = json.loads(process.stdout)["envelope"]
        assert body["status"]["collection"] == "complete", body
        assert body["status"]["scientific"] == "unassessed"
        for record in body["artifacts"]:
            rel = Path(record["path_rel"])
            assert not rel.is_absolute() and ".." not in rel.parts
            path = (workspace / rel).resolve(strict=True)
            path.relative_to(workspace.resolve())
            assert path.stat().st_size == record["size_bytes"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
        assert len(list((workspace / "reports/events").glob("*.json"))) == 1
        assert (workspace / "reports/forge-workspace.json").is_file()
        assert manifest(workspace / "scf") == source_manifest
        meta_path, = (workspace / "outputs/cohp").glob("*.meta.json")
        metadata = json.loads(meta_path.read_text())
        results[name] = {"icohp_ev": metadata["icohp"]["icohp"],
                         "bond": metadata["bond"], "nk_full": metadata["nk_full"],
                         "artifact_count": len(body["artifacts"]),
                         "status": body["status"]}
        if name == "all-all":
            reference = json.loads((args.reference / "cohp_i1_j2.meta.json").read_text())
            assert abs(metadata["icohp"]["icohp"] - reference["icohp"]["icohp"]) < 1e-10
            curve, = (workspace / "outputs/cohp").glob("*_EminusEf.dat")
            actual = np.loadtxt(curve)
            original = np.loadtxt(args.reference / "cohp_i1_j2_EminusEf.dat")
            np.testing.assert_allclose(actual, original, rtol=1e-10, atol=1e-10)
            results[name]["reference_curve_max_abs_diff"] = float(np.max(np.abs(actual-original)))
        print(name, results[name]["icohp_ev"], flush=True)
    residual = sum(results[key]["icohp_ev"] for key in ("s-s", "s-p", "p-s", "p-p")) - results["all-all"]["icohp_ev"]
    assert abs(residual) < 1e-10, residual
    (args.output / "summary.json").write_text(json.dumps(
        {"cases": results, "orbital_partition_residual_ev": residual,
         "scf_file_count": len(source_manifest), "python": str(args.python)}, indent=2))


if __name__ == "__main__":
    main()
