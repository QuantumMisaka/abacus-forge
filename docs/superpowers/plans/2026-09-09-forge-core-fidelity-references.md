# Forge core fidelity: reference evidence

This is supporting evidence for [the implementation plan](2026-09-09-forge-core-fidelity.md), not a separate specification. Inspection uses local checkouts; revisions below do not claim latest upstream status. Reference repositories were not modified or introduced as runtime dependencies.

| Reference | Inspected local HEAD | Relevant implementation | Adopt / avoid |
| --- | --- | --- | --- |
| Paimon v1.2 (`app-tools/toolbox/ABACUS`) | `85e55e6b83b3b1a883d41b7d149c8afa2c223aba` | `utils/stru_read.py:110` `_cell_face_heights`, `_largest_wrapped_gap`, `detect_vacuum_info`; `utils/abacus_structure_io.py:111` `atoms_from_abacus_stru_dict` | Adopt periodic fractional gap × interplanar height and explicit unit conversion. Keep platform adapter and scientific policies outside Forge. |
| Paimon v1.2 | same | `toolkits/structure_prepare_pipeline.py:599` `_native_stru_uses_selected_resources`, native copy at 718, explicit transformed PP/basis write at 733; `tests/test_structure_prepare_pipeline.py:430` | Preserve native source meaning. Resource selection/materialization is explicit; a structure serializer alone does not stage assets. |
| Paimon v1.2 | same | `utils/basic_result_evidence.py:51`, `utils/result_evidence.py:23`, `abacus_collector.py:71` | Adopt separation of facts, metrics, artifacts and provenance; do not inherit the four-metric ceiling or unconditional execution-status projection. |
| abacustest (`abacus-test`) | `1c9acbca026234ba91cdc19bca2f989d19d2ccff` | `abacustest/lib_prepare/stru.py:1329` `read_stru_file`, `:1460` `write_stru_file` | Writer explicitly accepts PP/mass/orbital data; reader omits parsed mass from returned dictionary. Do not copy that lossy round trip. |
| abacustest | same | `abacustest/lib_model/comm.py:864` `get_largest_vacuum_dir` | Cyclic fractional gaps are useful; multiplying by cell-vector lengths instead of face heights is unsuitable for skew cells. |
| abacustest | same | `abacustest/lib_collectdata/resultAbacus.py:10`; `abacustest/lib_collectdata/abacus/abacus.py:138,318,395,429,1187` | Use independent normal-end, convergence, energy, force, stress and relaxation facts as parser references. No typed completeness contract is supplied by this backend. |
| abacuscopilot | `91b945674d9fc183efcd40e1d1a7ce6058566356` | `abacuscopilot/io/stru_file.py:95` `read_stru`, writer at 285 | Species order and explicit resource fields are useful. Writer regenerates masses and fabricates default resource filenames: unsuitable for fidelity-preserving conversion. |
| abacuscopilot | same | `abacuscopilot/postprocessing/scf_tasks.py:22` and `:557` | Specific positive/negative markers provide parser examples; do not copy broad convergence regexes or turn marker presence into collection completeness. |
| abacuslab | `d641692171b37d52b890c7e0acd34b6f4ffdfb06` | `templates/scf_band_template_v2.yaml:127,166,232,241` | Explicit output handoff is useful. Local checkout contains templates/docs, not internal engine implementation; example success output despite missing artifacts is not a completeness reference. |
| ABACUS | `94576a80169de36e02e637edc2a0963fba9e1838` | `source/source_cell/read_atoms_helper.cpp:24,195`; `source/source_cell/print_cell.cpp:128` | Native coordinate/lattice-unit authority: Cartesian uses lat0; Cartesian_au uses Bohr; centered Angstrom modes add offsets; emitted lattice constant is in Bohr. |

## Corrections to the preceding review

- Forge's `Cartesian_au` followed its Cartesian prefix branch, not Direct. The defects were plain Cartesian missing lattice-constant scaling and centered modes losing their offsets.
- Forge's emitted `LATTICE_CONSTANT_UNIT Angstrom` is not a native ABACUS token. Correct output must be checked using native units independently of Forge's own reader.
- Passing baseline tests (593 passed, 3 skipped at `e7a9cc8`) did not cover these semantic defects. Some prior fixtures encoded the same wrong unit convention on both sides.

## Scope retained for later work

Typed prepare asset maps/materialization remain separate: explicit choice and source provenance, path containment, duplicate basenames, absent files and copy/link behavior need one coherent contract. Paimon v1.2's resource pipeline is the relevant reference; Forge must not inherit its Tool/runtime objects. This batch preserves STRU references but does not claim a complete executable-ready typed prepared directory.

Axis-swap Cartesian orientation, full centered-coordinate support, advanced per-atom STRU extras, broader MD/PyATB/property algorithms and upstream release verification are not closed by this batch.
