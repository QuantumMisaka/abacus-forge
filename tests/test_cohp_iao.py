from __future__ import annotations

import json
import tarfile
from pathlib import Path

import numpy as np
import pytest

from abacus_forge import cohp_iao
from abacus_forge.cohp_iao import (
    AbacusLcaoRun,
    RY_TO_EV,
    analyse_bond,
    build_iao_model,
    check_iao_species,
    parse_orbital_selector,
    run_iao_cohp,
    shell_spec,
)


SI_FIXTURE = Path(__file__).parent / "fixtures" / "cohp-iao" / "si_prim_4k.tar.gz"


@pytest.fixture
def si_run(tmp_path: Path) -> Path:
    with tarfile.open(SI_FIXTURE) as archive:
        archive.extractall(tmp_path, filter="data")
    return tmp_path / "si_prim_4k"


@pytest.mark.parametrize(
    ("element", "zval", "valence", "semicore"),
    [("Si", 4, {"s": 1, "p": 1}, {}), ("Ti", 12, {"s": 1, "d": 1}, {"s": 1, "p": 1})],
)
def test_shell_rules_match_the_reviewed_paimon_table(
    element: str, zval: float, valence: dict[str, int], semicore: dict[str, int]
) -> None:
    described = shell_spec(element, zval).describe()
    assert described["valence_shells"] == valence
    assert described["semicore_shells"] == semicore


def test_semicore_orbital_count_sets_frozen_bands(si_run: Path) -> None:
    assert build_iao_model(AbacusLcaoRun(si_run)).n_frozen == 0


def test_reader_identities_and_phase_sign(si_run: Path) -> None:
    model = build_iao_model(AbacusLcaoRun(si_run))
    diagnostics = model.diagnostics
    assert model.phase_sign == 1
    assert diagnostics["phase_residual"] < 1e-6 < diagnostics["phase_residual_other"]
    assert model.nk == 7
    assert diagnostics["n_electrons"] == pytest.approx(8.0, abs=1e-6)
    assert diagnostics["orthonormality_ratio"] < 1.0
    assert diagnostics["eigen_ratio"] < 1.0
    assert diagnostics["occupied_spilling_max"] < 1e-6
    assert abs(diagnostics["band_energy_sum_rule_dev_ev"]) < 1e-5


def test_element_symbol_prefers_the_upf_attribute() -> None:
    from abacus_forge.cohp_iao_shells import element_symbol

    assert element_symbol("Si1", "Si") == "Si"


@pytest.mark.parametrize(
    ("label", "upf_element"), [("CsPb", None), ("Xx", "Xx")]
)
def test_unknown_two_letter_elements_are_rejected(label: str, upf_element: str | None) -> None:
    from abacus_forge.cohp_iao_shells import element_symbol

    with pytest.raises(ValueError, match=label):
        element_symbol(label, upf_element)


def test_iao_matches_an_explicit_projector_reference(si_run: Path) -> None:
    run = AbacusLcaoRun(si_run)
    model = build_iao_model(run)
    bond = analyse_bond(model, 1, 2)
    t = tuple(bond["translation"])
    layout = run.layout
    valence = np.where((layout.zeta == 0) & (layout.l <= 1))[0]
    reference_basis = np.zeros((run.nbasis, valence.size))
    reference_basis[valence, np.arange(valence.size)] = 1.0

    def orthogonalize(matrix: np.ndarray, overlap: np.ndarray) -> np.ndarray:
        eigenvalues, vectors = np.linalg.eigh(matrix.conj().T @ overlap @ matrix)
        return matrix @ vectors @ np.diag(eigenvalues ** -0.5) @ vectors.conj().T

    per_k = []
    for kd in run.iter_kpoints():
        overlap, hamiltonian, coefficients = kd.S, kd.H[0], kd.C[0]
        occupation = kd.wg[0] / (run.kweight[kd.ik] * 2.0)
        occupied = coefficients[:, occupation > 0.5]
        identity = np.eye(run.nbasis)
        projected = occupied @ occupied.conj().T @ overlap
        transformed = orthogonalize(
            reference_basis
            @ np.linalg.inv(reference_basis.T @ overlap @ reference_basis)
            @ reference_basis.T
            @ overlap
            @ occupied,
            overlap,
        )
        transformed_projector = transformed @ transformed.conj().T @ overlap
        mixing = orthogonalize(
            (projected @ transformed_projector + (identity - projected) @ (identity - transformed_projector))
            @ reference_basis,
            overlap,
        )
        coefficient_transform = mixing.conj().T @ overlap @ coefficients
        per_k.append(
            (
                mixing.conj().T @ hamiltonian @ mixing,
                (coefficient_transform * occupation) @ coefficient_transform.conj().T,
            )
        )
    reduced_k = run.kfrac
    ia, ib = np.arange(0, 4), np.arange(4, 8)
    bond_h = np.zeros((4, 4), complex)
    bond_density = np.zeros((4, 4), complex)
    for k, j in zip(run.full_k, run.full_map):
        same = np.allclose(np.mod(k - reduced_k[j] + 0.5, 1.0), 0.5)
        hamiltonian, density = per_k[j] if same else (per_k[j][0].conj(), per_k[j][1].conj())
        phase = np.exp(-2j * np.pi * np.dot(k, t)) / len(run.full_k)
        bond_h += phase * hamiltonian[np.ix_(ia, ib)]
        bond_density += phase * density[np.ix_(ia, ib)]
    reference = 2.0 * float(np.real(np.sum(bond_h * np.conj(bond_density))))
    assert bond["primary"]["icohp"] == pytest.approx(reference, abs=1e-8)
    assert bond["primary"]["minus_icohp"] > 0


