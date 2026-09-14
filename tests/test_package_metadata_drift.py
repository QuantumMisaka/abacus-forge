"""Adversarial built-artifact cases for the optional parser release boundary."""
from __future__ import annotations

import zipfile

import pytest

from tests import test_package_contract as contract


@pytest.mark.parametrize("drift", ["added", "removed", "pin", "extra", "default", "version", "none", "matching"])
def test_candidate_wheel_source_metadata_consistency(tmp_path, monkeypatch, drift):
    project = {"name": "abacus-forge", "version": "0.1.0", "dependencies": [],
               "optional-dependencies": {"parser": ["abacuslite==1.0.0"]}}
    requirements = ['abacuslite==1.0.0; extra == "parser"']
    extras = ["parser"]
    version = "0.1.0"
    if drift == "added":
        project["optional-dependencies"] = {}
    elif drift == "removed":
        requirements, extras = [], []
    elif drift == "pin":
        requirements = ['abacuslite==2.0.0; extra == "parser"']
    elif drift == "extra":
        requirements, extras = ['abacuslite==1.0.0; extra == "other"'], ["other"]
    elif drift == "default":
        requirements = ['abacuslite==1.0.0']
    elif drift == "none":
        project["optional-dependencies"] = {}
        requirements, extras = [], []
    elif drift == "version":
        version = "0.2.0"
    metadata = f"Metadata-Version: 2.3\nName: abacus-forge\nVersion: {version}\n"
    metadata += ''.join(f"Provides-Extra: {extra}\n" for extra in extras)
    metadata += ''.join(f"Requires-Dist: {req}\n" for req in requirements)
    wheel = tmp_path / "candidate.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("abacus_forge-0.1.0.dist-info/METADATA", metadata)
    monkeypatch.setattr(contract, "_project_metadata", lambda: project)
    monkeypatch.setenv("ABACUS_FORGE_WHEEL", str(wheel))
    if drift in {"none", "matching"}:
        contract.test_built_wheel_keeps_the_same_optional_dependency_boundary()
    else:
        with pytest.raises(AssertionError):
            contract.test_built_wheel_keeps_the_same_optional_dependency_boundary()


@pytest.mark.parametrize('header', ['requires-dist', 'rEqUiReS-dIsT'])
def test_case_insensitive_dependency_header_cannot_hide_default_parser(tmp_path, monkeypatch, header):
    project = {'name': 'abacus-forge', 'version': '0.1.0',
               'dependencies': [], 'optional-dependencies': {}}
    wheel = tmp_path / 'candidate.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('abacus_forge-0.1.0.dist-info/METADATA',
                         'Name: abacus-forge\nVersion: 0.1.0\n'
                         f'{header}: abacuslite==1.0.0\n')
    monkeypatch.setattr(contract, '_project_metadata', lambda: project)
    monkeypatch.setenv('ABACUS_FORGE_WHEEL', str(wheel))
    with pytest.raises(AssertionError):
        contract.test_built_wheel_keeps_the_same_optional_dependency_boundary()


@pytest.mark.parametrize("folded", [False, True])
def test_case_insensitive_headers_accept_matching_optional_parser(tmp_path, monkeypatch, folded):
    project = {'name': 'abacus-forge', 'version': '0.1.0', 'dependencies': [],
               'optional-dependencies': {'parser': ['abacuslite==1.0.0']}}
    wheel = tmp_path / 'candidate.whl'
    separator = '\n ' if folded else ' '
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('abacus_forge-0.1.0.dist-info/METADATA',
                         'name: abacus-forge\nvErSiOn: 0.1.0\nprovides-extra: parser\n'
                         f'requires-dist: abacuslite==1.0.0;{separator}extra == "parser"\n')
    monkeypatch.setattr(contract, '_project_metadata', lambda: project)
    monkeypatch.setenv('ABACUS_FORGE_WHEEL', str(wheel))
    contract.test_built_wheel_keeps_the_same_optional_dependency_boundary()
