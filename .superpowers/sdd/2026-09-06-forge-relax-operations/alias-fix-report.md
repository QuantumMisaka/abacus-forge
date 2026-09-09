# Relax alias projection fix report

## Revision and scope

- Worktree: `/home/james/work/sidereus/workplace/abacus-forge/.worktrees/forge-stage4-relax`
- Revision under test: `b1253d31cbeddb2997b9806d00f64ac1b867a65a` (`b1253d3 fix: sanitize relax collection projections`) plus the working-tree fix below.
- Scope: resolve artifact targets before the Relax projection filters internal Forge bookkeeping. The lexical filter and existing contained artifact conversion remain in place.
- Real ABACUS evidence remains unavailable. Relax and cell-relax remain experimental.

The prior projection dropped lexical `reports/claims/*` and
`reports/forge-workspace.json` keys, but an output symlink alias survived that
filter. Artifact conversion then resolved the alias to the internal target;
the claim was removed and the manifest was changed during persistence. The
returned outcome could therefore contain a dangling claim reference or a
stale manifest digest. `_projection_artifacts` now resolves each raw target
relative to the workspace root before applying the same internal-bookkeeping
predicate. Escaped or unresolvable targets are left for the existing artifact
conversion, which omits them as before.

Changed files:

- `src/abacus_forge/relax_results.py`
- `tests/test_service_status.py`
- `.superpowers/sdd/2026-09-06-forge-relax-operations/alias-fix-report.md`

The regression parameterizes `relax` and `cell-relax`, and both a contained
output alias to the in-flight operation claim and an alias to the mutable
workspace manifest. Every returned artifact is checked for resolved internal
paths, post-return existence, SHA-256, and size. Existing successful
artifact/hash and final-structure selection regressions remain unchanged.
No SCF or legacy projection source was modified.

## TDD RED

Command (run with `HEAD=b1253d31cbeddb2997b9806d00f64ac1b867a65a` before the
production change):

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py -k 'filters_output_aliases_to_internal_bookkeeping'
```

Exit code: `1`.

Complete raw output:

```text
ERROR conda.cli.main_run:execute(148): `conda run env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py -k filters_output_aliases_to_internal_bookkeeping` failed. (See above for error)
FFFF                                                                     [100%]
=================================== FAILURES ===================================
_ test_relax_collect_filters_output_aliases_to_internal_bookkeeping[relax-claim-123e4567-e89b-42d3-a456-426614174154] _

tmp_path = PosixPath('/tmp/pytest-of-james/pytest-48/test_relax_collect_filters_out0')
capability = 'relax', internal_target = 'claim'
operation_id = '123e4567-e89b-42d3-a456-426614174154'

    @pytest.mark.parametrize(
        ("capability", "internal_target", "operation_id"),
        [
            ("relax", "claim", "123e4567-e89b-42d3-a456-426614174154"),
            ("relax", "manifest", "123e4567-e89b-42d3-a456-426614174155"),
            ("cell-relax", "claim", "123e4567-e89b-42d3-a456-426614174156"),
            ("cell-relax", "manifest", "123e4567-e89b-42d3-a456-426614174157"),
        ],
    )
    def test_relax_collect_filters_output_aliases_to_internal_bookkeeping(
        tmp_path: Path, capability: str, internal_target: str, operation_id: str
    ) -> None:
        workspace = _write_relax_collection_workspace(tmp_path, capability=capability)
        target = (
            workspace.reports_dir / "claims" / f"{operation_id}.json"
            if internal_target == "claim"
            else workspace.reports_dir / "forge-workspace.json"
        )
        alias = workspace.outputs_dir / f"{internal_target}-alias.json"
        alias.symlink_to(target)
        request = RelaxCollectRequest(
            operation_id=operation_id,
            workspace_rel="collection",
            capability=capability,
        )

        result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

        assert isinstance(result, OperationOutcome)
        for artifact in result.envelope.artifacts:
            path = workspace.root / artifact.path_rel
            resolved_rel = path.resolve().relative_to(workspace.root.resolve()).as_posix()
            assert resolved_rel != "reports/forge-workspace.json"
            assert not resolved_rel.startswith("reports/claims/")
            assert resolved_rel not in {
                "reports/.forge-operation.lock",
                "reports/.forge-workspace.lock",
            }
            assert path.is_file(), artifact.path_rel
            assert artifact.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
            assert artifact.size_bytes == path.stat().st_size

