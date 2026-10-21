"""Validate the provenance and distributions for a manual PyPI release.

The GitHub API is read-only here. Publishing happens in a separate job.
"""

from __future__ import annotations

import argparse
import email.parser
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tarfile
from urllib.parse import urlparse
from urllib.request import build_opener, HTTPRedirectHandler, Request, urlopen
import zipfile

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 development/test environments
    import tomli as tomllib


REPOSITORY = "QuantumMisaka/abacus-forge"
CI_PATH = ".github/workflows/ci.yml"
ARTIFACT_NAME = "forge-distributions-3.12"
REQUIRED_JOBS = {
    "test (3.10)",
    "test (3.12)",
    "installed-package (3.10)",
    "installed-package (3.12)",
}
SHA = re.compile(r"[0-9a-f]{40}\Z")
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024


class ReleaseValidationError(ValueError):
    pass


class ArtifactRedirect(HTTPRedirectHandler):
    """Do not send the GitHub API token to a signed artifact storage URL."""

    def redirect_request(self, request, fp, code, msg, headers, new_url):
        require(urlparse(new_url).scheme == "https", "artifact redirect must use HTTPS")
        redirected = super().redirect_request(request, fp, code, msg, headers, new_url)
        if redirected is not None and urlparse(new_url).hostname != urlparse(request.full_url).hostname:
            redirected.remove_header("Authorization")
        return redirected


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseValidationError(message)


def project_version() -> str:
    path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    return tomllib.loads(path.read_text(encoding="utf-8"))["project"]["version"]


def api_get(path: str, token: str) -> dict:
    request = Request(
        f"https://api.github.com/repos/{REPOSITORY}/{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def validate_release_run(
    *,
    tag: str,
    version: str,
    workflow_ref: str,
    workflow_sha: str,
    workflow_repository: str,
    run_id: str,
    tag_ref: dict,
    tag_object: dict | None,
    run: dict,
    jobs: dict,
    artifacts: dict,
) -> dict:
    require(tag == f"v{version}", "tag does not match project version")
    require(workflow_ref == f"refs/tags/{tag}", "dispatch the publish workflow at the release tag")
    require(workflow_repository == REPOSITORY, "publish workflow is not running in the expected repository")
    require(bool(SHA.fullmatch(workflow_sha)), "invalid workflow commit")
    require(run_id.isdecimal() and int(run_id) > 0, "invalid CI run ID")

    reference = tag_ref.get("ref")
    target = tag_ref.get("object", {})
    require(reference == f"refs/tags/{tag}", "tag reference does not match the requested tag")
    if target.get("type") == "tag":
        require(tag_object is not None, "annotated tag object missing")
        require(tag_object.get("sha") == target.get("sha"), "annotated tag object identity mismatch")
        target = tag_object.get("object", {})
    require(target.get("type") == "commit" and bool(SHA.fullmatch(target.get("sha", ""))),
            "tag must resolve directly to a commit")
    commit = target["sha"]
    require(commit == workflow_sha, "tag commit differs from dispatch workflow commit")

    require(run.get("id") == int(run_id), "CI run ID mismatch")
    require(run.get("event") == "push", "CI run must be from a push event")
    require(run.get("path") == CI_PATH, "run is not the expected CI workflow")
    require(run.get("repository", {}).get("full_name") == REPOSITORY, "CI run is from another repository")
    require(run.get("head_repository", {}).get("full_name") == REPOSITORY,
            "CI run source is from another repository")
    require(run.get("head_sha") == commit, "CI run did not test the tag commit")
    require(run.get("status") == "completed" and run.get("conclusion") == "success",
            "CI run did not finish successfully")
    # Re-runs can leave artifacts from an earlier attempt under the same run ID.
    require(run.get("run_attempt") == 1, "select an initial CI run, not a re-run")

    listed_jobs = jobs.get("jobs", [])
    require(jobs.get("total_count") == len(listed_jobs), "CI job list is incomplete")
    matching_jobs = {job.get("name"): job for job in listed_jobs if job.get("name") in REQUIRED_JOBS}
    require(set(matching_jobs) == REQUIRED_JOBS, "required CI jobs are missing")
    for name, job in matching_jobs.items():
        require(job.get("run_id") == int(run_id) and job.get("run_attempt") == 1,
                f"{name} belongs to another CI attempt")
        require(job.get("head_sha") == commit, f"{name} tested a different commit")
        require(job.get("status") == "completed" and job.get("conclusion") == "success",
                f"{name} did not pass")

    listed_artifacts = artifacts.get("artifacts", [])
    require(artifacts.get("total_count") == len(listed_artifacts), "CI artifact list is incomplete")
    matching_artifacts = [item for item in listed_artifacts if item.get("name") == ARTIFACT_NAME]
    require(len(matching_artifacts) == 1, "expected exactly one tested Python 3.12 distribution artifact")
    artifact = matching_artifacts[0]
    require(not artifact.get("expired"), "tested distribution artifact has expired")
    require(isinstance(artifact.get("id"), int), "artifact ID missing")
    require(artifact.get("workflow_run", {}).get("id") == int(run_id), "artifact is from another CI run")
    require(artifact.get("workflow_run", {}).get("head_sha") == commit,
            "artifact is from another commit")
    digest = artifact.get("digest", "")
    require(bool(re.fullmatch(r"sha256:[0-9a-f]{64}", digest)), "artifact archive digest missing")
    return {"artifact_id": artifact["id"], "digest": digest, "commit": commit, "run_id": int(run_id)}


