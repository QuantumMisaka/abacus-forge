from __future__ import annotations

import pytest

from abacus_forge.pyatb_manifest import (
    PYATB_MANIFEST_SCHEMA_VERSION,
    PyatbManifest,
    PyatbManifestEntry,
    classify_pyatb_output,
)


def test_manifest_round_trip_and_known_output_mapping() -> None:
    kind, spin, media_type = classify_pyatb_output(
        "inputs/Out/Band_Structure/band_up.dat"
    )
    assert (kind, spin, media_type) == ("band_data", "up", "text/plain")
    manifest = PyatbManifest(
        inputs=(PyatbManifestEntry(
            path_rel="inputs/Input", kind="pyatb_input", spin="shared",
            artifact_id="input-input", sha256="a" * 64,
        ),),
        outputs=(),
        missing=(PyatbManifestEntry(
            path_rel="inputs/Out/Band_Structure/band.dat",
            kind="band_data", spin="unknown", reason="missing",
        ),),
    )
    assert manifest.to_dict()["schema_version"] == PYATB_MANIFEST_SCHEMA_VERSION
    assert PyatbManifest.from_dict(manifest.to_dict()) == manifest


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("inputs/STRU", ("structure", "shared", "text/plain")),
        ("inputs/data-HR-sparse_SPIN0.csr", ("matrix_hr", "shared", "application/octet-stream")),
        ("inputs/data-SR-sparse_SPIN0.csr", ("matrix_sr", "shared", "application/octet-stream")),
        ("inputs/data-rR-sparse.csr", ("matrix_rr", "shared", "application/octet-stream")),
        ("inputs/Input", ("pyatb_input", "shared", "text/plain")),
        ("inputs/KPT_band", ("kpoint_path", "shared", "text/plain")),
        ("inputs/Out/Band_Structure/band_info.dat", ("band_info", "unknown", "text/plain")),
        ("inputs/Out/Band_Structure/band.dat", ("band_data", "unknown", "text/plain")),
        ("inputs/Out/Band_Structure/band_dn.dat", ("band_data", "down", "text/plain")),
        ("inputs/Out/Band_Structure/band.png", ("band_plot", "unknown", "image/png")),
        ("inputs/Out/Band_Structure/band.pdf", ("band_plot", "unknown", "application/pdf")),
        ("inputs/Out/Band_Structure/input.json", ("run_input", "unknown", "application/json")),
        ("inputs/other.bin", ("other", "unknown", "application/octet-stream")),
    ],
)
def test_classify_pyatb_output_is_deterministic(path: str, expected: tuple[str, str, str]) -> None:
    assert classify_pyatb_output(path) == expected


@pytest.mark.parametrize("field,value", [("path_rel", "../escape"), ("path_rel", "/absolute")])
def test_manifest_entry_rejects_noncanonical_paths(field: str, value: str) -> None:
    with pytest.raises(ValueError):
        PyatbManifestEntry(path_rel=value, kind="other", spin="unknown")


def test_manifest_entry_rejects_invalid_kind_spin_and_hash() -> None:
    with pytest.raises(ValueError):
        PyatbManifestEntry(path_rel="outputs/x", kind="bogus", spin="unknown")
    with pytest.raises(ValueError):
        PyatbManifestEntry(path_rel="outputs/x", kind="other", spin="left")
    with pytest.raises(ValueError):
        PyatbManifestEntry(path_rel="outputs/x", kind="other", spin="unknown", sha256="bad")


def test_manifest_accepts_total_spin_and_round_trips_it() -> None:
    entry = PyatbManifestEntry(path_rel="outputs/band.dat", kind="band_data", spin="total")
    manifest = PyatbManifest(inputs=(), outputs=(entry,), missing=())
    restored = PyatbManifest.from_dict(manifest.to_dict())
    assert restored.outputs[0].spin == "total"


def test_manifest_from_dict_rejects_unknown_fields() -> None:
    payload = PyatbManifest(
        inputs=(), outputs=(), missing=()
    ).to_dict()
    payload["extra"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        PyatbManifest.from_dict(payload)
