"""BPCS core: CGC bit-planes, complexity, conjugation, embed/extract."""

from __future__ import annotations

import math
import struct
from typing import Iterable, List, Optional, Tuple

import numpy as np
from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
from PIL import Image

BLOCK = 8
MAX_COMPLEXITY = 2 * BLOCK * (BLOCK - 1)  # 112
MAGIC = b"BPCS"
HEADER_FORMAT = ">4sBI"  # magic, flags, payload length
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
DEFAULT_ALPHA = 0.45
AES_SALT_LEN = 16
AES_IV_LEN = 16
AES_KEY_LEN = 32
FLAG_ENCRYPTED = 0x01

# Data bits live in every cell except (0, 0), which stores the conjugation flag.
DATA_POSITIONS = [
    (r, c) for r in range(BLOCK) for c in range(BLOCK) if (r, c) != (0, 0)
]
BITS_PER_BLOCK = len(DATA_POSITIONS)  # 63


def pbc_to_cgc(arr: np.ndarray) -> np.ndarray:
    return (arr ^ (arr >> 1)).astype(np.uint8)


def cgc_to_pbc(arr: np.ndarray) -> np.ndarray:
    out = arr.astype(np.uint16).copy()
    shift = 1
    while shift < 8:
        out ^= out >> shift
        shift *= 2
    return out.astype(np.uint8)


def complexity(block: np.ndarray) -> float:
    h = np.sum(block[:, :-1] != block[:, 1:])
    v = np.sum(block[:-1, :] != block[1:, :])
    return float(h + v) / MAX_COMPLEXITY


def checkerboard(size: int = BLOCK) -> np.ndarray:
    i, j = np.indices((size, size))
    return ((i + j) % 2).astype(np.uint8)


def conjugate(block: np.ndarray) -> np.ndarray:
    return (block ^ checkerboard(block.shape[0])).astype(np.uint8)


def load_rgb(path: str) -> np.ndarray:
    image = Image.open(path).convert("RGB")
    return np.array(image, dtype=np.uint8)


def save_png(path: str, arr: np.ndarray) -> None:
    Image.fromarray(arr, mode="RGB").save(path, format="PNG")


def pad_to_block(arr: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int]]:
    h, w = arr.shape[:2]
    ph = (BLOCK - h % BLOCK) % BLOCK
    pw = (BLOCK - w % BLOCK) % BLOCK
    if ph or pw:
        arr = np.pad(arr, ((0, ph), (0, pw), (0, 0)), mode="edge")
    return arr, (h, w)


def iter_bitplanes(cgc: np.ndarray) -> Iterable[Tuple[int, int, np.ndarray]]:
    """Yield (channel, bit, plane) from LSB to MSB, R then G then B."""
    for channel in range(cgc.shape[2]):
        for bit in range(8):
            plane = ((cgc[:, :, channel] >> bit) & 1).astype(np.uint8)
            yield channel, bit, plane


def write_bitplane(cgc: np.ndarray, channel: int, bit: int, plane: np.ndarray) -> None:
    mask = np.uint8(1 << bit)
    cgc[:, :, channel] = (cgc[:, :, channel] & ~mask) | (plane.astype(np.uint8) * mask)


def iter_blocks(plane: np.ndarray) -> Iterable[Tuple[int, int, np.ndarray]]:
    h, w = plane.shape
    for row in range(0, h, BLOCK):
        for col in range(0, w, BLOCK):
            yield row, col, plane[row : row + BLOCK, col : col + BLOCK]


def embeddable_block_coords(cgc: np.ndarray, alpha: float) -> List[Tuple[int, int, int, int]]:
    coords = []
    for channel, bit, plane in iter_bitplanes(cgc):
        for row, col, block in iter_blocks(plane):
            if complexity(block) >= alpha:
                coords.append((channel, bit, row, col))
    return coords


def bits_from_bytes(data: bytes) -> List[int]:
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def bytes_from_bits(bits: List[int]) -> bytes:
    pad = (-len(bits)) % 8
    if pad:
        bits = bits + [0] * pad
    out = bytearray()
    for i in range(0, len(bits), 8):
        value = 0
        for bit in bits[i : i + 8]:
            value = (value << 1) | int(bit)
        out.append(value)
    return bytes(out)


def pack_block(bits63: List[int], alpha: float) -> np.ndarray:
    block = np.zeros((BLOCK, BLOCK), dtype=np.uint8)
    for bit, (r, c) in zip(bits63, DATA_POSITIONS):
        block[r, c] = bit
    conjugated = 0
    if complexity(block) < alpha:
        block = conjugate(block)
        conjugated = 1
    block[0, 0] = conjugated
    return block


def unpack_block(block: np.ndarray) -> List[int]:
    work = block.copy()
    flag = int(work[0, 0])
    work[0, 0] = 0
    if flag:
        work = conjugate(work)
        work[0, 0] = 0
    return [int(work[r, c]) for r, c in DATA_POSITIONS]


def encrypt_payload(plaintext: bytes, passphrase: str) -> bytes:
    salt = get_random_bytes(AES_SALT_LEN)
    key = PBKDF2(passphrase, salt, dkLen=AES_KEY_LEN, count=200_000, hmac_hash_module=SHA256)
    iv = get_random_bytes(AES_IV_LEN)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    pad_len = 16 - (len(plaintext) % 16)
    padded = plaintext + bytes([pad_len] * pad_len)
    return salt + iv + cipher.encrypt(padded)


