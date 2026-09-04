from __future__ import annotations

import json

from abacus_forge.discovery import capabilities_document, request_schema_document


def test_discovery_documents_are_json_safe_and_deterministic() -> None:
    capabilities = capabilities_document()
    schema = request_schema_document("scf", "execute")
    assert json.dumps(capabilities, allow_nan=False, sort_keys=True)
    assert json.dumps(schema, allow_nan=False, sort_keys=True)
    assert capabilities == capabilities_document()
    assert schema == request_schema_document("scf", "execute")
