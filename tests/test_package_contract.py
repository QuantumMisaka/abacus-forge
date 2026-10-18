"""Installability contract for the optional abacuslite parser dependency.

``abacuslite`` is an optional extra pinned to the published 1.1.0 release and
must never enter the default dependency set.  The provenance record binds that
pin to the registry artifact and books the next pin as an explicit rebind item.
"""

from __future__ import annotations

import os
import json
from pathlib import Path
import re
import zipfile
from email.parser import Parser

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

import pytest


ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = ROOT / "docs/superpowers/evidence/2026-10-19-forge-abacuslite-1.1.0-package-provenance.json"
HISTORICAL_PROVENANCE = (
    ROOT / "docs/superpowers/evidence/2026-09-14-forge-stage1-package-provenance.json"
)
GPLV3_CLASSIFIER = "License :: OSI Approved :: GNU General Public License v3 (GPLv3)"


def _project_metadata() -> dict[str, object]:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        return tomllib.load(stream)["project"]


def test_published_abacuslite_release_provenance_binds_the_declared_extra() -> None:
    """Bind the optional parser extra to the published abacuslite artifact."""

    record = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    assert record["schema_version"] == "forge.stage1-package-provenance/v2"
    assert record["status"] == "published_release_bound"
    assert record["public_exact_release_available"] is True
    assert record["forge_optional_extra_declared"] is True
    assert record["history"]["supersedes"] == HISTORICAL_PROVENANCE.name
    assert HISTORICAL_PROVENANCE.is_file()

    # The superseded record stays frozen as the local-oracle-only stage.
    historical = json.loads(HISTORICAL_PROVENANCE.read_text(encoding="utf-8"))
    assert historical["status"] == "local_oracle_only"
    assert historical["public_exact_release_available"] is False
    assert historical["forge_optional_extra_declared"] is False

    release = record["abacuslite_release"]
    assert release["package_name"] == "abacuslite"
    assert release["package_version"] == "1.1.0"
    assert release["tag"] == "v1.1.0"
    assert release["tag_commit"] == "94a26e4c7f31ed817eac36c871ff74a7b7abe418"
    assert release["source_repository"] == "https://github.com/QuantumMisaka/abacuslite"
    assert release["wheel_filename"] == "abacuslite-1.1.0-py3-none-any.whl"
    assert release["wheel_sha256"] == (
        "c3e4504e9c9f5bceb69f70c79290e7843037ca72f625c5f66258e14d110f0ff3"
    )
    assert release["sdist_filename"] == "abacuslite-1.1.0.tar.gz"
    assert release["sdist_sha256"] == (
        "79a85f09a37e68ca97ba35f0a620bc888ace092bfd0fdfc533320498d46956e3"
    )
    assert release["requires_python"] == ">=3.10"
    runtime = release["runtime_files"]
    assert runtime["count"] == 8
    assert runtime["all_equal_tag_source"] is True
    assert re.fullmatch(r"[0-9a-f]{64}", release["wheel_sha256"])
    assert re.fullmatch(r"[0-9a-f]{64}", release["sdist_sha256"])

    # The declared extra must be exactly this published version.
    project = _project_metadata()
    optional = project.get("optional-dependencies", {})
    declared = [
        (str(extra), str(item))
        for extra, values in optional.items()
        for item in values
        if str(item).lower().startswith("abacuslite")
    ]
    assert len(declared) == 1
    extra_name, requirement = declared[0]
    assert requirement == f"abacuslite=={release['package_version']}"
    assert project["dependencies"].count("abacuslite") == 0
    forge_extra = record["forge_extra"]
    assert forge_extra["name"] == extra_name
    assert forge_extra["requirement"] == requirement
    assert forge_extra["change_kind"] == "added"
    assert forge_extra["scope"] == "project.optional-dependencies"
    assert forge_extra["default_dependencies_unchanged"] is True

    # The built candidate is bound to its source revision and artifact hash.
    forge = record["forge_candidate"]
    assert re.fullmatch(r"[0-9a-f]{40}", forge["revision"])
    assert forge["package_name"] == "abacus-forge"
    assert forge["package_version"] == project["version"]
    assert forge["wheel_filename"] == "abacus_forge-0.1.0-py3-none-any.whl"
    assert re.fullmatch(r"[0-9a-f]{64}", forge["wheel_sha256"])
    assert forge["artifact_binding"] == {
        "forge_revision": forge["revision"],
        "wheel_filename": forge["wheel_filename"],
        "wheel_sha256": forge["wheel_sha256"],
    }

    # The next pin is booked explicitly instead of being re-derived later.
    rebind = record["rebind_plan"]
    assert rebind["target_pin"] == "abacuslite==1.2.0"
    assert rebind["requires_four_capability_parity_rerun"] is True
    assert rebind["status"] == "pending_upstream_release"


def test_abacuslite_extra_is_exactly_pinned_if_declared() -> None:
    project = _project_metadata()
    dependencies = project.get("dependencies", [])
    optional = project.get("optional-dependencies", {})
    assert isinstance(dependencies, list)
    assert not any(str(item).lower().startswith("abacuslite") for item in dependencies)
    assert isinstance(optional, dict)

    declared = [
        str(item)
        for values in optional.values()
        if isinstance(values, list)
        for item in values
        if str(item).lower().startswith("abacuslite")
    ]
    if not declared:
        # No public exact release is currently available.  The optional
        # parser therefore remains deliberately blocked at the package layer.
        return
    assert len(declared) == 1
    assert re.fullmatch(r"abacuslite==[^;\s]+", declared[0], flags=re.IGNORECASE)


