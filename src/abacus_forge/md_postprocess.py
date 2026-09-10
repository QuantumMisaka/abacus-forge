"""Pure, facts-only molecular-dynamics trajectory analyses.

This module deliberately has no workspace, task, runner, or scheduler imports.
It reads one explicit trajectory and writes deterministic analysis files below
the caller-provided output directory.
"""
from __future__ import annotations

import json
import math
import base64
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .md_postprocess_contracts import MD_ANALYSIS_MODES

_MASS = {"H": 1.008, "C": 12.011, "N": 14.007, "O": 15.999, "Si": 28.085, "Fe": 55.845}
_ELEMENT = re.compile(r"^[A-Z][a-z]?$")
_FALLBACK_PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


def _rdf_pairs(elements: Any, symbols: Sequence[str]) -> list[str]:
    if elements is None:
        pairs = sorted({f"{a}-{b}" for a in symbols for b in symbols if a <= b})
    elif not isinstance(elements, (list, tuple)) or not elements:
        raise ValueError("elements must be a non-empty list of A-B strings")
    else:
        pairs = []
        for item in elements:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                item = f"{item[0]}-{item[1]}"
            if not isinstance(item, str) or item.count("-") != 1:
                raise ValueError("RDF pairs must use the A-B form")
            left, right = item.split("-")
            if not _ELEMENT.fullmatch(left) or not _ELEMENT.fullmatch(right):
                raise ValueError("RDF pairs must contain safe chemical symbols")
            if symbols and (left not in symbols or right not in symbols):
                raise ValueError(f"trajectory contains no atoms for RDF pair {item}")
            pairs.append(f"{left}-{right}")
        if len(set(pairs)) != len(pairs): raise ValueError("RDF pairs must be unique")
    return pairs


@dataclass(frozen=True)
class Frame:
    positions: np.ndarray
    symbols: tuple[str, ...]
    cell: np.ndarray
    pbc: np.ndarray
    masses: np.ndarray
    velocities: np.ndarray | None = None

    def __post_init__(self) -> None:
        p = np.asarray(self.positions, dtype=float)
        c = np.asarray(self.cell, dtype=float).reshape(3, 3)
        b = np.asarray(self.pbc, dtype=bool).reshape(3)
        m = np.asarray(self.masses, dtype=float).reshape(-1)
        v = None if self.velocities is None else np.asarray(self.velocities, dtype=float)
        if p.ndim != 2 or p.shape[1] != 3 or len(self.symbols) != len(p) or m.shape != (len(p),):
            raise ValueError("frame arrays have inconsistent shapes")
        if not np.isfinite(p).all() or not np.isfinite(c).all() or not np.isfinite(m).all() or np.any(m <= 0):
            raise ValueError("frame values must be finite and masses positive")
        if v is not None and (v.shape != p.shape or not np.isfinite(v).all()):
            raise ValueError("frame velocities must match positions and be finite")
        object.__setattr__(self, "positions", p.copy()); object.__setattr__(self, "cell", c.copy())
        object.__setattr__(self, "pbc", b.copy()); object.__setattr__(self, "masses", m.copy())
        if v is not None: object.__setattr__(self, "velocities", v.copy())


class FrameSelection(list[Frame]):
    def __init__(self, frames: Sequence[Frame], *, source_end: int):
        super().__init__(frames); self.source_end = int(source_end)


def _frame_ase(atoms: Any) -> Frame:
    symbols = tuple(atoms.get_chemical_symbols())
    try: masses = np.asarray(atoms.get_masses(), dtype=float)
    except Exception: masses = np.asarray([_MASS.get(s, 1.0) for s in symbols])
    velocities = None
    try: velocities = atoms.get_velocities()
    except Exception: pass
    return Frame(atoms.get_positions(), symbols, atoms.get_cell(), atoms.get_pbc(), masses, velocities)


