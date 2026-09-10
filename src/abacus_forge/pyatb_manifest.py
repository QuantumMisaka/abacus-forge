"""Facts-only manifest projection for typed PyATB operations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from abacus_forge.contracts import (
    JSONValue,
    ArtifactRecord,
    _construct_strict,
    _freeze_json,
    _mapping_payload,
    _require_nonempty_string,
    canonical_relative_path,
)
from abacus_forge.errors import ForgeInternalError


PYATB_MANIFEST_SCHEMA_VERSION = "forge.pyatb-manifest/v1"
_KINDS = frozenset({
    "structure", "matrix_hr", "matrix_sr", "matrix_rr", "pyatb_input",
    "kpoint_path", "band_info", "band_data", "band_plot", "run_input", "other",
})
_SPINS = frozenset({"shared", "up", "down", "total", "unknown"})
_REASONS = frozenset({"missing", "escaped", "unavailable"})
_HASH = re.compile(r"^[0-9a-f]{64}$")


def _path(value: str, field_name: str = "path_rel") -> str:
    try:
        normalized = canonical_relative_path(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a canonical relative path") from error
    if normalized == ".":
        raise ValueError(f"{field_name} must identify a file")
    return normalized


def _optional_path(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    return _path(value, field_name)


def _optional_hash(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
    return value


@dataclass(frozen=True, slots=True)
class PyatbManifestEntry:
    path_rel: str
    kind: str
    spin: str
    artifact_id: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    media_type: str | None = None
    source_path_rel: str | None = None
    handoff_mode: str | None = None
    source_sha256: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path_rel", _path(self.path_rel))
        if self.kind not in _KINDS:
            raise ValueError(f"kind must be one of: {', '.join(sorted(_KINDS))}")
        if self.spin not in _SPINS:
            raise ValueError("spin must be one of: down, shared, total, unknown, up")
        if self.artifact_id is not None:
            _require_nonempty_string(self.artifact_id, "artifact_id")
        object.__setattr__(self, "sha256", _optional_hash(self.sha256, "sha256"))
        if self.size_bytes is not None and (
            isinstance(self.size_bytes, bool) or not isinstance(self.size_bytes, int) or self.size_bytes < 0
        ):
            raise ValueError("size_bytes must be a non-negative integer")
        if self.media_type is not None:
            _require_nonempty_string(self.media_type, "media_type")
        object.__setattr__(self, "source_path_rel", _optional_path(self.source_path_rel, "source_path_rel"))
        object.__setattr__(self, "source_sha256", _optional_hash(self.source_sha256, "source_sha256"))
        if self.handoff_mode is not None and self.handoff_mode not in {"link", "copy"}:
            raise ValueError("handoff_mode must be one of: copy, link")
        if self.reason is not None and self.reason not in _REASONS:
            raise ValueError("reason must be one of: escaped, missing, unavailable")
        if self.reason is not None and self.artifact_id is not None:
            raise ValueError("missing entries cannot contain artifact_id")

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            key: value for key, value in {
                "path_rel": self.path_rel, "kind": self.kind, "spin": self.spin,
                "artifact_id": self.artifact_id, "sha256": self.sha256,
                "size_bytes": self.size_bytes, "media_type": self.media_type,
                "source_path_rel": self.source_path_rel, "handoff_mode": self.handoff_mode,
                "source_sha256": self.source_sha256,
                "reason": self.reason,
            }.items() if value is not None
        }

    @classmethod
    def from_dict(cls, payload: object) -> PyatbManifestEntry:
        return _construct_strict(cls, payload, "PyATB manifest entry")


@dataclass(frozen=True, slots=True)
class PyatbManifest:
    inputs: tuple[PyatbManifestEntry, ...] = field(default_factory=tuple)
    outputs: tuple[PyatbManifestEntry, ...] = field(default_factory=tuple)
    missing: tuple[PyatbManifestEntry, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for name in ("inputs", "outputs", "missing"):
            raw_entries = getattr(self, name)
            if isinstance(raw_entries, (str, bytes)):
                raise ValueError(f"{name} must be an array of entries")
            try:
                entries = tuple(raw_entries)
            except TypeError as error:
                raise ValueError(f"{name} must be an array of entries") from error
            if not all(isinstance(entry, PyatbManifestEntry) for entry in entries):
                raise ValueError(f"{name} must contain PyatbManifestEntry values")
            if name == "missing" and any(entry.reason is None for entry in entries):
                raise ValueError("missing entries require a reason")
            if name != "missing" and any(entry.reason is not None for entry in entries):
                raise ValueError(f"{name} entries cannot contain a missing reason")
            object.__setattr__(self, name, entries)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": PYATB_MANIFEST_SCHEMA_VERSION,
            "inputs": [entry.to_dict() for entry in self.inputs],
            "outputs": [entry.to_dict() for entry in self.outputs],
            "missing": [entry.to_dict() for entry in self.missing],
        }

    @classmethod
    def from_dict(cls, payload: object) -> PyatbManifest:
        values = _mapping_payload(payload, "PyATB manifest")
        if values.pop("schema_version", None) != PYATB_MANIFEST_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {PYATB_MANIFEST_SCHEMA_VERSION!r}")
        if set(values) - {"inputs", "outputs", "missing"}:
            unknown = sorted(set(values) - {"inputs", "outputs", "missing"})
            raise ValueError(f"PyATB manifest contains unknown fields: {', '.join(unknown)}")
        required_arrays = {"inputs", "outputs", "missing"}
        if set(values) != required_arrays:
            missing = sorted(required_arrays - set(values))
            raise ValueError(f"PyATB manifest is missing fields: {', '.join(missing)}")
        try:
            if any(not isinstance(values[name], list) for name in required_arrays):
                raise ValueError("manifest entry arrays must be JSON arrays")
            return cls(
                inputs=tuple(PyatbManifestEntry.from_dict(item) for item in values.get("inputs", ())),
                outputs=tuple(PyatbManifestEntry.from_dict(item) for item in values.get("outputs", ())),
                missing=tuple(PyatbManifestEntry.from_dict(item) for item in values.get("missing", ())),
            )
        except (TypeError, ValueError) as error:
            raise ValueError("PyATB manifest contains invalid entries") from error


def classify_pyatb_output(path_rel: str) -> tuple[str, str, str]:
    """Classify a known PyATB artifact by canonical path/name only."""
    path = _path(path_rel)
    name = Path(path).name
    if name == "STRU":
        return "structure", "shared", "text/plain"
    if name == "Input":
        return "pyatb_input", "shared", "text/plain"
    if name == "KPT_band":
        return "kpoint_path", "shared", "text/plain"
    if name == "band_info.dat":
        return "band_info", "unknown", "text/plain"
    if name in {"band_up.dat", "band_dn.dat", "band_down.dat", "band.dat"}:
        spin = "up" if name == "band_up.dat" else "down" if name in {"band_dn.dat", "band_down.dat"} else "unknown"
        return "band_data", spin, "text/plain"
    if name == "band.png":
        return "band_plot", "unknown", "image/png"
    if name == "band.pdf":
        return "band_plot", "unknown", "application/pdf"
    if name == "input.json":
        return "run_input", "unknown", "application/json"
    if "HR" in name and name.endswith(".csr"):
        return "matrix_hr", "shared", "application/octet-stream"
    if "SR" in name and name.endswith(".csr"):
        return "matrix_sr", "shared", "application/octet-stream"
    if ("rR" in name or "RR" in name) and name.endswith(".csr"):
        return "matrix_rr", "shared", "application/octet-stream"
    return "other", "unknown", "application/octet-stream"


def _entry_from_artifact(
    artifact: ArtifactRecord,
    *,
    source_path_rel: str | None = None,
    handoff_mode: str | None = None,
    spin: str | None = None,
    source_sha256: str | None = None,
    kind: str | None = None,
) -> PyatbManifestEntry:
    if artifact.sha256 is None or artifact.size_bytes is None:
        raise ForgeInternalError("typed PyATB manifest requires hashed, sized artifacts")
    classified_kind, classified_spin, media_type = classify_pyatb_output(artifact.path_rel)
    return PyatbManifestEntry(
        path_rel=artifact.path_rel,
        kind=kind or classified_kind,
        spin=spin or classified_spin,
        artifact_id=artifact.id,
        sha256=artifact.sha256,
        size_bytes=artifact.size_bytes,
        # The manifest vocabulary owns deterministic MIME classification;
        # ArtifactRecord's generic fallback must not obscure known outputs.
        media_type=media_type,
        source_path_rel=source_path_rel,
        handoff_mode=handoff_mode,
        source_sha256=source_sha256,
    )


def build_prepare_pyatb_manifest(
    request: Any,
    handoff: Sequence[Mapping[str, object]],
    artifacts: Sequence[ArtifactRecord],
) -> PyatbManifest:
    """Project staged handoff and generated inputs into same-envelope facts."""
    by_path = {artifact.path_rel: artifact for artifact in artifacts}
    hr_count = len(request.hr_paths_rel)
    hr_index = 0
    entries: list[PyatbManifestEntry] = []
    for record in handoff:
        destination = record.get("destination")
        if not isinstance(destination, str) or destination not in by_path:
            raise ForgeInternalError("typed PyATB handoff destination is absent from artifact envelope")
        source = record.get("source")
        mode = record.get("mode")
        source_sha256 = record.get("source_sha256")
        if not isinstance(source_sha256, str):
            raise ForgeInternalError("typed PyATB handoff is missing source hash provenance")
        role = record.get("role")
        kind_by_role = {"structure": "structure", "hr": "matrix_hr", "sr": "matrix_sr", "rR": "matrix_rr"}
        spin = None
        if record.get("role") == "hr":
            spin = ("up", "down")[hr_index] if hr_count == 2 else "shared"
            hr_index += 1
        elif record.get("role") in {"structure", "sr", "rR"}:
            spin = "shared"
        entries.append(_entry_from_artifact(
            by_path[destination],
            source_path_rel=source if isinstance(source, str) else None,
            handoff_mode=mode if isinstance(mode, str) else None,
            spin=spin,
            source_sha256=source_sha256,
            kind=kind_by_role.get(role) if isinstance(role, str) else None,
        ))
    for path_rel in ("inputs/Input", "inputs/KPT_band"):
        if path_rel not in by_path:
            raise ForgeInternalError("generated typed PyATB input is absent from artifact envelope")
        entries.append(_entry_from_artifact(by_path[path_rel]))
    return PyatbManifest(inputs=tuple(entries), outputs=(), missing=())


def _requested_collect_paths(request: Any) -> tuple[str, ...]:
    paths = (
        request.band_info_path_rel,
        *request.band_data_paths_rel,
        *request.band_picture_paths_rel,
    )
    return tuple(dict.fromkeys(_path(path) for path in paths))


def build_collect_pyatb_manifest(request: Any, envelope: Any) -> PyatbManifest:
    """Project only requested collection paths and their factual availability."""
    present = {artifact.path_rel: artifact for artifact in envelope.artifacts}
    diagnostics = envelope.to_dict()["diagnostics"]
    requested = _requested_collect_paths(request)
    requested_set = set(requested)
    outputs = tuple(
        _entry_from_artifact(present[path])
        for path in _requested_collect_paths(request)
        if path in present
    )
    missing: list[PyatbManifestEntry] = []
    seen_missing: set[str] = set()
    reason_paths = (
        ("missing", diagnostics.get("missing_output_paths_rel", ())),
        ("escaped", diagnostics.get("escaped_output_paths_rel", ())),
        ("unavailable", diagnostics.get("unavailable_output_paths_rel", ())),
    )
    for reason, raw_paths in reason_paths:
        if not isinstance(raw_paths, (list, tuple)):
            continue
        for path in raw_paths:
            if isinstance(path, str) and path in requested_set and path not in present and path not in seen_missing:
                kind, spin, media_type = classify_pyatb_output(path)
                missing.append(PyatbManifestEntry(
                    path_rel=path, kind=kind, spin=spin,
                    media_type=media_type, reason=reason,
                ))
                seen_missing.add(path)
    return PyatbManifest(inputs=(), outputs=outputs, missing=tuple(missing))


__all__ = ["PYATB_MANIFEST_SCHEMA_VERSION", "PyatbManifest", "PyatbManifestEntry", "classify_pyatb_output"]
