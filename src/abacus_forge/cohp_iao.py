"""Frozen-semicore IAO-COHP kernel (toolbox-local, deps zero-new).

Method (fixed by the 2026-09-30 COHP benchmark, see
``docs/reports/2026-09-30-cohp-iao-kernel.md``):

1. Reference minimal basis ``chi = phi W``: per atom, the first zeta of every
   occupied valence shell (rules in :mod:`toolkits.cohp_iao_shells`); ``W`` is a
   column selection of the NAO basis, so ``P12 = W`` and ``S2 = W^T S1 W``.
2. Frozen semicore: the lowest ``N_semi`` bands per (spin, k), ``N_semi`` =
   sum of semicore orbitals of all atoms, leave the occupied set and the
   density matrix.  Guards: semicore/valence gap, frozen-band occupation and
   semicore character.
3. Knizia IAO per k (JCTC 2013, 9, 4834) with occupied set ``f > 0.5``::

       C~ = orth_S1(W S2^-1 W^T S1 C_occ)
       A  = orth_S1((O O~ + (1-O)(1-O~)) W) = orth_S1(W - O W - O~ W + 2 O O~ W)
       T  = A^+ S1 C,  D = T f T^+,  H_IAO = A^+ H A

   Occupied states lie in span(A), so the occupied spilling is zero and
   ``H -> H + dS`` maps ``H_IAO -> H_IAO + d*1``: bond values do not depend on
   the energy zero (the legacy NAO-block kernel does).
4. Bond-resolved (translation ``T``, phase sign from S(R))::

       X_AB(T) = sum_k w_k exp(-i s 2pi k.T) X(k)[A, B]
       ICOHP_AB(T) = g * sum_spin Re sum_{mu in A, nu in B} H_mn(T) conj(D_mn(T))

   ``g = 2/nspin``; this is the LOBSTER single-ordering value (the
   "both orderings" value is twice it).  ``-ICOHP > 0`` means bonding.
"""

from __future__ import annotations

import itertools
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from abacus_forge.cohp_iao_reader import (
    RY_TO_EV,
    AbacusLcaoRun,
    read_csr_triplets,
    read_input_params,
    read_orb_counts,
    read_stru,
    read_upf_header,
    resolve_input_file,
    unfolding_signs,
)
from abacus_forge.cohp_iao_shells import ShellSpec, element_symbol, shell_spec

METHOD_NAME = "IAO-COHP"
ICOHP_CONVENTION = "lobster-single-ordering"
OCCUPIED_THRESHOLD = 0.5
CURVE_DE_EV = 0.01
CURVE_SIGMA_EV = 0.1
CURVE_EMAX_EV = 10.0
SEMICORE_GAP_MIN_EV = 1.0
FROZEN_OCC_MIN = 0.99
FROZEN_CHARACTER_MIN = 0.8
PHASE_RESIDUAL_MAX = 1e-5
ECHO_EIGEN_MIN = 1e-8
IMAGE_WINDOW_ANG = 1.0
MAX_LISTED_IMAGES = 24

_M_LABELS = {1: ("z", "x", "y"), 2: ("z2", "xz", "yz", "x2-y2", "xy")}
_L_LETTERS = "spdf"


def _orth(x: np.ndarray, s: np.ndarray) -> tuple[np.ndarray, float]:
    """Symmetric S-orthonormalisation of the columns of ``x``."""
    m = x.conj().T @ (s @ x)
    w, v = np.linalg.eigh(0.5 * (m + m.conj().T))
    if w.min() <= ECHO_EIGEN_MIN:
        raise RuntimeError(
            f"IAO 构造失败：投影后的轨道线性相关（最小本征值 {w.min():.2e}）；"
            "参考基无法表示占据空间，检查壳层规则与轨道文件"
        )
    return x @ ((v / np.sqrt(w)) @ v.conj().T), float(w.min())


def _truncation_eps(ndigits: int) -> float:
    return 0.5 * 10.0 ** (1 - ndigits)


