"""Static request type registry shared by discovery and the machine adapter."""

from abacus_forge.contracts import (
    AtstNebExecuteRequest,
    AtstNebPostprocessRequest,
    AtstNebPrepareRequest,
    ScfCollectRequest,
    ScfExecuteRequest,
    ScfModifyRequest,
    ScfPrepareRequest,
)
from abacus_forge.export_contracts import ExportRequest
from abacus_forge.md_contracts import (
    MdCollectRequest,
    MdExecuteRequest,
    MdModifyRequest,
    MdPrepareRequest,
)
from abacus_forge.md_postprocess_contracts import MdPostprocessRequest
from abacus_forge.postprocess_contracts import BandPostprocessRequest, DosPostprocessRequest
from abacus_forge.pyatb_contracts import (
    PyatbBandCollectRequest,
    PyatbBandExecuteRequest,
    PyatbBandPrepareRequest,
)
from abacus_forge.relax_contracts import (
    RelaxCollectRequest,
    RelaxExecuteRequest,
    RelaxModifyRequest,
    RelaxPrepareRequest,
)

SCF_REQUEST_TYPES = {
    "prepare": ScfPrepareRequest,
    "modify": ScfModifyRequest,
    "execute": ScfExecuteRequest,
    "collect": ScfCollectRequest,
}
ATST_NEB_REQUEST_TYPES = {
    "prepare": AtstNebPrepareRequest,
    "execute": AtstNebExecuteRequest,
    "postprocess": AtstNebPostprocessRequest,
}
RELAX_REQUEST_TYPES = {
    "prepare": RelaxPrepareRequest,
    "modify": RelaxModifyRequest,
    "execute": RelaxExecuteRequest,
    "collect": RelaxCollectRequest,
}
MD_REQUEST_TYPES = {
    "prepare": MdPrepareRequest,
    "modify": MdModifyRequest,
    "execute": MdExecuteRequest,
    "collect": MdCollectRequest,
    "postprocess": MdPostprocessRequest,
}
POSTPROCESS_REQUEST_TYPES = {
    "band": {"postprocess": BandPostprocessRequest},
    "dos": {"postprocess": DosPostprocessRequest},
}
PYATB_BAND_REQUEST_TYPES = {
    "prepare": PyatbBandPrepareRequest,
    "execute": PyatbBandExecuteRequest,
    "collect": PyatbBandCollectRequest,
}
EXPORT_REQUEST_TYPES = {"export": ExportRequest}

ALL_REQUEST_TYPES_BY_CAPABILITY = {
    "scf": SCF_REQUEST_TYPES,
    "relax": RELAX_REQUEST_TYPES,
    "cell-relax": RELAX_REQUEST_TYPES,
    "atst-neb": ATST_NEB_REQUEST_TYPES,
    "md": MD_REQUEST_TYPES,
    **POSTPROCESS_REQUEST_TYPES,
    "pyatb-band": PYATB_BAND_REQUEST_TYPES,
    "export": EXPORT_REQUEST_TYPES,
}

# Discovery historically keeps ATST NEB separate for its custom schema branch.
REQUEST_TYPES_BY_CAPABILITY = {
    name: operations
    for name, operations in ALL_REQUEST_TYPES_BY_CAPABILITY.items()
    if name != "atst-neb"
}
