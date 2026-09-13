"""Private parser backend selection for typed ABACUS collection.

This module intentionally has no import-time dependency on abacuslite.  The
backend is selected per collection call, which keeps long-lived Forge
processes free of the global IO switch used by older ABACUS helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from importlib.metadata import PackageNotFoundError, version as package_version
import re
from pathlib import Path
from typing import Any, Callable

from abacus_forge.errors import ForgePreconditionError, ForgeRequestError


class ParserRequestError(ForgeRequestError):
    """Invalid parser invocation configuration or version conflict."""

    affected_fields = ("parser_backend", "output_version")


class ParserPreconditionError(ForgePreconditionError):
    """Parser package/version precondition that belongs to collect admission."""

    affected_fields = ("parser_backend", "output_version", "workspace_rel")


_VERSION = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:\.(?P<extra>\d+))?"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)


@dataclass(frozen=True, slots=True)
class OutputVersion:
    raw: str
    normalized: str
    io_backend: str


def normalize_output_version(value: object) -> OutputVersion:
    """Validate a producer version and map the supported v3 IO generations."""
    raw, match, normalized = _normalize_version_syntax(value)
    major, minor = int(match["major"]), int(match["minor"])
    if major != 3 or minor not in {9, 10, 11}:
        raise ParserRequestError(f"unsupported output_version: {raw}")
    # Canonical abacuslite treats the 3.9 develop spellings (numeric extra
    # component or pre-release) as latestio; bare v3.9.0 remains legacyio.
    is_39_develop = minor == 9 and bool(match["extra"] or match["pre"])
    io_backend = "latestio" if minor == 11 or is_39_develop else "legacyio"
    return OutputVersion(raw=raw, normalized=normalized, io_backend=io_backend)


def normalize_version_syntax(value: object) -> str:
    """Normalize a syntactically valid producer version without support gating."""
    _raw, _match, normalized = _normalize_version_syntax(value)
    return normalized


def _normalize_version_syntax(value: object) -> tuple[str, re.Match[str], str]:
    if not isinstance(value, str) or not value.strip():
        raise ParserRequestError("output_version must be a supported semantic version")
    raw = value.strip()
    match = _VERSION.fullmatch(raw)
    if match is None:
        raise ParserRequestError(f"unsupported output_version: {raw}")
    # The canonical package emits both beta.8 and beta8; normalize that one
    # equivalent spelling while preserving other prerelease punctuation.
    major, minor = int(match["major"]), int(match["minor"])
    pre = match["pre"] or ""
    pre = re.sub(r"^beta\.(\d+)$", r"beta\1", pre, flags=re.IGNORECASE)
    build = match["build"] or ""
    normalized = f"v{major}.{minor}.{int(match['patch'])}"
    if match["extra"]:
        normalized += f".{int(match['extra'])}"
    if pre:
        normalized += f"-{pre}"
    if build:
        normalized += f"+{build}"
    return raw, match, normalized


def identify_output_version(text: str | None) -> OutputVersion | None:
    """Identify a single supported ABACUS version marker in a log."""
    candidates = output_version_markers(text)
    if not candidates:
        return None
    versions = [normalize_output_version(item) for item in dict.fromkeys(candidates)]
    if len({item.normalized for item in versions}) != 1:
        raise ParserRequestError("ambiguous ABACUS output version in running log")
    return versions[-1]


def output_version_markers(text: str | None) -> list[str]:
    """Return distinct producer-version markers without applying support policy."""
    if not text:
        return []
    return list(dict.fromkeys(re.findall(r"(?:ABACUS\s+)?VERSION\s*[:=]\s*([^\s,;]+)", text, re.I)))


def forge_backend_version() -> str | None:
    """Resolve Forge's installed package version for parser provenance."""
    try:
        return package_version("abacus-forge")
    except PackageNotFoundError:
        return "0.1.0"


def load_abacuslite(io_backend: str) -> Any:
    """Load one abacuslite IO module only after collect admission."""
    module_name = f"abacuslite.io.{io_backend}"
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if _is_missing_optional_module(error, module_name):
            raise ParserPreconditionError(
                "abacuslite package is required for parser_backend=abacuslite"
            ) from error
        raise


def ensure_abacuslite_available() -> None:
    """Check the optional package without selecting an IO generation."""
    module_name = "abacuslite"
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if _is_missing_optional_module(error, module_name):
            raise ParserPreconditionError(
                "abacuslite package is required for parser_backend=abacuslite"
            ) from error
        raise


def _is_missing_optional_module(error: ModuleNotFoundError, requested: str) -> bool:
    """Distinguish an absent optional module from an import-time defect."""
    missing = error.name or str(error).strip()
    if not isinstance(missing, str) or not missing:
        return False
    return missing == "abacuslite" or missing == requested or requested.startswith(f"{missing}.")