@dataclass
class IAOModel:
    """IAO-basis quantities on the full (unfolded) k grid."""

    nspin: int
    g: float
    kfrac: np.ndarray
    kweight: np.ndarray
    phase_sign: int
    efermi_ev: float
    iao_atom: np.ndarray
    iao_l: np.ndarray
    iao_m: np.ndarray
    h_iao: list
    t_coef: list
    eps: list
    focc: list
    n_frozen: int
    specs: dict
    run: AbacusLcaoRun
    diagnostics: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    @property
    def nk(self) -> int:
        return len(self.kfrac)

    def _phases(self, t) -> np.ndarray:
        return np.exp(self.phase_sign * 2j * np.pi * (self.kfrac @ np.asarray(t, float)))

    def block(self, mats: list, ia: np.ndarray, ib: np.ndarray, t) -> np.ndarray:
        """``X_AB(T) = sum_k w exp(-i s 2pi k.T) X(k)[ia, ib]``."""
        weights = self.kweight * np.conj(self._phases(t))
        out = np.zeros((ia.size, ib.size), complex)
        for ik in range(self.nk):
            out += weights[ik] * mats[ik][np.ix_(ia, ib)]
        return out

    def density_block(self, s: int, ia: np.ndarray, ib: np.ndarray, t) -> np.ndarray:
        weights = self.kweight * np.conj(self._phases(t))
        out = np.zeros((ia.size, ib.size), complex)
        for ik in range(self.nk):
            tm, f = self.t_coef[s][ik], self.focc[s][ik]
            out += weights[ik] * ((tm[ia] * f) @ tm[ib].conj().T)
        return out

    def orbitals(self, atom: int, selector: str = "all") -> np.ndarray:
        """IAO indices of ``atom`` (0-based) matching an orbital selector."""
        own = np.where(self.iao_atom == atom)[0]
        spec = self.specs[self.run.stru.atom_species[atom]]
        parts = parse_orbital_selector(selector, spec, atom + 1)
        if parts is None:
            return own
        chosen: set[int] = set()
        for l, m in parts:
            hits = own[self.iao_l[own] == l]
            if m is not None:
                hits = hits[self.iao_m[hits] == m]
            chosen.update(int(x) for x in hits)
        return np.array(sorted(chosen), int)


    def icohp_per_spin(self, ia: np.ndarray, ib: np.ndarray, t) -> list[float]:
        """ICOHP_AB(T) per spin (eV, LOBSTER single ordering, negative = bonding)."""
        return [
            self.g * float(np.real(np.sum(self.block(self.h_iao[s], ia, ib, t)
                                          * np.conj(self.density_block(s, ia, ib, t)))))
            for s in range(self.nspin)
        ]

    def icohp_all_images(self, ia: np.ndarray, ib: np.ndarray) -> float:
        """Sum over every translation inside the Born-von Karman cell (k-block value)."""
        total = 0.0
        for s in range(self.nspin):
            for ik in range(self.nk):
                tm, f = self.t_coef[s][ik], self.focc[s][ik]
                d = (tm[ia] * f) @ tm[ib].conj().T
                total += self.g * self.kweight[ik] * float(np.real(np.sum(self.h_iao[s][ik][np.ix_(ia, ib)] * np.conj(d))))
        return total

    def state_weights(self, s: int, ik: int, ia: np.ndarray, ib: np.ndarray, h_ab: np.ndarray, t) -> np.ndarray:
        """Per-band COHP weight x_n with ICOHP = g sum_k w sum_n f_n x_n."""
        tm = self.t_coef[s][ik]
        phase = np.exp(self.phase_sign * 2j * np.pi * float(np.dot(self.kfrac[ik], t)))
        return np.real(np.einsum("mn,vn,mv->n", tm[ia].conj(), tm[ib] * phase, h_ab))

    def curve(self, ia: np.ndarray, ib: np.ndarray, t, energy: np.ndarray, sigma: float) -> tuple[np.ndarray, float]:
        """Gaussian-broadened COHP(E) per spin on ``energy`` (E - E_F) and the
        discrete occupied-state sum of the same weights (must equal ICOHP)."""
        de = float(energy[1] - energy[0])
        y = np.zeros((self.nspin, energy.size))
        discrete = 0.0
        for s in range(self.nspin):
            h_ab = self.block(self.h_iao[s], ia, ib, t)
            hist = np.zeros(energy.size)
            for ik in range(self.nk):
                x = self.g * self.kweight[ik] * self.state_weights(s, ik, ia, ib, h_ab, t)
                discrete += float(np.sum(self.focc[s][ik] * x))
                pos = (self.eps[s][ik] - energy[0]) / de
                keep = (pos >= 0) & (pos < energy.size - 1)
                lo = np.floor(pos[keep]).astype(int)
                frac = pos[keep] - lo
                np.add.at(hist, lo, x[keep] * (1 - frac))
                np.add.at(hist, lo + 1, x[keep] * frac)
            half = int(math.ceil(5 * sigma / de))
            grid = np.arange(-half, half + 1) * de
            kernel = np.exp(-0.5 * (grid / sigma) ** 2) / (sigma * math.sqrt(2 * math.pi))
            y[s] = np.convolve(hist, kernel, mode="same")
        return y, discrete


