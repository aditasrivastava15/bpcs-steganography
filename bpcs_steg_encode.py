"""Encode a secret file into a vessel image with BPCS."""

from bpcs_core import DEFAULT_ALPHA, encode_file


def encode(vessel, message, output, alpha=DEFAULT_ALPHA, key=None):
    return encode_file(vessel, message, output, alpha=alpha, key=key)
