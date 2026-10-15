"""ABACUS LCAO output reader for the IAO-COHP kernel (toolbox-local, deps zero-new).

Reads one completed SCF directory written under the IAO-COHP output policy
(``out_mat_hs 1 8``, ``out_mat_hs2 1``, ``out_wfc_lcao 1``, ``symmetry 0``):
INPUT, STRU, orbital-file headers, UPF ``z_valence``/``element``,
``OUT.ABACUS/kpoints``, per-k ``data-{k}-H``/``data-{k}-S``,
``WFC_NAO_K{k}.txt``, the real-space overlap ``data-SR-sparse_SPIN0.csr`` and
the Fermi level in ``running_scf.log``.

Per-k matrices are streamed (:meth:`AbacusLcaoRun.iter_kpoints`) so one
NAO-sized S/H/C set is held at a time.  Format facts (ABACUS v3.10 platform
outputs):

* ``data-{k}-H/S``: first token = basis size, then the upper triangle as
  ``(re,im)``; k numbering starts at 0 (1 in older versions); with nspin=2 both
  H and S files are doubled, spin 2 at offset nk; H is in Ry.
* ``WFC_NAO_K{k}.txt``: 1-based k (spin 2 at offset nk); per band the energy,
  the ``wg = f * w_k * g`` occupation and interleaved re/im coefficients.
* ``kpoints``: 5-column rows = reduced k list; 8-column rows map the full grid
  onto it (time-reversal unfolding).
* Basis order: atom -> l -> zeta -> m.

Three reader facts the benchmark exposed are handled here: the text precision
comes from ``out_mat_hs 1 <ndigits>``; fractional coordinates are wrapped into
[0, 1) because ABACUS labels H(R)/S(R) by the wrapped cell; the Bloch phase
sign is determined from S(R) instead of assumed.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import numpy as np

RY_TO_EV = 13.605693122994
BOHR_TO_ANG = 0.529177210903

_NUM_RE = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eEdD][-+]?\d+)?")
_STRU_SECTIONS = {
    "ATOMIC_SPECIES", "NUMERICAL_ORBITAL", "LATTICE_CONSTANT", "LATTICE_VECTORS",
    "LATTICE_PARAMETERS", "ATOMIC_POSITIONS", "NUMERICAL_DESCRIPTOR", "ABFS_ORBITAL",
    "PAW_FILES",
}


def _floats(text: str) -> np.ndarray:
    return np.array([float(x.replace("D", "E").replace("d", "e")) for x in _NUM_RE.findall(text)])


def read_input_params(path: Path) -> dict[str, str]:
    """INPUT as ``{lowercase key: raw value string}`` (comments stripped)."""
    params: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.split("#")[0].strip()
        if not line or line.upper().startswith("INPUT_PARAMETERS"):
            continue
        tokens = line.split()
        params[tokens[0].lower()] = " ".join(tokens[1:])
    return params


def text_ndigits(params: dict[str, str]) -> int:
    """Significant digits of the H/S text output (``out_mat_hs 1 <n>``)."""
    tokens = params.get("out_mat_hs", "").split()
    if len(tokens) >= 2 and tokens[1].isdigit():
        return int(tokens[1])
    value = params.get("out_ndigits", "")
    return int(value) if value.isdigit() else 8


# ----------------------------------------------------------------------------- structure
@dataclass
class Structure:
    """STRU contents; ``frac`` is wrapped into [0, 1) (``wrapped_atoms``: 0-based)."""

    lattice_ang: np.ndarray
    species: list[str]
    pp_files: dict[str, str | None]
    orb_files: dict[str, str]
    atom_species: list[str]
    frac: np.ndarray
    wrapped_atoms: list[int] = field(default_factory=list)

    @property
    def natom(self) -> int:
        return len(self.atom_species)

    def distance(self, a: int, b: int, t) -> float:
        """Distance (Angstrom) from atom ``a`` to atom ``b`` translated by ``t``."""
        d = (self.frac[b] + np.asarray(t, float) - self.frac[a]) @ self.lattice_ang
        return float(np.linalg.norm(d))

    def images(self, a: int, b: int, rmax: float) -> list[tuple[tuple[int, int, int], float]]:
        """All translations ``t`` with 0 < d(a, b + t) < rmax, sorted by distance."""
        spacing = 1.0 / np.linalg.norm(np.linalg.inv(self.lattice_ang), axis=0)
        tmax = [int(np.ceil(rmax / s)) + 1 for s in spacing]
        out = []
        for t in itertools.product(*[range(-n, n + 1) for n in tmax]):
            d = self.distance(a, b, t)
            if 1e-6 < d < rmax:
                out.append((tuple(int(x) for x in t), d))
        return sorted(out, key=lambda item: (round(item[1], 6), item[0]))


def read_stru(path: Path) -> Structure:
    """STRU parser (section headers from a whitelist so C/N/F are not headers)."""
    lines = []
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#")[0].split("//")[0].strip()
        if line:
            lines.append(line)
    sections: dict[str, list[str]] = {}
    current = None
    for line in lines:
        head = line.split()[0]
        if head in _STRU_SECTIONS:
            current = head
            sections[current] = []
        elif current:
            sections[current].append(line)
    species, pp_files = [], {}
    for line in sections.get("ATOMIC_SPECIES", []):
        tokens = line.split()
        species.append(tokens[0])
        pp_files[tokens[0]] = tokens[2] if len(tokens) > 2 else None
    orb_files = {}
    for index, line in enumerate(sections.get("NUMERICAL_ORBITAL", [])):
        if index < len(species):
            orb_files[species[index]] = line.split()[0]
    missing = [sp for sp in species if sp not in orb_files]
    if missing:
        raise ValueError(f"STRU 缺少 NUMERICAL_ORBITAL 条目：{missing}（IAO-COHP 需要 LCAO 轨道文件）")
    if "LATTICE_VECTORS" not in sections:
        raise ValueError("STRU 缺少 LATTICE_VECTORS（latname != none 的输入当前不支持 IAO-COHP）")
    lat0_bohr = float(sections["LATTICE_CONSTANT"][0].split()[0])
    lattice = np.array([[float(x) for x in l.split()[:3]] for l in sections["LATTICE_VECTORS"][:3]])
    lattice_bohr = lattice * lat0_bohr
    positions = sections["ATOMIC_POSITIONS"]
    coord_type = positions[0].lower()
    atom_species, coords = [], []
    i = 1
    while i < len(positions):
        label = positions[i].split()[0]
        count = int(positions[i + 2].split()[0])
        i += 3
        for _ in range(count):
            coords.append([float(x) for x in positions[i].split()[:3]])
            atom_species.append(label)
            i += 1
    coords = np.array(coords, float)
    if "center" in coord_type:
        raise ValueError(f"坐标类型 {positions[0]}（center 变体）会平移原子，IAO-COHP 不复现该平移；请用 Direct")
    if coord_type.startswith("direct"):
        frac = coords
    elif coord_type.startswith("cartesian_angstrom"):
        frac = (coords / BOHR_TO_ANG) @ np.linalg.inv(lattice_bohr)
    elif coord_type.startswith("cartesian_au"):
        frac = coords @ np.linalg.inv(lattice_bohr)
    elif coord_type.startswith("cartesian"):
        frac = coords @ np.linalg.inv(lattice)
    else:
        raise ValueError(f"未知坐标类型 {positions[0]}")
    wrapped = np.mod(frac, 1.0)
    wrapped[np.abs(wrapped - 1.0) < 1e-8] = 0.0
    moved = [int(a) for a in np.where(np.abs(wrapped - frac).max(axis=1) > 1e-8)[0]]
    return Structure(lattice_bohr * BOHR_TO_ANG, species, pp_files, orb_files,
                     atom_species, wrapped, moved)


def read_orb_counts(path: Path) -> tuple[list[int], float | None]:
    """``[ns, np, nd, nf]`` and the radius cutoff (Bohr) from a .orb header."""
    counts = [0, 0, 0, 0]
    rcut = None
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            match = re.match(r"\s*Number of ([SPDF])orbital-->?\s*(\d+)", line) or re.match(
                r"\s*Number of ([SPDF])orbital\s+(\d+)", line
            )
            if match:
                counts["SPDF".index(match.group(1))] = int(match.group(2))
            if line.strip().startswith("Radius Cutoff"):
                values = _floats(line)
                rcut = float(values[-1]) if values.size else None
            if line.strip().startswith(("Type", "Mesh")):
                break
    if not any(counts):
        raise ValueError(f"{path}: 未解析到 Number of S/P/D/Forbital 头部")
    return counts, rcut


def read_upf_header(path: Path) -> tuple[float, str | None]:
    """``(z_valence, element)`` from a UPF v2 attribute header or a v1 header."""
    text = Path(path).read_text(encoding="utf-8", errors="ignore")[:20000]
    element = None
    match = re.search(r'element\s*=\s*"\s*([A-Za-z]{1,2})\s*"', text)
    if match:
        element = match.group(1)
    match = re.search(r'z_valence\s*=\s*"?\s*([-\d.Ee+]+)', text)
    if match:
        return float(match.group(1)), element
    match = re.search(r"([-\d.Ee+]+)\s+Z valence", text)
    if match:
        return float(match.group(1)), element
    raise ValueError(f"无法从 {path} 读取 z_valence")


@dataclass
class OrbitalLayout:
    """Per-basis-function labels in ABACUS order (atom -> l -> zeta -> m)."""

    atom: np.ndarray
    l: np.ndarray
    zeta: np.ndarray
    m: np.ndarray
    counts: dict[str, list[int]]
    rcut_ang: dict[str, float | None]

    @property
    def nbasis(self) -> int:
        return int(self.atom.size)


def build_layout(stru: Structure, orb_paths: dict[str, Path]) -> OrbitalLayout:
    counts, rcut = {}, {}
    for sp in stru.species:
        counts[sp], rc = read_orb_counts(orb_paths[sp])
        rcut[sp] = rc * BOHR_TO_ANG if rc else None
    atom, l_, zeta, m = [], [], [], []
    for index, sp in enumerate(stru.atom_species):
        for l, nz in enumerate(counts[sp]):
            for z in range(nz):
                for mi in range(2 * l + 1):
                    atom.append(index)
                    l_.append(l)
                    zeta.append(z)
                    m.append(mi)
    return OrbitalLayout(np.array(atom), np.array(l_), np.array(zeta), np.array(m), counts, rcut)


# ----------------------------------------------------------------------------- electronic files
def read_hs_k_txt(path: Path) -> np.ndarray:
    """Hermitian matrix from ``data-{k}-H/S`` (dimension + upper triangle ``(re,im)``)."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    body = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    head, _, rest = body.strip().partition("\n")
    n = int(head.split()[0])
    tail = head.split(None, 1)[1] if len(head.split()) > 1 else ""
    values = np.array(
        (tail + " " + rest).replace("(", " ").replace(")", " ").replace(",", " ").split(),
        dtype=float,
    )
    need = n * (n + 1) // 2
    if values.size < 2 * need:
        raise ValueError(f"{path}: 上三角复数元素不足（{values.size // 2} < {need}）")
    upper = values[: 2 * need : 2] + 1j * values[1 : 2 * need : 2]
    matrix = np.zeros((n, n), complex)
    matrix[np.triu_indices(n)] = upper
    return matrix + np.triu(matrix, 1).conj().T


