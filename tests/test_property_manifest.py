from __future__ import annotations

import json
from pathlib import Path

import pytest

from abacus_forge.contracts import ArtifactRecord
from abacus_forge.property_manifest import (
    PROPERTY_MANIFEST_SCHEMA_VERSION,
    PropertyArtifactSpec,
    PropertyManifest,
    PropertyManifestEntry,
    build_property_manifest,
)
from abacus_forge.workspace import Workspace


def _entry(**overrides: object) -> PropertyManifestEntry:
    values: dict[str, object] = {
        "path_rel": "inputs/OUT.ABACUS/SPIN1_CHG.cube",
        "kind": "cube",
        "role": "input",
        "origin": "source",
        "spin": "unknown",
        "artifact_id": "artifact-source",
        "sha256": "a" * 64,
        "size_bytes": 4,
        "media_type": "application/octet-stream",
    }
    values.update(overrides)
    return PropertyManifestEntry(**values)


def test_property_manifest_round_trip_and_derived_cube_refs() -> None:
    manifest = PropertyManifest(
        task="spin-density",
        inputs=(_entry(spin="up"),),
        outputs=(
            _entry(
                path_rel="reports/spin_density.cube",
                role="output",
                origin="derived",
                spin="shared",
                artifact_id="artifact-diff",
                sha256="b" * 64,
                source_artifact_ids=("artifact-source", "artifact-down"),
            ),
        ),
        missing=(),
    )

    restored = PropertyManifest.from_dict(manifest.to_dict())

    assert restored == manifest
    assert manifest.to_dict()["schema_version"] == PROPERTY_MANIFEST_SCHEMA_VERSION
    json.dumps(manifest.to_dict(), allow_nan=False)