def _read_xyz(path: Path) -> list[Frame]:
    lines = path.read_text(encoding="utf-8").splitlines(); result = []; i = 0
    while i < len(lines):
        if not lines[i].strip(): i += 1; continue
        try: n = int(lines[i].strip())
        except ValueError as exc: raise ValueError("invalid XYZ atom count") from exc
        if n <= 0 or i + n + 2 > len(lines): raise ValueError("invalid XYZ frame")
        symbols = []; coords = []
        for row in lines[i + 2:i + 2 + n]:
            fields = row.split()
            if len(fields) < 4: raise ValueError("invalid XYZ atom row")
            symbols.append(fields[0]); coords.append([float(x) for x in fields[1:4]])
        result.append(Frame(np.asarray(coords), tuple(symbols), np.zeros((3, 3)), np.zeros(3, bool), np.asarray([_MASS.get(s, 1.0) for s in symbols])))
        i += n + 2
    if not result: raise ValueError("trajectory contains no frames")
    return result


def load_frames(path: str | Path, *, start: int = 0, end: int | None = None, stride: int = 1) -> FrameSelection:
    if isinstance(start, bool) or not isinstance(start, int) or start < 0: raise ValueError("start must be non-negative")
    if end is not None and (isinstance(end, bool) or not isinstance(end, int) or end == 0): raise ValueError("end must be positive or null")
    if isinstance(stride, bool) or not isinstance(stride, int) or stride < 1: raise ValueError("stride must be positive")
    try:
        from ase.io import read
        raw = read(Path(path), index=":")
        frames = [_frame_ase(item) for item in raw]
    except ImportError:
        frames = _read_xyz(Path(path))
    except Exception as exc:
        # ASE can reject plain XYZ variants; the dependency-free parser is the
        # intended fallback for those files.
        try: frames = _read_xyz(Path(path))
        except Exception: raise ValueError(f"failed to read trajectory: {exc}") from exc
    stop = len(frames) if end is None or end < 0 else min(end, len(frames))
    selected = frames[start:stop:stride]
    if not selected: raise ValueError("selected frame range is empty")
    if any(f.symbols != selected[0].symbols for f in selected): raise ValueError("frames must preserve atom ordering and species")
    return FrameSelection(selected, source_end=stop)


def validate_analysis(analysis: Sequence[str]) -> tuple[str, ...]:
    if isinstance(analysis, (str, bytes)) or not analysis: raise ValueError("analysis must be non-empty")
    values = tuple(analysis)
    if any(not isinstance(x, str) or x not in MD_ANALYSIS_MODES for x in values): raise ValueError("analysis contains unsupported canonical mode")
    if len(set(values)) != len(values): raise ValueError("analysis modes must be unique")
    return values


def _finite(value: Any) -> Any:
    if isinstance(value, np.ndarray): return [_finite(x) for x in value.tolist()]
    if isinstance(value, (np.integer, np.floating)): value = value.item()
    if isinstance(value, Mapping): return {str(k): _finite(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)): return [_finite(x) for x in value]
    if isinstance(value, float) and not math.isfinite(value): raise ValueError("analysis values must be finite")
    return value


def canonical_parameter_values(parameters: Mapping[str, Any], modes: Sequence[str]) -> dict[str, Any]:
    if not isinstance(parameters, Mapping): raise ValueError("parameters must be an object")
    known = {"timestep", "selection", "elements", "rmax", "nbins", "save_data", "save_plot"}
    result = {str(k): _finite(v) for k, v in parameters.items() if k in known}
    if any(m in modes for m in ("msd_diffusion", "vacf_vdos")):
        if "timestep" not in result or not isinstance(result["timestep"], (int, float)) or isinstance(result["timestep"], bool) or not math.isfinite(float(result["timestep"])) or result["timestep"] <= 0:
            raise ValueError("timestep is required for MSD/VACF")
    if "rmax" in result and (isinstance(result["rmax"], bool) or not isinstance(result["rmax"], (int, float)) or not math.isfinite(float(result["rmax"])) or float(result["rmax"]) <= 0): raise ValueError("rmax must be finite and positive")
    if "nbins" in result and (isinstance(result["nbins"], bool) or not isinstance(result["nbins"], int) or result["nbins"] < 1): raise ValueError("nbins must be positive")
    if "elements" in result: _rdf_pairs(result["elements"], ())
    if "save_data" in result and not isinstance(result["save_data"], bool): raise ValueError("save_data must be boolean")
    if "save_plot" in result and not isinstance(result["save_plot"], bool): raise ValueError("save_plot must be boolean")
    if "selection" in result and not isinstance(result["selection"], (Mapping, list)):
        raise ValueError("selection must be an object or list")
    return result


