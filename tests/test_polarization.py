"""Synthetic source-shaped Berry log parsing; no real ABACUS run is claimed."""

from pathlib import Path

import pytest

from abacus_forge.polarization import collect_polarization_facts

pytestmark = pytest.mark.experimental


FIXTURE = Path(__file__).parent / "fixtures" / "polarization" / "source-shaped-r1.txt"


def _sources(tmp_path: Path) -> tuple[Path, Path, Path]:
    log = tmp_path / "running.log"
    log.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    stru = tmp_path / "STRU"
    stru.write_text(
        "ATOMIC_SPECIES\nH 1.0 H.upf\n\nLATTICE_CONSTANT\n"
        "1.0\n\nLATTICE_VECTORS\n"
        "2 0 0\n1 2 0\n0 0 3\n\nATOMIC_POSITIONS\nDirect\n"
        "H\n0\n1\n0 0 0 m 1 1 1\n",
        encoding="utf-8",
    )
    inp = tmp_path / "INPUT"
    inp.write_text("INPUT_PARAMETERS\nberry_phase 1\ngdir 1\nnspin 1\ncalculation nscf\n", encoding="utf-8")
    return log, stru, inp


def test_source_shaped_record_preserves_rows_geometry_and_input(tmp_path: Path) -> None:
    fact = collect_polarization_facts(*_sources(tmp_path))
    assert fact["schema_version"] == "forge.polarization/v1"
    assert fact["gdir"] == 1
    assert (fact["ionic_phase"], fact["electronic_phase"]) == (0.1, 0.4)
    assert list(fact["rows"]) == ["(e/Omega).bohr", "e/bohr^2", "C/m^2"]
    assert fact["rows"]["(e/Omega).bohr"]["modulus"] == 4.0
    assert fact["rows"]["(e/Omega).bohr"]["cartesian"] == [1.0, 0.0, 0.0]
    assert fact["geometry"]["atom_labels"] == ["H"]
    assert fact["input"]["calculation"] == "nscf"


@pytest.mark.parametrize("change", [
    lambda s: s.replace("VALUES OF POLARIZATION", "NO BERRY BLOCK"),
    lambda s: s.replace("in R1 direction", "in R4 direction"),
    lambda s: s.replace("0.0833333,   0.0000000", "BAD,   0.0000000"),
    lambda s: s.replace(" P =    4.7643102", " X =    4.7643102"),
])
def test_malformed_or_missing_block_fails(tmp_path: Path, change) -> None:
    log, stru, inp = _sources(tmp_path)
    log.write_text(change(log.read_text(encoding="utf-8")), encoding="utf-8")
    with pytest.raises(ValueError):
        collect_polarization_facts(log, stru, inp)


def test_input_direction_must_match_native_record(tmp_path: Path) -> None:
    log, stru, inp = _sources(tmp_path)
    inp.write_text("berry_phase 1\ngdir 2\nnspin 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="gdir"):
        collect_polarization_facts(log, stru, inp)
