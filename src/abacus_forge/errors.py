"""Typed failures at the Forge service and persistence boundaries."""

from __future__ import annotations


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
