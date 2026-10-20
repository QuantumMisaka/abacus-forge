"""Synthetic BEC numerical regressions; not material validation."""

from copy import deepcopy
from math import sqrt

import pytest

from abacus_forge.bec import calculate_bec
from abacus_forge.structure import BOHR_TO_ANG

pytestmark = pytest.mark.experimental


CELL = [[2.0, 0.0, 0.0], [1.0, 2.0, 0.0], [0.0, 0.0, 3.0]]  # bohr, skew
UNIT = [[1, 0, 0], [1 / sqrt(5), 2 / sqrt(5), 0], [0, 0, 1]]
QUANTA = [2.0, sqrt(5), 3.0]
VOLUME = 12.0
SI_FACTOR = 1.60097e-19 / (5.29177e-11) ** 2


def _fact(gdir: int, displacement_angstrom: float, scalar: float, *, quantum: float | None = None) -> dict:
    axis = [0.0, 0.0, 0.0]
    axis[0] = displacement_angstrom
    q = QUANTA[gdir - 1] if quantum is None else quantum
    row = {"unit": "(e/Omega).bohr", "scalar": scalar, "modulus": q,
           "cartesian": [scalar * v for v in UNIT[gdir - 1]], "source_log_path": "synthetic.log"}
    row2 = {"unit": "e/bohr^2", "scalar": scalar / VOLUME, "modulus": q / VOLUME,
            "cartesian": [scalar * v / VOLUME for v in UNIT[gdir - 1]], "source_log_path": "synthetic.log"}
    row3 = {"unit": "C/m^2", "scalar": scalar / VOLUME * SI_FACTOR,
            "modulus": q / VOLUME * SI_FACTOR,
            "cartesian": [scalar * v / VOLUME * SI_FACTOR for v in UNIT[gdir - 1]],
            "source_log_path": "synthetic.log"}
    return {"schema_version": "forge.polarization/v1", "gdir": gdir,
            "ionic_phase": 0.0, "electronic_phase": 0.0,
            "rows": {"(e/Omega).bohr": row, "e/bohr^2": row2, "C/m^2": row3},
            "geometry": {"cell_angstrom": [[v * BOHR_TO_ANG for v in r] for r in CELL],
                         "positions_angstrom": [axis], "symbols": ["H"], "atom_labels": ["H"],
                         "species_meta": {"H": {"mass": 1.0, "pp": "H.upf"}},
                         "move_flags": [[1, 1, 1]]},
            "input": {"berry_phase": "1", "gdir": str(gdir), "nspin": "1", "calculation": "nscf"}}


def _column(samples: list[tuple[float, list[float], dict | None]]) -> tuple[dict, dict]:
    facts = {}
    records = []
    for index, (displacement, scalars, offsets) in enumerate(samples):
        paths = []
        for gdir, scalar in enumerate(scalars, 1):
            path = f"outputs/s{index}/r{gdir}.json"
            facts[path] = _fact(gdir, displacement, scalar)
            paths.append(path)
        record = {"displacement_angstrom": displacement, "polarization_paths_rel": paths}
        if offsets is not None:
            record["branch_offsets"] = offsets
        records.append(record)
    return {"atom_index": 1, "direction": "x", "samples": records}, facts


def test_skew_cell_cartesian_sum_and_angstrom_conversion() -> None:
    delta = 0.1 * BOHR_TO_ANG
    column, facts = _column([(-delta, [-0.02, -0.03, -0.04], None),
                             (0.0, [0, 0, 0], None),
                             (delta, [0.02, 0.03, 0.04], None)])
    result = calculate_bec([column], facts, branch_mode="auto", max_step_fraction=0.1)
    assert result["requested_complete"] is True
    assert result["full_tensor_complete"] is False
    assert result["computed_columns"][0]["values"] == pytest.approx(
        [0.2 + 0.3 / sqrt(5), 0.3 * 2 / sqrt(5), 0.4], abs=1e-7)
    assert result["tensor"][0][0][0] == pytest.approx(0.2 + 0.3 / sqrt(5))
    assert result["tensor"][0][1][0] == pytest.approx(0.3 * 2 / sqrt(5))
    assert result["tensor"][0][0][1] is None


