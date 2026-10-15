"""SAI outer harness: real execute, then explicit trajectory postprocess."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import uuid

import abacus_forge
import atst_tools
import numpy as np
from ase.io import read


root = Path.cwd()
resume = sys.argv[1:] == ["--resume-postprocess"]
assert not sys.argv[1:] or resume, "only --resume-postprocess is supported"
identity = {"python": sys.executable, "forge_module": abacus_forge.__file__,
            "atst_module": atst_tools.__file__,
            "versions": {name: importlib.metadata.version(name) for name in
                         ("abacus-forge", "atst-tools", "ase", "numpy", "scipy", "pydantic")}}
(root / "runtime.json").write_text(json.dumps(identity, indent=2))


def operation(name, *, receipt_prefix=None, **kwargs):
    request = dict(schema_version="forge.request/v1", capability="atst-neb",
                   operation=name, workspace_rel=".", operation_id=str(uuid.uuid4()), **kwargs)
    receipt = receipt_prefix or name
    (root / f"{receipt}-request.json").write_text(json.dumps(request, indent=2))
    process = subprocess.run([sys.executable, "-m", "abacus_forge.cli", "operation", name, "--stdin"],
                             input=json.dumps(request), text=True, capture_output=True, timeout=2100)
    (root / f"{receipt}-response.json").write_text(process.stdout)
    (root / f"{receipt}-stderr.txt").write_text(process.stderr)
    assert process.returncode == 0, process.stdout + process.stderr
    envelope = json.loads(process.stdout)["envelope"]
    assert envelope["status"]["execution"] == "completed", envelope
    assert envelope["status"]["scientific"] == "unassessed", envelope
    for record in envelope["artifacts"]:
        relative = Path(record["path_rel"])
        assert not relative.is_absolute() and ".." not in relative.parts
        path = (root / relative).resolve(strict=True)
        path.relative_to(root)
        assert path.stat().st_size == record["size_bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
    print(name, envelope["status"], flush=True)
    return envelope


if resume:
    executed = json.loads((root / "execute-response.json").read_text())["envelope"]
    assert executed["status"]["execution"] == "completed"
else:
    executed = operation("execute", config_path_rel="workflow.yaml", dry_run=False,
                         check_input=False, timeout_seconds=1800)
trajectory = root / "neb.traj"
frames = read(trajectory, index=":")
assert len(frames) >= 10 and len(frames) % 5 == 0, len(frames)
for atoms in frames:
    assert np.isfinite(atoms.get_potential_energy())
    assert np.isfinite(atoms.get_forces()).all()
suffix = "-corrected" if resume else ""
post = operation("postprocess", receipt_prefix="postprocess" + suffix,
                 trajectory_path_rel="neb.traj", n_max=3,
                 summary_path_rel=f"reports/atst/neb-summary{suffix}.json",
                 output_prefix=f"outputs/atst/neb-ts{suffix}",
                 write_latest=True, write_neb_init_chain=True, plot=True)
assert post["status"]["collection"] == "complete", post
events = sorted((root / "reports/events").glob("*.json"))
assert len(events) == (3 if resume else 2)
assert (root / "reports/forge-workspace.json").is_file()
manifest = json.loads((root / "atst_artifacts.json").read_text())
summary = {"frames": len(frames), "atoms_per_frame": len(frames[0]),
           "execution_status": executed["status"], "postprocess_status": post["status"],
           "trajectory_sha256": hashlib.sha256(trajectory.read_bytes()).hexdigest(),
           "audit_events": len(events), "atst_manifest": manifest}
(root / "acceptance.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary), flush=True)
