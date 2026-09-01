from __future__ import annotations

from pathlib import Path

import pytest

from abacus_forge import collect
from tests.support.reference_workspaces import copy_abacustest_scf_workspace


@pytest.mark.benchmark
def test_abacustest_scf_projection_preserves_migration_metrics(tmp_path: Path) -> None:
    result = collect(copy_abacustest_scf_workspace(tmp_path / "benchmark"))
    assert result.status == "completed"
    assert len(result.metrics["force"]) == 81
    expected_stress_rows = [
        [-52.80278090212644, -0.20034687716893254, -0.16869734918889936],
        [-0.20034687716893204, -52.87869324794468, -0.45515956333833435],
        [-0.16869734918889878, -0.45515956333833385, -39.96544028144169],
    ]
    # The public collector contract stores the latest 3x3 stress tensor as a
    # flat list, while the ABACUSTest reference records rows.
    expected_stress = [value for row in expected_stress_rows for value in row]
    assert result.metrics["stress"] == pytest.approx(
        expected_stress
    )
    assert result.metrics["pressure"] == pytest.approx(-48.548971477133335)
    assert result.metrics["total_time"] == pytest.approx(932.927)