def test_icohp_is_independent_of_energy_zero(si_run: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = analyse_bond(build_iao_model(AbacusLcaoRun(si_run)), 1, 2)["primary"]["icohp"]
    original = AbacusLcaoRun.iter_kpoints
    shift_ev = 5.0

    def shifted(self: AbacusLcaoRun):
        for kd in original(self):
            kd.H = [h + shift_ev * kd.S for h in kd.H]
            kd.energy = [energy + shift_ev / RY_TO_EV for energy in kd.energy]
            yield kd

    monkeypatch.setattr(AbacusLcaoRun, "iter_kpoints", shifted)
    moved = analyse_bond(build_iao_model(AbacusLcaoRun(si_run)), 1, 2)["primary"]["icohp"]
    assert moved == pytest.approx(base, abs=1e-8)


def test_orbital_selectors_resolve_the_valence_iao(si_run: Path) -> None:
    model = build_iao_model(AbacusLcaoRun(si_run))
    assert model.orbitals(0, "all").size == 4
    assert model.orbitals(0, "s").size == 1
    assert model.orbitals(0, "3p").size == 3
    assert model.orbitals(0, "pz,s").size == 2
    with pytest.raises(ValueError, match="2p"):
        model.orbitals(0, "2p")
    with pytest.raises(ValueError, match="d"):
        model.orbitals(0, "d")


def test_species_check_runs_on_inputs_alone(si_run: Path) -> None:
    specs = check_iao_species(si_run)
    assert specs["Si"].describe()["valence_shells"] == {"s": 1, "p": 1}
    upf = si_run / "Si.upf"
    upf.write_text(
        upf.read_text(encoding="utf-8").replace('z_valence="    4.00"', 'z_valence="   12.00"'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Si"):
        check_iao_species(si_run)


def test_missing_overlap_r_is_rejected(si_run: Path) -> None:
    (si_run / "OUT.ABACUS" / "data-SR-sparse_SPIN0.csr").unlink()
    with pytest.raises(FileNotFoundError, match="out_mat_hs2"):
        build_iao_model(AbacusLcaoRun(si_run))


def test_gamma_only_input_is_rejected(si_run: Path) -> None:
    path = si_run / "INPUT"
    path.write_text(
        path.read_text(encoding="utf-8").replace("gamma_only          0", "gamma_only          1"),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="gamma_only"):
        AbacusLcaoRun(si_run)


def test_run_writes_legacy_compatible_artifacts(si_run: Path, tmp_path: Path) -> None:
    meta = run_iao_cohp(
        scf_dir=si_run,
        atom_i_index=1,
        atom_j_index=2,
        atom_i_orbs="all",
        atom_j_orbs="all",
        work_dir=tmp_path / "work",
        output_prefix="cohp",
    )
    work = tmp_path / "work"
    on_disk = json.loads((work / "cohp.meta.json").read_text(encoding="utf-8"))
    assert on_disk["method"] == cohp_iao.METHOD_NAME
    assert on_disk["icohp"]["minus_icohp"] == pytest.approx(-on_disk["icohp"]["icohp"])
    assert on_disk["icohp"]["convention"] == cohp_iao.ICOHP_CONVENTION
    assert on_disk["bond"]["distance_ang"] == pytest.approx(2.3517, abs=1e-3)
    assert np.loadtxt(work / "cohp_EminusEf.dat").shape[1] == 2
    images = json.loads((work / "cohp_bond_images.json").read_text(encoding="utf-8"))
    assert images["images"][0]["translation"] == on_disk["bond"]["translation"]
    assert (work / "cohp.png").stat().st_size > 0
    assert [item["code"] for item in on_disk["cautions"]] == ["irregular_kgrid"]
    assert meta["paths"]["meta"].endswith("cohp.meta.json")
