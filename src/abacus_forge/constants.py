"""Physical constants shared across Forge modules.

ABACUS reports several energies in Rydberg.  Keep one exact conversion factor
so individual packs cannot drift to a different precision.
"""

from __future__ import annotations

RY_TO_EV = 13.605693122994