E           AssertionError: assert not True
E            +  where True = <built-in method startswith of str object at 0x74b3727c6170>('reports/claims/')
E            +    where <built-in method startswith of str object at 0x74b3727c6170> = 'reports/claims/123e4567-e89b-42d3-a456-426614174154.json'.startswith

tests/test_service_status.py:1692: AssertionError
_ test_relax_collect_filters_output_aliases_to_internal_bookkeeping[relax-manifest-123e4567-e89b-42d3-a456-426614174155] _

tmp_path = PosixPath('/tmp/pytest-of-james/pytest-48/test_relax_collect_filters_out1')
capability = 'relax', internal_target = 'manifest'
operation_id = '123e4567-e89b-42d3-a456-426614174155'

    @pytest.mark.parametrize(
        ("capability", "internal_target", "operation_id"),
        [
            ("relax", "claim", "123e4567-e89b-42d3-a456-426614174154"),
            ("relax", "manifest", "123e4567-e89b-42d3-a456-426614174155"),
            ("cell-relax", "claim", "123e4567-e89b-42d3-a456-426614174156"),
            ("cell-relax", "manifest", "123e4567-e89b-42d3-a456-426614174157"),
        ],
    )
    def test_relax_collect_filters_output_aliases_to_internal_bookkeeping(
        tmp_path: Path, capability: str, internal_target: str, operation_id: str
    ) -> None:
        workspace = _write_relax_collection_workspace(tmp_path, capability=capability)
        target = (
            workspace.reports_dir / "claims" / f"{operation_id}.json"
            if internal_target == "claim"
            else workspace.reports_dir / "forge-workspace.json"
        )
        alias = workspace.outputs_dir / f"{internal_target}-alias.json"
        alias.symlink_to(target)
        request = RelaxCollectRequest(
            operation_id=operation_id,
            workspace_rel="collection",
            capability=capability,
        )

        result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

        assert isinstance(result, OperationOutcome)
        for artifact in result.envelope.artifacts:
            path = workspace.root / artifact.path_rel
            resolved_rel = path.resolve().relative_to(workspace.root.resolve()).as_posix()
>           assert resolved_rel != "reports/forge-workspace.json"
E           AssertionError: assert 'reports/forge-workspace.json' != 'reports/forge-workspace.json'

tests/test_service_status.py:1691: AssertionError
_ test_relax_collect_filters_output_aliases_to_internal_bookkeeping[cell-relax-claim-123e4567-e89b-42d3-a456-426614174156] _

tmp_path = PosixPath('/tmp/pytest-of-james/pytest-48/test_relax_collect_filters_out2')
capability = 'cell-relax', internal_target = 'claim'
operation_id = '123e4567-e89b-42d3-a456-426614174156'

    @pytest.mark.parametrize(
        ("capability", "internal_target", "operation_id"),
        [
            ("relax", "claim", "123e4567-e89b-42d3-a456-426614174154"),
            ("relax", "manifest", "123e4567-e89b-42d3-a456-426614174155"),
            ("cell-relax", "claim", "123e4567-e89b-42d3-a456-426614174156"),
            ("cell-relax", "manifest", "123e4567-e89b-42d3-a456-426614174157"),
        ],
    )
    def test_relax_collect_filters_output_aliases_to_internal_bookkeeping(
        tmp_path: Path, capability: str, internal_target: str, operation_id: str
    ) -> None:
        workspace = _write_relax_collection_workspace(tmp_path, capability=capability)
        target = (
            workspace.reports_dir / "claims" / f"{operation_id}.json"
            if internal_target == "claim"
            else workspace.reports_dir / "forge-workspace.json"
        )
        alias = workspace.outputs_dir / f"{internal_target}-alias.json"
        alias.symlink_to(target)
        request = RelaxCollectRequest(
            operation_id=operation_id,
            workspace_rel="collection",
            capability=capability,
        )

        result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

        assert isinstance(result, OperationOutcome)
        for artifact in result.envelope.artifacts:
            path = workspace.root / artifact.path_rel
            resolved_rel = path.resolve().relative_to(workspace.root.resolve()).as_posix()
            assert resolved_rel != "reports/forge-workspace.json"
            assert not resolved_rel.startswith("reports/claims/")
            assert resolved_rel not in {
                "reports/.forge-operation.lock",
                "reports/.forge-workspace.lock",
            }
            assert path.is_file(), artifact.path_rel
            assert artifact.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
            assert artifact.size_bytes == path.stat().st_size

