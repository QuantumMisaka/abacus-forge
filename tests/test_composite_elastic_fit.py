import numpy as np
import pytest

from abacus_forge.composite.elastic import _fit_elastic, _strain_set


def _stress_voigt(voigt_strain: np.ndarray) -> np.ndarray:
    voigt_stiffness = np.diag([200.0, 200.0, 200.0, 50.0, 50.0, 50.0])
    return voigt_stiffness @ voigt_strain


def _rows_for_cubic_tensor() -> list[dict]:
    rows = []
    for strain in _strain_set(normal_strain=0.01, shear_strain=0.01):
        if np.allclose(strain, 0):
            stress_3x3 = np.zeros((3, 3))
        else:
            voigt_strain = np.array([
                strain[0, 0], strain[1, 1], strain[2, 2],
                2 * strain[1, 2], 2 * strain[0, 2], 2 * strain[0, 1],
            ])
            stress_voigt = _stress_voigt(voigt_strain)
            stress_3x3 = np.array([
                [stress_voigt[0], stress_voigt[5], stress_voigt[4]],
                [stress_voigt[5], stress_voigt[1], stress_voigt[3]],
                [stress_voigt[4], stress_voigt[3], stress_voigt[2]],
            ])
            # Independent normal strains deliberately retain transverse C12 stress.
            if abs(strain[0, 0]) > 0:
                stress_3x3[1, 1] = 100.0 * strain[0, 0]
                stress_3x3[2, 2] = 100.0 * strain[0, 0]
            if abs(strain[1, 1]) > 0:
                stress_3x3[0, 0] = 100.0 * strain[1, 1]
                stress_3x3[2, 2] = 100.0 * strain[1, 1]
            if abs(strain[2, 2]) > 0:
                stress_3x3[0, 0] = 100.0 * strain[2, 2]
                stress_3x3[1, 1] = 100.0 * strain[2, 2]
        # Forge collector exposes raw ABACUS kbar; helper converts sign/units.
        rows.append({"strain": strain.tolist(), "stress": (-10.0 * stress_3x3).tolist()})
    return rows


def test_elastic_fit_recovers_cubic_moduli():
    fit = _fit_elastic(_rows_for_cubic_tensor())

    assert fit is not None
    assert np.asarray(fit["elastic_tensor_GPa"])[0, 0] == pytest.approx(200.0)
    assert np.asarray(fit["elastic_tensor_GPa"])[0, 1] == pytest.approx(100.0)
    assert np.asarray(fit["elastic_tensor_GPa"])[3, 3] == pytest.approx(50.0)
    assert fit["bulk_modulus_GPa"] == pytest.approx(133.3333333333)
    assert fit["shear_modulus_GPa"] == pytest.approx(50.0)
    assert fit["young_modulus_GPa"] == pytest.approx(133.3333333333)
    assert fit["poisson_ratio"] == pytest.approx(1 / 3)


def test_elastic_fit_requires_base_and_deformed_rows():
    rows = _rows_for_cubic_tensor()
    assert _fit_elastic([row for row in rows if not np.allclose(row["strain"], 0)]) is None
    assert _fit_elastic([row for row in rows if np.allclose(row["strain"], 0)]) is None


def test_post_elastic_publishes_fit_from_collected_stresses(tmp_path, monkeypatch):
    from abacus_forge.api import prepare
    from abacus_forge.composite import elastic
    from ase import Atoms

    workspace = tmp_path / "elastic-case"
    prepare(workspace, structure=Atoms("Si", positions=[[0, 0, 0]], cell=[5, 5, 5], pbc=True), task="scf")
    prepared = elastic.prepare_elastic(workspace)
    synthetic = _rows_for_cubic_tensor()
    rows = [
        {
            "workspace": item["workspace"],
            "status": "completed",
            "metrics": {"stress": synthetic[index]["stress"]},
            "diagnostics": {},
        }
        for index, item in enumerate(prepared.subtasks)
    ]
    monkeypatch.setattr(elastic, "collect_subtasks", lambda _paths: rows)

    result = elastic.post_elastic(workspace)

    assert result.summary["elastic_fit"] == "available"
    assert (workspace / "reports" / "metrics_elastic.json").is_file()
    assert (workspace / "reports" / "elastic_tensor.json").is_file()
    assert (workspace / "reports" / "elastic_fit.json").is_file()
