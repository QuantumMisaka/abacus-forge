from __future__ import annotations

import pytest

import abacus_forge
from abacus_forge.contracts import CheckRecord


def _check(name: str, status: str) -> CheckRecord:
    return CheckRecord(name=name, status=status)  # type: ignore[arg-type]


def _evaluate(
    *,
    execution: str = "completed",
    collection: str = "complete",
    normal_end: str = "passed",
    convergence: str = "passed",
    parser_complete: str = "passed",
    required_artifacts_present: bool = True,
):
    return abacus_forge.evaluate_abacus_scf_v1(
        execution=execution,
        collection=collection,
        normal_end=_check("normal_end", normal_end),
        convergence=_check("scf_convergence", convergence),
        parser_complete=_check("parser_complete", parser_complete),
        required_artifacts_present=required_artifacts_present,
    )


def test_scf_policy_accepts_only_complete_positive_evidence() -> None:
    status, checks = abacus_forge.evaluate_abacus_scf_v1(
        execution="completed",
        collection="complete",
        normal_end=_check("normal_end", "passed"),
        convergence=_check("scf_convergence", "passed"),
        parser_complete=_check("parser_complete", "passed"),
        required_artifacts_present=True,
    )

    assert status.to_dict() == {"execution": "completed", "scientific": "accepted", "collection": "complete"}
    assert [check.name for check in checks] == ["normal_end", "scf_convergence", "parser_complete"]


def test_scf_policy_rejects_explicit_nonconvergence() -> None:
    status, _ = abacus_forge.evaluate_abacus_scf_v1(
        execution="completed",
        collection="complete",
        normal_end=_check("normal_end", "passed"),
        convergence=_check("scf_convergence", "failed"),
        parser_complete=_check("parser_complete", "passed"),
        required_artifacts_present=True,
    )

    assert status.scientific == "rejected"


def test_scf_policy_keeps_missing_evidence_unassessed() -> None:
    status, _ = abacus_forge.evaluate_abacus_scf_v1(
        execution="not_run",
        collection="missing_output",
        normal_end=_check("normal_end", "unavailable"),
        convergence=_check("scf_convergence", "unavailable"),
        parser_complete=_check("parser_complete", "unavailable"),
        required_artifacts_present=False,
    )

    assert status.scientific == "unassessed"


@pytest.mark.parametrize("execution", ["completed", "not_run"])
def test_scf_policy_preserves_valid_execution_fact(execution: str) -> None:
    status, _ = _evaluate(execution=execution)

    assert status.execution == execution
    assert status.scientific == "accepted"


@pytest.mark.parametrize("execution", ["failed", "skipped"])
def test_scf_policy_never_accepts_failed_or_skipped_execution(execution: str) -> None:
    status, _ = _evaluate(execution=execution)

    assert status.execution == execution
    assert status.scientific == "unassessed"


@pytest.mark.parametrize("collection", ["not_collected", "missing_output"])
def test_scf_policy_keeps_absent_collection_unassessed(collection: str) -> None:
    status, _ = _evaluate(collection=collection, required_artifacts_present=False)

    assert status.collection == collection
    assert status.scientific == "unassessed"


def test_scf_policy_guards_partial_collection_with_usable_evidence() -> None:
    status, _ = _evaluate(collection="partial")

    assert status.scientific == "guarded"


def test_scf_policy_keeps_missing_required_artifacts_unassessed() -> None:
    status, _ = _evaluate(required_artifacts_present=False)

    assert status.scientific == "unassessed"


@pytest.mark.parametrize("status_name", ["failed", "warning", "unavailable"])
def test_scf_policy_guards_nonpassing_normal_end(status_name: str) -> None:
    status, _ = _evaluate(normal_end=status_name)

    assert status.scientific == "guarded"


@pytest.mark.parametrize("status_name", ["warning", "unavailable"])
def test_scf_policy_guards_uncertain_convergence(status_name: str) -> None:
    status, _ = _evaluate(convergence=status_name)

    assert status.scientific == "guarded"


@pytest.mark.parametrize("status_name", ["warning", "unavailable"])
def test_scf_policy_guards_degraded_parser_evidence(status_name: str) -> None:
    status, _ = _evaluate(parser_complete=status_name)

    assert status.scientific == "guarded"


def test_scf_policy_keeps_failed_parser_evidence_unassessed() -> None:
    status, _ = _evaluate(parser_complete="failed")

    assert status.scientific == "unassessed"


def test_scf_policy_rejects_explicit_nonconvergence_with_complete_parse() -> None:
    status, _ = _evaluate(convergence="failed")

    assert status.scientific == "rejected"


def test_scf_policy_does_not_turn_missing_collection_into_rejection() -> None:
    status, _ = _evaluate(collection="missing_output", convergence="failed", required_artifacts_present=False)

    assert status.scientific == "unassessed"


@pytest.mark.parametrize(
    ("field", "wrong_name"),
    [("normal_end", "completion"), ("convergence", "converged"), ("parser_complete", "parse")],
)
def test_scf_policy_requires_exact_check_names(field: str, wrong_name: str) -> None:
    checks = {
        "normal_end": _check("normal_end", "passed"),
        "convergence": _check("scf_convergence", "passed"),
        "parser_complete": _check("parser_complete", "passed"),
    }
    checks[field] = _check(wrong_name, "passed")

    with pytest.raises(ValueError, match=field):
        abacus_forge.evaluate_abacus_scf_v1(
            execution="completed",
            collection="complete",
            normal_end=checks["normal_end"],
            convergence=checks["convergence"],
            parser_complete=checks["parser_complete"],
            required_artifacts_present=True,
        )


def test_scf_policy_rejects_invalid_execution() -> None:
    with pytest.raises(ValueError, match="execution"):
        _evaluate(execution="done")


def test_scf_policy_rejects_invalid_collection() -> None:
    with pytest.raises(ValueError, match="collection"):
        _evaluate(collection="unknown")
