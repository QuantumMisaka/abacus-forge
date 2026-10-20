# Forge polarization facts and BEC design

**Status:** Approved bounded implementation, 2026-10-21. User confirmed conditional Forge branch handling plus explicit offsets, requested atom/axis subsets and explicit incomplete results, then instructed continuation. The concrete contract below records implementation rulings within that authorization.

**Scope:** Reusable ABACUS polarization preparation, one-stage execution, native polarization fact collection, and finite-difference Born effective charge (BEC) postprocessing. This document supersedes the technical proposal in [the 2026-09-29 HTML draft](2026-09-29-forge-typed-bec-design.html); that file remains historical.

## Accepted direction

- Forge provides reusable, explicit displacement/preparation primitives. A primitive prepares an input for a requested displacement; it does not create or own a multi-run workflow.
- One execution operation runs one ABACUS stage in one caller-selected workspace. The caller chooses which stage to execute and in what order.
- Collection parses native ABACUS Berry-phase output into structured facts, including the reported direction, phases, printed polarization values, units, and Cartesian vector.
- A separate BEC postprocess operation consumes caller-provided polarization facts from the required displaced calculations and computes finite differences.
- Cross-run orchestration, retries, continuation, and scientific acceptance remain caller-owned. The numerical branch policy is conditional path unwrapping or explicit integer offsets, as defined below.

These boundaries reuse Forge's `prepare`, `execute`, `collect`, and `postprocess` responsibilities in [the current architecture](../../architecture.md). This draft does not define public function names, request schemas, artifact schemas, or a universal BEC workflow.

## Current behavior and evidence

The existing legacy `prepare_bec` writes `berry_phase=1` into prepared displacement inputs, while `run_bec` delegates to the generic subtask runner. `post_bec` reads a caller/workspace-supplied `bec/.../reports/polarization.json` and differences the three values. It does not parse ABACUS Berry-phase logs. See [`composite/properties.py`](../../../src/abacus_forge/composite/properties.py).

