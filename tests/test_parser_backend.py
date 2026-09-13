from __future__ import annotations

from pathlib import Path

import pytest

from abacus_forge import ScfCollectRequest, ScfServiceSet
from abacus_forge.errors import ForgePreconditionError, ForgeRequestError
from abacus_forge.parser_backend import normalize_output_version


def test_supported_output_versions_select_local_io_generation() -> None:
    assert normalize_output_version("v3.10.1").io_backend == "legacyio"
    assert normalize_output_version("v3.9.0").io_backend == "legacyio"
    assert normalize_output_version("v3.9.0.1").io_backend == "latestio"
    assert normalize_output_version("v3.9.0-beta.8").io_backend == "latestio"
    assert normalize_output_version("v3.11.0-beta8+56").io_backend == "latestio"
    assert normalize_output_version("v3.11.0-beta.8+56").normalized == "v3.11.0-beta8+56"
    assert normalize_output_version("v3.11.0-rc.1").normalized == "v3.11.0-rc.1"


@pytest.mark.parametrize("value", ["v2.9.0", "v3.12.0", "LTS", ""])
def test_unsupported_output_version_is_rejected(value: str) -> None:
    with pytest.raises(ForgeRequestError):
        normalize_output_version(value)


def test_abacuslite_import_is_delayed_until_adapter_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus_forge import parser_backend

    calls: list[str] = []
    monkeypatch.setattr(parser_backend.importlib, "import_module", lambda name: calls.append(name) or (_ for _ in ()).throw(ModuleNotFoundError(name)))
    with pytest.raises(ForgePreconditionError):
        parser_backend.load_abacuslite("latestio")
    assert calls == ["abacuslite.io.latestio"]


def test_abacuslite_unexpected_import_dependency_is_internal_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus_forge import parser_backend

    def fail_import(_name: str) -> object:
        raise ModuleNotFoundError("dependency missing", name="unexpected_dependency")

    monkeypatch.setattr(parser_backend.importlib, "import_module", fail_import)
    with pytest.raises(ModuleNotFoundError, match="dependency missing"):
        parser_backend.load_abacuslite("latestio")


def test_abacuslite_energy_tuple_uses_final_ev_iteration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus_forge import parser_backend

    class FakeIO:
        @staticmethod
        def read_energies_from_running_log(_source: object) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
            return ([{"E_KS(sigma->0)": -1.0}], [{"E_KS(sigma->0)": -2.5, "E_Fermi": 3.1}])

    monkeypatch.setattr(parser_backend, "load_abacuslite", lambda _backend: FakeIO)
    values = parser_backend.parse_abacuslite(
        tmp_path / "running_scf.log",
        version=normalize_output_version("v3.11.0-beta8+56"),
    )
    assert values["total_energy"] == -2.5
    assert values["fermi_energy"] == 3.1


def test_abacuslite_energy_mapping_keeps_total_and_fermi_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from abacus_forge import parser_backend

    class FakeIO:
        @staticmethod
        def read_energies_from_running_log(_source: object) -> dict[str, float]:
            return {"total_energy": -2.5, "fermi_energy": 3.1}

    monkeypatch.setattr(parser_backend, "load_abacuslite", lambda _backend: FakeIO)
    values = parser_backend.parse_abacuslite(
        tmp_path / "running_scf.log",
        version=normalize_output_version("v3.11.0-beta8+56"),
    )
    assert values["total_energy"] == -2.5
    assert values["fermi_energy"] == 3.1


def test_abacuslite_stress_matrix_is_flattened_to_kbar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus_forge import parser_backend

    class FakeIO:
        @staticmethod
        def read_stress_from_running_log(_source: object) -> list[list[list[float]]]:
            return [[[1.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 3.0]]]

    monkeypatch.setattr(parser_backend, "load_abacuslite", lambda _backend: FakeIO)
    values = parser_backend.parse_abacuslite(
        tmp_path / "running_scf.log",
        version=normalize_output_version("v3.10.1"),
    )
    assert len(values["stress"]) == 9
    assert values["stress"][0] == pytest.approx(-1602.1777023087202)
    assert values["stresses"] == [values["stress"]]


