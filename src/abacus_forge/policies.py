"""Explicit, task-scoped validation policies over collected Forge facts."""

from __future__ import annotations

from abacus_forge.contracts import CheckRecord, OperationStatus


_EXECUTION_STATUSES = frozenset({"not_run", "completed", "failed", "skipped"})
_COLLECTION_STATUSES = frozenset({"not_collected", "complete", "partial", "missing_output"})
_REQUIRED_CHECK_NAMES = ("normal_end", "scf_convergence", "parser_complete")


def evaluate_abacus_scf_v1(
    *,
    execution: str,
    collection: str,
    normal_end: CheckRecord,
    convergence: CheckRecord,
    parser_complete: CheckRecord,
    required_artifacts_present: bool,
) -> tuple[OperationStatus, tuple[CheckRecord, ...]]:
    """Evaluate the complete evidence set required by ``abacus.scf/v1``.

    This function is deliberately a pure policy: all execution and collection
    facts are supplied by the caller, and no filesystem, process, or parser is
    consulted here.  The policy preserves the operation-local execution fact
    while deriving only the scientific assessment.
    """

    if not isinstance(execution, str) or execution not in _EXECUTION_STATUSES:
        raise ValueError("execution must be one of: " + ", ".join(sorted(_EXECUTION_STATUSES)))
    if not isinstance(collection, str) or collection not in _COLLECTION_STATUSES:
        raise ValueError("collection must be one of: " + ", ".join(sorted(_COLLECTION_STATUSES)))
    if not isinstance(required_artifacts_present, bool):
        raise ValueError("required_artifacts_present must be a boolean")

    checks = (normal_end, convergence, parser_complete)
    for check, expected_name in zip(checks, _REQUIRED_CHECK_NAMES):
        if not isinstance(check, CheckRecord):
            raise ValueError("SCF policy checks must be CheckRecord values")
        if check.name != expected_name:
            raise ValueError(f"{expected_name} check must be named {expected_name!r}")

    # Missing collection/artifacts do not provide enough evidence for a
    # scientific assessment.  In particular, missing collection must not be
    # misreported as scientific rejection.  Execution is an independent,
    # service-supplied axis and must never be used to infer scientific state.
    if collection in {"not_collected", "missing_output"} or not required_artifacts_present:
        scientific = "unassessed"
    # A failed parser cannot establish usable domain evidence.  Warnings and
    # unavailable checks retain a guarded assessment when output is usable.
    elif parser_complete.status == "failed":
        scientific = "unassessed"
    elif convergence.status == "failed":
        scientific = "rejected"
    elif (
        collection == "complete"
        and all(check.status == "passed" for check in checks)
    ):
        scientific = "accepted"
    else:
        scientific = "guarded"
    return OperationStatus(execution=execution, scientific=scientific, collection=collection), checks
