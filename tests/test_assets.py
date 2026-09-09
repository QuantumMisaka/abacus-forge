import hashlib
import json
from pathlib import Path

import pytest

from abacus_forge.assets import AssetMaterialization, materialize_assets


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_copy_and_provenance_for_internal_and_external(tmp_path):
    root = tmp_path / "workspace"; root.mkdir()
    inputs = root / "inputs"; inputs.mkdir()
    (root / "P.upf").write_bytes(b"pseudo")
    external = tmp_path / "O.orb"; external.write_bytes(b"orbital")
    result = materialize_assets(inputs, root, {"Si": "P.upf"}, {"Si": external}, "copy")
    assert len(result) == 2
    assert {x.family for x in result} == {"pseudo", "orbital"}
    assert (inputs / "P.upf").read_bytes() == b"pseudo"
    assert (inputs / "O.orb").read_bytes() == b"orbital"
    for item in result:
        assert item.source_sha256 == item.destination_sha256
        assert item.destination == "inputs/" + Path(item.destination).name
        assert json.loads(json.dumps(item.to_dict()))["mode"] == "copy"


def test_internal_link_is_relative_and_external_link_rejected(tmp_path):
    root = tmp_path / "w"; root.mkdir(); inputs = root / "target"; inputs.mkdir()
    source = root / "Si.upf"; source.write_bytes(b"x")
    item = materialize_assets(inputs, root, {"Si": source}, mode="link")[0]
    assert (inputs / "Si.upf").is_symlink()
    assert not (inputs / "Si.upf").readlink().is_absolute()
    outside = tmp_path / "outside.upf"; outside.write_bytes(b"x")
    with pytest.raises(ValueError): materialize_assets(inputs, root, {"O": outside}, mode="link")


@pytest.mark.parametrize("sources", [
    {"Si": "missing.upf"}, {"Si": "bad.txt"}, {"Si": "../unsafe.upf"},
    {"Si": "a.upf", "O": "b.upf"},
])
def test_validation_fail_closed_without_partial_writes(tmp_path, sources):
    root = tmp_path / "w"; root.mkdir(); inputs = root / "target"; inputs.mkdir()
    (root / "a.upf").write_bytes(b"a"); (root / "b.upf").write_bytes(b"b")
    if len(sources) == 2:
        first = root / "one"; second = root / "two"; first.mkdir(); second.mkdir()
        (first / "same.upf").write_bytes(b"a"); (second / "same.upf").write_bytes(b"b")
        sources = {"Si": "one/same.upf", "O": "two/same.upf"}
    with pytest.raises((ValueError, FileNotFoundError)):
        materialize_assets(inputs, root, sources)
    assert not any(inputs.iterdir())


def test_duplicate_basename_and_existing_conflict_fail_closed(tmp_path):
    root = tmp_path / "w"; root.mkdir(); inputs = root / "target"; inputs.mkdir()
    a = root / "a"; a.mkdir(); (a / "same.upf").write_bytes(b"a")
    b = root / "b"; b.mkdir(); (b / "same.upf").write_bytes(b"b")
    with pytest.raises(ValueError): materialize_assets(inputs, root, {"Si": a / "same.upf", "O": b / "same.upf"})
    assert not any(inputs.iterdir())
    (inputs / "same.upf").write_bytes(b"old")
    with pytest.raises(ValueError): materialize_assets(inputs, root, {"Si": root / "a" / "same.upf"})
    assert (inputs / "same.upf").read_bytes() == b"old"


def test_same_source_reused_without_duplicate_write(tmp_path):
    root = tmp_path / "w"; root.mkdir(); inputs = root / "target"; inputs.mkdir()
    source = root / "Si.vp"; source.write_bytes(b"vp")
    result = materialize_assets(inputs, root, {"Si": source, "Silicon": source})
    assert len(result) == 2 and len(list(inputs.iterdir())) == 1