def test_auto_wrap_and_explicit_multiple_winding() -> None:
    delta = 0.1 * BOHR_TO_ANG
    column, facts = _column([(-delta, [0.7, 0, 0], None), (0, [0.9, 0, 0], None),
                             (delta, [-0.9, 0, 0], None)])
    # Physical endpoint q is 1.1 after adding one printed quantum of 2.
    result = calculate_bec([column], facts, branch_mode="auto", max_step_fraction=0.2)
    assert result["columns"][0]["status"] == "computed"
    assert result["computed_columns"][0]["values"][0] == pytest.approx(2)
    result = calculate_bec([column], facts, branch_mode="auto", max_step_fraction=0.1)
    assert result["columns"][0]["status"] == "ambiguous"  # exactly at caller bound
    for sample, offset in zip(column["samples"], [-3, 0, 3]):
        sample["branch_offsets"] = {"1": offset, "2": 0, "3": 0}
    result = calculate_bec([column], facts, branch_mode="explicit", max_step_fraction=None)
    assert result["columns"][0]["status"] == "computed"
    assert result["computed_columns"][0]["values"][0] == pytest.approx(52.0)
    assert result["columns"][0]["branch_trace"][0]["method"] == "manual_offsets"


def test_auto_wrap_with_connected_small_steps() -> None:
    delta = 0.1 * BOHR_TO_ANG
    column, facts = _column([(-delta, [0.8, 0, 0], None), (-delta / 2, [0.4, 0, 0], None),
                             (0, [0, 0, 0], None), (delta / 2, [-0.4, 0, 0], None),
                             (delta, [-0.8, 0, 0], None)])
    result = calculate_bec([column], facts, branch_mode="auto", max_step_fraction=0.25)
    assert result["columns"][0]["status"] == "computed"
    assert result["computed_columns"][0]["values"][0] == pytest.approx(-8)


def test_missing_gdir_and_endpoint_keep_independent_column() -> None:
    delta = 0.1 * BOHR_TO_ANG
    good, facts = _column([(-delta, [0, 0, 0], {"1": 0, "2": 0, "3": 0}),
                           (delta, [0.1, 0, 0], {"1": 0, "2": 0, "3": 0})])
    bad = deepcopy(good)
    bad["direction"] = "y"
    bad["samples"][1]["polarization_paths_rel"] = ["missing.json"]
    result = calculate_bec([good, bad], facts, branch_mode="explicit", max_step_fraction=None)
    assert len(result["computed_columns"]) == 1
    assert result["requested_complete"] is False
    assert result["columns"][1]["status"] == "missing"


def _three_axis_columns(*, two_atoms: bool) -> tuple[list[dict], dict]:
    delta = 0.1 * BOHR_TO_ANG
    columns = []
    all_facts = {}
    for axis, direction in enumerate("xyz"):
        column, facts = _column([(-delta, [-0.01, 0, 0], {"1": 0, "2": 0, "3": 0}),
                                 (delta, [0.01, 0, 0], {"1": 0, "2": 0, "3": 0})])
        column["direction"] = direction
        for sample in column["samples"]:
            displacement = sample["displacement_angstrom"]
            new_paths = []
            for old_path in sample["polarization_paths_rel"]:
                fact = facts[old_path]
                fact["geometry"]["positions_angstrom"][0] = [0.0, 0.0, 0.0]
                fact["geometry"]["positions_angstrom"][0][axis] = displacement
                if two_atoms:
                    fact["geometry"]["positions_angstrom"].append([0.2, 0.3, 0.4])
                    fact["geometry"]["symbols"].append("H")
                    fact["geometry"]["atom_labels"].append("H")
                    fact["geometry"]["move_flags"].append([1, 1, 1])
                new_path = f"{direction}/{old_path}"
                all_facts[new_path] = fact
                new_paths.append(new_path)
            sample["polarization_paths_rel"] = new_paths
        columns.append(column)
    return columns, all_facts


