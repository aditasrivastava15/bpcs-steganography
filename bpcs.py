#!/usr/bin/env python3
"""BPCS steganography CLI.

Examples (from the original capstone):
  python bpcs.py encode -i files/vessel.png -m files/message.txt -o stegg/encoded.png
  python bpcs.py decode -i stegg/encoded.png -a 0.45 -o stegg/message_decoded.txt
  python bpcs.py capacity -i files/vessel.png -a 0.45
"""

from __future__ import annotations

import argparse
import os
import sys

import matplotlib.pyplot as plt

from bpcs_core import DEFAULT_ALPHA, histogram_data, load_rgb, save_png
from bpcs_steg_capacity import capacity
from bpcs_steg_decode import decode
from bpcs_steg_encode import encode


def cmd_encode(args: argparse.Namespace) -> int:
    result = encode(args.input, args.message, args.output, alpha=args.alpha, key=args.key)
    print("Embedded {message_bytes} bytes using {blocks_used}/{blocks_available} complex blocks.".format(**result))
    print("Stego image written to {output}".format(**result))
    if result["encrypted"]:
        print("Payload was AES-encrypted with the provided key.")
    return 0


def cmd_decode(args: argparse.Namespace) -> int:
    result = decode(args.input, args.output, alpha=args.alpha, key=args.key)
    print("Extracted {message_bytes} bytes to {output}".format(**result))
    return 0


def cmd_capacity(args: argparse.Namespace) -> int:
    result = capacity(args.input, alpha=args.alpha)
    print("Complexity threshold alpha = {alpha}".format(**result))
    print("Noise-like 8x8 blocks: {embeddable_blocks}".format(**result))
    print("Approximate payload capacity: {payload_bytes} bytes".format(**result))
    return 0


def cmd_histogram(args: argparse.Namespace) -> int:
    r, g, b = histogram_data(args.input)
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, channel, color, name in zip(axes, (r, g, b), ("red", "green", "blue"), ("R", "G", "B")):
        ax.hist(channel.ravel(), bins=256, range=(0, 255), color=color, alpha=0.8)
        ax.set_title(f"{name} histogram")
        ax.set_xlim(0, 255)
    fig.suptitle(os.path.basename(args.input))
    fig.tight_layout()
    if args.output:
        fig.savefig(args.output, dpi=120)
        print(f"Histogram saved to {args.output}")
    else:
        plt.show()
    plt.close(fig)
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    arr = load_rgb(args.input)
    save_png(args.output, arr)
    print(f"Wrote lossless PNG: {args.output} ({arr.shape[1]}x{arr.shape[0]})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bit-Plane Complexity Segmentation steganography")
    sub = parser.add_subparsers(dest="command", required=True)

    enc = sub.add_parser("encode", help="Hide a file inside a vessel image")
    enc.add_argument("-i", "--input", required=True, help="Vessel / cover image")
    enc.add_argument("-m", "--message", required=True, help="Secret file to hide")
    enc.add_argument("-o", "--output", required=True, help="Output stego PNG")
    enc.add_argument("-a", "--alpha", type=float, default=DEFAULT_ALPHA, help="Complexity threshold (default 0.45)")
    enc.add_argument("--key", default=None, help="Optional AES passphrase")
    enc.set_defaults(func=cmd_encode)

    dec = sub.add_parser("decode", help="Extract a hidden file from a stego image")
    dec.add_argument("-i", "--input", required=True, help="Stego image")
    dec.add_argument("-o", "--output", required=True, help="Recovered secret file")
    dec.add_argument("-a", "--alpha", type=float, default=DEFAULT_ALPHA, help="Complexity threshold used at encode time")
    dec.add_argument("--key", default=None, help="AES passphrase if the payload was encrypted")
    dec.set_defaults(func=cmd_decode)

    cap = sub.add_parser("capacity", help="Estimate hiding capacity")
    cap.add_argument("-i", "--input", required=True, help="Vessel image")
    cap.add_argument("-a", "--alpha", type=float, default=DEFAULT_ALPHA)
    cap.set_defaults(func=cmd_capacity)

    hist = sub.add_parser("histogram", help="Plot RGB histograms of an image")
    hist.add_argument("-i", "--input", required=True)
    hist.add_argument("-o", "--output", default=None, help="Optional PNG path; shows a window if omitted")
    hist.set_defaults(func=cmd_histogram)

    conv = sub.add_parser("convert", help="Convert any image to lossless PNG")
    conv.add_argument("-i", "--input", required=True)
    conv.add_argument("-o", "--output", required=True)
    conv.set_defaults(func=cmd_convert)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
