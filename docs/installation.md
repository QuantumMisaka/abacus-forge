# Install ABACUS-Forge

Forge requires Python 3.10 or newer. Create a fresh virtual environment before choosing a package source:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
```

The first public PyPI release is being prepared. Today, install directly from the Git repository if you have access, without cloning it into your working directory:

```bash
python -m pip install 'git+https://github.com/QuantumMisaka/abacus-forge.git'
```

Alternatively, install a wheel supplied by the project maintainer:

```bash
python -m pip install /path/to/abacus_forge-0.1.0-py3-none-any.whl
```

The wheel filename above is an example; use the actual wheel you received. Once the first PyPI release is confirmed, `python -m pip install abacus-forge` will become a direct index-install option. Do not treat a prepared release candidate as already published.

Check the installed command and its environment report:

```bash
abacus-forge --version
abacus-forge doctor
abacus-forge doctor --json
abacus-forge capabilities
```

The default doctor check is useful without ABACUS: it checks the installed Python package and core dependencies, and does not run an engine. For a real calculation, explicitly check your executable and input assets:

```bash
abacus-forge doctor --executable /path/to/abacus --asset /path/to/Si.upf
```

The doctor command checks discoverability, executability, and file readability. It cannot prove ABI compatibility, pseudopotential suitability, or scientific convergence. A missing explicitly requested executable or asset is reported as unavailable and exits with code 3; invalid command arguments exit with code 2.

Forge does not install ABACUS or provide pseudopotentials or numerical orbitals. Plane-wave SCF needs the pseudopotential selected for each species. LCAO also needs matching orbital files. Add an optional extra to the Git install only when its capability is needed, for example:

```bash
python -m pip install 'abacus-forge[phonon] @ git+https://github.com/QuantumMisaka/abacus-forge.git'
python -m pip install 'abacus-forge[abacuslite] @ git+https://github.com/QuantumMisaka/abacus-forge.git'
```

These are alternative installation commands; choose the extra you need. The `abacuslite` extra pins the verified parser release. The engine-free [quickstart](quickstart.md) needs neither extra nor an engine.

For development from a local checkout, `python -m pip install -e '.[dev]'` is supported. The user quickstart and Agent examples use the installed package and do not require `PYTHONPATH` or access to the source tree.