def read_wfc_nao_txt(path: Path) -> dict:
    """``WFC_NAO_K{k}.txt``: band energies (file units), ``wg`` and coefficients."""
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    header: dict[str, int] = {}
    index = 0
    while index < len(lines) and "(band)" not in lines[index]:
        line = lines[index]
        if "number of bands" in line:
            header["nbands"] = int(_floats(line)[0])
        elif "number of orbitals" in line:
            header["nlocal"] = int(_floats(line)[0])
        index += 1
    if "nbands" not in header or "nlocal" not in header:
        raise ValueError(f"{path}: 缺少 number of bands / number of orbitals 头部")
    nbands, nlocal = header["nbands"], header["nlocal"]
    blocks = re.split(r"\n\s*\d+\s*\(band\)[^\n]*", "\n" + "\n".join(lines[index:]))
    blocks = [b for b in blocks if b.strip()]
    if len(blocks) != nbands:
        raise ValueError(f"{path}: 期望 {nbands} 个能带块，解析到 {len(blocks)}")
    energies = np.zeros(nbands)
    wg = np.zeros(nbands)
    coeff = np.zeros((nlocal, nbands), complex)
    for band, block in enumerate(blocks):
        rows = block.strip().splitlines()
        energies[band] = _floats(rows[0])[0]
        wg[band] = _floats(rows[1])[0]
        values = np.array(" ".join(rows[2:]).split(), dtype=float)
        if values.size != 2 * nlocal:
            raise ValueError(f"{path} band {band + 1}: 系数个数 {values.size} != 2*nlocal {2 * nlocal}")
        coeff[:, band] = values[0::2] + 1j * values[1::2]
    return {"nbands": nbands, "nlocal": nlocal, "energy": energies, "wg": wg, "C": coeff}