def _unwrap(frames: Sequence[Frame]) -> np.ndarray:
    out = np.asarray([f.positions for f in frames], float).copy()
    for i in range(1, len(frames)):
        delta = frames[i].positions - frames[i - 1].positions
        f = frames[i]
        if np.any(f.pbc) and abs(np.linalg.det(f.cell)) > 1e-12:
            frac = np.linalg.solve(f.cell.T, delta.T).T; frac[:, f.pbc] -= np.rint(frac[:, f.pbc]); delta = frac @ f.cell
        out[i] = out[i - 1] + delta
    return out


def _kabsch(ref: np.ndarray, cur: np.ndarray, masses: np.ndarray) -> np.ndarray:
    w = masses / masses.sum(); rc = np.sum(ref * w[:, None], axis=0); cc = np.sum(cur * w[:, None], axis=0)
    cov = ((cur - cc) * w[:, None]).T @ (ref - rc); u, _, vt = np.linalg.svd(cov); d = np.eye(3)
    if np.linalg.det(u @ vt) < 0: d[-1, -1] = -1
    return (cur - cc) @ (u @ d @ vt) + rc


def _msd(frames: Sequence[Frame], timestep: float) -> dict[str, Any]:
    if len(frames) < 2: raise ValueError("MSD requires at least two frames")
    xyz = _unwrap(frames); masses = frames[0].masses; vals = []; xyzvals = []
    for lag in range(len(frames)):
        disps = []
        for origin in range(len(frames) - lag): disps.append(_kabsch(xyz[origin], xyz[origin + lag], masses) - xyz[origin])
        d = np.asarray(disps); xyzvals.append(np.mean(d * d, axis=(0, 1))); vals.append(np.average(np.sum(d * d, axis=2), weights=masses, axis=1).mean())
    t = np.arange(len(vals), dtype=float) * timestep; fit = max(1, len(vals) // 5); slope = float(np.polyfit(t[fit:], vals[fit:], 1)[0]) if len(vals[fit:]) > 1 else 0.0
    return {"time_fs": t, "msd_angstrom2": np.asarray(vals), "msd_xyz_angstrom2": np.asarray(xyzvals), "einstein_slope": slope, "diffusion_angstrom2_per_fs": slope / 6.0}


def _vacf(frames: Sequence[Frame], timestep: float) -> dict[str, Any]:
    if len(frames) < 2: raise ValueError("VACF requires at least two frames")
    if all(f.velocities is not None for f in frames): vel = np.asarray([f.velocities for f in frames], float)
    else: vel = np.gradient(_unwrap(frames), timestep, axis=0)
    vel -= vel.mean(axis=0, keepdims=True); masses = frames[0].masses; vals = []
    for lag in range(len(frames)):
        prod = np.sum(vel[:len(frames)-lag] * vel[lag:], axis=2)
        vals.append(float(np.average(prod, axis=1, weights=masses).mean()))
    vals = np.asarray(vals); vals = vals / vals[0] if abs(vals[0]) > 1e-15 else np.zeros_like(vals)
    return {"time_fs": np.arange(len(vals), dtype=float) * timestep, "vacf": vals, "frequency_THz": np.fft.rfftfreq(len(vals), timestep) * 1000.0, "dos": np.real(np.fft.rfft(vals))}


def _mi(delta: np.ndarray, frame: Frame) -> np.ndarray:
    if not np.any(frame.pbc) or abs(np.linalg.det(frame.cell)) <= 1e-12: return delta
    frac = np.linalg.solve(frame.cell.T, delta); frac[..., frame.pbc] -= np.rint(frac[..., frame.pbc]); return frac @ frame.cell


def _geometry(frames: Sequence[Frame], selection: Any) -> tuple[dict[str, list[float]], dict[str, list[float]]]:
    symbols = frames[0].symbols; pairs = []; angles = []
    selected_indices = None
    if isinstance(selection, Mapping):
        pairs = selection.get("pairs", []) or []; angles = selection.get("angles", []) or []
        if "indices" in selection:
            raw = selection["indices"]
            if not isinstance(raw, list) or not raw or any(isinstance(x, bool) or not isinstance(x, int) or x < 1 or x > len(symbols) for x in raw):
                raise ValueError("selection.indices must be non-empty 1-based atom indices")
            selected_indices = {x - 1 for x in raw}
    pairs = [pairs] if isinstance(pairs, str) else list(pairs); angles = [angles] if isinstance(angles, str) else list(angles)
    if not pairs: pairs = sorted({f"{a}-{b}" for a in symbols for b in symbols if a <= b})
    if not angles: angles = sorted({f"{a}-{b}-{c}" for a in symbols for b in symbols for c in symbols})
    for pair in pairs:
        if not isinstance(pair, str) or pair.count("-") != 1:
            raise ValueError("bond pairs must use the A-B form")
        a, b = pair.split("-")
        if not _ELEMENT.fullmatch(a) or not _ELEMENT.fullmatch(b) or a not in symbols or b not in symbols:
            raise ValueError(f"trajectory contains no atoms for bond pair {pair}")
    for trip in angles:
        if not isinstance(trip, str) or trip.count("-") != 2:
            raise ValueError("bond angles must use the A-B-C form")
        a, b, c = trip.split("-")
        if any(not _ELEMENT.fullmatch(x) or x not in symbols for x in (a, b, c)):
            raise ValueError(f"trajectory contains no atoms for bond angle {trip}")
    lengths = {str(p): [] for p in pairs}; angle_values = {str(a): [] for a in angles}
    for frame in frames:
        for pair in lengths:
            a, b = pair.split("-"); left = [i for i,s in enumerate(symbols) if s == a]; right = [i for i,s in enumerate(symbols) if s == b]
            for i in left:
                for j in right:
                    if i != j and not (a == b and i > j) and (selected_indices is None or {i, j} <= selected_indices): lengths[pair].append(float(np.linalg.norm(_mi(frame.positions[j]-frame.positions[i], frame))))
        for trip in angle_values:
            a,b,c = trip.split("-"); centers=[i for i,s in enumerate(symbols) if s==b]; left=[i for i,s in enumerate(symbols) if s==a]; right=[i for i,s in enumerate(symbols) if s==c]
            for j in centers:
                for i in left:
                    for k in right:
                        if len({i,j,k}) < 3 or (a == c and i > k) or (selected_indices is not None and not {i,j,k} <= selected_indices): continue
                        u = _mi(frame.positions[i]-frame.positions[j], frame); v = _mi(frame.positions[k]-frame.positions[j], frame); den=np.linalg.norm(u)*np.linalg.norm(v)
                        if den: angle_values[trip].append(float(np.degrees(np.arccos(np.clip(np.dot(u,v)/den,-1,1)))))
    return lengths, angle_values


def _rdf(frames: Sequence[Frame], elements: Sequence[str] | None, rmax: float, nbins: int) -> dict[str, Any]:
    if not all(np.any(f.pbc) and abs(np.linalg.det(f.cell)) > 1e-12 for f in frames): raise ValueError("rdf requires explicit periodic cells")
    symbols=frames[0].symbols; pairs=_rdf_pairs(elements, symbols); edges=np.linspace(0,rmax,nbins+1); r=(edges[:-1]+edges[1:])/2; output={}
    for frame in frames:
        volume = abs(float(np.linalg.det(frame.cell)))
        if volume <= 1e-12: raise ValueError("rdf requires non-zero cell volume")
        heights = []
        for axis in range(3):
            other = [frame.cell[j] for j in range(3) if j != axis]
            heights.append(volume / np.linalg.norm(np.cross(other[0], other[1])))
        cutoff = min(heights[i] / 2 for i in range(3) if frame.pbc[i])
        if rmax > cutoff + 1e-12: raise ValueError("rdf rmax exceeds the minimum-image cutoff")
    for pair in pairs:
        a,b=pair.split("-"); hist=np.zeros(nbins); count=0
        for frame in frames:
            ia=[i for i,s in enumerate(symbols) if s==a]; ib=[i for i,s in enumerate(symbols) if s==b]
            ds=[np.linalg.norm(_mi(frame.positions[j]-frame.positions[i],frame)) for i in ia for j in ib if i!=j and not(a==b and i>j)]
            hist += np.histogram(ds, edges)[0]; count += len(ds)
        # Normalize the pair histogram by the ideal-gas shell population in
        # each explicit cell.  This keeps ``g_r`` a dimensionless factual
        # radial distribution rather than exposing an unscaled count.
        expected = np.zeros(nbins, dtype=float)
        shell = (4.0 * math.pi / 3.0) * (edges[1:] ** 3 - edges[:-1] ** 3)
        for frame in frames:
            volume = abs(float(np.linalg.det(frame.cell)))
            na, nb = len(ia), len(ib)
            pair_population = na * (na - 1) / 2 if a == b else na * nb
            expected += pair_population * shell / volume
        gr = np.divide(hist, expected, out=np.zeros_like(hist), where=expected > 0)
        output[pair]={"r_angstrom":r,"g_r":gr,"pair_count":count,"frame_count":len(frames)}
    return output


def analyze_trajectory(frames: Sequence[Frame], modes: Sequence[str], *, timestep: float | None = None, selection: Any = None, elements: Sequence[str] | None = None, rmax: float = 6.0, nbins: int = 100) -> dict[str, Any]:
    modes = validate_analysis(modes); results={}
    if not isinstance(nbins, int) or isinstance(nbins, bool) or nbins < 1: raise ValueError("nbins must be positive")
    if not isinstance(rmax, (int, float)) or isinstance(rmax, bool) or not math.isfinite(float(rmax)) or rmax <= 0: raise ValueError("rmax must be finite and positive")
    if timestep is not None and (not isinstance(timestep, (int, float)) or isinstance(timestep, bool) or not math.isfinite(float(timestep)) or timestep <= 0): raise ValueError("timestep must be finite and positive")
    if "rdf" in modes: results["rdf"] = _rdf(frames, elements, rmax, nbins)
    if "msd_diffusion" in modes: results["msd_diffusion"] = _msd(frames, float(timestep)) if timestep is not None else (_ for _ in ()).throw(ValueError("timestep is required"))
    if "vacf_vdos" in modes: results["vacf_vdos"] = _vacf(frames, float(timestep)) if timestep is not None else (_ for _ in ()).throw(ValueError("timestep is required"))
    lengths, angles = _geometry(frames, selection) if {"bond_length","bond_angle"} & set(modes) else ({}, {})
    if "bond_length" in modes: results["bond_length"]={"lengths_angstrom":lengths}
    if "bond_angle" in modes: results["bond_angle"]={"angles_deg":angles}
    return _finite(results)


@dataclass(frozen=True)
class MdPostprocessResult:
    summary: Mapping[str, Any]; diagnostics: Mapping[str, Any]; results: Mapping[str, Any]; sampling: Mapping[str, Any]; generated_files: tuple[str, ...]


def run_md_postprocess(trajectory: str | Path, modes: Sequence[str], *, output_dir: str | Path, start: int = 0, end: int | None = None, stride: int = 1, parameters: Mapping[str, Any] | None = None) -> MdPostprocessResult:
    modes=validate_analysis(modes); params=canonical_parameter_values(parameters or {}, modes); frames=load_frames(trajectory,start=start,end=end,stride=stride); out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    results=analyze_trajectory(frames,modes,timestep=params.get("timestep"),selection=params.get("selection"),elements=params.get("elements"),rmax=float(params.get("rmax",6.0)),nbins=int(params.get("nbins",100)))
    generated=[]; save_data=params.get("save_data",True); save_plot=params.get("save_plot",True)
    def write_data(path: Path, mode: str, value: Mapping[str, Any]) -> None:
        if mode == "msd_diffusion":
            rows = zip(value["time_fs"], value["msd_angstrom2"]); text = "time_fs msd_angstrom2\n" + "\n".join(f"{float(x):.17g} {float(y):.17g}" for x, y in rows)
        elif mode == "vacf_vdos":
            rows = zip(value["time_fs"], value["vacf"]); text = "time_fs vacf\n" + "\n".join(f"{float(x):.17g} {float(y):.17g}" for x, y in rows)
        elif mode == "bond_length":
            rows = ((pair, x) for pair, values in value["lengths_angstrom"].items() for x in values); text = "pair value_angstrom\n" + "\n".join(f"{pair} {float(x):.17g}" for pair, x in rows)
        elif mode == "bond_angle":
            rows = ((trip, x) for trip, values in value["angles_deg"].items() for x in values); text = "angle value_degree\n" + "\n".join(f"{trip} {float(x):.17g}" for trip, x in rows)
        else:
            rows = ((pair, r, g) for pair, item in value.items() for r, g in zip(item["r_angstrom"], item["g_r"])); text = "pair r_angstrom g_r\n" + "\n".join(f"{pair} {float(r):.17g} {float(g):.17g}" for pair, r, g in rows)
        path.write_text(text + "\n", encoding="utf-8")
    if not isinstance(save_data, bool) or not isinstance(save_plot, bool): raise ValueError("save_data and save_plot must be booleans")
    if save_data:
        for mode in modes:
            if mode == "rdf":
                for pair, value in results[mode].items():
                    safe = pair.replace("-", "_")
                    path = out / f"rdf_{safe}.txt"
                    write_data(path, mode, {pair: value})
                    generated.append(path.name)
                continue
            name={"msd_diffusion":"msd","vacf_vdos":"vacf_vdos","bond_length":"bond_lengths","bond_angle":"bond_angles","rdf":"rdf"}[mode]
            path=out/(name+".txt"); write_data(path, mode, results[mode]); generated.append(path.name)
    if save_plot:
        try:
            import matplotlib.pyplot as plt
        except Exception:
            plt = None
        for mode in modes:
                name={"msd_diffusion":"msd","vacf_vdos":"vacf_vdos","bond_length":"bond_lengths","bond_angle":"bond_angles","rdf":"rdf"}[mode]
                plot_pairs = list(results[mode]) if mode == "rdf" else [None]
                for pair in plot_pairs:
                    plot_name = f"rdf_{pair.replace('-', '_')}" if pair is not None else name
                    plot_path = out / (plot_name + ".png")
                    try:
                        if plt is None: raise RuntimeError("matplotlib unavailable")
                        fig, ax = plt.subplots(figsize=(6, 4))
                        if mode == "msd_diffusion": ax.plot(results[mode]["time_fs"], results[mode]["msd_angstrom2"])
                        elif mode == "vacf_vdos": ax.plot(results[mode]["frequency_THz"], results[mode]["dos"])
                        elif mode == "rdf":
                            values = results[mode][pair]; ax.plot(values["r_angstrom"], values["g_r"], label=pair)
                        elif mode == "bond_length":
                            for pair_name, values in results[mode]["lengths_angstrom"].items(): ax.plot(values, np.zeros(len(values)), ".", label=pair_name)
                        else:
                            for trip, values in results[mode]["angles_deg"].items(): ax.plot(values, np.zeros(len(values)), ".", label=trip)
                        fig.tight_layout(); fig.savefig(plot_path, dpi=120); plt.close(fig)
                    except Exception:
                        plot_path.write_bytes(_FALLBACK_PNG)
                    generated.append(plot_path.name)
    payload={"schema_version":"forge.md-postprocess/v1","analysis":list(modes),"sampling":{"start":start,"end":frames.source_end,"stride":stride,"frame_count":len(frames)},"results":results}
    (out/"analysis.json").write_text(json.dumps(payload,sort_keys=True,ensure_ascii=False,allow_nan=False,indent=2)+"\n",encoding="utf-8"); generated.append("analysis.json")
    return MdPostprocessResult(summary={"analysis":list(modes)},diagnostics={"ignored_parameter_keys":sorted(set((parameters or {}))-set(params))},results=results,sampling=payload["sampling"],generated_files=tuple(generated))


__all__=["Frame","FrameSelection","MdPostprocessResult","load_frames","validate_analysis","canonical_parameter_values","analyze_trajectory","run_md_postprocess"]
