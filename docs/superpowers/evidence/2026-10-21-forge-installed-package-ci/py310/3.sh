python - <<'PY'
import json
import os
from pathlib import Path
import tomli

project = tomli.loads(Path("pyproject.toml").read_text())["project"]
requirement, = project["optional-dependencies"]["abacuslite"]
assert requirement.startswith("abacuslite=="), requirement
version = requirement.removeprefix("abacuslite==")
record_path, = Path("docs/superpowers/evidence").glob(
    f"*-forge-abacuslite-{version}-package-provenance.json"
)
release = json.loads(record_path.read_text())["abacuslite_release"]
assert release["package_version"] == version
with open(os.environ["GITHUB_OUTPUT"], "a") as output:
    output.write(f"commit={release['tag_commit']}\n")
PY