ABACUS documentation describes a converged SCF followed by an NSCF calculation with `berry_phase=1`, symmetry disabled, `init_chg=file`, and a selected `gdir`. It defines `gdir=1,2,3` as the three lattice-vector directions, and says the values in parentheses are the Cartesian projection for that direction. The full Cartesian polarization is formed by calculating all three lattice directions and summing their Cartesian vectors. [ABACUS Berry Phase Calculation documentation](https://abacus.deepmodeling.com/en/v3.11.0-beta9/advanced/elec_properties/Berry_phase.html)

The inspected ABACUS producer, [`berryphase.cpp`](https://github.com/deepmodeling/abacus-develop/blob/7b33a94bfb4132c33656c41719e0fcae4e6ebdbe/source/source_io/module_unk/berryphase.cpp), confirms that it prints three unit forms for each direction. `outFormat` formats the value, modulus, and Cartesian vector using floating-point formatting. The displayed modulus therefore carries the same unit scaling as its associated polarization row; it is not an integer quantum count. The source constructs the Cartesian vector along the normalized lattice vector selected by `gdir`.

## Polarization fact model

Collection should preserve the native record without interpreting its branch. At minimum, the record needs:

- the reported lattice direction (`R1`, `R2`, or `R3`);
- ionic and electronic phase values;
- the printed polarization scalar and printed modulus for each recognized unit row;
- the three Cartesian components associated with each row;
- the unit label and source log path for each parsed row.

The modulus is a floating-point, unit-bearing printed value. A parser must not coerce it to an integer or call it the dimensionless branch index. Preserve the native text precision as numeric facts; do not infer branch offsets from a rounded display value.

For the `(e/Omega).bohr` row, each printed Cartesian component has units of `e·bohr/bohr³` (equivalently `(e/Ω)·bohr`). For the `e/bohr²` row, it has units of `e/bohr²`. Let `q[g, α]` be the printed Cartesian component `α` from the first row of the run with `gdir=g`, and `p[g, α]` the corresponding component from the second row. For one structure and displacement, the exact aggregations are:

```text
q_α = Σ(g=1..3) q[g, α]       # printed (e/Omega).bohr values
p_α = Σ(g=1..3) p[g, α]       # printed e/bohr^2 values
p_α = q_α / Ω_bohr3
```

The two rows describe equivalent physical polarization and must not be mixed within a calculation. The Cartesian vector from one `gdir` is one lattice-direction projection, not the complete cell polarization. Construct a complete Cartesian vector only by summing the three direction vectors for the same structure and displacement.

The parser reports facts even when they are insufficient for BEC postprocessing. Missing or malformed output must remain an explicit collection failure/absence; the parser must not synthesize zero components or guess a direction.

## BEC finite difference and units

For a Cartesian displacement of atom `i` along Cartesian axis `β`, let `Δq_α = q_α(+) − q_α(−)` and `Δp_α = p_α(+) − p_α(−)`. With cell volume `Ω_bohr3` and positive displacement magnitude `δ_bohr`, the equivalent formulas are:

```text
Z*_(i, αβ) = Δq_α / (2 δ_bohr)
            = Ω_bohr3 × Δp_α / (2 δ_bohr)
```

The first form consumes the summed printed `(e/Omega).bohr` components; the second consumes the summed printed `e/bohr²` components. If the preparation displacement is expressed in ångström, convert it as `δ_bohr = δ_Å / 0.529177` (approximately `1.88973 × δ_Å`).

Do not multiply `Δq` by volume: the first printed unit row already contains `1/Ω`. For the second row, multiply `Δp` by `Ω_bohr3` exactly once. The resulting tensor element is in units of `e`.

The first tensor index is the Cartesian polarization component; the second is the Cartesian displacement direction. The `gdir` index is a lattice-vector selector and must not be substituted for either Cartesian index. This distinction is observable for a nonorthogonal cell.

## Boundaries

Forge owns the local input transformation, one-stage process execution, parsing of native output facts, and the explicitly requested numerical postprocess. The caller owns selection and ordering of stages, moving or reusing SCF products, retries, pairing runs, and deciding whether the resulting tensor is scientifically acceptable. BEC supports explicit integer branch offsets and conditional deterministic path unwrapping; scientific acceptance remains with the caller.

The postprocess reports incomplete requested columns explicitly and retains independently valid columns. It must not silently turn missing directional data into zero polarization or a complete tensor.

No decisions are made here about a universal BEC task/workflow, automatic SCF-to-NSCF handoff, scheduler behavior, tensor-symmetry enforcement, acoustic sum-rule corrections, or scientific acceptance.

## Acceptance criteria for the implementation contract

These requirements guide the linked implementation plan; evidence is recorded there.

1. Given a known ABACUS Berry-phase log, collection returns the selected `gdir`, phase facts, every supported unit row, floating-point modulus values, and all three printed Cartesian components with their units and provenance.
2. Logs containing no polarization block, an invalid `gdir`, a truncated row, or a nonnumeric field do not yield fabricated facts or a successful complete polarization record.
3. For a nonorthogonal lattice fixture, three `gdir` Cartesian projection vectors are summed to the expected full Cartesian vector. Tests distinguish lattice direction labels from Cartesian axes.
4. A synthetic plus/minus pair with a known full Cartesian polarization difference and a displacement supplied in ångström produces the expected BEC tensor, including the `Å`-to-bohr conversion.
5. Equivalent inputs expressed with the `(e/Ω).bohr` row and the `e/bohr²` row produce the same BEC when the volume conversion is applied once. A regression catches a missing or duplicated volume factor.
6. A polarization branch-wrap fixture must not be converted into a fabricated BEC. Automatic ambiguity and explicit offsets are covered by the policy below.
7. Incomplete `gdir` coverage or a missing plus/minus member must be identified explicitly. Independent valid columns are retained, while incomplete requested columns prevent requested_complete.
8. The single-stage execution boundary is observable: one call starts at most the one explicitly selected ABACUS process and does not run another stage, retry, or orchestrate a sequence.

## Frozen implementation slice

New experimental typed capabilities are `polarization/collect` and `bec/postprocess`.
Preparation/displacement and one-stage execution reuse existing generic primitives; no
multi-run workflow or automatic SCF/NSCF execution is introduced. The legacy BEC pack
is not the numerical implementation of these capabilities. Single-stage preparation
and execute reuse must be demonstrated with a local fixture and documented recipe.

`PolarizationCollectRequest` carries the usual operation identity plus explicit
`log_path_rel`, `structure_path_rel`, `input_path_rel` and `output_path_rel`
(default `outputs/polarization.json`), all inside the workspace. It consumes one
unambiguous native polarization block and writes a `forge.polarization/v1` JSON
artifact. Preserve raw unit rows and floating modulus; parse the corresponding STRU
and INPUT for geometry, nspin (1/2 only) and gdir correspondence. Missing or malformed
sources give explicit collection diagnostics, never invented facts. No output target
may overwrite a source, existing file or reserved audit path; parent symlinks remain
contained. Output JSON and source files have normal v1 artifact records.

`BecPostprocessRequest` carries identity plus nonempty `columns`, `branch_mode`
(`auto` default, or `explicit`), optional `max_step_fraction`, and `output_path_rel`
(default `outputs/bec.json`). Each column has `atom_index` (1-based), `direction`
(x/y/z), and `samples`; each sample has `displacement_angstrom`, an explicit list
`polarization_paths_rel`, and optional `branch_offsets` mapping keys `1`,`2`,`3` to
integers. Every sample needs one collected fact per gdir for a calculable column.
Unknown keys, nonfinite numbers, duplicate columns/displacements/gdir facts, and
unsupported requests are rejected or reported as invalid data rather than guessed.
The outer input and nested request shapes are strict. Missing files/records are
reported per column so independent requested columns can still succeed.

All samples in a column must describe the same fixed nonsingular cell, atom order,
species/PP/ORB references, spin and compatible INPUT settings except gdir. Their
geometries must differ only by the declared Cartesian displacement of the selected
atom. Do not synthesize atom identity, geometry or pairing from filenames. Endpoints
must be symmetric ±delta with delta>0. For explicit mode, a zero sample is optional;
for auto it is required. In both modes emit computed columns as Cartesian polarization
components, not gdir scalars; uncomputed tensor slots remain null.

### Conditional automatic branch handling

`max_step_fraction` is required for auto and satisfies 0<f<0.5. It is an explicit
caller assertion about the TRUE physical change in each gdir between adjacent
samples, in units of that direction's printed quantum; it is not a conclusion drawn
from small wrapped differences. Auto additionally requires a connected ordered path
containing zero and ±delta. Sort by the explicit displacement, anchor each gdir at
zero with offset 0, then traverse separately toward positive and negative endpoints.
For each step choose an integer offset k such that the corrected scalar change is
strictly within f times the printed quantum, allowing for seven-decimal log precision.
Use the unique candidate only; boundary-near/no candidate means ambiguous, with the
missing reference/condition reported. Additional path samples do not by themselves
prove absence of hidden winding. Offsets may exceed ±1.

Use the actual positive printed quantum, verify its consistency across the fixed-cell
path, and form the correction vector k*q*R_i/|R_i| for the `(e/Omega).bohr` row.
Sum all three corrected Cartesian contributions before finite difference. This
per-gdir algorithm does not select a nearest Cartesian lattice image in a skew cell.
A trace records each selected offset, bound, reference and method; results explicitly
state that continuity is conditional on the caller's bound.

### Explicit offsets and subset completeness

Explicit mode requires three caller-supplied integer offsets for every used sample;
it does not require an automatic bound. Retain the offsets and `manual_offsets`
method in the output. Geometry, units, quantum and data completeness checks still
apply. Do not mix an undeclared auto fallback into explicit mode.

Result `forge.bec/v1` reports requested/computed columns, per-column missing/invalid/
ambiguous reasons, tensor values in e, and branch trace. `requested_complete` means
all requested columns computed; `full_tensor_complete` additionally requires x/y/z
for every atom in the supplied structure. Thus a single requested valid column can
complete its operation without claiming a full tensor. No zero filling, silent
symmetry completion or acoustic sum-rule correction. Collection status is complete
only for requested_complete; otherwise partial when facts/results exist and
missing_output when no usable inputs exist. Scientific state always unassessed.

### Scientific verification boundary

Tests use clearly labeled synthetic/source-shaped logs, including a skew-cell known
BEC, branch wrap, half-quantum/tolerance ambiguity, multiple winding explicit offsets,
missing gdir/endpoints, subset vs full completeness, inconsistent geometry/quantum,
unit conversion, and CLI/Python equivalence. No native Berry running-log fixture was
found in the checked workspace; do not label these tests real ABACUS/BEC validation.
A future material calculation is a separate scientific acceptance task.

Algorithm references: [ABACUS producer](https://github.com/deepmodeling/abacus-develop/blob/7b33a94bfb4132c33656c41719e0fcae4e6ebdbe/source/source_io/module_unk/berryphase.cpp),
[official Berry instructions](https://abacus-rtd.readthedocs.io/en/latest/advanced/elec_properties/Berry_phase.html),
[King-Smith and Vanderbilt 1993](https://journals.aps.org/prb/abstract/10.1103/PhysRevB.47.1651).
The guarded bound and explicit ambiguity behavior are Forge design choices, not a
claim that these sources certify any sampled path as converged.

## Source coverage and limitations

- Current Forge implementation: `src/abacus_forge/composite/properties.py` (`prepare_bec`, `run_bec`, `post_bec`, and `_read_polarization`).
- ABACUS primary documentation: [Berry Phase Calculation, v3.11.0-beta9](https://abacus.deepmodeling.com/en/v3.11.0-beta9/advanced/elec_properties/Berry_phase.html).
- Producer source inspected at pinned revision: [berryphase.cpp, `7b33a94`](https://github.com/deepmodeling/abacus-develop/blob/7b33a94bfb4132c33656c41719e0fcae4e6ebdbe/source/source_io/module_unk/berryphase.cpp), especially `Macroscopic_polarization` and `outFormat`.
- Forge responsibility baseline: [`docs/architecture.md`](../../architecture.md) and [`AGENTS.md`](../../../AGENTS.md).

This source review confirms output interpretation for the inspected ABACUS source and documentation version. It does not establish compatibility across every ABACUS release, prove numerical convergence, or prove the caller-provided continuity bound.