def parse_orbital_selector(selector: str, spec: ShellSpec, atom_1based: int) -> list[tuple[int, int | None]] | None:
    """``[(l, m or None), ...]`` for an orbital selector on one atom's valence
    IAO set; ``None`` means all orbitals.  The m labels follow the global
    Cartesian axes (ABACUS order); a leading principal number must name the
    valence shell selected by the element's period/group rule."""
    tokens = [t.strip().lower() for t in str(selector or "all").split(",") if t.strip()]
    if not tokens or "all" in tokens:
        return None
    valence = spec.valence_zetas()
    parts = []
    for token in tokens:
        match = re.fullmatch(r"(\d*)([spdf])([a-z0-9\-]*)", token)
        if not match:
            raise ValueError(f"无法解析轨道选择器 {token!r}（可用 all/s/p/d/f、px/dz2 等 m 分量或逗号组合）")
        l = _L_LETTERS.index(match.group(2))
        suffix = match.group(3)
        if l not in valence:
            raise ValueError(
                f"原子 {atom_1based}（{spec.element}）在 IAO 价层参考基中没有 {token} 轨道；"
                f"该原子的价层为 {spec.describe()['valence_shells']}，半芯与外层空轨道不在此基组中"
            )
        principal = match.group(1)
        expected = spec.valence_principal_number(l)
        if principal and int(principal) != expected:
            raise ValueError(
                f"原子 {atom_1based}（{spec.element}）的 {token} 不在 IAO 价层参考基中；"
                f"该角动量的价层是 {expected}{_L_LETTERS[l]}"
            )
        m = None
        if suffix:
            labels = _M_LABELS.get(l, ())
            if suffix not in labels:
                raise ValueError(f"轨道选择器 {token!r} 的 m 分量未知（{_L_LETTERS[l]}: {', '.join(labels)}）")
            m = labels.index(suffix)
        parts.append((l, m))
    return parts


def _species_specs(species: list[str], zval: dict, upf_element: dict, counts: dict) -> dict[str, ShellSpec]:
    specs = {}
    for sp in species:
        spec = shell_spec(element_symbol(sp, upf_element.get(sp)), zval[sp])
        for l, n in spec.occupied.items():
            if counts[sp][l] < n:
                raise ValueError(
                    f"{sp} 的轨道文件只有 {counts[sp][l]} 个 {_L_LETTERS[l]} zeta，IAO 参考需要至少 {n} 个"
                    f"（占据壳层 {spec.describe()}）"
                )
        specs[sp] = spec
    return specs


def check_iao_bond_request(
    inputs_dir: Path, atom_i: int, atom_j: int, orbs_i: str = "all", orbs_j: str = "all"
) -> dict[str, ShellSpec]:
    """Everything the kernel would reject about the request itself (species,
    atom indices, orbital selectors), checked from the inputs before any SCF."""
    specs = check_iao_species(inputs_dir)
    stru = read_stru(Path(inputs_dir) / "STRU")
    for label, atom, selector in (("atom_i", atom_i, orbs_i), ("atom_j", atom_j, orbs_j)):
        if not 1 <= atom <= stru.natom:
            raise ValueError(f"{label}={atom} 超出结构原子数 1..{stru.natom}")
        parse_orbital_selector(selector, specs[stru.atom_species[atom - 1]], atom)
    return specs


def check_iao_species(inputs_dir: Path) -> dict[str, ShellSpec]:
    """Resolve the shell rules and orbital-zeta coverage from INPUT/STRU/UPF/ORB
    alone, so unsupported pseudopotentials fail before any SCF is started."""
    inputs_dir = Path(inputs_dir)
    params = read_input_params(inputs_dir / "INPUT")
    stru = read_stru(inputs_dir / "STRU")
    zval, element, counts = {}, {}, {}
    for sp in stru.species:
        pp = resolve_input_file(
            inputs_dir,
            params.get("pseudo_dir"),
            stru.pp_files[sp] or "",
            allowed_root=inputs_dir,
        )
        orb = resolve_input_file(
            inputs_dir,
            params.get("orbital_dir"),
            stru.orb_files[sp],
            allowed_root=inputs_dir,
        )
        if pp is None or orb is None:
            raise FileNotFoundError(f"找不到 {sp} 的赝势或轨道文件（{stru.pp_files[sp]}, {stru.orb_files[sp]}）")
        zval[sp], element[sp] = read_upf_header(pp)
        counts[sp], _ = read_orb_counts(orb)
    return _species_specs(stru.species, zval, element, counts)


def _select(run: AbacusLcaoRun, specs: dict[str, ShellSpec], semicore: bool) -> np.ndarray:
    lay = run.layout
    cols = []
    for mu in range(lay.nbasis):
        spec = specs[run.stru.atom_species[lay.atom[mu]]]
        zetas = (spec.semicore_zetas() if semicore else spec.valence_zetas()).get(int(lay.l[mu]), [])
        if int(lay.zeta[mu]) in zetas:
            cols.append(mu)
    return np.array(cols, int)