def read_csr_triplets(path: Path) -> tuple[int, dict[tuple[int, int, int], tuple]]:
    """ABACUS text CSR (``data-SR-sparse_SPIN0.csr``) as ``{R: (rows, cols, vals)}``."""
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    if "gamma-only folded" in raw:
        raise ValueError(f"{path}: gamma_only 的 S(R) 被折叠为单块，无法判定 Bloch 相位符号")
    lines = raw.splitlines()
    dim = n_r = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if "Dimension" in line:
            dim = int(_floats(line)[-1])
        if "Matrix number" in line:
            n_r = int(_floats(line)[-1])
            i += 1
            break
        i += 1
    if dim is None or n_r is None:
        raise ValueError(f"{path}: 未找到 Matrix Dimension / Matrix number 头部")
    blocks: dict[tuple[int, int, int], tuple] = {}
    while i < len(lines) and len(blocks) < n_r:
        tokens = lines[i].split()
        i += 1
        if len(tokens) != 4 or not all(re.fullmatch(r"[-+]?\d+", t) for t in tokens):
            continue
        r = (int(tokens[0]), int(tokens[1]), int(tokens[2]))
        nnz = int(tokens[3])
        if nnz == 0:
            blocks[r] = (np.zeros(0, int), np.zeros(0, int), np.zeros(0))
            continue
        segments = []
        while len(segments) < 3 and i < len(lines):
            text = lines[i].strip()
            i += 1
            if text and not text.startswith("#"):
                segments.append(text)
        if "(" in segments[0]:
            parts = np.array(segments[0].replace("(", " ").replace(")", " ").replace(",", " ").split(), float)
            vals = parts[0::2] + 1j * parts[1::2]
        else:
            vals = np.array(segments[0].split(), float)
        cols = np.array(segments[1].split(), int)
        rowptr = np.array(segments[2].split(), int)
        if vals.size != nnz or cols.size != nnz or rowptr.size != dim + 1:
            raise ValueError(f"{path} R={r}: CSR 长度不一致")
        rows = np.repeat(np.arange(dim), np.diff(rowptr))
        blocks[r] = (rows, cols, vals)
    return dim, blocks


