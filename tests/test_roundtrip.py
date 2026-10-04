"""Encode/decode roundtrips for the BPCS implementation."""

from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bpcs_core import decode_file, encode_file

VESSEL = ROOT / "files" / "vessel.png"
MESSAGE = ROOT / "files" / "message.txt"


def test_plain_roundtrip(tmp: Path) -> None:
    stego = tmp / "stego.png"
    out = tmp / "out.bin"
    encode_file(str(VESSEL), str(MESSAGE), str(stego))
    decode_file(str(stego), str(out))
    assert out.read_bytes() == MESSAGE.read_bytes()


def test_aes_roundtrip(tmp: Path) -> None:
    stego = tmp / "stego_aes.png"
    out = tmp / "out.bin"
    encode_file(str(VESSEL), str(MESSAGE), str(stego), key="shared-secret")
    decode_file(str(stego), str(out), key="shared-secret")
    assert out.read_bytes() == MESSAGE.read_bytes()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_plain_roundtrip(tmp)
        test_aes_roundtrip(tmp)
    print("roundtrip tests passed")
