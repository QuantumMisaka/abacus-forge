from __future__ import annotations

from pathlib import Path

import pytest

from tests.real_smoke.test_abacuslite_dual_track import (
    _assert_release_matrix,
    _matrix,
)


def test_release_gate_requires_matrix_instead_of_skipping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ABACUS_FORGE_ABACUSLITE_DUAL_TRACK_MATRIX", raising=False)
    monkeypatch.setenv("ABACUS_FORGE_ABACUSLITE_REQUIRE_FULL_MATRIX", "1")

    with pytest.raises(pytest.fail.Exception, match="release gate requires"):
        _matrix()


def test_release_gate_checks_executable_digest(tmp_path: Path) -> None:
    executable = tmp_path / "abacus"
    executable.write_bytes(b"candidate executable")
    executable.chmod(0o755)
    case = {
        "track": "develop",
        "capability": "scf",
        "version": "v3.11.0",
        "basis": "pw",
        "nspin": 1,
        "executable": str(executable),
        "executable_sha256": "0" * 64,
        "input_identity": "pw-scf-fixture",
        "workspace": str(tmp_path),
    }

    with pytest.raises(pytest.fail.Exception, match="SHA-256 mismatch"):
        _assert_release_matrix([case])
