# abacuslite 1.2.0 → 1.2.2 offline real-log replay

These are previously executed ABACUS v3.11.0-beta8 / v3.10.1 logs, not new engine executions.
Each of eight source workspaces was copied and hash checked before/after collection.
The four parser combinations per cell ran with installed Python `-I`.

| Cell | Track | Capability | Old/new native | Old/new abacuslite | New native/1.2.2 | Status |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | develop | scf | same | same | same | {'collection': 'complete', 'execution': 'not_run', 'scientific': 'unassessed'} |
| 1 | develop | relax | same | same | same | {'collection': 'complete', 'execution': 'not_run', 'scientific': 'unassessed'} |
| 2 | develop | cell-relax | same | same | same | {'collection': 'complete', 'execution': 'not_run', 'scientific': 'unassessed'} |
| 3 | develop | md | same | same | same | {'collection': 'complete', 'execution': 'not_run', 'scientific': 'unassessed'} |
| 4 | lts | scf | same | same | same | {'collection': 'complete', 'execution': 'not_run', 'scientific': 'unassessed'} |
| 5 | lts | relax | same | same | same | {'collection': 'partial', 'execution': 'not_run', 'scientific': 'unassessed'} |
| 6 | lts | cell-relax | same | same | same | {'collection': 'partial', 'execution': 'not_run', 'scientific': 'unassessed'} |
| 7 | lts | md | same | same | same | {'collection': 'complete', 'execution': 'not_run', 'scientific': 'unassessed'} |

Numerical tolerances mirror the prior real parity gate: energy/Fermi 0.005 eV, force 0.001 eV/Å, stress/pressure 0.001 kbar. Structure and status are exact.
Full collection results, typed envelopes, commands, stdout/stderr, file hashes, and field-level differences are in this directory's JSON files.
This replay does not establish compatibility with newly executed ABACUS, different basis/spin, or scientific acceptance.
