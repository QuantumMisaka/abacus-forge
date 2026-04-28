"""Argparse-based CLI for the minimal primitives."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from abacus_forge.api import collect, export, prepare, run
from abacus_forge.runner import LocalRunner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="abacus-forge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="prepare a minimal workspace")
    prepare_parser.add_argument("workspace")
    prepare_parser.add_argument("--structure")
    prepare_parser.add_argument("--structure-format")
    prepare_parser.add_argument("--task", default="scf")
    prepare_parser.add_argument("--parameter", action="append", default=[], help="KEY=VALUE")
    prepare_parser.add_argument("--remove-parameter", action="append", default=[])
    prepare_parser.add_argument("--kpoint", action="append", type=int, default=[])
    prepare_parser.add_argument("--pseudo-path")
    prepare_parser.add_argument("--orbital-path")
    prepare_parser.add_argument("--asset-mode", choices=["copy", "link"], default="link")
    prepare_parser.add_argument("--ensure-pbc", action="store_true")

    run_parser = subparsers.add_parser("run", help="run a prepared workspace")
    run_parser.add_argument("workspace")
    run_parser.add_argument("--executable", default="abacus")
    run_parser.add_argument("--mpi", type=int, default=1)
    run_parser.add_argument("--omp", type=int, default=1)

    collect_parser = subparsers.add_parser("collect", help="collect metrics from a workspace")
    collect_parser.add_argument("workspace")
    collect_parser.add_argument("--json", action="store_true", help="print JSON to stdout")

    export_parser = subparsers.add_parser("export", help="collect and export JSON to file")
    export_parser.add_argument("workspace")
    export_parser.add_argument("--output", required=True)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "prepare":
        parameters = _parse_parameters(args.parameter)
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
        )
        print(workspace.root)
        return 0

    if args.command == "run":
        runner = LocalRunner(executable=args.executable, mpi_ranks=args.mpi, omp_threads=args.omp)
        result = run(args.workspace, runner=runner)
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
        return 0 if result.returncode == 0 else result.returncode

    if args.command == "collect":
        result = collect(args.workspace)
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

    parser.error(f"unsupported command: {args.command}")
    return 2


def _parse_parameters(raw_values: Sequence[str]) -> dict[str, str]:
    parameters: dict[str, str] = {}
    for raw in raw_values:
        if "=" not in raw:
            raise SystemExit(f"invalid parameter: {raw}")
        key, value = raw.split("=", 1)
        parameters[key.strip()] = value.strip()
    return parameters


if __name__ == "__main__":
    raise SystemExit(main())
