# Forge Typed MD Postprocess Review Fixes Implementation Plan

**Goal:** 修复独立算法审计发现的 typed `md.postprocess` 重要缺口，保持已批准的事实型、显式轨迹和 Agent-first 边界不变。
**Spec:** `docs/superpowers/specs/2026-09-10-forge-typed-md-postprocess-design.html`（尤其是参数错误、周期最小镜像、MSD diffusion metric、产物完整性和错误映射条款）。
**Authorization:** 用户已持续授权以 `$superpowers:subagent-driven-development` 推进 Forge；本批次仅在 `forge-md-postprocess-review-fixes` 隔离分支验证，不合入 `main`、不 push。
**Architecture:** 将请求级参数校验置于 workspace admission 之前；纯算法层使用可靠的任意斜晶胞 minimum-image 和 fail-closed 元素质量；绘图失败只返回事实诊断并让服务按缺失产物标记 partial/missing；服务公开 SPEC 要求的 diffusion metric，不新增 workflow、科学验收或平台语义。
**Verification:** 先分别运行两个拥有者的 TDD focused suites，再运行 typed MD/API-CLI parity、architecture、完整离线 pytest、benchmark（仅既有 opt-in fixture）和 `git diff --check`；无 ABACUS/PyATB 真实运行环境时不声称科学证据。

## Scope and ownership

- **Package A — contract/service boundary:** `src/abacus_forge/md_postprocess_contracts.py`, `src/abacus_forge/md_postprocess_services.py`, nearest contract/service/machine tests. Owns pre-admission recognized-parameter validation, request.schema mapping, claim absence, and `diffusion_coefficient` reported metric with API/CLI parity.
- **Package B — pure algorithms:** `src/abacus_forge/md_postprocess.py`, `tests/test_md_postprocess_algorithms.py`. Owns exact minimum-image for full/partial periodic cells, complete/fail-closed XYZ mass handling, and truthful plot failure outputs/diagnostics.
- **Controller docs/review:** this plan, the approved MD SPEC hardening note, and branch-level integration/review evidence. Do not rewrite unrelated historical plans.

## Global constraints

- Capability remains `md`, maturity remains `experimental`; canonical modes and request/result/error schema versions do not change.
- Invalid recognized parameter values are `request.schema` / exit 2, and must not read the trajectory, create an admission claim, write domain outputs, or append an operation event.
- `timestep` is the elapsed time between adjacent frames in the sampled frame view. Callers that select every `stride`-th source frame must provide the corresponding sampled-frame interval; this clarification does not add a field or silently multiply values.
- A periodic distance/unwrap must be the nearest image under the declared lattice for arbitrary non-singular triclinic cells, including the periodic subset used by a partially periodic frame.
- XYZ fallback must use a complete finite element-mass table or reject unknown symbols; it must never assign a synthetic mass to an unknown symbol. Existing ASE masses remain authoritative when valid.
- `save_plot=true` never emits a placeholder image after import/render failure. Missing plots are recorded in diagnostics and cause the existing `complete|partial|missing_output` logic to reflect missing declared files.
- The envelope exposes the algorithm's diffusion result as one `MetricRecord` named `diffusion_coefficient`, unit `Angstrom^2/fs`, kind `reported`, sourced from the contained `analysis.json` artifact when present. No scientific acceptance is implied.
- No task adds trajectory conversion, MD scheduling, restart/resume, workflow orchestration, scientific validation, or a new dependency requirement.

## Task 1: Request validation and factual metric projection

**Dependencies:** none; base is `da1d4df`.

**Files:** `md_postprocess_contracts.py`, `md_postprocess_services.py`, nearest contract/service/machine tests.

**Behavior:** Reuse one small validation helper at the typed request boundary for the seven recognized parameters. Mode-dependent `timestep` and numeric/list/boolean bounds fail during request construction/decoding. The service must never enter `operation_guard` for these errors. After successful analysis, add the finite `msd_diffusion.diffusion_angstrom2_per_fs` value as a reported metric with an `analysis.json` source artifact ID; omit it when the mode/result or artifact is absent. Preserve unknown-parameter diagnostics and all existing status/error classes.

