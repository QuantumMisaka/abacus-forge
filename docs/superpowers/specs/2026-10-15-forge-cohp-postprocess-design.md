# Forge COHP postprocess design (W1)

Status: Approved for the first bounded W1 slice by QuantumMisaka on 2026-10-15
("按此推进" in response to the COHP capability gap review).

## Goal

Expose an agent-first, workspace-local COHP postprocessing unit operation in
ABACUS-Forge.  The first slice implements the frozen-semicore IAO kernel
already validated by Paimon v1.2, while keeping all task orchestration in the
caller.

## Boundary

Forge `cohp` / `postprocess` accepts an explicit completed ABACUS LCAO SCF
directory and explicit atom/orbital selectors.  It reads the declared ABACUS
artifacts, computes one bond-resolved IAO-COHP, and writes a fixed set of
JSON/numeric/plot artifacts.  It does not prepare inputs, run ABACUS, reuse or
schedule SCF, judge scientific quality, or manage platform tasks.

Out of W1 scope:

- `abacus-cohp-lcao` legacy subprocess bridge and its packaging story;
- automatic selection or promotion of `cohp_method`;
- Paimon `abacus_worker_cohp` migration;
- scientific acceptance or benchmark parity claims.

## Contract

- Capability name: `cohp`.
- Operation: `postprocess`.
- Request class: `CohpPostprocessRequest` with schema `forge.request/v1`.
- Method: `iao` only in this slice; the field is explicit so later legacy
  support cannot silently change the default.
- Workspace inputs: `scf_dir_rel` plus optional `out_dir_rel`.  The directory
  is an explicit bounded root; the kernel may resolve the standard artifacts
  inside it, including INPUT/STRU/KPT/ORBITAL/UPF references and OUT artifacts.
- Selectors: `atom_i_index` and `atom_j_index` are ABACUS 1-based atom numbers;
  orbital selectors use the existing Paimon IAO syntax (`all`, `s`, `3p`, `pz,s`).
- Outputs, relative to `output_dir_rel` (default `outputs`):
  `cohp.meta.json`, `cohp_EminusEf.dat`, `cohp.png`,
  `cohp_bond_images.json`.

## Data and diagnostics

The envelope records parser facts only: method, atom pair, translated bond,
distance, equivalent images, Fermi level, IAO/frozen-band counts, k-point
facts, output paths, and kernel cautions.  A finite nonzero ICOHP is not a
scientific conclusion; the caller interprets chemistry.

## Ownership and provenance

The numeric algorithm and reader originate in Paimon v1.2
`toolbox/ABACUS/toolkits/cohp_{iao,iao_reader,iao_shells}.py`, introduced by
feature/abacus/cohp-iao and merged as v2 `52798406d`.  Forge migration must
preserve numeric behavior and guards, but change imports/names only as needed
for the Forge package.  Paimon retains its adapter and may later consume the
Forge capability after W1/W2 parity evidence exists.

## Maturity

The capability is `experimental` and engine `abacus`.  Its optional dependency
list is empty: this slice is pure Python with NumPy/Matplotlib, which are
already Forge dependencies.  Legacy/external engine dependencies require a
separate packaging decision.