def test_built_wheel_keeps_the_same_optional_dependency_boundary() -> None:
    """Check built metadata when a release candidate wheel is supplied.

    Source metadata and wheel metadata are generated by different layers of
    the build backend.  This opt-in check makes the Stage 1 package gate
    executable against the exact wheel that is about to be reviewed without
    requiring every ordinary test run to build or download a wheel.
    """

    wheel_value = os.environ.get("ABACUS_FORGE_WHEEL")
    if not wheel_value:
        pytest.skip("set ABACUS_FORGE_WHEEL to inspect a release candidate wheel")
    wheel = Path(wheel_value).expanduser().resolve()
    assert wheel.is_file(), wheel

    with zipfile.ZipFile(wheel) as archive:
        metadata_paths = [
            name
            for name in archive.namelist()
            if name.endswith(".dist-info/METADATA")
        ]
        assert len(metadata_paths) == 1
        metadata = archive.read(metadata_paths[0]).decode("utf-8")

    headers = Parser().parsestr(metadata)
    names = headers.get_all("Name", [])
    assert names == ["abacus-forge"]
    # Core Metadata permits RFC-style continuation lines. Unfold before
    # checking requirement syntax and its extra marker.
    requires = [" ".join(value.split()) for value in headers.get_all("Requires-Dist", [])]
    abacuslite = [
        requirement
        for requirement in requires
        if re.match(r"^abacuslite(?:\s|[<>=!~;]|$)", requirement, flags=re.IGNORECASE)
    ]
    assert not any(
        requirement.lower().startswith("abacuslite") and "; extra" not in requirement.lower()
        for requirement in requires
    ), "abacuslite must not enter the default wheel dependencies"
    if abacuslite:
        assert len(abacuslite) == 1
        assert re.fullmatch(
            r"abacuslite==[^;\s]+;\s*extra\s*==\s*['\"][^'\"]+['\"]",
            abacuslite[0],
            flags=re.IGNORECASE,
        )


    # Bind the generated artifact to the source declaration, not merely to a
    # syntactically acceptable optional requirement in either file.
    project = _project_metadata()
    assert names == [project["name"]]
    assert headers.get_all("Version", []) == [project["version"]]
    optional = project.get("optional-dependencies", {})
    expected_extras = {canonicalize_name(extra) for extra in optional}
    actual_extras = [canonicalize_name(extra) for extra in headers.get_all("Provides-Extra", [])]
    assert len(actual_extras) == len(set(actual_extras))
    assert set(actual_extras) == expected_extras

    expected_parser = []
    for extra, dependencies in optional.items():
        for dependency in dependencies:
            requirement = Requirement(dependency)
            if canonicalize_name(requirement.name) == "abacuslite":
                assert re.fullmatch(r"abacuslite==[^;\s*]+", dependency, flags=re.IGNORECASE)
                expected_parser.append((str(requirement.specifier), canonicalize_name(extra)))
    assert len(expected_parser) <= 1
    assert all(canonicalize_name(Requirement(item).name) != "abacuslite"
               for item in project.get("dependencies", []))

    actual_parser = []
    for dependency in requires:
        requirement = Requirement(dependency)
        if canonicalize_name(requirement.name) != "abacuslite":
            continue
        marker = re.fullmatch(r"extra == [\"']([^\"']+)[\"']", str(requirement.marker))
        assert marker is not None, "abacuslite must be scoped to exactly one extra"
        assert requirement.url is None and not requirement.extras
        actual_parser.append((str(requirement.specifier), canonicalize_name(marker[1])))
    assert actual_parser == expected_parser, "source/wheel abacuslite dependency drift"


def test_built_wheel_license_metadata_matches_the_gplv3_source() -> None:
    """Keep release metadata aligned with the actual GPL-3.0-only LICENSE."""

    wheel_value = os.environ.get("ABACUS_FORGE_WHEEL")
    if not wheel_value:
        pytest.skip("set ABACUS_FORGE_WHEEL to inspect a release candidate wheel")
    wheel = Path(wheel_value).expanduser().resolve()
    assert wheel.is_file(), wheel

    with zipfile.ZipFile(wheel) as archive:
        metadata_paths = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        assert len(metadata_paths) == 1
        headers = Parser().parsestr(archive.read(metadata_paths[0]).decode("utf-8"))
        license_members = [
            name
            for name in archive.namelist()
            if name.endswith(".dist-info/licenses/LICENSE")
        ]

    classifiers = headers.get_all("Classifier", [])
    assert GPLV3_CLASSIFIER in classifiers
    assert not any("mit" in classifier.lower() for classifier in classifiers)

    project = _project_metadata()
    assert project["license"] == {"file": "LICENSE"}
    assert headers.get_all("License-File", []) == ["LICENSE"]
    assert len(license_members) == 1
    with zipfile.ZipFile(wheel) as archive:
        assert archive.read(license_members[0]) == (ROOT / "LICENSE").read_bytes()