class _PhaseProbe:
    """Accumulates max |S(k) - sum_R exp(+/- i2pi k.R) S(R)| on the S(R) pattern."""

    def __init__(self, path: Path, nbasis: int):
        dim, blocks = read_csr_triplets(path)
        if dim != nbasis:
            raise ValueError(f"{path.name}: 维度 {dim} 与 nbasis {nbasis} 不符")
        rows, cols, vals, rvec = [], [], [], []
        for r, (ro, co, va) in blocks.items():
            rows.append(ro)
            cols.append(co)
            vals.append(va)
            rvec.append(np.tile(np.array(r, float), (ro.size, 1)))
        lin = np.concatenate(rows) * nbasis + np.concatenate(cols)
        self.unique, self.inverse = np.unique(lin, return_inverse=True)
        self.vals = np.concatenate(vals).astype(complex)
        self.rvec = np.concatenate(rvec)
        self.err = {+1: 0.0, -1: 0.0}

    def update(self, kfrac: np.ndarray, s_k: np.ndarray) -> None:
        target = s_k.ravel()[self.unique]
        theta = 2 * np.pi * (self.rvec @ kfrac)
        for sign in (+1, -1):
            weighted = self.vals * np.exp(sign * 1j * theta)
            folded = (np.bincount(self.inverse, weighted.real, self.unique.size)
                      + 1j * np.bincount(self.inverse, weighted.imag, self.unique.size))
            self.err[sign] = max(self.err[sign], float(np.abs(folded - target).max()))