def test_full_tensor_requires_all_axes_of_every_atom() -> None:
    columns, facts = _three_axis_columns(two_atoms=False)
    complete = calculate_bec(columns, facts, branch_mode="explicit", max_step_fraction=None)
    assert complete["requested_complete"] is True
    assert complete["full_tensor_complete"] is True
    assert all(value is not None for row in complete["tensor"][0] for value in row)
    columns, facts = _three_axis_columns(two_atoms=True)
    subset = calculate_bec(columns, facts, branch_mode="explicit", max_step_fraction=None)
    assert subset["requested_complete"] is True
    assert subset["full_tensor_complete"] is False
    assert len(subset["tensor"]) == 2


def test_supported_spin_and_printed_quantum_multiples() -> None:
    delta = 0.1 * BOHR_TO_ANG
    column, facts = _column([(-delta, [0, 0, 0], {"1": 0, "2": 0, "3": 0}),
                             (delta, [0.02, 0, 0], {"1": 0, "2": 0, "3": 0})])
    for fact in facts.values():
        fact["input"]["nspin"] = "2"
    assert calculate_bec([column], facts, branch_mode="explicit", max_step_fraction=None)["requested_complete"] is True
    for fact in facts.values():
        fact["input"]["nspin"] = "1"
        for row in fact["rows"].values():
            row["modulus"] *= 2
    assert calculate_bec([column], facts, branch_mode="explicit", max_step_fraction=None)["requested_complete"] is True
    for fact in facts.values():
        fact["input"]["nspin"] = "2"
    assert calculate_bec([column], facts, branch_mode="explicit", max_step_fraction=None)["columns"][0]["status"] == "invalid"


@pytest.mark.parametrize("mutation", [
    lambda facts, paths: facts[paths[0]]["geometry"]["positions_angstrom"][0].__setitem__(1, 0.03),
    lambda facts, paths: facts[paths[0]]["input"].__setitem__("nspin", "2"),
    lambda facts, paths: facts[paths[0]]["rows"]["(e/Omega).bohr"].__setitem__("modulus", 5.0),
    lambda facts, paths: facts[paths[0]]["rows"]["(e/Omega).bohr"].__setitem__("cartesian", [0, 1, 0]),
    lambda facts, paths: facts[paths[0]]["rows"]["C/m^2"].__setitem__("scalar", "BAD"),
])
def test_invalid_geometry_spin_quantum_or_vector(mutation) -> None:
    delta = 0.1 * BOHR_TO_ANG
    column, facts = _column([(-delta, [0, 0, 0], None), (0, [0, 0, 0], None),
                             (delta, [0, 0, 0], None)])
    mutation(facts, column["samples"][0]["polarization_paths_rel"])
    result = calculate_bec([column], facts, branch_mode="auto", max_step_fraction=0.2)
    assert result["columns"][0]["status"] == "invalid"


def test_auto_requires_bound_and_zero_sample_and_rejects_half_quantum() -> None:
    delta = 0.1 * BOHR_TO_ANG
    column, facts = _column([(-delta, [-1, 0, 0], None), (0, [0, 0, 0], None),
                             (delta, [1, 0, 0], None)])
    assert calculate_bec([column], facts, branch_mode="auto", max_step_fraction=0.499)["columns"][0]["status"] == "ambiguous"
    assert calculate_bec([column], facts, branch_mode="auto", max_step_fraction=None)["columns"][0]["status"] == "invalid"
    column["samples"] = [column["samples"][0], column["samples"][2]]
    assert calculate_bec([column], facts, branch_mode="auto", max_step_fraction=0.2)["columns"][0]["status"] == "missing"