def read_kpoints(path: Path) -> dict:
    """Reduced k list (5-column rows) and, when present, the full-grid map (8 columns).

    Weights come from the full-grid map counts when available (the WEIGHT
    column only has 4 decimals), else from equal printed weights, else the
    column itself; they are normalised to sum 1.
    """
    rows_a, rows_b = [], []
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        tokens = line.split()
        if not tokens or not re.fullmatch(r"\d+", tokens[0]):
            continue
        values = _floats(line)
        if values.size == 5:
            rows_a.append(values)
        elif values.size == 8:
            rows_b.append(values)
    if not rows_a:
        raise ValueError(f"{path}: 未解析到约化 k 点表（idx kx ky kz weight）")
    a = np.array(rows_a)
    weights = a[:, 4] / a[:, 4].sum()
    full_k = full_map = None
    if rows_b:
        b = np.array(rows_b)
        full_k, full_map = b[:, 1:4], b[:, 4].astype(int) - 1
        if full_map.min() >= 0 and full_map.max() < len(a):
            counts = np.bincount(full_map, minlength=len(a)).astype(float)
            if (counts > 0).all():
                weights = counts / counts.sum()
    elif np.ptp(a[:, 4]) == 0.0:
        weights = np.full(len(a), 1.0 / len(a))
    return {"kfrac": a[:, 1:4], "weights": weights, "full_k": full_k, "full_map": full_map}


