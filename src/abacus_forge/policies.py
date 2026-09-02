"""Explicit, task-scoped validation policies over collected Forge facts."""

from __future__ import annotations

from abacus_forge.contracts import CheckRecord, OperationStatus


def evaluate_abacus_scf_v1(
    *,
    collection: str,
    normal_end: CheckRecord,
    convergence: CheckRecord,
    parser_complete: CheckRecord,
    required_artifacts_present: bool,
) -> tuple[OperationStatus, tuple[CheckRecord, ...]]:
    """Evaluate the complete evidence set required by the ``abacus.scf/v1`` policy."""

    if collection not in {"complete", "partial", "missing_output", "not_collected"}:
        raise ValueError("collection must be a Forge collection status")
    checks = (normal_end, convergence, parser_complete)
    if collection != "complete" or not required_artifacts_present or parser_complete.status != "passed":
        scientific = "unassessed"
    elif convergence.status == "failed":
        scientific = "rejected"
    elif all(check.status == "passed" for check in checks):
        scientific = "accepted"
    else:
        scientific = "guarded"
    return OperationStatus(execution="not_run", scientific=scientific, collection=collection), checks
