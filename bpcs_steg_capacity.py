"""Estimate BPCS hiding capacity for a vessel image."""

from bpcs_core import DEFAULT_ALPHA, capacity_bytes


def capacity(vessel, alpha=DEFAULT_ALPHA):
    n_blocks, usable_bytes, payload_bytes = capacity_bytes(vessel, alpha)
    return {
        "embeddable_blocks": n_blocks,
        "raw_bytes": usable_bytes,
        "payload_bytes": payload_bytes,
        "alpha": alpha,
    }
