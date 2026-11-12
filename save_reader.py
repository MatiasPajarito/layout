"""Lector del archivo `main` de Pokémon Ultra Sol / Ultra Luna (Gen 7, formato PK7).

Estructura (según PKHeX / Project Pokémon):
  * El save `main` de USUM mide 0x6CC00 bytes y NO está cifrado a nivel de archivo.
  * Bloque 04 "PokePartySave": offset 0x1600, longitud 0x61C.
      - 6 slots de 0x104 (260) bytes: PK7 de 232 bytes + 28 bytes de stats de party.
      - Byte en 0x1600 + 6*0x104 = cantidad de Pokémon en el equipo.
  * Cada Pokémon va cifrado: XOR con un LCG de 16 bits sembrado con la
    Encryption Constant (EC) y con los 4 bloques de 56 bytes barajados según
    sv = (EC >> 13) & 31.
"""
from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

USUM_SAVE_SIZE = 0x6CC00
PARTY_OFFSET = 0x1600
PARTY_SLOT_SIZE = 0x104
PARTY_STORED_SIZE = 0xE8  # 232 bytes (PK7 "stored")
PARTY_MAX = 6
PARTY_COUNT_OFFSET = PARTY_OFFSET + PARTY_MAX * PARTY_SLOT_SIZE
BLOCK_SIZE = 56

# Orden de bloques por shuffle value (idéntico a PKHeX.Core PokeCrypto.BlockPosition).
BLOCK_POSITION = [
    0, 1, 2, 3, 0, 1, 3, 2, 0, 2, 1, 3, 0, 3, 1, 2,
    0, 2, 3, 1, 0, 3, 2, 1, 1, 0, 2, 3, 1, 0, 3, 2,
    2, 0, 1, 3, 3, 0, 1, 2, 2, 0, 3, 1, 3, 0, 2, 1,
    1, 2, 0, 3, 1, 3, 0, 2, 2, 1, 0, 3, 3, 1, 0, 2,
    2, 3, 0, 1, 3, 2, 0, 1, 1, 2, 3, 0, 1, 3, 2, 0,
    2, 1, 3, 0, 3, 1, 2, 0, 2, 3, 1, 0, 3, 2, 1, 0,
    0, 1, 2, 3, 0, 1, 3, 2, 0, 2, 1, 3, 0, 3, 1, 2,
    0, 2, 3, 1, 0, 3, 2, 1, 1, 0, 2, 3, 1, 0, 3, 2,
]

DATA_DIR = Path(__file__).resolve().parent / "data"
_NAMES_FILE = DATA_DIR / "names.json"
_TYPES_FILE = DATA_DIR / "types.json"
_NAMES: dict = {}
_TYPES: dict = {}

# Formas de Alola (form == 1 en el save): cambian de tipo respecto a la especie base.
ALOLA_TYPES = {
    19: ["siniestro", "normal"], 20: ["siniestro", "normal"],
    26: ["electrico", "psiquico"],
    27: ["hielo", "acero"], 28: ["hielo", "acero"],
    37: ["hielo", None], 38: ["hielo", "hada"],
    50: ["tierra", "acero"], 51: ["tierra", "acero"],
    52: ["siniestro", None], 53: ["siniestro", None],
    74: ["roca", "electrico"], 75: ["roca", "electrico"], 76: ["roca", "electrico"],
    88: ["veneno", "siniestro"], 89: ["veneno", "siniestro"],
    103: ["planta", "dragon"],
    105: ["fuego", "fantasma"],
}
# Sprite de PokéAPI de cada forma de Alola (species_id -> id en /sprites/pokemon/).
ALOLA_SPRITE_IDS = {
    19: 10091, 20: 10092, 26: 10100, 27: 10101, 28: 10102, 37: 10103, 38: 10104,
    50: 10105, 51: 10106, 52: 10107, 53: 10108, 74: 10109, 75: 10110, 76: 10111,
    88: 10112, 89: 10113, 103: 10114, 105: 10115,
}


class SaveReadError(Exception):
    """El archivo no se pudo interpretar como un save de Ultra Sol/Luna."""


# --------------------------------------------------------------------------- #
# Cifrado PK7
# --------------------------------------------------------------------------- #
def _crypt(data: bytearray, start: int, end: int, seed: int) -> None:
    for i in range(start, end, 2):
        seed = (0x41C64E6D * seed + 0x6073) & 0xFFFFFFFF
        xor = seed >> 16
        data[i] ^= xor & 0xFF
        data[i + 1] ^= (xor >> 8) & 0xFF


def decrypt_pk7(raw: bytes) -> bytearray:
    """Descifra un Pokémon de party (260 bytes) o almacenado (232 bytes)."""
    data = bytearray(raw)
    ec = struct.unpack_from("<I", data, 0)[0]
    sv = (ec >> 13) & 31

    _crypt(data, 8, PARTY_STORED_SIZE, ec)
    if len(data) > PARTY_STORED_SIZE:
        _crypt(data, PARTY_STORED_SIZE, len(data), ec)

    original = bytes(data[8:PARTY_STORED_SIZE])
    for i in range(4):
        src = BLOCK_POSITION[sv * 4 + i]
        data[8 + i * BLOCK_SIZE: 8 + (i + 1) * BLOCK_SIZE] = original[src * BLOCK_SIZE:(src + 1) * BLOCK_SIZE]
    return data


