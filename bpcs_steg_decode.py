"""Decode a secret file from a BPCS stego image."""

from bpcs_core import DEFAULT_ALPHA, decode_file


def decode(stego, output, alpha=DEFAULT_ALPHA, key=None):
    return decode_file(stego, output, alpha=alpha, key=key)