**Verification:** RED tests construct/decode malformed parameter payloads and assert `request.schema`, exit 2, no claim/event/output; GREEN runs contract/service/machine focused tests and API/CLI parity, including the reported metric and source ref.

## Task 2: Pure numerical and output truthfulness hardening

**Dependencies:** none; base is `da1d4df`.

**Files:** `md_postprocess.py`, `tests/test_md_postprocess_algorithms.py`.

**Behavior:** Add a dependency-free nearest-lattice-image helper for arbitrary full or partial periodic cells and use it from unwrap, geometry and RDF. Extend the fallback mass table to all supported chemical symbols and reject syntactically shaped but unknown symbols. Replace placeholder PNG writes with skipped files plus finite diagnostics describing each failed plot; successful data/JSON artifacts remain deterministic.

**Verification:** RED tests cover a highly skewed triclinic counterexample, partial-PBC image, Li/Ti/Au fallback masses and unknown `Xx`, matplotlib import failure and render exception; GREEN runs the algorithm suite and service status checks.

## Task 3: Documentation, review and branch acceptance

**Dependencies:** Tasks 1–2.

- [x] Update this plan with exact commit/range evidence and review rulings; update the approved MD SPEC only with concise clarified semantics (sampled-frame timestep, fail-closed mass, no placeholder plot) if the implementation requires normative wording.
- [x] Run focused owning suites, typed MD machine/API parity, architecture and complete offline gates in `conda run -n paimon`; record environment skips separately.
- [x] Dispatch independent task-scoped reviews for Packages A/B and one whole-branch review against the exact SPEC/plan diff. Resolve every Critical/Important finding; record justified Minor deferrals.
- [x] Keep `main`, formal integration branch, freshness candidate, and remote untouched until the user explicitly authorizes merge.

## Completion evidence (2026-09-11)

- Implementation/documentation range: `da1d4df..e6559ce`; review-fix commits are `b052649` (request validation and reported diffusion metric), `2aeec15` (mass/MIC/plot hardening), `a55b5b2` (Babai-localized MIC translation invariance), `36e14a6` (README and historical-plan alignment), and `4e642c5` (preserve pre-fix historical evidence). The final `07cf8f8` and `e6559ce` changes only correct and finalize the skip/range evidence in this ledger.
- Focused contract/algorithm/service/machine/architecture gate: `174 passed in 62.46s`.
- Full offline gate: `1252 passed, 5 skipped in 110.58s`; the skips are three opt-in real-smoke cases and two opt-in benchmark cases, none of which is scientific acceptance evidence.
- Opt-in benchmark gate: `2 passed, 1255 deselected in 2.71s` with `--run-benchmark -m benchmark`.
- Package-owner evidence: contract/service owner `179 passed`; algorithm owner `102 passed` after the MIC follow-up; both workers reported clean `git diff --check`.
- Whole-branch review of `da1d4df..5133981`: no Critical/Important findings. The only Minor (historical evidence attribution) was fixed in `4e642c5`; reviewer independently checked the former MIC counterexample plus 45 random full/partial-PBC finite-enumeration cases and large lattice translations. The later `07cf8f8` edit is evidence-only and was explicitly confirmed non-blocking by the reviewer.
- The approved MD SPEC now records sampled-frame `timestep`, fail-closed unknown symbols, truthful plot omission/partial collection, and the input/provenance/output artifact mapping. No new workflow, scheduler, scientific-validation, or dependency boundary was added.
- Formal integration (`forge-mainline-integration` at `da1d4df`), `main`, freshness candidate, and remote remain untouched. No real ABACUS/PyATB execution was available or claimed.

## Rulings

- `Ruling: treat all four Important findings as in-scope correctness fixes — each contradicts an explicit approved MD postprocess contract or produces a misleading fact; the cost of a wrong fix is confined to one experimental capability branch.`
- `Ruling: clarify, rather than silently reinterpret, timestep/stride — the operation already accepts both values and the current algorithm uses the supplied timestep as the sampled-frame interval; changing it to implicit multiplication would alter caller-visible numbers without a migration decision.`
- `Ruling: prefer fail-closed unknown symbols over retaining the old `1.0` sentinel — synthetic mass is not a factual observation and a false number is worse than an actionable precondition error.`
