"""Facts-only artifact manifests for the legacy property packs.

The manifest is deliberately capability-specific and additive.  It describes
which files a legacy property post operation consumed or produced; it does
not interpret the scientific result or discover files on its own.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from os import fspath
from pathlib import Path
from typing import Any

from abacus_forge.contracts import (
    ArtifactRecord,
    JSONValue,
    _construct_strict,
    _mapping_payload,
    _require_nonempty_string,
    canonical_relative_path,
)
from abacus_forge.errors import ForgeInternalError


PROPERTY_MANIFEST_SCHEMA_VERSION = "forge.property-manifest/v1"

_KINDS = frozenset({"cube", "report", "text", "other"})
_ROLES = frozenset({"input", "output"})
_ORIGINS = frozenset({"source", "derived"})
_SPINS = frozenset({"shared", "up", "down", "unknown"})
_REASONS = frozenset({"missing", "escaped", "unavailable"})
_PARSE_STATUSES = frozenset({"ok", "malformed"})
_HASH = re.compile(r"^[0-9a-f]{64}$")
_MEDIA_TYPES = {
    "cube": "application/octet-stream",
    "report": "application/json",
    "text": "text/plain",
    "other": "application/octet-stream",
}


def _path(value: str, field_name: str = "path_rel") -> str:
    try:
        normalized = canonical_relative_path(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be a canonical relative path") from error
    if normalized == ".":
        raise ValueError(f"{field_name} must identify a file")
    return normalized


def _optional_hash(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase SHA-256 hex digest")
    return value


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)):
        raise ValueError(f"{field_name} must contain non-empty strings")
    try:
        values = tuple(value)  # type: ignore[arg-type]
    except TypeError as error:
        raise ValueError(f"{field_name} must contain non-empty strings") from error
    if not all(isinstance(item, str) and item for item in values):
        raise ValueError(f"{field_name} must contain non-empty strings")
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must contain unique strings")
    return values


def _path_value(value: str | Path, field_name: str = "path") -> str | Path:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value:
        return value
    raise ValueError(f"{field_name} must be a non-empty path")


@dataclass(frozen=True, slots=True)
class PropertyManifestEntry:
    """One present or missing property artifact fact."""

    path_rel: str
    kind: str
    role: str
    origin: str
    spin: str = "unknown"
    artifact_id: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    media_type: str | None = None
    parse_status: str | None = None
    source_artifact_ids: tuple[str, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "path_rel", _path(self.path_rel))
        if self.kind not in _KINDS:
            raise ValueError("kind must be one of: cube, other, report, text")
        if self.role not in _ROLES:
            raise ValueError("role must be one of: input, output")
        if self.origin not in _ORIGINS:
            raise ValueError("origin must be one of: derived, source")
        if self.spin not in _SPINS:
            raise ValueError("spin must be one of: down, shared, unknown, up")
        if self.artifact_id is not None:
            _require_nonempty_string(self.artifact_id, "artifact_id")
        object.__setattr__(self, "sha256", _optional_hash(self.sha256, "sha256"))
        if self.size_bytes is not None and (
            isinstance(self.size_bytes, bool)
            or not isinstance(self.size_bytes, int)
            or self.size_bytes < 0
        ):
            raise ValueError("size_bytes must be a non-negative integer")
        if self.media_type is not None:
            _require_nonempty_string(self.media_type, "media_type")
        if self.parse_status is not None and self.parse_status not in _PARSE_STATUSES:
            raise ValueError("parse_status must be one of: malformed, ok")
        source_ids = _string_tuple(self.source_artifact_ids, "source_artifact_ids")
        object.__setattr__(self, "source_artifact_ids", source_ids)
        if source_ids and not (self.kind == "cube" and self.origin == "derived"):
            raise ValueError("source_artifact_ids are only valid for derived cube entries")
        if self.reason is not None:
            if self.reason not in _REASONS:
                raise ValueError("reason must be one of: escaped, missing, unavailable")
            if any(
                value is not None
                for value in (self.artifact_id, self.sha256, self.size_bytes, self.media_type, self.parse_status)
            ) or source_ids:
                raise ValueError("missing entries cannot contain artifact facts")
        else:
            if any(value is None for value in (self.artifact_id, self.sha256, self.size_bytes, self.media_type)):
                raise ValueError("present entries require artifact_id, sha256, size_bytes, and media_type")
            if self.kind == "cube" and self.origin == "derived" and not source_ids:
                raise ValueError("derived cube entries require source_artifact_ids")

    def to_dict(self) -> dict[str, JSONValue]:
        values: dict[str, object] = {
            "path_rel": self.path_rel,
            "kind": self.kind,
            "role": self.role,
            "origin": self.origin,
            "spin": self.spin,
            "artifact_id": self.artifact_id,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "media_type": self.media_type,
            "parse_status": self.parse_status,
            "source_artifact_ids": list(self.source_artifact_ids) if self.source_artifact_ids else None,
            "reason": self.reason,
        }
        return {key: value for key, value in values.items() if value is not None}  # type: ignore[return-value]

    @classmethod
    def from_dict(cls, payload: object) -> "PropertyManifestEntry":
        return _construct_strict(cls, payload, "property manifest entry")


@dataclass(frozen=True, slots=True)
class PropertyManifest:
    """Versioned property artifact facts grouped by operation role."""

    task: str
    inputs: tuple[PropertyManifestEntry, ...] = field(default_factory=tuple)
    outputs: tuple[PropertyManifestEntry, ...] = field(default_factory=tuple)
    missing: tuple[PropertyManifestEntry, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        _require_nonempty_string(self.task, "task")
        seen: set[str] = set()
        for name in ("inputs", "outputs", "missing"):
            raw_entries = getattr(self, name)
            if isinstance(raw_entries, (str, bytes)):
                raise ValueError(f"{name} must be an array of entries")
            try:
                entries = tuple(raw_entries)
            except TypeError as error:
                raise ValueError(f"{name} must be an array of entries") from error
            if not all(isinstance(entry, PropertyManifestEntry) for entry in entries):
                raise ValueError(f"{name} must contain PropertyManifestEntry values")
            for entry in entries:
                if entry.path_rel in seen:
                    raise ValueError("manifest entries must not repeat a path")
                seen.add(entry.path_rel)
                if name == "missing" and entry.reason is None:
                    raise ValueError("missing entries require a reason")
                if name != "missing" and entry.reason is not None:
                    raise ValueError(f"{name} entries cannot contain a missing reason")
            object.__setattr__(self, name, entries)

    def to_dict(self) -> dict[str, JSONValue]:
        return {
            "schema_version": PROPERTY_MANIFEST_SCHEMA_VERSION,
            "task": self.task,
            "inputs": [entry.to_dict() for entry in self.inputs],
            "outputs": [entry.to_dict() for entry in self.outputs],
            "missing": [entry.to_dict() for entry in self.missing],
        }

    @classmethod
    def from_dict(cls, payload: object) -> "PropertyManifest":
        values = _mapping_payload(payload, "property manifest")
        if values.pop("schema_version", None) != PROPERTY_MANIFEST_SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {PROPERTY_MANIFEST_SCHEMA_VERSION!r}")
        allowed = {"task", "inputs", "outputs", "missing"}
        unknown = sorted(set(values) - allowed)
        if unknown:
            raise ValueError(f"property manifest contains unknown fields: {', '.join(map(str, unknown))}")
        if set(values) != allowed:
            missing = sorted(allowed - set(values))
            raise ValueError(f"property manifest is missing fields: {', '.join(missing)}")
        if any(not isinstance(values[name], list) for name in ("inputs", "outputs", "missing")):
            raise ValueError("property manifest entry arrays must be JSON arrays")
        try:
            return cls(
                task=values["task"],  # type: ignore[arg-type]
                inputs=tuple(PropertyManifestEntry.from_dict(item) for item in values["inputs"]),  # type: ignore[arg-type]
                outputs=tuple(PropertyManifestEntry.from_dict(item) for item in values["outputs"]),  # type: ignore[arg-type]
                missing=tuple(PropertyManifestEntry.from_dict(item) for item in values["missing"]),  # type: ignore[arg-type]
            )
        except (TypeError, ValueError) as error:
            raise ValueError("property manifest contains invalid entries") from error


@dataclass(frozen=True, slots=True)
class PropertyArtifactSpec:
    """Internal explicit file declaration consumed by the manifest builder."""

    path: str | Path
    kind: str
    role: str
    origin: str
    spin: str = "unknown"
    parse_status: str | None = None
    source_paths: tuple[str | Path, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _path_value(self.path))
        if self.kind not in _KINDS:
            raise ValueError("kind must be one of: cube, other, report, text")
        if self.role not in _ROLES:
            raise ValueError("role must be one of: input, output")
        if self.origin not in _ORIGINS:
            raise ValueError("origin must be one of: derived, source")
        if self.spin not in _SPINS:
            raise ValueError("spin must be one of: down, shared, unknown, up")
        if self.parse_status is not None and self.parse_status not in _PARSE_STATUSES:
            raise ValueError("parse_status must be one of: malformed, ok")
        if isinstance(self.source_paths, (str, bytes)):
            raise ValueError("source_paths must be an array of paths")
        try:
            source_values = tuple(self.source_paths)
        except TypeError as error:
            raise ValueError("source_paths must be an array of paths") from error
        source_paths = tuple(_path_value(item, "source_paths") for item in source_values)
        object.__setattr__(self, "source_paths", source_paths)
        if source_paths and not (self.kind == "cube" and self.origin == "derived"):
            raise ValueError("source_paths are only valid for derived cube specs")
        if self.kind == "cube" and self.origin == "derived" and not source_paths:
            raise ValueError("derived cube specs require source_paths")


def _resolve_path(workspace: Path, value: str | Path) -> tuple[str | None, str | None]:
    root = Path(workspace).resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    lexical_rel: str | None = None
    try:
        lexical_rel = _path(candidate.relative_to(root).as_posix())
    except (ValueError, TypeError):
        # Absolute paths outside the workspace have no safe lexical path to
        # expose.  A path declared inside the workspace remains useful even
        # when its resolved symlink target escapes.
        lexical_rel = None
    try:
        resolved = candidate.resolve(strict=False)
    except (OSError, RuntimeError):
        return lexical_rel, "unavailable"
    try:
        relative = resolved.relative_to(root).as_posix()
    except ValueError:
        return lexical_rel, "escaped"
    try:
        relative = _path(relative)
    except ValueError:
        return lexical_rel, "unavailable"
    if not resolved.exists():
        return relative, "missing"
    if not resolved.is_file():
        return relative, "unavailable"
    return relative, None


def _missing_entry(spec: PropertyArtifactSpec, path_rel: str | None, reason: str) -> PropertyManifestEntry:
    raw = path_rel
    if raw is None:
        candidate = Path(spec.path)
        raw = candidate.name or "unavailable-artifact"
        try:
            raw = _path(raw)
        except ValueError:
            raw = "unavailable-artifact"
    return PropertyManifestEntry(
        path_rel=raw,
        kind=spec.kind,
        role=spec.role,
        origin=spec.origin,
        spin=spec.spin,
        reason=reason,
    )


def _present_entry(
    workspace: Path,
    spec: PropertyArtifactSpec,
    path_rel: str,
    artifacts: Mapping[str, ArtifactRecord],
) -> PropertyManifestEntry:
    artifact = artifacts.get(path_rel)
    if artifact is None or artifact.sha256 is None or artifact.size_bytes is None:
        raise ForgeInternalError(f"property manifest artifact is absent or incomplete: {path_rel}")
    source_ids: tuple[str, ...] = ()
    if spec.kind == "cube" and spec.origin == "derived":
        resolved_ids: list[str] = []
        for source_path in spec.source_paths:
            source_rel, source_reason = _resolve_path(workspace, source_path)
            if source_reason is not None or source_rel is None:
                raise ForgeInternalError(f"derived property source is unavailable: {source_path}")
            source_artifact = artifacts.get(source_rel)
            if source_artifact is None:
                raise ForgeInternalError(f"derived property source artifact is absent: {source_rel}")
            resolved_ids.append(source_artifact.id)
        source_ids = tuple(dict.fromkeys(resolved_ids))
        if not source_ids:
            raise ForgeInternalError(f"derived property cube has no source artifacts: {path_rel}")
    return PropertyManifestEntry(
        path_rel=path_rel,
        kind=spec.kind,
        role=spec.role,
        origin=spec.origin,
        spin=spec.spin,
        artifact_id=artifact.id,
        sha256=artifact.sha256,
        size_bytes=artifact.size_bytes,
        media_type=_MEDIA_TYPES[spec.kind],
        parse_status=spec.parse_status,
        source_artifact_ids=source_ids,
    )


def _resolve_specs(
    workspace: Path,
    specs: Sequence[PropertyArtifactSpec],
    artifacts: Mapping[str, ArtifactRecord],
    seen: set[str],
) -> tuple[list[PropertyManifestEntry], list[PropertyManifestEntry]]:
    present: list[PropertyManifestEntry] = []
    missing: list[PropertyManifestEntry] = []
    for spec in specs:
        path_rel, reason = _resolve_path(workspace, spec.path)
        key = path_rel or f"{reason}:{fspath(spec.path)}"
        if key in seen:
            continue
        seen.add(key)
        if reason is not None or path_rel is None:
            missing.append(_missing_entry(spec, path_rel, reason or "unavailable"))
            continue
        try:
            present.append(_present_entry(workspace, spec, path_rel, artifacts))
        except ForgeInternalError:
            # The filesystem path exists but the common artifact projection
            # could not verify it.  This is an unavailable fact, not a made-up
            # artifact record.
            missing.append(_missing_entry(spec, path_rel, "unavailable"))
    return present, missing


def build_property_manifest(
    workspace: Path,
    *,
    task: str,
    inputs: Sequence[PropertyArtifactSpec],
    outputs: Sequence[PropertyArtifactSpec],
    artifacts: Sequence[ArtifactRecord],
) -> PropertyManifest:
    """Build a manifest from explicit paths and existing artifact facts.

    No directory walk or filename inference occurs here.  The caller supplies
    the paths selected by the legacy post operation; this function only checks
    containment/availability and projects matching same-result artifacts.
    """

    by_path: dict[str, ArtifactRecord] = {}
    for artifact in artifacts:
        if artifact.path_rel in by_path:
            raise ForgeInternalError(f"duplicate property artifact path: {artifact.path_rel}")
        by_path[artifact.path_rel] = artifact
    seen: set[str] = set()
    present_inputs, missing_inputs = _resolve_specs(workspace, inputs, by_path, seen)
    present_outputs, missing_outputs = _resolve_specs(workspace, outputs, by_path, seen)
    return PropertyManifest(
        task=task,
        inputs=tuple(present_inputs),
        outputs=tuple(present_outputs),
        missing=tuple((*missing_inputs, *missing_outputs)),
    )


__all__ = [
    "PROPERTY_MANIFEST_SCHEMA_VERSION",
    "PropertyArtifactSpec",
    "PropertyManifest",
    "PropertyManifestEntry",
    "build_property_manifest",
]
