"""Typed failures at the Forge service and persistence boundaries."""

from __future__ import annotations


_EMPTY_MESSAGE_FALLBACKS = {
    "request.invalid": "invalid Forge request",
    "request.schema": "invalid Forge request schema",
    "request.path": "invalid Forge request path",
    "operation.conflict": "operation conflicts with an existing operation",
    "precondition.missing": "required Forge precondition is missing",
    "persistence.failure": "Forge persistence failure",
    "internal.failure": "unexpected Forge internal failure",
}


def normalize_error_message(error_class: str, message: str) -> str:
    """Keep error envelopes valid without hiding a useful original message."""
    if isinstance(message, str) and message:
        return message
    return _EMPTY_MESSAGE_FALLBACKS.get(error_class, "Forge operation failed")


class ForgeRequestError(ValueError):
    """The request cannot be accepted as a Forge operation."""


class ForgeSchemaError(ForgeRequestError):
    """The request has an invalid schema or field value."""


class ForgePathError(ForgeRequestError):
    """A request path is invalid or escapes its declared workspace."""


class OperationConflictError(ForgeRequestError):
    """The operation identity is already admitted or durably committed."""


class ForgePreconditionError(RuntimeError):
    """A required local input or execution precondition is absent."""


class ForgePersistenceError(ValueError):
    """Forge could not durably read or write its audit records."""


class ForgeInternalError(RuntimeError):
    """An unexpected Forge implementation failure."""
