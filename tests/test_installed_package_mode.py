"""Contracts for the ``ABACUS_FORGE_INSTALLED_PACKAGE_ONLY`` guard.

The guard must reject every installation mode that executes source (editable
installs and imports outside the distribution) while accepting a wheel
installed into a virtual environment inside the repository.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests import conftest as suite_conftest
from tests.support import installed_package


class _FakeDistribution:
    def __init__(
        self,
        site_packages: Path,
        *,
        files: tuple[str, ...] | None = ("abacus_forge/__init__.py",),
        direct_url: dict[str, object] | None = None,
        dist_path: Path | None = None,
    ) -> None:
        self._site_packages = Path(site_packages)
        self.files = None if files is None else list(files)
        self._direct_url = None if direct_url is None else json.dumps(direct_url)
        self._path = dist_path

    def locate_file(self, item: str) -> Path:
        return self._site_packages / str(item)

    def read_text(self, name: str) -> str | None:
        return self._direct_url if name == "direct_url.json" else None


def _module_at(path: Path) -> SimpleNamespace:
    return SimpleNamespace(__file__=str(path))


def test_wheel_install_is_accepted(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    distribution = _FakeDistribution(site_packages)
    module = _module_at(site_packages / "abacus_forge" / "__init__.py")

    installed_package.validate_wheel_install(module, distribution)


def test_wheel_install_inside_repository_venv_is_accepted() -> None:
    """A wheel in ``<repo>/.venv`` is an install, not a source checkout."""

    site_packages = suite_conftest.ROOT / ".venv" / "lib" / "python3.13" / "site-packages"
    distribution = _FakeDistribution(
        site_packages,
        files=("abacus_forge/__init__.py", "abacus_forge/cli.py"),
    )
    module = _module_at(site_packages / "abacus_forge" / "__init__.py")

    installed_package.validate_wheel_install(module, distribution)


def test_editable_direct_url_is_rejected(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    distribution = _FakeDistribution(
        site_packages,
        direct_url={"url": (tmp_path / "checkout").as_uri(), "dir_info": {"editable": True}},
    )
    module = _module_at(site_packages / "abacus_forge" / "__init__.py")

    with pytest.raises(installed_package.NotWheelInstalledError, match="editable"):
        installed_package.validate_wheel_install(module, distribution)


def test_legacy_egg_link_is_rejected(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    distribution = _FakeDistribution(
        site_packages,
        dist_path=tmp_path / "abacus-forge.egg-link",
    )
    module = _module_at(site_packages / "abacus_forge" / "__init__.py")

    with pytest.raises(installed_package.NotWheelInstalledError, match="editable"):
        installed_package.validate_wheel_install(module, distribution)


def test_source_checkout_import_is_rejected(tmp_path: Path) -> None:
    site_packages = tmp_path / "site-packages"
    distribution = _FakeDistribution(site_packages)
    module = _module_at(tmp_path / "checkout" / "src" / "abacus_forge" / "__init__.py")

    with pytest.raises(installed_package.NotWheelInstalledError, match="not one of"):
        installed_package.validate_wheel_install(module, distribution)


def test_distribution_without_files_is_rejected(tmp_path: Path) -> None:
    distribution = _FakeDistribution(tmp_path, files=None)
    module = _module_at(tmp_path / "abacus_forge" / "__init__.py")

    with pytest.raises(installed_package.NotWheelInstalledError, match="no installed Python files"):
        installed_package.validate_wheel_install(module, distribution)


def test_configure_turns_validation_failure_into_a_usage_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(suite_conftest.INSTALLED_PACKAGE_ONLY_ENV, "1")

    def reject(_module: object) -> None:
        raise installed_package.NotWheelInstalledError("editable install")

    monkeypatch.setattr(installed_package, "validate_wheel_install", reject)

    with pytest.raises(pytest.UsageError, match="requires a wheel install"):
        suite_conftest.pytest_configure(None)  # type: ignore[arg-type]
