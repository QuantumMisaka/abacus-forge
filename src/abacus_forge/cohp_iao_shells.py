"""Valence / semicore shell rules for the frozen-semicore IAO-COHP reference.

The IAO reference basis takes, per atom, the first zeta of every occupied
valence shell of the pseudo-atom; semicore shells carried by the
pseudopotential are frozen (their bands leave the occupied set and the density
matrix).  Which shells are occupied and which of them are semicore follows from
the element's group/period and the UPF ``z_valence``:

* groups 1-2: ``z = group`` -> ns; ``z = group + 2`` (period 2) -> (n-1)s
  semicore; ``z = group + 8`` -> (n-1)s(n-1)p semicore; ``z = group + 6`` ->
  (n-1)p semicore.
* groups 3-12: ``z = group`` -> ns + (n-1)d; ``z = group + 8`` -> ns(n-1)s
  (n-1)p semicore (s, p) + (n-1)d valence.
* groups 13-18: ``z = group - 10`` -> ns np; ``z = group`` (period >= 4) ->
  (n-1)d10 semicore.

Any other (element, z_valence) combination (f-in-valence pseudopotentials,
lanthanides, uncommon semicore splits) raises ``ValueError`` so the kernel
never guesses a reference.  Shell counts are per angular momentum ``l`` and
index the zetas of the numerical orbital file in ABACUS order (the lowest
zetas of an ``l`` channel are taken as the lowest shells).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# (period, group) for the elements the rule set covers (lanthanides excluded).
_PERIODIC: dict[str, tuple[int, int]] = {}
for _period, _row in (
    (1, "H:1 He:18"),
    (2, "Li:1 Be:2 B:13 C:14 N:15 O:16 F:17 Ne:18"),
    (3, "Na:1 Mg:2 Al:13 Si:14 P:15 S:16 Cl:17 Ar:18"),
    (4, "K:1 Ca:2 Sc:3 Ti:4 V:5 Cr:6 Mn:7 Fe:8 Co:9 Ni:10 Cu:11 Zn:12 "
        "Ga:13 Ge:14 As:15 Se:16 Br:17 Kr:18"),
    (5, "Rb:1 Sr:2 Y:3 Zr:4 Nb:5 Mo:6 Tc:7 Ru:8 Rh:9 Pd:10 Ag:11 Cd:12 "
        "In:13 Sn:14 Sb:15 Te:16 I:17 Xe:18"),
    (6, "Cs:1 Ba:2 La:3 Hf:4 Ta:5 W:6 Re:7 Os:8 Ir:9 Pt:10 Au:11 Hg:12 "
        "Tl:13 Pb:14 Bi:15 Po:16 At:17 Rn:18"),
):
    for _item in _row.split():
        _symbol, _group = _item.split(":")
        _PERIODIC[_symbol] = (_period, int(_group))

_L_LETTERS = "spdf"


@dataclass(frozen=True)
class ShellSpec:
    """Occupied pseudo-atom shells and their semicore subset, per ``l``."""

    element: str
    zval: int
    occupied: dict[int, int]
    semicore: dict[int, int]

    def valence_zetas(self) -> dict[int, list[int]]:
        """Zeta indices (per ``l``) of the valence reference functions."""
        return {
            l: list(range(self.semicore.get(l, 0), n))
            for l, n in self.occupied.items()
            if n > self.semicore.get(l, 0)
        }

    def semicore_zetas(self) -> dict[int, list[int]]:
        """Zeta indices (per ``l``) of the frozen semicore functions."""
        return {l: list(range(n)) for l, n in self.semicore.items() if n}

    def valence_principal_number(self, l: int) -> int:
        """Principal number of the valence shell selected by this rule set."""
        period, _ = _PERIODIC[self.element]
        return period - 1 if l == 2 else period

    @property
    def n_semicore_orbitals(self) -> int:
        """Semicore orbitals per atom = frozen bands per (spin, k) per atom."""
        return sum(n * (2 * l + 1) for l, n in self.semicore.items())

    def describe(self) -> dict:
        """JSON-ready description (``l`` given as letters)."""
        return {
            "element": self.element,
            "z_valence": self.zval,
            "valence_shells": {
                _L_LETTERS[l]: len(z) for l, z in sorted(self.valence_zetas().items())
            },
            "semicore_shells": {
                _L_LETTERS[l]: n for l, n in sorted(self.semicore.items()) if n
            },
        }


def element_symbol(label: str, upf_element: str | None = None) -> str:
    """Element symbol of an ABACUS species label (``Ni1`` -> ``Ni``).

    The UPF ``element`` attribute wins when present; otherwise the leading
    letters of the label are used.
    """
    if upf_element and upf_element.strip():
        symbol = upf_element.strip().capitalize()
        if symbol in _PERIODIC:
            return symbol
        raise ValueError(f"UPF 明确元素 {upf_element!r} 不在 IAO-COHP 壳层规则支持范围内")
    match = re.match(r"\s*([A-Za-z]+)", label)
    symbol = match.group(1).capitalize() if match else None
    if symbol in _PERIODIC:
        return symbol
    raise ValueError(f"无法从物种标签 {label!r} 识别受支持的元素 {symbol!r}（IAO-COHP 壳层规则）")


def shell_spec(element: str, zval: float) -> ShellSpec:
    """Shell rule for one (element, z_valence); raises ``ValueError`` when the
    combination is outside the supported rule set."""
    if element not in _PERIODIC:
        raise ValueError(f"IAO-COHP 壳层规则未覆盖元素 {element}（镧系/锕系或超出第 6 周期）")
    z = int(round(float(zval)))
    if abs(float(zval) - z) > 1e-6:
        raise ValueError(f"{element} 的 z_valence={zval} 不是整数，无法确定价层/半芯壳层")
    period, group = _PERIODIC[element]
    occupied: dict[int, int] | None = None
    semicore: dict[int, int] = {}
    if element in ("H", "He"):
        if z == (1 if element == "H" else 2):
            occupied = {0: 1}
    elif group in (1, 2):
        if z == group:
            occupied = {0: 1}
        elif period == 2 and z == group + 2:
            occupied, semicore = {0: 2}, {0: 1}
        elif period >= 3 and z == group + 8:
            occupied, semicore = {0: 2, 1: 1}, {0: 1, 1: 1}
        elif period >= 3 and z == group + 6:
            occupied, semicore = {0: 1, 1: 1}, {1: 1}
    elif 3 <= group <= 12:
        if z == group:
            occupied = {0: 1, 2: 1}
        elif z == group + 8:
            occupied, semicore = {0: 2, 1: 1, 2: 1}, {0: 1, 1: 1}
    else:
        if z == group - 10:
            occupied = {0: 1, 1: 1}
        elif period >= 4 and z == group:
            occupied, semicore = {0: 1, 1: 1, 2: 1}, {2: 1}
    if occupied is None:
        raise ValueError(
            f"IAO-COHP 壳层规则不支持 {element}（z_valence={z}）：该赝势的价电子划分不在"
            "已验证的规则集内（主族名义价、+2/+6/+8 的 s/p 半芯、过渡金属 +8、13-18 族 +10 的 d10 半芯）"
        )
    return ShellSpec(element, z, occupied, semicore)
