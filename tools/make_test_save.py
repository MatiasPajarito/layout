"""Genera un `main` falso de USUM (con equipo cifrado) para probar la app sin el juego.

Uso:  python tools/make_test_save.py [salida]     (por defecto: test_main.bin)
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from save_reader import (BLOCK_POSITION, BLOCK_SIZE, PARTY_COUNT_OFFSET, PARTY_OFFSET,  # noqa: E402
                         PARTY_SLOT_SIZE, PARTY_STORED_SIZE, USUM_SAVE_SIZE, _crypt)

# Tabla de PKHeX para cifrar (BlockPositionInvert), independiente de la lógica de descifrado.
INVERT = [0, 1, 2, 4, 3, 5, 6, 7, 12, 18, 13, 19, 8, 10, 14, 20, 16, 22, 9, 11, 15, 21, 17, 23,
          0, 1, 2, 4, 3, 5, 6, 7]


def encrypt_pk7(plain: bytes) -> bytes:
    d = bytearray(plain)
    ec = struct.unpack_from("<I", d, 0)[0]
    sv = INVERT[(ec >> 13) & 31]
    orig = bytes(d[8:PARTY_STORED_SIZE])
    for i in range(4):
        src = BLOCK_POSITION[sv * 4 + i]
        d[8 + i * BLOCK_SIZE: 8 + (i + 1) * BLOCK_SIZE] = orig[src * BLOCK_SIZE:(src + 1) * BLOCK_SIZE]
    _crypt(d, 8, PARTY_STORED_SIZE, ec)
    _crypt(d, PARTY_STORED_SIZE, len(d), ec)
    return bytes(d)


def build_pk7(ec, species, item, ability, moves, nick, tid=12345, sid=54321, pid=0x12345678,
              level=50, egg=False, form=0):
    d = bytearray(PARTY_SLOT_SIZE)
    struct.pack_into("<I", d, 0, ec)
    struct.pack_into("<HH", d, 0x08, species, item)
    struct.pack_into("<HH", d, 0x0C, tid, sid)
    d[0x14] = ability
    struct.pack_into("<I", d, 0x18, pid)
    d[0x1D] = form << 3
    struct.pack_into("<4H", d, 0x5A, *moves)
    d[0x40:0x40 + 24] = nick.encode("utf-16-le")[:24].ljust(24, b"\x00")
    struct.pack_into("<I", d, 0x74, (1 << 31) | ((1 << 30) if egg else 0))
    d[0xEC] = level
    return encrypt_pk7(bytes(d))


def make_save(path: Path) -> None:
    buf = bytearray(USUM_SAVE_SIZE)
    tid, sid = 1000, 2000
    shiny_pid = ((tid ^ sid) << 16)  # tid^sid^pid_hi^pid_lo == 0 -> shiny
    team = [
        build_pk7(0xAABBCCDD, 785, 1, 1, [1, 2, 3, 4], "Koko", tid, sid),                 # Tapu Koko
        build_pk7(0x0001E000, 25, 50, 9, [85, 98, 0, 0], "Pika", tid, sid, shiny_pid),    # Pikachu shiny
        build_pk7(0xDEADBEEF, 800, 0, 232, [100, 200, 300, 400], "Necrozma", tid, sid),
        build_pk7(0x12345678, 6, 0, 66, [53, 0, 0, 0], "Charizard", tid, sid),
        build_pk7(0x00C0FFEE, 26, 0, 9, [85, 94, 0, 0], "Raichu", tid, sid, form=1),      # Raichu de Alola
        build_pk7(0x0BADF00D, 134, 0, 11, [55, 56, 57, 58], "Vaporeon", tid, sid),
    ]
    for i, mon in enumerate(team):
        off = PARTY_OFFSET + i * PARTY_SLOT_SIZE
        buf[off:off + PARTY_SLOT_SIZE] = mon
    buf[PARTY_COUNT_OFFSET] = len(team)
    path.write_bytes(buf)


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "test_main.bin")
    make_save(out)
    print("Creado", out)
