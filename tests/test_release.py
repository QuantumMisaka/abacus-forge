"""The manual release gate must reject wrong source and package identities."""

from __future__ import annotations

import hashlib
import importlib.util
from io import BytesIO
from pathlib import Path
import re
import tarfile
from urllib.request import Request
import zipfile

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10/3.11 test environments
    import tomli as tomllib

pytestmark = pytest.mark.core


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/release_validate.py"
SPEC = importlib.util.spec_from_file_location("release_validate", SCRIPT)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)
COMMIT = "a" * 40
PROJECT_ROOT = SCRIPT.parents[1]


def release_case():
    run_id = 12345
    return {
        "tag": "v0.1.0",
        "version": "0.1.0",
        "workflow_ref": "refs/tags/v0.1.0",
        "workflow_sha": COMMIT,
        "workflow_repository": release.REPOSITORY,
        "run_id": str(run_id),
        "tag_ref": {"ref": "refs/tags/v0.1.0", "object": {"type": "commit", "sha": COMMIT}},
        "tag_object": None,
        "run": {
            "id": run_id,
            "event": "push",
            "path": release.CI_PATH,
            "repository": {"full_name": release.REPOSITORY},
            "head_repository": {"full_name": release.REPOSITORY},
            "head_sha": COMMIT,
            "status": "completed",
            "conclusion": "success",
            "run_attempt": 1,
        },
        "jobs": {
            "total_count": len(release.REQUIRED_JOBS),
            "jobs": [
                {
                    "name": name,
                    "run_id": run_id,
                    "run_attempt": 1,
                    "head_sha": COMMIT,
                    "status": "completed",
                    "conclusion": "success",
                }
                for name in sorted(release.REQUIRED_JOBS)
            ],
        },
        "artifacts": {
            "total_count": 1,
            "artifacts": [{
                "id": 24680,
                "name": release.ARTIFACT_NAME,
                "expired": False,
                "workflow_run": {"id": run_id, "head_sha": COMMIT},
                "digest": "sha256:" + "b" * 64,
            }],
        },
    }