def decrypt_payload(blob: bytes, passphrase: str) -> bytes:
    if len(blob) < AES_SALT_LEN + AES_IV_LEN + 16:
        raise ValueError("Encrypted payload is truncated.")
    salt = blob[:AES_SALT_LEN]
    iv = blob[AES_SALT_LEN : AES_SALT_LEN + AES_IV_LEN]
    ciphertext = blob[AES_SALT_LEN + AES_IV_LEN :]
    key = PBKDF2(passphrase, salt, dkLen=AES_KEY_LEN, count=200_000, hmac_hash_module=SHA256)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded = cipher.decrypt(ciphertext)
    pad_len = padded[-1]
    if pad_len < 1 or pad_len > 16 or padded[-pad_len:] != bytes([pad_len] * pad_len):
        raise ValueError("AES decryption failed. Check the key.")
    return padded[:-pad_len]


def build_secret_stream(message: bytes, key: Optional[str]) -> bytes:
    flags = 0
    payload = message
    if key:
        flags |= FLAG_ENCRYPTED
        payload = encrypt_payload(message, key)
    return struct.pack(HEADER_FORMAT, MAGIC, flags, len(payload)) + payload


def parse_secret_stream(raw: bytes, key: Optional[str]) -> bytes:
    if len(raw) < HEADER_SIZE:
        raise ValueError("Hidden data is missing or the complexity threshold does not match encoding.")
    magic, flags, length = struct.unpack(HEADER_FORMAT, raw[:HEADER_SIZE])
    if magic != MAGIC:
        raise ValueError("No BPCS payload found. Check the image and the -a threshold.")
    payload = raw[HEADER_SIZE : HEADER_SIZE + length]
    if len(payload) != length:
        raise ValueError("Hidden payload is incomplete. Try the same -a value used for encoding.")
    if flags & FLAG_ENCRYPTED:
        if not key:
            raise ValueError("This stego image was encrypted. Pass --key to decode.")
        return decrypt_payload(payload, key)
    return payload


def capacity_bytes(image_path: str, alpha: float = DEFAULT_ALPHA) -> Tuple[int, int, int]:
    arr, _orig = pad_to_block(load_rgb(image_path))
    cgc = pbc_to_cgc(arr)
    n_blocks = len(embeddable_block_coords(cgc, alpha))
    usable_bits = n_blocks * BITS_PER_BLOCK
    usable_bytes = usable_bits // 8
    payload_bytes = max(0, usable_bytes - HEADER_SIZE)
    return n_blocks, usable_bytes, payload_bytes


def histogram_data(image_path: str):
    arr = load_rgb(image_path)
    return arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]


def encode_file(
    vessel_path: str,
    message_path: str,
    output_path: str,
    alpha: float = DEFAULT_ALPHA,
    key: Optional[str] = None,
) -> dict:
    message = open(message_path, "rb").read()
    arr = load_rgb(vessel_path)
    orig_h, orig_w = arr.shape[:2]
    padded, _ = pad_to_block(arr)
    cgc = pbc_to_cgc(padded)
    coords = embeddable_block_coords(cgc, alpha)

    stream = build_secret_stream(message, key)
    bits = bits_from_bytes(stream)
    needed_blocks = math.ceil(len(bits) / BITS_PER_BLOCK)
    if needed_blocks > len(coords):
        _, _, payload_bytes = capacity_bytes(vessel_path, alpha)
        raise ValueError(
            f"Message is too large ({len(message)} bytes). "
            f"Vessel capacity at alpha={alpha} is about {payload_bytes} bytes."
        )

    while len(bits) % BITS_PER_BLOCK:
        bits.append(0)

    planes = {(ch, bit): plane.copy() for ch, bit, plane in iter_bitplanes(cgc)}
    for i, (channel, bit, row, col) in enumerate(coords[:needed_blocks]):
        chunk = bits[i * BITS_PER_BLOCK : (i + 1) * BITS_PER_BLOCK]
        planes[(channel, bit)][row : row + BLOCK, col : col + BLOCK] = pack_block(chunk, alpha)

    stego_cgc = cgc.copy()
    for (channel, bit), plane in planes.items():
        write_bitplane(stego_cgc, channel, bit, plane)

    stego = cgc_to_pbc(stego_cgc)[:orig_h, :orig_w]
    save_png(output_path, stego)
    return {
        "message_bytes": len(message),
        "blocks_used": needed_blocks,
        "blocks_available": len(coords),
        "alpha": alpha,
        "encrypted": bool(key),
        "output": output_path,
    }


def decode_file(
    stego_path: str,
    output_path: str,
    alpha: float = DEFAULT_ALPHA,
    key: Optional[str] = None,
) -> dict:
    arr = load_rgb(stego_path)
    padded, _ = pad_to_block(arr)
    cgc = pbc_to_cgc(padded)
    coords = embeddable_block_coords(cgc, alpha)
    planes = {(ch, bit): plane for ch, bit, plane in iter_bitplanes(cgc)}

    bits: List[int] = []
    needed_bits = None
    for channel, bit, row, col in coords:
        block = planes[(channel, bit)][row : row + BLOCK, col : col + BLOCK]
        bits.extend(unpack_block(block))
        if needed_bits is None and len(bits) >= HEADER_SIZE * 8:
            header = bytes_from_bits(bits[: HEADER_SIZE * 8])
            magic, _flags, length = struct.unpack(HEADER_FORMAT, header)
            if magic == MAGIC:
                needed_bits = (HEADER_SIZE + length) * 8
        if needed_bits is not None and len(bits) >= needed_bits:
            bits = bits[:needed_bits]
            break

    message = parse_secret_stream(bytes_from_bits(bits), key)
    with open(output_path, "wb") as handle:
        handle.write(message)
    return {
        "output": output_path,
        "message_bytes": len(message),
        "alpha": alpha,
    }
