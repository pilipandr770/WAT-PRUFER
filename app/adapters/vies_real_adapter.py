"""Shim for legacy vies_real_adapter — delegate to the new ViesAdapter.

This file exists so older imports still resolve, but it does not perform any
zeep/WSDL actions; it simply forwards to the requests-based adapter.
"""

from .vies_adapter import ViesAdapter


class ViesRealAdapter(ViesAdapter):
    """Backward-compatible alias (inherits the requests-based implementation)."""
    pass
