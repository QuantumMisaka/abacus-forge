from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

pytestmark = [pytest.mark.composite, pytest.mark.integration]


def test_public_composite_example_uses_partial_gather_and_selected_retry(tmp_path, capsys):
    script = Path(__file__).resolve().parents[1] / "examples/composite_unit_consumer.py"
    module = runpy.run_path(str(script), run_name="composite_example")
    module["main"](tmp_path)
    output = capsys.readouterr().out
    assert "prepared 7 vibration units" in output
    assert "partial gather: degraded, missing=5" in output
    assert "after selected retry: degraded, missing=5" in output

    root = tmp_path
    plan = json.loads((root / "reports/vibration_plan.json").read_text())
    selected = next(unit for unit in plan["subtasks"] if unit["unit_id"] == "vibration/eq")
    attempts = list((root / selected["workspace_rel"] / "reports/subtask-results").glob("*.json"))
    execute_attempts = []
    for path in attempts:
        payload = json.loads(path.read_text())
        if payload["phase"] == "execute":
            execute_attempts.append(payload)
    assert len(execute_attempts) == 2
    gathers = [json.loads(path.read_text()) for path in sorted((root / "reports/vibration-collections").glob("*.json"))]
    assert len(gathers) == 2
    assert all(row["status"] == "degraded" for row in gathers)
    assert all(len(row["summary"]["missing_units"]) == 5 for row in gathers)