def build_iao_model(run: AbacusLcaoRun) -> IAOModel:
    """Stream the run, build the frozen-semicore IAO per (spin, k) and gate
    the result on the reader identities and the physical guards."""
    specs = _species_specs(run.stru.species, run.zval, run.upf_element, run.layout.counts)
    val = _select(run, specs, semicore=False)
    semi = _select(run, specs, semicore=True)
    n_frozen = sum(specs[sp].n_semicore_orbitals for sp in run.stru.atom_species)
    nmin, nb = val.size, run.nbasis
    lay = run.layout
    w_sel = np.zeros((nb, nmin))
    w_sel[val, np.arange(nmin)] = 1.0
    sr_path = run.overlap_r_path()
    if sr_path is None:
        raise FileNotFoundError(
            f"{run.out_dir} 缺少 data-SR-sparse_SPIN0.csr：IAO-COHP 需要 out_mat_hs2 1 输出的 S(R) 判定 Bloch 相位符号"
        )
    probe = _PhaseProbe(sr_path, nb)
    eps_t = _truncation_eps(run.ndigits)

    h_red = [[None] * run.nk for _ in range(run.nspin)]
    t_red = [[None] * run.nk for _ in range(run.nspin)]
    e_red = [[None] * run.nk for _ in range(run.nspin)]
    f_red = [[None] * run.nk for _ in range(run.nspin)]
    diag = {
        "orthonormality_ratio": 0.0, "eigen_ratio": 0.0, "echo_eigen_min": math.inf,
        "occupied_spilling_max": 0.0, "frozen_character_min": None, "frozen_occupation_min": None,
        "semicore_top_ev": -math.inf, "valence_bottom_ev": math.inf,
    }
    n_elec = 0.0
    tr_dh = eband = 0.0
    spill_num = spill_den = 0.0
    frac_max = 0.0
    occ_scale = None
    energy_factor = None

    for kd in run.iter_kpoints():
        s1 = kd.S
        probe.update(run.kfrac[kd.ik], s1)
        s1w = s1[:, val]
        s2 = s1[np.ix_(val, val)]
        s3_inv = np.linalg.inv(s1[np.ix_(semi, semi)]) if semi.size else None
        w_k = run.kweight[kd.ik]
        for s in range(run.nspin):
            c, h, wg = kd.C[s], kd.H[s], kd.wg[s]
            # --- occupations f = wg / (w_k * scale); scale measured on the lowest band once
            if occ_scale is None:
                occ_scale = float(wg[0] / w_k) if w_k > 0 else run.g
                if abs(occ_scale - run.g) <= 0.05 * run.g:
                    occ_scale = run.g
            f = wg / (w_k * occ_scale)
            if f.max() > 1.0 + 1e-3:
                raise RuntimeError(f"占据数还原异常（k={kd.ik + 1}, f_max={f.max():.4f}）：kpoints 权重与 WFC 占据不一致")
            f = np.clip(f, 0.0, 1.0)
            n_elec += run.g * w_k * float(f.sum())
            frac_max = max(frac_max, float(np.max(f * (1.0 - f))))
            # --- reader identities: C^+SC = I and HC = SCE (text-truncation bounds)
            ortho = np.abs(c.conj().T @ s1 @ c - np.eye(c.shape[1]))
            ca = np.abs(c)
            bound_o = 3 * eps_t * (ca.T @ np.abs(s1) @ ca) + 1e-8
            diag["orthonormality_ratio"] = max(diag["orthonormality_ratio"], float((ortho / bound_o).max()))
            if energy_factor is None:
                res = {}
                for factor in (RY_TO_EV, 1.0):
                    res[factor] = float(np.abs(h @ c - s1 @ c * (kd.energy[s] * factor)).max())
                energy_factor = min(res, key=res.get)
            e_abs = kd.energy[s] * energy_factor
            resid = np.abs(h @ c - s1 @ c * e_abs)
            bound_h = 3 * eps_t * (np.abs(h) @ ca + (np.abs(s1) @ ca) * np.abs(e_abs)) + 1e-6
            diag["eigen_ratio"] = max(diag["eigen_ratio"], float((resid / bound_h).max()))
            # --- frozen semicore bands
            if n_frozen:
                if n_frozen >= c.shape[1]:
                    raise RuntimeError(f"冻结半芯能带数 {n_frozen} 不小于总能带数 {c.shape[1]}")
                fz = f[:n_frozen]
                occ_min = float(fz.min())
                diag["frozen_occupation_min"] = occ_min if diag["frozen_occupation_min"] is None else min(diag["frozen_occupation_min"], occ_min)
                x = s1[:, semi].conj().T @ c[:, :n_frozen]
                char = np.real(np.einsum("in,ij,jn->n", x.conj(), s3_inv, x))
                cmin = float(char.min())
                diag["frozen_character_min"] = cmin if diag["frozen_character_min"] is None else min(diag["frozen_character_min"], cmin)
                diag["semicore_top_ev"] = max(diag["semicore_top_ev"], float(e_abs[n_frozen - 1]))
                diag["valence_bottom_ev"] = min(diag["valence_bottom_ev"], float(e_abs[n_frozen]))
            f_val = f[n_frozen:]
            c_val = c[:, n_frozen:]
            occ = f_val > OCCUPIED_THRESHOLD
            if int(occ.sum()) > nmin:
                raise RuntimeError(
                    f"占据价带数 {int(occ.sum())} 超过 IAO 参考基大小 {nmin}（k={kd.ik + 1}）：壳层规则不适用于该体系"
                )
            # --- IAO (Knizia) in the NAO span
            c_occ = c_val[:, occ]
            y = np.zeros((nb, c_occ.shape[1]), complex)
            y[val] = np.linalg.solve(s2, s1w.conj().T @ c_occ)
            if c_occ.shape[1]:
                c_tilde, echo = _orth(y, s1)
                diag["echo_eigen_min"] = min(diag["echo_eigen_min"], echo)
                ot_w = c_tilde @ (c_tilde.conj().T @ s1w)
                o_w = c_occ @ (c_occ.conj().T @ s1w)
                oot_w = c_occ @ (c_occ.conj().T @ (s1 @ ot_w))
                a_raw = w_sel - o_w - ot_w + 2 * oot_w
            else:
                a_raw = w_sel.astype(complex)
            a, _ = _orth(a_raw, s1)
            tm = a.conj().T @ (s1 @ c_val)
            hi = a.conj().T @ h @ a
            hi = 0.5 * (hi + hi.conj().T)
            norms = np.sum(np.abs(tm) ** 2, axis=0)
            if occ.any():
                diag["occupied_spilling_max"] = max(diag["occupied_spilling_max"], float(np.abs(1 - norms[occ]).max()))
            spill_num += w_k * float(np.sum(f_val * (1 - norms)))
            spill_den += w_k * float(np.sum(f_val))
            tr_dh += run.g * w_k * float(np.real(np.sum(((tm * f_val) @ tm.conj().T) * hi.T)))
            eband += run.g * w_k * float(np.sum(f_val * e_abs[n_frozen:]))
            h_red[s][kd.ik] = hi
            t_red[s][kd.ik] = tm
            e_red[s][kd.ik] = e_abs[n_frozen:] - run.ef_spin[s]
            f_red[s][kd.ik] = f_val

    # --- gates on the reader identities
    notes: list[str] = []
    if abs(float(run.kweight.sum()) - 1.0) > 1e-8:
        raise RuntimeError(f"k 权重和 {run.kweight.sum():.8f} != 1")
    ne_ref = run.nelec_reference()
    if abs(n_elec - ne_ref) > 1e-3 * max(1.0, ne_ref):
        raise RuntimeError(f"电子数自检失败：sum g w f = {n_elec:.6f}，参考 {ne_ref:g}")
    if diag["orthonormality_ratio"] > 1.0:
        raise RuntimeError(f"C^+SC = I 自检失败（超出 {run.ndigits} 位文本截断上界 ×{diag['orthonormality_ratio']:.1f}）")
    if diag["eigen_ratio"] > 1.0:
        raise RuntimeError(f"HC = SCE 自检失败（超出文本截断上界 ×{diag['eigen_ratio']:.1f}）；检查 H/S/WFC 是否同一次 SCF")
    err_p, err_m = probe.err[+1], probe.err[-1]
    phase_sign = +1 if err_p <= err_m else -1
    best, other = min(err_p, err_m), max(err_p, err_m)
    if best > PHASE_RESIDUAL_MAX:
        raise RuntimeError(f"S(R) 与 S(k) 不一致（最小残差 {best:.2e}）：无法判定 Bloch 相位符号")
    if other <= PHASE_RESIDUAL_MAX:
        notes.append("所有 k 点的相位因子为实数，相位符号不影响结果")
    # --- physical guards
    if n_frozen:
        gap = diag["valence_bottom_ev"] - diag["semicore_top_ev"]
        diag["semicore_gap_ev"] = gap
        if gap < SEMICORE_GAP_MIN_EV:
            raise RuntimeError(f"半芯与价带能隙 {gap:.2f} eV < {SEMICORE_GAP_MIN_EV} eV：冻结半芯不成立")
        if diag["frozen_occupation_min"] < FROZEN_OCC_MIN:
            raise RuntimeError(f"冻结能带最小占据 {diag['frozen_occupation_min']:.3f} < {FROZEN_OCC_MIN}")
        if diag["frozen_character_min"] < FROZEN_CHARACTER_MIN:
            raise RuntimeError(
                f"冻结能带的半芯成分最低 {diag['frozen_character_min']:.2f} < {FROZEN_CHARACTER_MIN}：半芯与价层强烈杂化，冻结半芯不成立"
            )
    sum_rule_dev = tr_dh - eband
    diag["band_energy_sum_rule_dev_ev"] = sum_rule_dev
    if frac_max <= 1e-3 and abs(sum_rule_dev) > 1e-5 * max(1.0, abs(eband)):
        raise RuntimeError(f"带能求和律失败（偏差 {sum_rule_dev:.2e} eV，整数占据下应精确成立）")
    if frac_max > 1e-3:
        notes.append(f"存在分数占据（max f(1-f)={frac_max:.2e}），带能求和律只作参考")

    # --- time-reversal unfolding to the full grid
    kfrac, kweight = run.kfrac, run.kweight
    if run.full_k is not None and len(run.full_k) > run.nk:
        signs = unfolding_signs(run.kfrac, run.full_k, run.full_map)
        if (signs == 0).any():
            raise RuntimeError("k 网格经点群约化（symmetry=1?）：需要 symmetry 0 的输出")
        new = [[[None] * len(signs) for _ in range(run.nspin)] for _ in range(4)]
        for i, (j, sg) in enumerate(zip(run.full_map, signs)):
            for s in range(run.nspin):
                for dest, src in zip(new, (h_red, t_red, e_red, f_red)):
                    item = src[s][j]
                    dest[s][i] = item.conj() if (sg < 0 and np.iscomplexobj(item)) else item
        h_red, t_red, e_red, f_red = new
        kfrac = np.asarray(run.full_k, float)
        kweight = np.full(len(signs), 1.0 / len(signs))
        notes.append(f"时间反演展开：{run.nk} -> {len(signs)} 个 k 点")

    diag.update(
        phase_residual=best, phase_residual_other=other, n_electrons=n_elec,
        f_weighted_spilling=spill_num / spill_den if spill_den else 0.0,
        energy_unit="Ry" if energy_factor == RY_TO_EV else "eV", occupation_scale=occ_scale,
        text_ndigits=run.ndigits, max_fractional_occupation=frac_max,
    )
    if diag["frozen_character_min"] is None:
        for key in ("frozen_character_min", "frozen_occupation_min", "semicore_top_ev", "valence_bottom_ev"):
            diag[key] = None
    if run.stru.wrapped_atoms:
        notes.append(f"原子 {[a + 1 for a in run.stru.wrapped_atoms]} 的分数坐标已折回 [0,1)")
    return IAOModel(
        nspin=run.nspin, g=run.g, kfrac=kfrac, kweight=kweight, phase_sign=phase_sign,
        efermi_ev=run.efermi_ev, iao_atom=lay.atom[val], iao_l=lay.l[val], iao_m=lay.m[val],
        h_iao=h_red, t_coef=t_red, eps=e_red, focc=f_red, n_frozen=n_frozen, specs=specs,
        run=run, diagnostics=diag, notes=notes,
    )