# --------------------------------------------------------------------------- #
# Nombres y tipos
# --------------------------------------------------------------------------- #
def _names(lang: str) -> dict:
    global _NAMES
    if not _NAMES:
        _NAMES = json.loads(_NAMES_FILE.read_text(encoding="utf-8")) if _NAMES_FILE.exists() else {"es": {}, "en": {}}
    return _NAMES.get(lang) or _NAMES.get("es") or {}


def _lookup(lang: str, kind: str, idx: int) -> str:
    table = _names(lang).get(kind, [])
    if 0 <= idx < len(table) and table[idx]:
        return table[idx]
    return f"#{idx}" if idx else ""


def get_types(species_id: int, form: int = 0) -> list:
    """Devuelve [tipo1, tipo2|None] (slugs en español) a partir del Species ID."""
    global _TYPES
    if not _TYPES:
        _TYPES = json.loads(_TYPES_FILE.read_text(encoding="utf-8")) if _TYPES_FILE.exists() else {"_": 0}
    if form == 1 and species_id in ALOLA_TYPES:
        return list(ALOLA_TYPES[species_id])
    return list(_TYPES.get(str(species_id), [None, None]))


# --------------------------------------------------------------------------- #
# Modelo
# --------------------------------------------------------------------------- #
@dataclass
class Pokemon:
    slot: int
    species_id: int
    species: str
    nickname: str
    ability_id: int
    ability: str
    item_id: int
    item: str
    moves: list[str] = field(default_factory=list)
    move_ids: list[int] = field(default_factory=list)
    shiny: bool = False
    is_egg: bool = False
    level: int = 0
    form: int = 0
    is_alola: bool = False
    sprite_id: int = 0  # id para PokéAPI (forma de Alola o Species ID)
    gender: int = 0  # 0 macho, 1 hembra, 2 sin género
    types: list = field(default_factory=lambda: [None, None])  # [tipo1, tipo2|None]

    def to_dict(self) -> dict:
        return asdict(self)


def _parse_pokemon(slot: int, raw: bytes, lang: str) -> Optional[Pokemon]:
    if len(raw) < PARTY_SLOT_SIZE or not any(raw[:8]):
        return None
    d = decrypt_pk7(raw)

    species_id = struct.unpack_from("<H", d, 0x08)[0]
    if species_id == 0:
        return None
    if species_id > 1000:  # basura -> no es un PK7 válido
        raise SaveReadError(f"Species ID inválido ({species_id}) en el slot {slot + 1}.")

    item_id = struct.unpack_from("<H", d, 0x0A)[0]
    tid, sid = struct.unpack_from("<HH", d, 0x0C)
    ability_id = d[0x14]
    pid = struct.unpack_from("<I", d, 0x18)[0]
    flags = d[0x1D]
    gender = (flags >> 1) & 3
    form = flags >> 3

    nick_raw = bytes(d[0x40:0x58])
    nickname = nick_raw.decode("utf-16-le", errors="ignore").split("\x00")[0]
    nickname = "".join(c for c in nickname if not 0xE000 <= ord(c) <= 0xF8FF) or nickname

    move_ids = list(struct.unpack_from("<4H", d, 0x5A))
    iv32 = struct.unpack_from("<I", d, 0x74)[0]
    is_egg = bool((iv32 >> 30) & 1)

    level = d[0xEC] if len(d) > 0xEC and 1 <= d[0xEC] <= 100 else 0
    shiny = ((tid ^ sid ^ (pid >> 16) ^ (pid & 0xFFFF)) < 16)

    is_alola = form == 1 and species_id in ALOLA_TYPES
    species = _lookup(lang, "species", species_id)
    return Pokemon(
        slot=slot,
        species_id=species_id,
        species=species,
        nickname=nickname or species,
        ability_id=ability_id,
        ability=_lookup(lang, "abilities", ability_id),
        item_id=item_id,
        item=_lookup(lang, "items", item_id) if item_id else "",
        moves=[_lookup(lang, "moves", m) for m in move_ids if m],
        move_ids=[m for m in move_ids if m],
        shiny=shiny,
        is_egg=is_egg,
        level=level,
        form=form,
        is_alola=is_alola,
        sprite_id=ALOLA_SPRITE_IDS[species_id] if is_alola else species_id,
        gender=gender,
        types=get_types(species_id, form),
    )


def read_party(path: str | Path, lang: str = "es") -> list[Pokemon]:
    """Lee el archivo `main` y devuelve los Pokémon del equipo (máx. 6)."""
    data = Path(path).read_bytes()
    if len(data) != USUM_SAVE_SIZE:
        raise SaveReadError(
            f"Tamaño inesperado ({len(data):#x} bytes). Un `main` de Ultra Sol/Luna "
            f"debe medir {USUM_SAVE_SIZE:#x} bytes."
        )
    count = data[PARTY_COUNT_OFFSET]
    if count > PARTY_MAX:
        raise SaveReadError(f"Cantidad de Pokémon en el equipo inválida ({count}).")

    team: list[Pokemon] = []
    for slot in range(count):
        off = PARTY_OFFSET + slot * PARTY_SLOT_SIZE
        mon = _parse_pokemon(slot, data[off:off + PARTY_SLOT_SIZE], lang)
        if mon:
            team.append(mon)
    return team
