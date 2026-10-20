"""Consume a legacy spin-density/charge-diff JSON result without guessing names.

This is a caller example, not a new Forge result protocol or workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from abacus_forge.cube import CubeData
from abacus_forge.property_manifest import PropertyManifest, PropertyManifestEntry


def consume(result: dict, workspace: Path) -> dict:
    """Select the derived cube and its actual sources, then read its grid."""
    payload = result.get("diagnostics", {}).get("property_manifest")
    if payload is None:
        raise ValueError("property manifest unavailable; inspect producer diagnostics")
    manifest = PropertyManifest.from_dict(payload)
    if manifest.task not in {"spin-density", "charge-diff"}:
        raise ValueError("this example consumes spin-density or charge-diff")
    if manifest.missing:
        raise ValueError("missing property artifacts; inspect manifest.missing")
    outputs = [
        entry for entry in manifest.outputs
        if entry.kind == "cube" and entry.origin == "derived" and entry.role == "output"
    ]
    if len(outputs) != 1:
        raise ValueError("expected exactly one derived cube")
    output = outputs[0]
    inputs = {entry.artifact_id: entry for entry in manifest.inputs}
    sources = [inputs[source_id] for source_id in output.source_artifact_ids]
    root = Path(workspace).resolve()

    def checked_file(entry: PropertyManifestEntry) -> Path:
        path = (root / entry.path_rel).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"artifact unavailable: {entry.path_rel}")
        # Detect a changed file between producer and consumer; the manifest
        # describes those bytes, not whichever file later occupies the path.
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if path.stat().st_size != entry.size_bytes or digest.hexdigest() != entry.sha256:
            raise ValueError(f"artifact changed since production: {entry.path_rel}")
        return path

    for entry in sources:
        checked_file(entry)
    cube = CubeData.from_file(checked_file(output))
    return {
        "task": manifest.task,
        "derived_cube": output.path_rel,
        "grid_shape": list(cube.data.shape),
        "sources": [{"path_rel": entry.path_rel, "spin": entry.spin} for entry in sources],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True, help="legacy post --json output")
    args = parser.parse_args()
    try:
        result = json.loads(args.result.read_text(encoding="utf-8"))
        print(json.dumps(consume(result, args.workspace), allow_nan=False))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