def get_abacuslite_version(io_backend: str) -> str | None:
    """Return package metadata when the installed backend publishes it."""
    module = load_abacuslite(io_backend)
    try:
        distribution = package_version("abacuslite")
    except PackageNotFoundError:
        distribution = None
    if isinstance(distribution, str) and distribution.strip():
        return distribution.strip()
    try:
        package = importlib.import_module("abacuslite")
    except ModuleNotFoundError as error:
        if not _is_missing_optional_module(error, "abacuslite"):
            raise
        package = None
    for candidate in (module, package):
        if candidate is None:
            continue
        value = getattr(candidate, "__version__", None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def parse_abacuslite(log_path: Path, *, version: OutputVersion) -> dict[str, Any]:
    """Read the selected primary-log fields through abacuslite's local IO API.

    The adapter accepts the small return-shape differences between released
    abacuslite revisions while keeping responsibility limited to energy,
    Fermi energy, force and stress fields.
    """
    module = load_abacuslite(version.io_backend)
    source: object = str(log_path)
    values: dict[str, Any] = {}
    for name, metric in (("read_energies_from_running_log", "total_energy"),
                         ("read_forces_from_running_log", "force"),
                         ("read_stress_from_running_log", "stress")):
        reader: Callable[..., Any] | None = getattr(module, name, None)
        if reader is None:
            continue
        try:
            result = reader(source)
        except FileNotFoundError:
            continue
        # Canonical readers return an empty sequence for a missing/truncated
        # section.  Let ValueError from a reader implementation propagate so
        # an unexpected parser defect becomes internal.failure instead of a
        # fabricated partial result.
        if result is None:
            continue
        if metric == "total_energy":
            if isinstance(result, dict):
                for key in ("fermi_energy", "fermi", "E_Fermi"):
                    if key in result:
                        values["fermi_energy"] = float(result[key])
                        break
                total_key = next(
                    (key for key in ("total_energy", "energy", "etot") if key in result),
                    None,
                )
                if total_key is not None:
                    result = result[total_key]
            # Some releases return (energies_ry, energies_ev); Forge consumes
            # the eV value and therefore takes the final member.
            if isinstance(result, tuple) and len(result) >= 2:
                result = result[1]
            while isinstance(result, (list, tuple)) and result:
                result = result[-1]
            if isinstance(result, dict):
                total = next(
                    (result[key] for key in ("E_KS(sigma->0)", "E_KohnSham", "total_energy", "energy")
                     if key in result),
                ) if any(key in result for key in ("E_KS(sigma->0)", "E_KohnSham", "total_energy", "energy")) else None
                if "E_Fermi" in result:
                    values["fermi_energy"] = float(result["E_Fermi"])
                result = total
            if isinstance(result, (int, float)) and not isinstance(result, bool):
                values[metric] = float(result)
        else:
            frames = _normalise_frames(result)
            if not frames:
                continue
            flattened = [_flatten_frame(frame) for frame in frames]
            flattened = [frame for frame in flattened if frame]
            if not flattened:
                continue
            if metric == "stress":
                # abacuslite exposes the ASE stress sign convention in
                # eV/Angstrom^3.  Forge's historical contract reports the
                # ABACUS running-log values in kbar, so invert the sign while
                # applying the exact kbar conversion.
                factor = -1.0 / 0.0006241504912713559
                flattened = [[item * factor for item in frame] for frame in flattened]
            values[metric] = flattened[-1]
            values["forces" if metric == "force" else "stresses"] = flattened
    return values


def _normalise_frames(value: object) -> list[object]:
    """Convert an abacuslite frame sequence into plain Python values."""
    value = _to_builtin(value)
    if value is None:
        return []
    if not isinstance(value, list):
        return [value]
    if not value:
        return []
    # A direct vector is one frame; released readers normally return a list
    # of arrays, which is already a frame sequence.
    if all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value):
        return [value]
    if all(
        isinstance(item, list)
        and all(isinstance(number, (int, float)) and not isinstance(number, bool) for number in item)
        for item in value
    ):
        return [value]
    return value


def _flatten_frame(value: object) -> list[float]:
    output: list[float] = []
    _flatten_numbers(_to_builtin(value), output)
    return output


def _to_builtin(value: object) -> object:
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, tuple):
        return [_to_builtin(item) for item in value]
    if isinstance(value, list):
        return [_to_builtin(item) for item in value]
    return value


def _flatten_numbers(value: object, output: list[float]) -> None:
    if isinstance(value, (list, tuple)):
        for item in value:
            _flatten_numbers(item, output)
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        output.append(float(value))


def validate_backend(value: object) -> str:
    if not isinstance(value, str) or value not in {"native", "abacuslite"}:
        raise ParserRequestError("parser_backend must be 'native' or 'abacuslite'")
    return value
