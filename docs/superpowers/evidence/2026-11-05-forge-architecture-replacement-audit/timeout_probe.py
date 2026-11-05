"""Offline reproduction of launcher descendants surviving a Forge timeout."""
import json
import pathlib
import sys
import tempfile
import time

import abacus_forge
from abacus_forge.runner import LocalRunner
from abacus_forge.workspace import Workspace

root = pathlib.Path(tempfile.mkdtemp(prefix="forge-timeout-audit-"))
child = (
    "import pathlib,time; time.sleep(0.7); "
    "pathlib.Path('late-engine-output').write_text('written after timeout')"
)
parent = (
    "import pathlib,subprocess,sys,time; "
    "p=subprocess.Popen([sys.executable,'-c'," + repr(child) + "],"
    "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
    "pathlib.Path('probe-child.pid').write_text(str(p.pid)); time.sleep(5)"
)
result = LocalRunner(
    executable=sys.executable, extra_args=["-c", parent], timeout_seconds=0.2,
).run(Workspace(root))
marker = root / "inputs" / "late-engine-output"
print(json.dumps({
    "forge_module": abacus_forge.__file__, "workspace": str(root),
    "result_status": result.status,
    "failure_class": result.diagnostics["failure_class"],
    "marker_at_return": marker.exists(),
}))
time.sleep(0.8)
print(json.dumps({
    "marker_after_return": marker.exists(),
    "content": marker.read_text() if marker.exists() else None,
}))
pid = (root / "inputs" / "probe-child.pid").read_text()
status = pathlib.Path("/proc") / pid / "stat"
state = status.read_text().rsplit(")", 1)[1].split()[0] if status.exists() else "exited"
print(json.dumps({"probe_child_state": state, "probe_child_running": state not in {"Z", "exited"}}))