def read_metadata(data: bytes):
    return email.parser.BytesParser().parsebytes(data, headersonly=True)


def validate_distributions(dist_dir: Path, version: str) -> dict:
    files = sorted(path for path in dist_dir.iterdir() if path.is_file())
    wheel_name = f"abacus_forge-{version}-py3-none-any.whl"
    sdist_name = f"abacus_forge-{version}.tar.gz"
    require({path.name for path in files} == {wheel_name, sdist_name} and len(files) == 2,
            "distribution directory must contain exactly the expected wheel and sdist")
    wheel = dist_dir / wheel_name
    sdist = dist_dir / sdist_name
    with zipfile.ZipFile(wheel) as archive:
        metadata_path = f"abacus_forge-{version}.dist-info/METADATA"
        require(archive.namelist().count(metadata_path) == 1, "wheel metadata missing or duplicated")
        wheel_metadata = read_metadata(archive.read(metadata_path))
    with tarfile.open(sdist, "r:gz") as archive:
        metadata_path = f"abacus_forge-{version}/PKG-INFO"
        matches = [member for member in archive.getmembers() if member.name == metadata_path and member.isfile()]
        require(len(matches) == 1, "sdist metadata missing or duplicated")
        stream = archive.extractfile(matches[0])
        require(stream is not None, "sdist metadata unreadable")
        sdist_metadata = read_metadata(stream.read())
    for metadata in (wheel_metadata, sdist_metadata):
        require(metadata.get("Name") == "abacus-forge", "distribution package name mismatch")
        require(metadata.get("Version") == version, "distribution version mismatch")
        require(metadata.get("Requires-Python") == ">=3.10", "distribution Python range mismatch")
    for key in ("Name", "Version", "Summary", "Requires-Python"):
        require(wheel_metadata.get(key) == sdist_metadata.get(key), f"wheel/sdist {key} mismatch")
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


def download_artifact(*, artifact_id: int, digest: str, token: str, dist_dir: Path) -> None:
    require(artifact_id > 0, "invalid artifact ID")
    require(bool(re.fullmatch(r"sha256:[0-9a-f]{64}", digest)), "invalid artifact digest")
    request = Request(
        f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{artifact_id}/zip",
        headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"},
    )
    with build_opener(ArtifactRedirect()).open(request, timeout=60) as response:
        payload = response.read(MAX_ARCHIVE_BYTES + 1)
    require(len(payload) <= MAX_ARCHIVE_BYTES, "artifact archive exceeds size limit")
    require(hashlib.sha256(payload).hexdigest() == digest.removeprefix("sha256:"),
            "artifact archive SHA-256 does not match GitHub metadata")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = archive.infolist()
        require(len(members) == 2, "artifact must contain exactly two distributions")
        require(all(member.filename == Path(member.filename).name and not member.is_dir()
                    and member.file_size <= MAX_ARCHIVE_BYTES for member in members),
                "artifact contains an unexpected path or oversized file")
        dist_dir.mkdir(parents=True, exist_ok=False)
        for member in members:
            with (dist_dir / member.filename).open("xb") as output:
                output.write(archive.read(member))


def command_verify_run(args: argparse.Namespace) -> None:
    tag = os.environ["RELEASE_TAG"]
    run_id = os.environ["RELEASE_RUN_ID"]
    require(bool(re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", tag)), "invalid release tag")
    require(run_id.isdecimal() and int(run_id) > 0, "invalid CI run ID")
    token = os.environ["GITHUB_TOKEN"]
    tag_ref = api_get(f"git/ref/tags/{tag}", token)
    tag_object = None
    if tag_ref.get("object", {}).get("type") == "tag":
        object_sha = tag_ref["object"]["sha"]
        require(bool(SHA.fullmatch(object_sha)), "invalid annotated tag SHA")
        tag_object = api_get(f"git/tags/{object_sha}", token)
    run = api_get(f"actions/runs/{run_id}", token)
    jobs = api_get(f"actions/runs/{run_id}/jobs?per_page=100", token)
    artifacts = api_get(f"actions/runs/{run_id}/artifacts?per_page=100", token)
    result = validate_release_run(
        tag=tag,
        version=project_version(),
        workflow_ref=os.environ["GITHUB_REF"],
        workflow_sha=os.environ["GITHUB_SHA"],
        workflow_repository=os.environ["GITHUB_REPOSITORY"],
        run_id=run_id,
        tag_ref=tag_ref,
        tag_object=tag_object,
        run=run,
        jobs=jobs,
        artifacts=artifacts,
    )
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"artifact_id={result['artifact_id']}\n")
        output.write(f"digest={result['digest']}\n")
    print(json.dumps(result, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify-run")
    download = commands.add_parser("download")
    download.add_argument("--artifact-id", type=int, required=True)
    download.add_argument("--digest", required=True)
    download.add_argument("--dist-dir", type=Path, required=True)
    distributions = commands.add_parser("verify-distributions")
    distributions.add_argument("--dist-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "verify-run":
            command_verify_run(args)
        elif args.command == "download":
            download_artifact(
                artifact_id=args.artifact_id,
                digest=args.digest,
                token=os.environ["GITHUB_TOKEN"],
                dist_dir=args.dist_dir,
            )
        else:
            print(json.dumps(validate_distributions(args.dist_dir, project_version()), sort_keys=True))
    except (ReleaseValidationError, KeyError, OSError, zipfile.BadZipFile, tarfile.TarError) as error:
        parser.exit(1, f"release validation failed: {error}\n")


if __name__ == "__main__":
    main()