def unfolding_signs(kred: np.ndarray, full_k: np.ndarray, full_map: np.ndarray) -> np.ndarray:
    """+1 when full-grid k_i == k_j (mod G), -1 when k_i == -k_j, 0 otherwise."""
    signs = np.zeros(len(full_k), int)
    for i, (k, j) in enumerate(zip(full_k, full_map)):
        plus = np.asarray(k) - kred[j]
        minus = np.asarray(k) + kred[j]
        if np.abs(plus - np.round(plus)).max() < 1e-6:
            signs[i] = 1
        elif np.abs(minus - np.round(minus)).max() < 1e-6:
            signs[i] = -1
    return signs


def read_fermi_ev(log_path: Path) -> tuple[float, float | None, float | None]:
    """Last ``EFERMI = x eV`` (or ``E_Fermi <Ry> <eV>``) and spin-resolved values."""
    ef = up = dw = None
    for line in Path(log_path).read_text(encoding="utf-8", errors="ignore").splitlines():
        if "E_Fermi_up" in line or "E_Fermi_dw" in line or "EFERMI" in line or re.search(r"E_Fermi\b", line):
            nums = _floats(re.sub(r"E_Fermi(_up|_dw)?|EFERMI", " ", line))
            if not nums.size:
                continue
            if nums.size >= 2 and nums[0] != 0 and abs(nums[1] / nums[0] - RY_TO_EV) < 0.05:
                value = float(nums[1])
            elif re.search(r"\bRy\b", line) and not re.search(r"\beV\b", line):
                value = float(nums[-1]) * RY_TO_EV
            else:
                value = float(nums[-1])
            if "E_Fermi_up" in line:
                up = value
            elif "E_Fermi_dw" in line:
                dw = value
            else:
                ef = value
    if ef is None and up is not None and dw is not None:
        ef = 0.5 * (up + dw)
    if ef is None:
        raise ValueError(f"{log_path}: 未找到费米能（EFERMI / E_Fermi）")
    return ef, up, dw


# ----------------------------------------------------------------------------- run directory
@dataclass
class KPointData:
    """One reduced k point: S, and per spin H (eV), C, raw energies, wg."""

    ik: int
    S: np.ndarray
    H: list[np.ndarray]
    C: list[np.ndarray]
    energy: list[np.ndarray]
    wg: list[np.ndarray]


def resolve_input_file(base: Path, directory: str | None, name: str) -> Path | None:
    """PP/ORB file lookup: ``pseudo_dir``/``orbital_dir`` (relative to the run
    dir when relative), then the run dir itself."""
    candidates = []
    if directory:
        folder = Path(directory)
        candidates.append(folder / name if folder.is_absolute() else base / folder / name)
    candidates += [base / name, Path(name)]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