def test_abacuslite_force_and_stress_keep_final_and_all_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from abacus_forge import parser_backend

    class FakeIO:
        @staticmethod
        def read_forces_from_running_log(_source: object) -> list[list[list[float]]]:
            return [[[1.0, 2.0, 3.0]], [[4.0, 5.0, 6.0]]]

        @staticmethod
        def read_stress_from_running_log(_source: object) -> list[list[list[float]]]:
            return [
                [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 2.0]],
            ]

    monkeypatch.setattr(parser_backend, "load_abacuslite", lambda _backend: FakeIO)
    values = parser_backend.parse_abacuslite(
        tmp_path / "running_scf.log",
        version=normalize_output_version("v3.11.0-beta8+56"),
    )
    assert values["force"] == [4.0, 5.0, 6.0]
    assert values["forces"] == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    assert values["stress"] == pytest.approx([-3204.3554046174404, 0.0, 0.0, 0.0, -3204.3554046174404, 0.0, 0.0, 0.0, -3204.3554046174404])
    assert len(values["stresses"]) == 2


def test_abacuslite_missing_owned_field_does_not_fall_back_to_native(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from abacus_forge import collection
    from abacus_forge.workspace import Workspace

    workspace = Workspace(tmp_path / "scf").ensure_layout()
    workspace.write_text(
        "outputs/running_scf.log",
        "ABACUS VERSION: v3.11.0-beta8+56\nTOTAL ENERGY = -9.0\nSCF CONVERGED\n",
    )
    monkeypatch.setattr(collection, "parse_abacuslite", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(collection, "get_abacuslite_version", lambda _backend: None)
    monkeypatch.setattr(collection, "ensure_abacuslite_available", lambda: None)
    result = collection.collect_contained(workspace, parser_backend="abacuslite")
    assert "total_energy" not in result.metrics
    assert result.diagnostics["parser"]["actual_backend"] == "abacuslite"


def test_abacuslite_reader_value_error_is_internal_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from abacus_forge import parser_backend

    class FakeIO:
        @staticmethod
        def read_energies_from_running_log(_source: object) -> object:
            raise ValueError("unexpected reader implementation failure")

    monkeypatch.setattr(parser_backend, "load_abacuslite", lambda _backend: FakeIO)
    with pytest.raises(ValueError, match="unexpected reader implementation failure"):
        parser_backend.parse_abacuslite(
            tmp_path / "running_scf.log",
            version=normalize_output_version("v3.11.0-beta8+56"),
        )


def test_abacuslite_skips_native_numeric_extraction_before_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from abacus_forge import collection
    from abacus_forge.collectors import abacus
    from abacus_forge.workspace import Workspace

    workspace = Workspace(tmp_path / "scf-native-guard").ensure_layout()
    workspace.write_text(
        "outputs/running_scf.log",
        "ABACUS VERSION: v3.11.0-beta8+56\nTOTAL ENERGY = -9.0\n"
        "NATOM = 2\nNELEC = 8\nBAND GAP = 1.2\nVOLUME = 10.0\n"
        "STEP OF RELAXATION : 3\nSCF CONVERGED\n",
    )
    monkeypatch.setattr(collection, "parse_abacuslite", lambda *_args, **_kwargs: {"total_energy": -8.5})
    monkeypatch.setattr(collection, "get_abacuslite_version", lambda _backend: None)
    monkeypatch.setattr(collection, "ensure_abacuslite_available", lambda: None)
    monkeypatch.setattr(
        abacus._REGISTRY,
        "extract",
        lambda _content: (_ for _ in ()).throw(AssertionError("native numeric parser ran")),
    )
    monkeypatch.setattr(
        abacus,
        "_regex_metrics",
        lambda _content: (_ for _ in ()).throw(AssertionError("native regex parser ran")),
    )

    result = collection.collect_contained(workspace, parser_backend="abacuslite")

    assert result.metrics["total_energy"] == -8.5
    assert result.metrics["version"] == "v3.11.0-beta8+56"
    assert result.metrics["natom"] == 2
    assert result.metrics["nelec"] == 8.0
    assert result.metrics["band_gap"] == 1.2
    assert result.metrics["volume"] == 10.0
    assert result.metrics["relax_steps"] == 3
    assert result.metrics["converged"] is True


def test_abacuslite_projection_derives_common_energy_and_pressure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from abacus_forge import collection
    from abacus_forge.workspace import Workspace

    workspace = Workspace(tmp_path / "scf-derived").ensure_layout()
    workspace.write_text(
        "outputs/running_scf.log",
        "ABACUS VERSION: v3.11.0-beta8+56\nNATOM = 2\nSCF CONVERGED\n",
    )
    monkeypatch.setattr(
        collection,
        "parse_abacuslite",
        lambda *_args, **_kwargs: {
            "total_energy": -8.0,
            "fermi_energy": 1.5,
            "force": [1.0, 2.0, 3.0],
            "forces": [[1.0, 2.0, 3.0]],
            "stress": [3.0, 0.0, 0.0, 0.0, 6.0, 0.0, 0.0, 0.0, 9.0],
            "stresses": [[3.0, 0.0, 0.0, 0.0, 6.0, 0.0, 0.0, 0.0, 9.0]],
        },
    )
    monkeypatch.setattr(collection, "get_abacuslite_version", lambda _backend: None)
    monkeypatch.setattr(collection, "ensure_abacuslite_available", lambda: None)
    result = collection.collect_contained(workspace, parser_backend="abacuslite")
    assert result.metrics["energy_per_atom"] == pytest.approx(-4.0)
    assert result.metrics["pressure"] == pytest.approx(6.0)
    assert "energy_per_atom" in result.derived_metrics
    assert "pressure" in result.derived_metrics
    assert result.metric_units["total_energy"] == "eV"


def test_empty_primary_running_log_does_not_dispatch_optional_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from abacus_forge import collection
    from abacus_forge.workspace import Workspace

    workspace = Workspace(tmp_path / "empty-running").ensure_layout()
    workspace.write_text("outputs/running_scf.log", "")
    monkeypatch.setattr(
        collection,
        "parse_abacuslite",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("backend dispatched")),
    )
    monkeypatch.setattr(collection, "ensure_abacuslite_available", lambda: None)
    result = collection.collect_contained(
        workspace,
        parser_backend="abacuslite",
        output_version="v3.11.0-beta8+56",
    )
    assert result.diagnostics["parser"]["actual_backend"] is None
    assert result.diagnostics["parser"]["io_backend"] is None
    assert result.diagnostics["parser"]["log_source_rel"] == "outputs/running_scf.log"


def test_valid_log_and_caller_versions_conflict_for_native_too(
    tmp_path: Path,
) -> None:
    from abacus_forge import collection
    from abacus_forge.errors import ForgeRequestError
    from abacus_forge.workspace import Workspace

    workspace = Workspace(tmp_path / "native-conflict").ensure_layout()
    workspace.write_text(
        "outputs/running_scf.log",
        "ABACUS VERSION: v3.11.0-beta8+56\nTOTAL ENERGY = -1.0\n",
    )
    with pytest.raises(ForgeRequestError):
        collection.collect_contained(
            workspace,
            parser_backend="native",
            output_version="v3.10.1",
        )


def test_unsupported_log_version_still_conflicts_for_native_with_caller_version(
    tmp_path: Path,
) -> None:
    from abacus_forge import collection
    from abacus_forge.workspace import Workspace

    workspace = Workspace(tmp_path / "native-unsupported-conflict").ensure_layout()
    workspace.write_text(
        "outputs/running_scf.log",
        "ABACUS VERSION: v3.12.0\nTOTAL ENERGY = -1.0\n",
    )
    with pytest.raises(ForgeRequestError, match="conflicts"):
        collection.collect_contained(
            workspace,
            parser_backend="native",
            output_version="v3.11.0-beta8+56",
        )


def test_native_keeps_unsupported_log_version_provenance(
    tmp_path: Path,
) -> None:
    from abacus_forge import collection
    from abacus_forge.workspace import Workspace

    workspace = Workspace(tmp_path / "native-unsupported-provenance").ensure_layout()
    workspace.write_text(
        "outputs/running_scf.log",
        "ABACUS VERSION: 3.8.0\nTOTAL ENERGY = -1.0\n",
    )
    result = collection.collect_contained(workspace, parser_backend="native")
    parser = result.diagnostics["parser"]
    assert parser["output_version_raw"] == "3.8.0"
    assert parser["output_version_normalized"] == "v3.8.0"
    assert parser["version_source"] == "log"


def test_unsupported_log_version_conflicts_before_optional_support_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from abacus_forge import collection
    from abacus_forge.workspace import Workspace

    workspace = Workspace(tmp_path / "optional-conflict").ensure_layout()
    workspace.write_text(
        "outputs/running_scf.log",
        "ABACUS VERSION: v3.12.0\nTOTAL ENERGY = -1.0\n",
    )
    monkeypatch.setattr(collection, "ensure_abacuslite_available", lambda: None)
    with pytest.raises(ForgeRequestError, match="conflicts"):
        collection.collect_contained(
            workspace,
            parser_backend="abacuslite",
            output_version="v3.11.0-beta8+56",
        )


def test_python_service_rejects_invalid_parser_configuration_before_claim(tmp_path: Path) -> None:
    services = ScfServiceSet.default(workspace_root=tmp_path, parser_backend="invalid")
    result = services.collect.collect(
        ScfCollectRequest(
            operation_id="123e4567-e89b-42d3-a456-426614174298",
            workspace_rel="job",
        )
    )
    assert result.error_class == "request.invalid"
    assert result.affected_fields == ("parser_backend", "output_version")
    assert not (tmp_path / "job").exists()
