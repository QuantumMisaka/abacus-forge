from __future__ import annotations

import json
from pathlib import Path

from abacus_forge.workspace import Workspace


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "abacustest-abacus-scf"
NATIVE_MD_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "abacus-native-md"
NATIVE_RELAX_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "abacus-native-relax"


def copy_abacustest_scf_workspace(root: Path) -> Workspace:
    workspace = Workspace(root).ensure_layout()
    for relative_path in ("INPUT", "KPT", "STRU"):
        workspace.write_text(
            f"inputs/{relative_path}",
            (FIXTURE_ROOT / relative_path).read_text(encoding="utf-8"),
        )
    workspace.write_text(
        "outputs/OUT.ABACUS/running_scf.log",
        (FIXTURE_ROOT / "OUT.ABACUS" / "running_scf.log").read_text(encoding="utf-8"),
    )
    workspace.write_text(
        "outputs/out.log",
        (FIXTURE_ROOT / "out.log").read_text(encoding="utf-8"),
    )
    workspace.write_text(
        "outputs/OUT.ABACUS/INPUT",
        (FIXTURE_ROOT / "OUT.ABACUS" / "INPUT").read_text(encoding="utf-8"),
    )
    workspace.write_text("outputs/stderr.log", "")
    workspace.write_json(
        "outputs/OUT.ABACUS/time.json",
        json.loads((FIXTURE_ROOT / "time.json").read_text(encoding="utf-8")),
    )
    return workspace


def copy_native_md_workspace(root: Path) -> Workspace:
    """Copy the compact native ABACUS MD output fixture into a workspace."""
    workspace = Workspace(root).ensure_layout()
    for relative_path in ("INPUT", "STRU"):
        workspace.write_text(
            f"inputs/{relative_path}",
            (NATIVE_MD_FIXTURE_ROOT / relative_path).read_text(encoding="utf-8"),
        )
    workspace.write_text(
        "outputs/OUT.ABACUS/running_md.log",
        (NATIVE_MD_FIXTURE_ROOT / "OUT.ABACUS" / "running_md.log").read_text(encoding="utf-8"),
    )
    workspace.write_text(
        "outputs/OUT.ABACUS/MD_dump",
        (NATIVE_MD_FIXTURE_ROOT / "OUT.ABACUS" / "MD_dump").read_text(encoding="utf-8"),
    )
    workspace.write_text("outputs/stderr.log", "")
    return workspace


def copy_native_relax_workspace(root: Path, capability: str = "relax") -> Workspace:
    if capability not in {"relax", "cell-relax"}:
        raise ValueError(f"unsupported Relax fixture capability: {capability}")
    workspace = Workspace(root).ensure_layout()
    input_text = (NATIVE_RELAX_FIXTURE_ROOT / "INPUT").read_text(encoding="utf-8")
    input_text = input_text.replace("calculation relax", f"calculation {capability}", 1)
    workspace.write_text("inputs/INPUT", input_text)
    for relative_path in ("KPT", "STRU"):
        workspace.write_text(
            f"inputs/{relative_path}",
            (NATIVE_RELAX_FIXTURE_ROOT / relative_path).read_text(encoding="utf-8"),
        )
    workspace.write_text(
        f"outputs/OUT.ABACUS/running_{capability}.log",
        (NATIVE_RELAX_FIXTURE_ROOT / "OUT.ABACUS" / "running_relax.log").read_text(encoding="utf-8"),
    )
    workspace.write_text(
        "outputs/OUT.ABACUS/STRU_FINAL",
        (NATIVE_RELAX_FIXTURE_ROOT / "OUT.ABACUS" / "STRU_FINAL").read_text(encoding="utf-8"),
    )
    workspace.write_text("outputs/stderr.log", "")
    return workspace
