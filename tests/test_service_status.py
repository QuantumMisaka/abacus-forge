from __future__ import annotations

import abacus_forge
from abacus_forge.contracts import CheckRecord


def _check(name: str, status: str) -> CheckRecord:
    return CheckRecord(name=name, status=status)  # type: ignore[arg-type]


def test_scf_policy_accepts_only_complete_positive_evidence() -> None:
    status, checks = abacus_forge.evaluate_abacus_scf_v1(
        collection="complete",
        normal_end=_check("normal_end", "passed"),
        convergence=_check("scf_convergence", "passed"),
        parser_complete=_check("parser_complete", "passed"),
        required_artifacts_present=True,
    )

    assert status.to_dict() == {"execution": "not_run", "scientific": "accepted", "collection": "complete"}
    assert [check.name for check in checks] == ["normal_end", "scf_convergence", "parser_complete"]


def test_scf_policy_rejects_explicit_nonconvergence() -> None:
    status, _ = abacus_forge.evaluate_abacus_scf_v1(
        collection="complete",
        normal_end=_check("normal_end", "passed"),
        convergence=_check("scf_convergence", "failed"),
        parser_complete=_check("parser_complete", "passed"),
        required_artifacts_present=True,
    )

    assert status.scientific == "rejected"


def test_scf_policy_keeps_missing_evidence_unassessed() -> None:
    status, _ = abacus_forge.evaluate_abacus_scf_v1(
        collection="missing_output",
        normal_end=_check("normal_end", "unavailable"),
        convergence=_check("scf_convergence", "unavailable"),
        parser_complete=_check("parser_complete", "unavailable"),
        required_artifacts_present=False,
    )

    assert status.scientific == "unassessed"
