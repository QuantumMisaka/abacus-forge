"""Command-line entrypoints for Forge's thin primitives and task-oriented workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from abacus_forge.api import collect, export, prepare, run
from abacus_forge.modify import modify_input, modify_kpt, modify_stru
from abacus_forge.runner import LocalRunner
from abacus_forge.structure import AbacusStructure
from abacus_forge.tasks import run_band, run_dos, run_relax, run_scf


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser for Forge subcommands."""
    parser = argparse.ArgumentParser(prog="abacus-forge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="prepare a minimal workspace")
    prepare_parser.add_argument("workspace")
    prepare_parser.add_argument("--structure")
    prepare_parser.add_argument("--structure-format")
    prepare_parser.add_argument("--task", default="scf")
    prepare_parser.add_argument("--parameter", action="append", default=[], help="KEY=VALUE")
    prepare_parser.add_argument("--magmom", action="append", default=[], help="ELEMENT=VALUE")
    prepare_parser.add_argument("--remove-parameter", action="append", default=[])
    prepare_parser.add_argument("--kpoint", action="append", type=int, default=[])
    prepare_parser.add_argument("--pseudo-path")
    prepare_parser.add_argument("--orbital-path")
    prepare_parser.add_argument("--asset-mode", choices=["copy", "link"], default="link")
    prepare_parser.add_argument("--ensure-pbc", action="store_true")

    modify_input_parser = subparsers.add_parser("modify-input", help="modify one INPUT file")
    modify_input_parser.add_argument("source")
    modify_input_parser.add_argument("--output", required=True)
    modify_input_parser.add_argument("--set", action="append", default=[], help="KEY=VALUE")
    modify_input_parser.add_argument("--remove", action="append", default=[])
    modify_input_parser.add_argument("--header", default="INPUT_PARAMETERS")

    modify_stru_parser = subparsers.add_parser("modify-stru", help="modify one structure or STRU file")
    modify_stru_parser.add_argument("source")
    modify_stru_parser.add_argument("--output", required=True)
    modify_stru_parser.add_argument("--magmom", action="append", default=[], help="ELEMENT=VALUE")
    modify_stru_parser.add_argument("--afm", action="store_true")
    modify_stru_parser.add_argument("--afm-element", action="append", default=[])
    modify_stru_parser.add_argument("--site-magmoms", help="Comma-separated per-atom collinear magmoms")
    modify_stru_parser.add_argument("--ensure-pbc", action="store_true")
    modify_stru_parser.add_argument("--vacuum", type=float, default=10.0)
    modify_stru_parser.add_argument("--structure-format")

    modify_kpt_parser = subparsers.add_parser("modify-kpt", help="modify one KPT file")
    modify_kpt_parser.add_argument("source")
    modify_kpt_parser.add_argument("--output", required=True)
    modify_kpt_parser.add_argument("--mode", choices=["mesh", "line"], required=True)
    modify_kpt_parser.add_argument("--mesh", nargs=3, type=int, metavar=("NX", "NY", "NZ"))
    modify_kpt_parser.add_argument("--shifts", nargs=3, type=int, metavar=("SX", "SY", "SZ"))
    modify_kpt_parser.add_argument("--segments", type=int)
    modify_kpt_parser.add_argument("--point", action="append", default=[], help="kx,ky,kz[:LABEL]")

    run_parser = subparsers.add_parser("run", help="run a prepared workspace")
    run_parser.add_argument("workspace")
    run_parser.add_argument("--executable", default="abacus")
    run_parser.add_argument("--mpi", type=int, default=1)
    run_parser.add_argument("--omp", type=int, default=1)

    collect_parser = subparsers.add_parser("collect", help="collect metrics from a workspace")
    collect_parser.add_argument("workspace")
    collect_parser.add_argument("--json", action="store_true", help="print JSON to stdout")
    collect_parser.add_argument("--output-log", help="explicit stdout-like output log path")

    export_parser = subparsers.add_parser("export", help="collect and export JSON to file")
    export_parser.add_argument("workspace")
    export_parser.add_argument("--output", required=True)

    for task_name in ("scf", "relax", "band", "dos"):
        task_parser = subparsers.add_parser(task_name, help=f"run one {task_name} task end-to-end")
        _add_task_arguments(task_parser, task_name=task_name)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse CLI arguments, dispatch to a Forge primitive, and return an exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "prepare":
        parameters = _parse_parameters(args.parameter)
        magmom_by_element = _parse_numeric_mapping(args.magmom)
        kpoints = args.kpoint if args.kpoint else None
        workspace = prepare(
            args.workspace,
            structure=args.structure,
            structure_format=args.structure_format,
            task=args.task,
            parameters=parameters,
            remove_parameters=args.remove_parameter,
            kpoints=kpoints,
            pseudo_path=args.pseudo_path,
            orbital_path=args.orbital_path,
            asset_mode=args.asset_mode,
            ensure_pbc=args.ensure_pbc,
            magmom_by_element=magmom_by_element or None,
        )
        print(workspace.root)
        return 0

    if args.command == "modify-input":
        parameters = _parse_parameters(args.set)
        modified = modify_input(
            args.source,
            updates=parameters,
            remove_keys=args.remove,
            destination=args.output,
            header=args.header,
        )
        print(json.dumps({"keys": len(modified), "output": str(Path(args.output))}, sort_keys=True))
        return 0

    if args.command == "modify-stru":
        magmom_by_element = _parse_numeric_mapping(args.magmom)
        magmoms = _parse_float_list(args.site_magmoms)
        structure_source: str | AbacusStructure = args.source
        if args.structure_format:
            structure_source = AbacusStructure.from_input(args.source, structure_format=args.structure_format)
        modified = modify_stru(
            structure_source,
            ensure_pbc=args.ensure_pbc,
            vacuum=args.vacuum,
            magmom_by_element=magmom_by_element or None,
            magmoms=magmoms,
            afm=args.afm,
            afm_elements=args.afm_element or None,
            destination=args.output,
        )
        print(json.dumps({"source_format": modified.source_format, "output": str(Path(args.output))}, sort_keys=True))
        return 0

    if args.command == "modify-kpt":
        points = _parse_kpt_points(args.point)
        _validate_kpt_arguments(args.mode, mesh=args.mesh, shifts=args.shifts, segments=args.segments, points=points)
        modified = modify_kpt(
            args.source,
            mode=args.mode,
            mesh=args.mesh,
            shifts=args.shifts,
            segments=args.segments,
            points=points,
            destination=args.output,
        )
        print(json.dumps({"mode": modified["mode"], "output": str(Path(args.output))}, sort_keys=True))
        return 0

    if args.command == "run":
        runner = LocalRunner(executable=args.executable, mpi_ranks=args.mpi, omp_threads=args.omp)
        result = run(args.workspace, runner=runner)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0 if result.returncode == 0 else result.returncode

    if args.command == "collect":
        result = collect(args.workspace, output_log=args.output_log)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        else:
            print(result.status)
        return 0

    if args.command == "export":
        result = collect(args.workspace)
        export(result, destination=Path(args.output))
        print(args.output)
        return 0

    if args.command in {"scf", "relax", "band", "dos"}:
        parameters = _parse_parameters(args.parameter)
        magmom_by_element = _parse_numeric_mapping(args.magmom)
        line_kpoints = _parse_kpt_points(getattr(args, "point", []))
        task_runner = {
            "scf": run_scf,
            "relax": run_relax,
            "band": run_band,
            "dos": run_dos,
        }[args.command]
        kwargs: dict[str, Any] = {
            "structure": args.structure,
            "structure_format": args.structure_format,
            "parameters": parameters,
            "pseudo_path": args.pseudo_path,
            "orbital_path": args.orbital_path,
            "asset_mode": args.asset_mode,
            "ensure_pbc": args.ensure_pbc,
            "magmom_by_element": magmom_by_element or None,
            "executable": args.executable,
            "mpi": args.mpi,
            "omp": args.omp,
            "export_destination": args.output,
        }
        if args.command == "band":
            if not line_kpoints:
                raise SystemExit("band task requires explicit line-mode KPT points via --point")
            result = task_runner(
                args.workspace,
                line_kpoints=line_kpoints,
                line_segments=args.segments,
                **kwargs,
            )
        else:
            result = task_runner(args.workspace, **kwargs)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        else:
            print(result.status)
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2


def _parse_parameters(raw_values: Sequence[str]) -> dict[str, str]:
    """Parse repeated ``KEY=VALUE`` arguments into a string mapping."""
    parameters: dict[str, str] = {}
    for raw in raw_values:
        if "=" not in raw:
            raise SystemExit(f"invalid parameter: {raw}")
        key, value = raw.split("=", 1)
        parameters[key.strip()] = value.strip()
    return parameters


def _parse_numeric_mapping(raw_values: Sequence[str]) -> dict[str, float]:
    """Parse repeated ``KEY=VALUE`` arguments into a float mapping."""
    mapping: dict[str, float] = {}
    for raw in raw_values:
        if "=" not in raw:
            raise SystemExit(f"invalid mapping: {raw}")
        key, value = raw.split("=", 1)
        try:
            mapping[key.strip()] = float(value.strip())
        except ValueError as exc:
            raise SystemExit(f"invalid numeric value in mapping: {raw}") from exc
    return mapping


def _parse_float_list(raw_value: str | None) -> list[float] | None:
    """Parse a comma-separated float list used by site-level magnetic moments."""
    if raw_value is None:
        return None
    parts = [part.strip() for part in raw_value.split(",") if part.strip()]
    try:
        return [float(part) for part in parts]
    except ValueError as exc:
        raise SystemExit(f"invalid float list: {raw_value}") from exc


def _parse_kpt_points(raw_values: Sequence[str]) -> list[dict[str, Any]] | None:
    """Parse repeated ``kx,ky,kz[:LABEL]`` values into line-mode KPT points."""
    if not raw_values:
        return None
    points: list[dict[str, Any]] = []
    for raw in raw_values:
        coords_text, _, label_text = raw.partition(":")
        parts = [part.strip() for part in coords_text.split(",") if part.strip()]
        if len(parts) != 3:
            raise SystemExit(f"invalid KPT point: {raw}")
        try:
            coords = [float(part) for part in parts]
        except ValueError as exc:
            raise SystemExit(f"invalid KPT point: {raw}") from exc
        points.append({"coords": coords, "label": label_text.strip() or None})
    return points


def _validate_kpt_arguments(
    mode: str,
    *,
    mesh: Sequence[int] | None,
    shifts: Sequence[int] | None,
    segments: int | None,
    points: Sequence[dict[str, Any]] | None,
) -> None:
    """Validate mode-specific CLI arguments before dispatching to ``modify_kpt``."""
    if mode == "mesh":
        if segments is not None or points:
            raise SystemExit("mesh mode does not accept --segments or --point")
        if mesh is None and shifts is None:
            raise SystemExit("mesh mode requires --mesh and/or --shifts")
        return
    if mode == "line":
        if mesh is not None or shifts is not None:
            raise SystemExit("line mode does not accept --mesh or --shifts")
        if segments is None and not points:
            raise SystemExit("line mode requires --segments and/or --point")
        return
    raise SystemExit(f"unsupported KPT mode: {mode}")


def _add_task_arguments(parser: argparse.ArgumentParser, *, task_name: str) -> None:
    parser.add_argument("workspace")
    parser.add_argument("--structure")
    parser.add_argument("--structure-format")
    parser.add_argument("--parameter", action="append", default=[], help="KEY=VALUE")
    parser.add_argument("--magmom", action="append", default=[], help="ELEMENT=VALUE")
    parser.add_argument("--pseudo-path")
    parser.add_argument("--orbital-path")
    parser.add_argument("--asset-mode", choices=["copy", "link"], default="link")
    parser.add_argument("--ensure-pbc", action="store_true")
    parser.add_argument("--executable", default="abacus")
    parser.add_argument("--mpi", type=int, default=1)
    parser.add_argument("--omp", type=int, default=1)
    parser.add_argument("--json", action="store_true", help="print JSON to stdout")
    parser.add_argument("--output", help="optional export path for collected JSON")
    if task_name == "band":
        parser.add_argument("--segments", type=int, default=20)
        parser.add_argument("--point", action="append", default=[], help="kx,ky,kz[:LABEL]")


if __name__ == "__main__":
    raise SystemExit(main())
