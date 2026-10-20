# Installed-only pytest invocation receipt

The following is the exact shell command executed from
`/home/james/work/sidereus/workplace/abacus-forge/.worktrees/forge-integration-reference-review`.
It exited with code 0. The pytest parent process was **not** invoked with
`python -I`; `PYTHONPATH` was explicitly set to the empty string, and the
installed-only guard validated the wheel distribution. The repository's CLI
test helper isolates its own CLI subprocesses separately.

```bash
env ABACUS_FORGE_INSTALLED_PACKAGE_ONLY=1 PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 /home/james/scratch/forge-release-validation-20261021/venv/bin/python -m pytest -q -p no:cacheprovider tests/test_pyatb_cohp.py tests/test_polarization.py tests/test_bec.py tests/test_polarization_services.py tests/test_contracts.py tests/test_workspace.py tests/test_machine_cli.py tests/test_cli_process.py > /home/james/scratch/forge-release-validation-20261021/installed-pytest.log 2>&1
```

Raw stdout/stderr: `installed-pytest.log` (520 passed, 1 warning).