class AbacusLcaoRun:
    """Metadata of one ABACUS LCAO SCF run plus streamed per-k readers."""

    def __init__(self, run_dir: Path, out_dir: Path | None = None):
        self.run_dir = Path(run_dir).resolve()
        self.out_dir = Path(out_dir) if out_dir else self.run_dir / "OUT.ABACUS"
        if not self.out_dir.is_dir():
            raise FileNotFoundError(f"未找到 {self.out_dir}")
        self.params = read_input_params(self.run_dir / "INPUT")
        p = self.params
        if p.get("basis_type", "lcao").lower() != "lcao":
            raise ValueError(f"basis_type={p.get('basis_type')}：IAO-COHP 只处理 LCAO")
        self.nspin = int(p.get("nspin", "1") or 1)
        if self.nspin not in (1, 2) or p.get("noncolin", "0").lower() in ("1", "true") or \
                p.get("lspinorb", "0").lower() in ("1", "true"):
            raise ValueError("IAO-COHP 支持 nspin=1/2 的共线计算；nspin=4 / SOC 不在范围内")
        if p.get("gamma_only", "0").lower() in ("1", "true", "t"):
            raise ValueError("gamma_only=1 的输出没有 k 分辨矩阵，IAO-COHP 需要 gamma_only 0（Γ 点可用 KPT 1 1 1）")
        self.ndigits = text_ndigits(p)
        self.stru = read_stru(self.run_dir / "STRU")
        orb_paths, self.zval, self.upf_element = {}, {}, {}
        for sp in self.stru.species:
            orb = resolve_input_file(self.run_dir, p.get("orbital_dir"), self.stru.orb_files[sp])
            if orb is None:
                raise FileNotFoundError(f"找不到 {sp} 的轨道文件 {self.stru.orb_files[sp]}")
            orb_paths[sp] = orb
            pp = resolve_input_file(self.run_dir, p.get("pseudo_dir"), self.stru.pp_files[sp] or "")
            if pp is None:
                raise FileNotFoundError(f"找不到 {sp} 的赝势文件 {self.stru.pp_files[sp]}")
            self.zval[sp], self.upf_element[sp] = read_upf_header(pp)
        self.layout = build_layout(self.stru, orb_paths)
        kinfo = read_kpoints(self.out_dir / "kpoints")
        self.kfrac, self.kweight = kinfo["kfrac"], kinfo["weights"]
        self.full_k, self.full_map = kinfo["full_k"], kinfo["full_map"]
        log = self.out_dir / "running_scf.log"
        if not log.is_file():
            raise FileNotFoundError(f"缺少 {log}")
        ef, up, dw = read_fermi_ev(log)
        self.efermi_ev = ef
        self.ef_spin = [ef] * self.nspin
        if self.nspin == 2 and up is not None and dw is not None and abs(up - dw) > 1e-6:
            self.ef_spin = [up, dw]
        self._base_s = self._detect_kbase("S", self.nk)
        self._base_h = self._detect_kbase("H", self.nk * self.nspin)

    @property
    def nk(self) -> int:
        return len(self.kfrac)

    @property
    def g(self) -> float:
        return 2.0 / self.nspin

    @property
    def nbasis(self) -> int:
        return self.layout.nbasis

    def nelec_reference(self) -> float:
        value = self.params.get("nelec", "")
        try:
            nelec = float(value)
        except ValueError:
            nelec = 0.0
        return nelec if nelec > 0 else float(sum(self.zval[sp] for sp in self.stru.atom_species))

    def _detect_kbase(self, kind: str, needed: int) -> int:
        pattern = re.compile(r"^(?:\d+_)?data-(\d+)-" + kind + r"$")
        present = {int(m.group(1)) for n in (p.name for p in self.out_dir.iterdir())
                   if (m := pattern.match(n))}
        for base in (0, 1):
            if all(i + base in present for i in range(needed)):
                return base
        raise FileNotFoundError(
            f"{self.out_dir}: data-*-{kind} 文件不完整（需要 {needed} 个，找到 {len(present)} 个；"
            "需要 out_mat_hs 1 8 的 k 分辨输出）"
        )

    def _file(self, name: str) -> Path:
        path = self.out_dir / name
        if path.is_file():
            return path
        prefixed = sorted(self.out_dir.glob(f"*_{name}"))
        if prefixed:
            return prefixed[-1]
        raise FileNotFoundError(f"缺少 {self.out_dir / name}")

    def overlap_r_path(self) -> Path | None:
        for name in ("data-SR-sparse_SPIN0.csr", "sr_nao.csr"):
            path = self.out_dir / name
            if path.is_file():
                return path
        return None

    def iter_kpoints(self) -> Iterator[KPointData]:
        """Yield each reduced k point; files are read lazily, one k at a time."""
        for ik in range(self.nk):
            s_mat = read_hs_k_txt(self._file(f"data-{ik + self._base_s}-S"))
            if s_mat.shape[0] != self.nbasis:
                raise ValueError(f"data-{ik + self._base_s}-S 维度 {s_mat.shape[0]} 与轨道头推出的 nbasis {self.nbasis} 不符")
            h_list, c_list, e_list, wg_list = [], [], [], []
            for s in range(self.nspin):
                h_list.append(read_hs_k_txt(self._file(f"data-{ik + self._base_h + s * self.nk}-H")) * RY_TO_EV)
                wfc = read_wfc_nao_txt(self._file(f"WFC_NAO_K{ik + 1 + s * self.nk}.txt"))
                if wfc["nlocal"] != self.nbasis:
                    raise ValueError(f"WFC_NAO_K{ik + 1 + s * self.nk}.txt: nlocal={wfc['nlocal']} 与 nbasis={self.nbasis} 不符")
                c_list.append(wfc["C"])
                e_list.append(wfc["energy"])
                wg_list.append(wfc["wg"])
            yield KPointData(ik, s_mat, h_list, c_list, e_list, wg_list)