def _bvk_dims(kfrac: np.ndarray) -> tuple[list[int], bool]:
    dims = [int(np.unique(np.round(np.mod(kfrac[:, i], 1.0), 6) % 1.0).size) for i in range(3)]
    return dims, int(np.prod(dims)) == len(kfrac)


def _aliased_distance(model: IAOModel, a: int, b: int, t: tuple[int, int, int], dims: list[int]) -> float:
    """Distance of the nearest translation that the k grid cannot tell from ``t``."""
    best = math.inf
    for shift in itertools.product((-1, 0, 1), repeat=3):
        if shift == (0, 0, 0):
            continue
        tt = tuple(t[i] + shift[i] * dims[i] for i in range(3))
        best = min(best, model.run.stru.distance(a, b, tt))
    return best


def analyse_bond(model: IAOModel, atom_i: int, atom_j: int, orbs_i: str = "all", orbs_j: str = "all") -> dict:
    """Nearest-image bond between 1-based atoms ``atom_i``/``atom_j``, all images
    within ``IMAGE_WINDOW_ANG`` of it, and the curve of the nearest one."""
    stru = model.run.stru
    for label, atom in (("atom_i", atom_i), ("atom_j", atom_j)):
        if not 1 <= atom <= stru.natom:
            raise ValueError(f"{label}={atom} 超出结构原子数 1..{stru.natom}")
    a, b = atom_i - 1, atom_j - 1
    ia, ib = model.orbitals(a, orbs_i), model.orbitals(b, orbs_j)
    rmax = 6.0
    images = stru.images(a, b, rmax)
    while not images and rmax < 60.0:
        rmax *= 2
        images = stru.images(a, b, rmax)
    if not images:
        raise ValueError(f"原子 {atom_i} 与 {atom_j} 在 {rmax:.0f} Å 内没有周期像")
    d0 = images[0][1]
    window = [img for img in images if img[1] <= d0 + IMAGE_WINDOW_ANG][:MAX_LISTED_IMAGES]
    dims, regular = _bvk_dims(model.kfrac)
    listed = []
    for t, d in window:
        per_spin = model.icohp_per_spin(ia, ib, t)
        listed.append({
            "translation": list(t), "distance_ang": d,
            "icohp": sum(per_spin), "minus_icohp": -sum(per_spin),
            "icohp_per_spin": per_spin,
        })
    primary_t, primary_d = window[0]
    equivalent = [img for img in listed if abs(img["distance_ang"] - primary_d) < 1e-3]
    alias_d = _aliased_distance(model, a, b, primary_t, dims)
    rc = model.run.layout.rcut_ang
    rc_sum = sum(filter(None, (rc.get(stru.atom_species[a]), rc.get(stru.atom_species[b]))))
    # cautions: conditions that qualify the reported number (surfaced to the agent as warnings)
    cautions = []
    if alias_d < primary_d + 1.0:
        raise ValueError(
            f"k 网格 {dims} 无法区分平移 {list(primary_t)}（{primary_d:.3f} Å）与 {alias_d:.3f} Å 处的周期像：请加密 k 点"
        )
    if rc_sum and alias_d < rc_sum:
        cautions.append({
            "code": "image_aliasing",
            "message": f"k 网格 {dims} 的混叠像距离 {alias_d:.2f} Å 小于轨道截断半径和 {rc_sum:.2f} Å，"
                       "数值含该像的小量贡献；分子/表面体系可增大真空层，晶体可加密 k 点",
        })
    if not regular:
        cautions.append({
            "code": "irregular_kgrid",
            "message": f"k 点集不是完整的规则网格（{len(model.kfrac)} 点，维度估计 {dims}），按键平移分辨只作近似",
        })
    all_images = None if a == b else model.icohp_all_images(ia, ib)
    return {
        "atom_i": atom_i, "atom_j": atom_j,
        "element_i": model.specs[stru.atom_species[a]].element,
        "element_j": model.specs[stru.atom_species[b]].element,
        "orbitals_i": orbs_i, "orbitals_j": orbs_j,
        "n_orbitals_i": int(ia.size), "n_orbitals_j": int(ib.size),
        "translation": list(primary_t), "distance_ang": primary_d,
        "primary": listed[0], "equivalent_images": len(equivalent),
        "equivalent_spread_ev": (max(e["minus_icohp"] for e in equivalent) - min(e["minus_icohp"] for e in equivalent)),
        "images": listed,
        "all_images_icohp": all_images,
        "bvk_dims": dims, "aliased_image_distance_ang": alias_d,
        "cautions": cautions, "_ia": ia, "_ib": ib,
    }


