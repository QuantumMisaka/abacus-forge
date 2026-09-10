# SDD ledger — plan: docs/superpowers/plans/2026-09-10-forge-typed-pyatb-band.md

Workflow: L3β via `using-superpowers`; `brainstorming` read-only audit settled the narrow public boundary, then `writing-plans` and `subagent-driven-development` are authorized by the user's continued Forge-development instruction.

Plan/spec self-review: checked against the two approved SPECs, local PyATB `80f7c2d`, Forge legacy helper/tests, Paimon/abacus-agent-tools and abacuslab references. Boundary audit is in `pyatb-surface-audit.md`. No cross-workspace merge/push is authorized in this batch.

Ruling: `pyatb-band` is a separate capability with exactly `prepare`, `execute`, `collect`; generic PyATB properties and SCF sequence orchestration remain outside this plan.

Ruling: all typed handoff source paths are workspace-relative and explicit; external absolute sources and implicit SCF discovery are rejected. Same-workspace relative links are the default because matrix files can be large; copy is opt-in.

## Task status

- Task 1 BASE: `84adfcc`
- Task 1: complete at `d49c515` (`feat: add typed PyATB band request contracts`); implementer acceptance `396 passed in 35.81s`, independent review CLEAN/APPROVED, focused rerun `396 passed in 35.28s`, `git diff --check` passed, worktree clean.
- Task 2: complete at `a487557` (implementation `940706a`, R1 fix `ec97e35`, report `a487557`); owning/legacy suites `35 passed`, scoped re-review CLEAN/APPROVED, `git diff --check` passed, worktree clean.
- Task 3: complete at `f06e2c3` (implementation `3ef68db`, report `f06e2c3`); selected suite `469 passed`, independent review CLEAN/APPROVED, focused rerun `469 passed`, `git diff --check` passed, worktree clean.
- Task 4: docs and verification complete in working tree after `36d87fe`; README/ROADMAP now describe the experimental typed `pyatb-band` prepare/execute/collect surface and its explicit workspace-local handoff. The stale architecture capability-list assertion was corrected in `tests/test_architecture.py` to include the eighth descriptor and its exact contract. Full gate: `892 passed, 3 skipped in 70.51s (0:01:10)`. Architecture gate: `8 passed in 4.93s`; forbidden/dependency subset: `3 passed, 5 deselected in 0.22s`; typed discovery subset: `11 passed, 64 deselected in 0.56s`; `git diff --check` passed. Direct `capabilities` and all three `schema pyatb-band {prepare,execute,collect}` commands exited 0. Raw outputs and remaining no-real-smoke uncertainty are in `task-4-report.md`; final whole-branch review remains with the parent agent.`