E           AssertionError: assert not True
E            +  where True = <built-in method startswith of str object at 0x74b36f48a3a0>('reports/claims/')
E            +    where <built-in method startswith of str object at 0x74b36f48a3a0> = 'reports/claims/123e4567-e89b-42d3-a456-426614174156.json'.startswith

tests/test_service_status.py:1692: AssertionError
_ test_relax_collect_filters_output_aliases_to_internal_bookkeeping[cell-relax-manifest-123e4567-e89b-42d3-a456-426614174157] _

tmp_path = PosixPath('/tmp/pytest-of-james/pytest-48/test_relax_collect_filters_out3')
capability = 'cell-relax', internal_target = 'manifest'
operation_id = '123e4567-e89b-42d3-a456-426614174157'

    @pytest.mark.parametrize(
        ("capability", "internal_target", "operation_id"),
        [
            ("relax", "claim", "123e4567-e89b-42d3-a456-426614174154"),
            ("relax", "manifest", "123e4567-e89b-42d3-a456-426614174155"),
            ("cell-relax", "claim", "123e4567-e89b-42d3-a456-426614174156"),
            ("cell-relax", "manifest", "123e4567-e89b-42d3-a456-426614174157"),
        ],
    )
    def test_relax_collect_filters_output_aliases_to_internal_bookkeeping(
        tmp_path: Path, capability: str, internal_target: str, operation_id: str
    ) -> None:
        workspace = _write_relax_collection_workspace(tmp_path, capability=capability)
        target = (
            workspace.reports_dir / "claims" / f"{operation_id}.json"
            if internal_target == "claim"
            else workspace.reports_dir / "forge-workspace.json"
        )
        alias = workspace.outputs_dir / f"{internal_target}-alias.json"
        alias.symlink_to(target)
        request = RelaxCollectRequest(
            operation_id=operation_id,
            workspace_rel="collection",
            capability=capability,
        )

        result = RelaxServiceSet.default(workspace_root=tmp_path).collect.collect(request)

        assert isinstance(result, OperationOutcome)
        for artifact in result.envelope.artifacts:
            path = workspace.root / artifact.path_rel
            resolved_rel = path.resolve().relative_to(workspace.root.resolve()).as_posix()
>           assert resolved_rel != "reports/forge-workspace.json"
E           AssertionError: assert 'reports/forge-workspace.json' != 'reports/forge-workspace.json'

tests/test_service_status.py:1691: AssertionError
=========================== short test summary info ===========================
=========================== short test summary info ===========================
4 failed, 91 deselected in 1.20s
```

The four failures are the intended baseline symptoms: lexical aliases under
`outputs/` resolved to the in-flight claim or manifest and reached the result
conversion.

## Focused GREEN regression

Command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py -k 'filters_output_aliases_to_internal_bookkeeping or live_artifacts_with_current_hashes or reselects_output_stru_after_input_stru'
```

Exit code: `0`.

Complete raw output:

```text
........                                                                 [100%]
8 passed, 87 deselected in 1.20s
```

## Verification

### Owning service/API/result gate

Command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_service_status.py tests/test_api.py tests/test_result_contract.py
```

Exit code: `0`.

Complete raw output:

```text
........................................................................ [ 58%]
...................................................                      [100%]
123 passed in 7.51s
```

### Full offline suite

Command:

```text
conda run -n paimon env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider
```

Exit code: `0`.

Complete raw output:

```text
sss..................................................................... [ 13%]
........................................................................ [ 26%]
........................................................................ [ 39%]
........................................................................ [ 52%]
........................................................................ [ 65%]
........................................................................ [ 78%]
........................................................................ [ 91%]
............................................                             [100%]
545 passed, 3 skipped in 39.24s
```

### Diff hygiene

Command:

```text
git diff --check
```

Exit code: `0`.

Complete raw output: *(empty)*.

## Concerns and boundary

- No known implementation concerns remain for this bounded alias fix.
- The implementation intentionally does not change SCF or legacy result
  projection behavior.
- No real ABACUS execution environment or Relax workspace was available;
  experimental maturity is unchanged and no scientific result claim is made.