def test_report_derived_entry_may_omit_source_refs() -> None:
    entry = _entry(
        path_rel="reports/metrics_spin_density.json",
        kind="report",
        role="output",
        origin="derived",
        media_type="application/json",
        artifact_id="artifact-report",
        sha256="c" * 64,
        size_bytes=2,
    )

    assert entry.to_dict()["kind"] == "report"
    assert "source_artifact_ids" not in entry.to_dict()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("path_rel", "../escape"),
        ("path_rel", "/absolute"),
        ("kind", "potential"),
        ("role", "source"),
        ("origin", "computed"),
        ("spin", "total"),
        ("parse_status", "invalid"),
        ("sha256", "not-a-digest"),
        ("size_bytes", -1),
    ],
)
def test_manifest_entry_rejects_invalid_values(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        _entry(**{field: value})


def test_missing_entry_rejects_present_artifact_facts() -> None:
    with pytest.raises(ValueError, match="missing entries"):
        _entry(reason="missing")

    missing = PropertyManifestEntry(
        path_rel="charge-density/scf/inputs/OUT.ABACUS/SPIN1_CHG.cube",
        kind="cube",
        role="input",
        origin="source",
        reason="missing",
    )
    assert missing.to_dict() == {
        "path_rel": "charge-density/scf/inputs/OUT.ABACUS/SPIN1_CHG.cube",
        "kind": "cube",
        "role": "input",
        "origin": "source",
        "spin": "unknown",
        "reason": "missing",
    }


def test_derived_cube_requires_nonempty_source_refs() -> None:
    with pytest.raises(ValueError, match="source_artifact_ids"):
        _entry(path_rel="reports/diff.cube", role="output", origin="derived")


def test_manifest_from_dict_rejects_unknown_fields_and_missing_arrays() -> None:
    payload = PropertyManifest(task="charge-density").to_dict()
    payload["extra"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        PropertyManifest.from_dict(payload)

    del payload["extra"]
    del payload["missing"]
    with pytest.raises(ValueError, match="missing fields"):
        PropertyManifest.from_dict(payload)


def test_build_property_manifest_classifies_explicit_paths_and_missing(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path).ensure_layout()
    cube = workspace.root / "charge-density/scf/inputs/OUT.ABACUS/SPIN1_CHG.cube"
    cube.parent.mkdir(parents=True)
    cube.write_text("cube", encoding="utf-8")
    artifact = ArtifactRecord(
        id="artifact-source",
        path_rel=cube.relative_to(workspace.root).as_posix(),
        role="output",
        stage="collect",
        sha256="a" * 64,
        size_bytes=4,
    )

    manifest = build_property_manifest(
        workspace.root,
        task="charge-density",
        inputs=(
            PropertyArtifactSpec(cube, "cube", "input", "source", "unknown"),
            PropertyArtifactSpec(
                workspace.root / "charge-density/scf/inputs/OUT.ABACUS/MISSING.cube",
                "cube",
                "input",
                "source",
                "unknown",
            ),
        ),
        outputs=(),
        artifacts=(artifact,),
    )

    assert [entry.path_rel for entry in manifest.inputs] == [artifact.path_rel]
    assert manifest.inputs[0].artifact_id == artifact.id
    assert manifest.missing[0].reason == "missing"
    assert "artifact_id" not in manifest.missing[0].to_dict()


def test_property_artifact_spec_rejects_string_source_paths() -> None:
    with pytest.raises(ValueError, match="source_paths"):
        PropertyArtifactSpec(
            path="reports/derived.cube",
            kind="cube",
            role="output",
            origin="derived",
            source_paths="inputs/source.cube",
        )


def test_build_property_manifest_preserves_lexical_path_for_escaped_symlink(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path / "workspace").ensure_layout()
    outside = tmp_path / "outside.cube"
    outside.write_text("outside", encoding="utf-8")
    link = workspace.root / "outputs" / "escaped.cube"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")

    manifest = build_property_manifest(
        workspace.root,
        task="charge-density",
        inputs=(PropertyArtifactSpec(link, "cube", "input", "source"),),
        outputs=(),
        artifacts=(),
    )

    assert manifest.missing[0].path_rel == "outputs/escaped.cube"
    assert manifest.missing[0].reason == "escaped"


def test_build_property_manifest_classifies_directory_as_unavailable(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path).ensure_layout()
    directory = workspace.root / "outputs" / "not-a-file"
    directory.mkdir(parents=True)

    manifest = build_property_manifest(
        workspace.root,
        task="charge-density",
        inputs=(PropertyArtifactSpec(directory, "cube", "input", "source"),),
        outputs=(),
        artifacts=(),
    )

    assert manifest.missing[0].path_rel == "outputs/not-a-file"
    assert manifest.missing[0].reason == "unavailable"


def test_build_property_manifest_classifies_incomplete_artifact_projection_as_unavailable(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path).ensure_layout()
    cube = workspace.root / "outputs" / "unhashed.cube"
    cube.write_text("cube", encoding="utf-8")
    artifact = ArtifactRecord(
        id="artifact-unhashed",
        path_rel="outputs/unhashed.cube",
        role="output",
        stage="collect",
        sha256=None,
        size_bytes=cube.stat().st_size,
    )

    manifest = build_property_manifest(
        workspace.root,
        task="charge-density",
        inputs=(PropertyArtifactSpec(cube, "cube", "input", "source"),),
        outputs=(),
        artifacts=(artifact,),
    )

    assert manifest.missing[0].path_rel == "outputs/unhashed.cube"
    assert manifest.missing[0].reason == "unavailable"


def test_build_property_manifest_links_present_derived_cube_to_same_result_sources(tmp_path: Path) -> None:
    workspace = Workspace(tmp_path).ensure_layout()
    source_paths = (workspace.root / "inputs" / "up.cube", workspace.root / "inputs" / "down.cube")
    derived_path = workspace.root / "reports" / "spin_density.cube"
    for path, content in ((source_paths[0], "up"), (source_paths[1], "down"), (derived_path, "diff")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    artifacts = tuple(
        ArtifactRecord(
            id=f"artifact-{index}",
            path_rel=path.relative_to(workspace.root).as_posix(),
            role="output",
            stage="collect",
            sha256=f"{index + 1:x}" * 64,
            size_bytes=path.stat().st_size,
        )
        for index, path in enumerate((*source_paths, derived_path))
    )

    manifest = build_property_manifest(
        workspace.root,
        task="spin-density",
        inputs=tuple(PropertyArtifactSpec(path, "cube", "input", "source") for path in source_paths),
        outputs=(PropertyArtifactSpec(
            derived_path,
            "cube",
            "output",
            "derived",
            spin="shared",
            source_paths=source_paths,
        ),),
        artifacts=artifacts,
    )

    assert manifest.outputs[0].source_artifact_ids == ("artifact-0", "artifact-1")
