# BPCS Steganography

Bit-Plane Complexity Segmentation (BPCS) steganography  *Steganography Using Bit-Plane Complexity Segmentation Technique* (Adita Srivastava, 14BCB0018).

Noise-like 8×8 regions on Canonical Gray Coded bit-planes are replaced with secret data. Typical hiding capacity on a 24-bit color image is around 40–50%, much higher than LSB methods (~5–15%).

## Features

- Segment each bit-plane into informative vs noise-like regions
- Black–white border complexity measure (max 112 transitions on an 8×8 block)
- Conjugation so simple secret blocks become complex enough to embed
- CGC bit-planes instead of pure binary code
- Optional AES-256 encryption of the payload before embedding
- Histogram, PNG conversion, and capacity estimation

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Hide a file in a vessel image:

```bash
python bpcs.py encode -i files/vessel.png -m files/message.txt -o stegg/encoded.png
```

Extract it (use the same complexity threshold `-a`):

```bash
python bpcs.py decode -i stegg/encoded.png -a 0.45 -o stegg/message_decoded.txt
```

Optional AES passphrase:

```bash
python bpcs.py encode -i files/vessel.png -m files/message.txt -o stegg/encoded.png --key "shared-secret"
python bpcs.py decode -i stegg/encoded.png -o stegg/message_decoded.txt --key "shared-secret"
```

Other tools:

```bash
python bpcs.py capacity -i files/vessel.png -a 0.45
python bpcs.py histogram -i files/vessel.png -o stegg/histogram.png
python bpcs.py convert -i photo.jpg -o files/vessel.png
```

Default complexity threshold `alpha` is `0.45`. Encode and decode must use the same value.

```bash
python tests/test_roundtrip.py
```

## How it works

1. Convert the vessel image from PBC to CGC and keep it as PNG (lossless).
2. Split RGB into 24 bit-planes, then into 8×8 blocks.
3. Complexity of a block is the count of 0↔1 transitions horizontally and vertically, divided by 112.
4. Blocks with complexity ≥ `alpha` are embedding slots.
5. Secret bytes (optionally AES-encrypted) are packed into 8×8 patterns. Simple patterns are conjugated with a checkerboard.
6. Convert CGC back to PBC and save the stego PNG.

BPCS is a high-capacity hiding method, not a robust watermark: lossy compression or filtering will destroy the payload.

## Project layout

| Path | Role |
| --- | --- |
| `bpcs.py` | Command-line interface |
| `bpcs_core.py` | CGC, complexity, conjugation, embed/extract |
| `bpcs_steg_encode.py` | Encoder |
| `bpcs_steg_decode.py` | Decoder |
| `bpcs_steg_capacity.py` | Capacity estimate |
| `files/` | Sample vessel image and message |
| `stegg/` | Encode/decode output |