def _curve_grid(model: IAOModel) -> np.ndarray:
    lowest = min(float(e.min()) for spin in model.eps for e in spin if e.size)
    highest = max(float(e.max()) for spin in model.eps for e in spin if e.size)
    emin = math.floor(lowest - 5 * CURVE_SIGMA_EV - 1.0)
    emax = min(math.ceil(highest + 5 * CURVE_SIGMA_EV), CURVE_EMAX_EV)
    n = int(round((emax - emin) / CURVE_DE_EV)) + 1
    return np.linspace(emin, emax, n)


def _write_plot(path: Path, energy: np.ndarray, curves: np.ndarray, title: str, nspin: int) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.plot(energy, -curves.sum(axis=0), color="C0", lw=1.2, label="total")
    if nspin == 2:
        ax.plot(energy, -curves[0], color="C3", lw=0.8, alpha=0.8, label="spin up")
        ax.plot(energy, -curves[1], color="C2", lw=0.8, alpha=0.8, label="spin down")
        ax.legend(fontsize=8)
    ax.axvline(0.0, color="grey", ls=":", lw=0.8)
    ax.axhline(0.0, color="grey", lw=0.5)
    ax.set_xlabel("E - E_F (eV)")
    ax.set_ylabel("-COHP (bonding > 0)")
    ax.set_title(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def run_iao_cohp(
    *,
    scf_dir: Path,
    atom_i_index: int,
    atom_j_index: int,
    atom_i_orbs: str,
    atom_j_orbs: str,
    work_dir: Path,
    output_prefix: str,
    out_dir: Path | None = None,
) -> dict:
    """Run the IAO-COHP kernel on a completed SCF and write the delivery files
    ``{prefix}.meta.json``, ``{prefix}_EminusEf.dat``, ``{prefix}.png`` and
    ``{prefix}_bond_images.json`` into ``work_dir``; returns the meta dict."""
    run = AbacusLcaoRun(Path(scf_dir), out_dir)
    model = build_iao_model(run)
    bond = analyse_bond(model, atom_i_index, atom_j_index, atom_i_orbs, atom_j_orbs)
    ia, ib = bond.pop("_ia"), bond.pop("_ib")
    energy = _curve_grid(model)
    curves, discrete = model.curve(ia, ib, bond["translation"], energy, CURVE_SIGMA_EV)
    icohp = bond["primary"]["icohp"]
    if abs(discrete - icohp) > 1e-8 * max(1.0, abs(icohp)):
        raise RuntimeError(f"COHP 曲线权重与 ICOHP 不一致（{discrete:.3e} vs {icohp:.3e}）")

    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    prefix = work_dir / output_prefix
    curve_path = prefix.with_name(f"{output_prefix}_EminusEf.dat")
    meta_path = prefix.with_name(f"{output_prefix}.meta.json")
    png_path = prefix.with_name(f"{output_prefix}.png")
    images_path = prefix.with_name(f"{output_prefix}_bond_images.json")
    columns = [energy, curves.sum(axis=0)] + ([curves[0], curves[1]] if model.nspin == 2 else [])
    header = "Energy-E_Fermi(eV) COHP" + (" COHP_up COHP_down" if model.nspin == 2 else "")
    header += (f" shifted_by_efermi=true method={METHOD_NAME} convention={ICOHP_CONVENTION}"
               f" translation={bond['translation']} sigma_ev={CURVE_SIGMA_EV}")
    np.savetxt(curve_path, np.column_stack(columns), header=header)
    pair = f"{bond['element_i']}{atom_i_index}-{bond['element_j']}{atom_j_index}"
    _write_plot(png_path, energy, curves,
                f"{METHOD_NAME} {pair} T={bond['translation']} d={bond['distance_ang']:.3f} A  "
                f"-ICOHP={-icohp:.3f} eV", model.nspin)
    images_doc = {
        "method": METHOD_NAME, "convention": ICOHP_CONVENTION,
        "atom_pair": [atom_i_index, atom_j_index], "images": bond["images"],
        "all_images_icohp": bond["all_images_icohp"],
        "all_images_minus_icohp": None if bond["all_images_icohp"] is None else -bond["all_images_icohp"],
        "bvk_dims": bond["bvk_dims"],
    }
    images_path.write_text(json.dumps(images_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    meta = {
        "method": METHOD_NAME,
        "efermi_ev": float(model.efermi_ev),
        "shift_toefermi": True,
        "nspin": model.nspin,
        "icohp": {
            "icohp": icohp,
            "minus_icohp": -icohp,
            "integration": "occupied_discrete_state_sum",
            "convention": ICOHP_CONVENTION,
            "icohp_per_spin": bond["primary"]["icohp_per_spin"],
            "icohp_both_orderings": 2 * icohp,
        },
        "bond": {k: bond[k] for k in (
            "atom_i", "atom_j", "element_i", "element_j", "orbitals_i", "orbitals_j",
            "n_orbitals_i", "n_orbitals_j", "translation", "distance_ang",
            "equivalent_images", "equivalent_spread_ev", "bvk_dims", "aliased_image_distance_ang")},
        "basis": {
            "reference": "first zeta of each occupied valence shell (frozen semicore)",
            "occupied_threshold": OCCUPIED_THRESHOLD,
            "n_iao": int(model.iao_atom.size),
            "n_frozen_bands": model.n_frozen,
            "species": {sp: spec.describe() for sp, spec in model.specs.items()},
        },
        "phase_sign": model.phase_sign,
        "diagnostics": {k: (None if isinstance(v, float) and not math.isfinite(v) else v)
                        for k, v in model.diagnostics.items()},
        "curve": {"de_ev": CURVE_DE_EV, "sigma_ev": CURVE_SIGMA_EV, "unit": "dimensionless",
                  "columns": header.split(" shifted_by_efermi")[0].split()},
        "nk_full": int(model.nk),
        "notes": model.notes,
        "cautions": bond["cautions"],
        "files": {"shifted": curve_path.name, "plot": png_path.name, "bond_images": images_path.name},
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=float) + "\n", encoding="utf-8")
    return {**meta, "paths": {"meta": str(meta_path), "curve": str(curve_path),
                              "png": str(png_path), "bond_images": str(images_path)}}
