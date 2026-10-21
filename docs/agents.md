# Use Forge from a general Agent

The machine CLI accepts one typed operation per request. The Agent chooses and sequences operations; Forge records each operation in its workspace. Begin with [the installed-package quickstart](quickstart.md) to create `forge-first-run/scf`, then run the following from the directory containing `forge-first-run`:

```bash
abacus-forge capabilities > capabilities.json
abacus-forge schema scf execute > scf-execute-schema.json
```

Both files are JSON. Check that the `scf` descriptor lists `execute`, inspect the discovered request schema, and construct a fresh lowercase UUIDv4 for every call. The following complete example uses only the installed command, the existing prepared workspace, and Python's standard library:

```bash
python - <<'PY'
import json
import subprocess
from uuid import uuid4

capabilities = json.load(open("capabilities.json", encoding="utf-8"))
assert any(item["name"] == "scf" and "execute" in item["operations"]
           for item in capabilities["capabilities"])
schema = json.load(open("scf-execute-schema.json", encoding="utf-8"))
assert schema["request_schema"]["properties"]["dry_run"]["type"] == "boolean"

def call(operation, **fields):
    request = {"schema_version": "forge.request/v1", "operation": operation,
               "operation_id": str(uuid4()), "workspace_rel": "forge-first-run/scf", **fields}
    result = subprocess.run(["abacus-forge", "operation", operation, "--stdin"],
                            input=json.dumps(request), text=True, capture_output=True)
    response = json.loads(result.stdout)
    return result.returncode, request, response

code, dry_request, dry = call("execute", executable="abacus", dry_run=True)
assert code == 0 and dry["envelope"]["status"] == {
    "execution": "skipped", "collection": "not_collected", "scientific": "unassessed"
}
code, absent_request, absent = call(
    "execute", executable="forge-example-missing-abacus-executable", dry_run=False)
assert code == 3 and absent["error"]["class"] == "precondition.missing"
code, collect_request, collected = call("collect")
assert code == 0
assert collected["envelope"]["status"]["collection"] in ("partial", "missing_output")
print(json.dumps({"dry_run": dry["envelope"]["status"],
                  "missing_executable": absent["error"]["class"],
                  "collect_without_engine": collected["envelope"]["status"]["collection"]}, indent=2))
PY
```

The missing-executable request performs preflight and does not start an engine. The collect request sees no ABACUS output from the dry-run; its process exit code is zero, but its collection state is incomplete. A missing `inputs/INPUT`, `STRU`, or `KPT` on a non-dry execute similarly returns `precondition.missing` (exit 3). Schema/path errors exit 2; unexpected internal failures exit 5. Inspect `error.class` on errors and `envelope.status` plus required metrics/artifacts on outcomes. `scientific=unassessed` is an explicit absence of scientific acceptance.

Use workspace-relative paths in requests and keep the process working directory stable. Operation IDs are unique per admitted request; retries should inspect the prior outcome and choose a new operation ID only for a genuinely new call. The CLI persists append-only events and artifact references in the workspace. For direct Python integration, the equivalent typed API is `ScfServiceSet.default(workspace_root=...).execute.execute(ScfExecuteRequest(...))`; the quickstart demonstrates this call. Other capabilities have different operation sets and inputs, so discover each schema before constructing its request. The current descriptors mark these typed capabilities experimental.