def test_release_jobs_cover_declared_python_and_ci_matrix():
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = {
        classifier.rsplit(" ", 1)[-1]
        for classifier in project["project"]["classifiers"]
        if classifier.startswith("Programming Language :: Python :: 3.")
    }
    ci_text = (PROJECT_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    ci_matrices = re.findall(r"python-version:\s*\[([^\]]+)\]", ci_text)
    ci_versions = [
        {version.strip().strip('"\'') for version in matrix.split(",") if version.strip()}
        for matrix in ci_matrices
    ]

    required_versions = set(getattr(release, "REQUIRED_PYTHON_VERSIONS", ()))
    required_jobs = set(getattr(release, "REQUIRED_JOBS", ()))

    assert required_versions == declared
    assert len(ci_versions) == 2
    assert all(versions == declared for versions in ci_versions)
    assert required_jobs == {
        *(f"test ({version})" for version in declared),
        *(f"installed-package ({version})" for version in declared),
    }


def test_accepts_matching_tag_run_jobs_and_artifact():
    result = release.validate_release_run(**release_case())
    assert result["artifact_id"] == 24680
    assert result["commit"] == COMMIT


@pytest.mark.parametrize(
    "change",
    [
        lambda case: case.update(tag="v0.1.1"),
        lambda case: case.update(workflow_ref="refs/heads/main"),
        lambda case: case["tag_ref"]["object"].update(sha="c" * 40),
        lambda case: case["run"].update(id=56789),
        lambda case: case["run"].update(head_sha="c" * 40),
        lambda case: case["run"].update(event="pull_request"),
        lambda case: case["run"].update(path=".github/workflows/other.yml"),
        lambda case: case["run"].update(conclusion="failure"),
        lambda case: case["run"].update(run_attempt=2),
        lambda case: case["run"].update(repository={"full_name": "other/fork"}),
        lambda case: case["run"].update(head_repository={"full_name": "other/fork"}),
        lambda case: case["jobs"]["jobs"][0].update(conclusion="failure"),
        lambda case: case["jobs"]["jobs"].pop(),
        lambda case: case["artifacts"]["artifacts"][0].update(expired=True),
        lambda case: case["artifacts"]["artifacts"][0]["workflow_run"].update(id=56789),
        lambda case: case["artifacts"]["artifacts"][0].update(digest=""),
    ],
)
def test_rejects_wrong_release_identity(change):
    case = release_case()
    change(case)
    with pytest.raises(release.ReleaseValidationError):
        release.validate_release_run(**case)


def test_accepts_annotated_tag():
    case = release_case()
    case["tag_ref"]["object"] = {"type": "tag", "sha": "d" * 40}
    case["tag_object"] = {"sha": "d" * 40, "object": {"type": "commit", "sha": COMMIT}}
    assert release.validate_release_run(**case)["commit"] == COMMIT


def write_distributions(directory: Path, wheel_version: str = "0.1.0", sdist_version: str = "0.1.0"):
    directory.mkdir()
    def metadata(version):
        return (f"Name: abacus-forge\nVersion: {version}\n"
                "Summary: Example\nRequires-Python: >=3.10\n\n").encode()
    wheel = directory / f"abacus_forge-{wheel_version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(f"abacus_forge-{wheel_version}.dist-info/METADATA", metadata(wheel_version))
    sdist = directory / f"abacus_forge-{sdist_version}.tar.gz"
    with tarfile.open(sdist, "w:gz") as archive:
        payload = metadata(sdist_version)
        info = tarfile.TarInfo(f"abacus_forge-{sdist_version}/PKG-INFO")
        info.size = len(payload)
        archive.addfile(info, BytesIO(payload))


def test_accepts_matching_pair_of_distribution_metadata(tmp_path):
    directory = tmp_path / "dist"
    write_distributions(directory)
    hashes = release.validate_distributions(directory, "0.1.0")
    assert len(hashes) == 2
    assert all(len(value) == 64 for value in hashes.values())


@pytest.mark.parametrize("wheel_version,sdist_version", [("0.1.1", "0.1.0"), ("0.1.0", "0.1.1")])
def test_rejects_distribution_version_mismatch(tmp_path, wheel_version, sdist_version):
    directory = tmp_path / "dist"
    write_distributions(directory, wheel_version, sdist_version)
    with pytest.raises(release.ReleaseValidationError):
        release.validate_distributions(directory, "0.1.0")


def test_rejects_extra_distribution(tmp_path):
    directory = tmp_path / "dist"
    write_distributions(directory)
    (directory / "unrelated.whl").write_bytes(b"")
    with pytest.raises(release.ReleaseValidationError):
        release.validate_distributions(directory, "0.1.0")


def test_redirect_drops_api_authorization_header():
    request = Request(
        "https://api.github.com/repos/QuantumMisaka/abacus-forge/actions/artifacts/1/zip",
        headers={"Authorization": "Bearer secret"},
    )
    redirected = release.ArtifactRedirect().redirect_request(
        request, None, 302, "Found", {}, "https://storage.example.test/archive.zip"
    )
    assert redirected is not None
    assert redirected.get_header("Authorization") is None


def test_download_rejects_wrong_archive_digest_before_writing(tmp_path, monkeypatch):
    payload = BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("abacus_forge-0.1.0-py3-none-any.whl", b"wheel")
        archive.writestr("abacus_forge-0.1.0.tar.gz", b"sdist")

    class Response:
        def __enter__(self):
            return BytesIO(payload.getvalue())

        def __exit__(self, *_):
            return False

    class Opener:
        def open(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(release, "build_opener", lambda *_: Opener())
    wrong_digest = "sha256:" + hashlib.sha256(b"different").hexdigest()
    target = tmp_path / "dist"
    with pytest.raises(release.ReleaseValidationError, match="SHA-256"):
        release.download_artifact(artifact_id=1, digest=wrong_digest, token="test", dist_dir=target)
    assert not target.exists()
