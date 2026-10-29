# Public contract and maturity

The initial public package is `0.1.0` and early/experimental. Maturity describes the present scope and validation of a scientific capability; it does not make a documented machine contract disposable. Current capability maturity and supported operations are returned by `abacus-forge capabilities`.

Within `0.x`, patch releases will not intentionally break documented v1 requests, result envelopes, exit-code meanings, or append-only workspace records. If a breaking change becomes necessary, it belongs in a minor/schema version change with migration guidance. This commitment does not promise that every experimental capability already has full scientific validation or that every undocumented internal Python symbol remains fixed.

Before the first public release, the owner authorized withdrawing the unused
2026-10-29 Phase A prototype introduced at `3d3ae52`. Its
`abacus_forge.capability_registry` records and `capability-contracts` command
are removed. Source-checkout consumers of that prototype should use
`abacus-forge capabilities` and `abacus-forge schema <capability> <operation>`
(Python: `discovery.capabilities_document()` and
`discovery.request_schema_document()`), then inspect actual operation results
for artifacts, metrics and diagnostics. These interfaces retain their existing
schemas; this is an explicit prototype withdrawal, not a promise of wire
compatibility with its seed document. There is no replacement global identity,
resource or Paimon projection schema. See the
[scoped decision and verification](superpowers/plans/2026-10-29-forge-computation-factory-phase-a.md).

The typed request schema is `forge.request/v1`; result, error, capability, and workspace schemas identify their own versions. An Agent should discover a capability and its operation schema, construct a fresh operation ID, then check both process exit status and the returned envelope or error. `execution=completed` reports process behavior, `collection=complete` reports available requested facts, and `scientific=unassessed` leaves scientific acceptance to the caller. A successful transport or a normal engine exit alone is not evidence that a requested calculation is complete or physically acceptable.

The human `prepare`, `execute`, and `collect` primitives remain available. Their JSON shapes differ from typed outcomes: human `collect --json` returns a `CollectionResult` with top-level `status` (`completed`, `unfinished`, `failed`, or `missing-output`), `metrics`, and `diagnostics`, rather than an `envelope.status.collection` or `checks` field. Typed services and machine requests are separate operation boundaries; typed prepare requires explicit asset maps, while the human prepare primitive can discover assets from supplied directories. Legacy unit, sequence, and property-pack APIs remain available with their existing behavior, but they are not the recommended starting point for a new Agent integration. See the [quickstart](quickstart.md), [Agent guide](agents.md), and [current interface reference](reference.md) for concrete calls.
