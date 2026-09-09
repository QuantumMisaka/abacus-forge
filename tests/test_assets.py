import hashlib
import json
from pathlib import Path

import pytest

from abacus_forge.assets import AssetMaterialization, collect_assets, materialize_assets
from abacus_forge.errors import ForgePathError, ForgePreconditionError, ForgeRequestError


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
    expected = {"pseudo": hashlib.sha256(b"pseudo").hexdigest(), "orbital": hashlib.sha256(b"orbital").hexdigest()}
    for item in result:
        assert item.species == "Si" and item.mode == "copy"
        assert item.source_sha256 == expected[item.family]
        assert item.source_sha256 == item.destination_sha256
        assert item.destination in {"inputs/P.upf", "inputs/O.orb"}
        if item.family == "pseudo": assert item.source == "P.upf"
        else: assert Path(item.source).is_absolute()
        assert json.loads(json.dumps(item.to_dict()))["mode"] == "copy"


def test_internal_link_is_relative_and_external_link_rejected(tmp_path):
    root = tmp_path / "w"; root.mkdir(); inputs = root / "target"; inputs.mkdir()
    source = root / "Si.upf"; source.write_bytes(b"x")
    item = materialize_assets(inputs, root, {"Si": source}, mode="link")[0]
    assert (inputs / "Si.upf").is_symlink()
    assert not (inputs / "Si.upf").readlink().is_absolute()
    outside = tmp_path / "outside.upf"; outside.write_bytes(b"x")
    with pytest.raises(ForgeRequestError): materialize_assets(inputs, root, {"O": outside}, mode="link")


@pytest.mark.parametrize("sources", [
    {"Si": "missing.upf"}, {"Si": "bad.txt"}, {"Si": "../unsafe.upf"},
    {"Si": "a.upf", "O": "b.upf"},
])
def test_validation_fail_closed_without_partial_writes(tmp_path, sources):
    root = tmp_path / "w"; root.mkdir(); inputs = root / "target"; inputs.mkdir()
    (root / "a.upf").write_bytes(b"a"); (root / "b.upf").write_bytes(b"b")
    (root / "bad.txt").write_bytes(b"bad")
    if len(sources) == 2:
        first = root / "one"; second = root / "two"; first.mkdir(); second.mkdir()
        (first / "same.upf").write_bytes(b"a"); (second / "same.upf").write_bytes(b"b")
        sources = {"Si": "one/same.upf", "O": "two/same.upf"}
    expected = ForgePathError if sources.get("Si") == "../unsafe.upf" else ForgePreconditionError if sources.get("Si") == "missing.upf" else ForgeRequestError
    with pytest.raises(expected):
        materialize_assets(inputs, root, sources)
    assert not any(inputs.iterdir())


def test_duplicate_basename_and_existing_conflict_fail_closed(tmp_path):
    root = tmp_path / "w"; root.mkdir(); inputs = root / "target"; inputs.mkdir()
    a = root / "a"; a.mkdir(); (a / "same.upf").write_bytes(b"a")
    b = root / "b"; b.mkdir(); (b / "same.upf").write_bytes(b"b")
    with pytest.raises(ForgeRequestError): materialize_assets(inputs, root, {"Si": a / "same.upf", "O": b / "same.upf"})
    assert not any(inputs.iterdir())
    (inputs / "same.upf").write_bytes(b"old")
    with pytest.raises(ForgeRequestError): materialize_assets(inputs, root, {"Si": root / "a" / "same.upf"})
    assert (inputs / "same.upf").read_bytes() == b"old"


def test_same_source_reused_without_duplicate_write(tmp_path):
    root = tmp_path / "w"; root.mkdir(); inputs = root / "target"; inputs.mkdir()
    source = root / "Si.vp"; source.write_bytes(b"vp")
    result = materialize_assets(inputs, root, {"Si": source, "Silicon": source})
    assert len(result) == 2 and len(list(inputs.iterdir())) == 1


def test_legacy_collection_does_not_infer_vp(tmp_path):
    (tmp_path / "Si.vp").write_bytes(b"vp")
    assert collect_assets(tmp_path, family="pseudo") == {}


@pytest.mark.parametrize("target", ["../outside", "external-link"])
def test_target_must_be_inside_workspace(tmp_path, target):
    root = tmp_path / "w"; root.mkdir(); (root / "Si.upf").write_bytes(b"x")
    if target == "external-link":
        outside = tmp_path / "outside"; outside.mkdir(); (root / "external-link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ForgePathError): materialize_assets(root / target, root, {"Si": "Si.upf"})
    assert not (tmp_path / "outside" / "Si.upf").exists()


@pytest.mark.parametrize("mode", ["bad", None, 1])
def test_invalid_mode_is_request_error(tmp_path, mode):
    root = tmp_path / "w"; root.mkdir(); target = root / "target"
    with pytest.raises(ForgeRequestError): materialize_assets(target, root, {}, mode=mode)
    assert not target.exists()


def test_empty_source_is_request_error(tmp_path):
    root = tmp_path / "w"; root.mkdir(); target = root / "target"
    with pytest.raises(ForgeRequestError): materialize_assets(target, root, {"Si": ""})
    assert not target.exists()


def test_existing_target_types_are_mode_strict(tmp_path):
    root = tmp_path / "w"; root.mkdir(); target = root / "target"; target.mkdir()
    source = root / "Si.upf"; source.write_bytes(b"x")
    (target / "Si.upf").write_bytes(b"x")
    with pytest.raises(ForgeRequestError): materialize_assets(target, root, {"Si": source}, mode="link")
    (target / "Si.upf").unlink(); (target / "Si.upf").symlink_to(source)
    with pytest.raises(ForgeRequestError): materialize_assets(target, root, {"Si": source}, mode="copy")
    (target / "Si.upf").unlink(); (target / "Si.upf").symlink_to(source.resolve())
    with pytest.raises(ForgeRequestError): materialize_assets(target, root, {"Si": source}, mode="link")
    assert (target / "Si.upf").is_symlink()


def test_source_symlink_and_target_file_fail_without_writes(tmp_path):
    root = tmp_path / "w"; root.mkdir(); source = root / "Si.upf"; source.write_bytes(b"x")
    alias = root / "alias.upf"; alias.symlink_to(source)
    with pytest.raises(ForgePreconditionError): materialize_assets(root / "target", root, {"Si": "alias.upf"})
    target = root / "target"; target.write_bytes(b"not-dir")
    with pytest.raises(ForgeRequestError): materialize_assets(target, root, {"Si": source})


@pytest.mark.parametrize("basename", ["bad name.upf", "bad\tname.upf", "#hidden.upf"])
def test_typed_asset_basename_must_be_a_single_stru_token(tmp_path, basename):
    root = tmp_path / "w"; root.mkdir(); target = root / "target"
    source = root / basename; source.write_bytes(b"x")

    with pytest.raises(ForgeRequestError):
        materialize_assets(target, root, {"Si": source})

    assert not target.exists()


@pytest.mark.parametrize("supplied", [[], "", False])
def test_falsy_non_mapping_sources_are_rejected_before_target_creation(tmp_path, supplied):
    root = tmp_path / "w"; root.mkdir(); target = root / "target"
    with pytest.raises(ForgeRequestError): materialize_assets(target, root, supplied)
    assert not target.exists()
