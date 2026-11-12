"""Genera data/names.json (nombres ES/EN) y data/types.json (tipos por Species ID).

Nombres: listas de texto de PKHeX. Tipos: CSV de PokeAPI, guardados como slugs en español sin
tildes (los mismos nombres que los íconos static/tipos/{slug}.png).
Solo hace falta ejecutarlo una vez (requiere internet).  Uso:  python tools/build_data.py
"""
import csv
import io
import json
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

PKHEX = "https://raw.githubusercontent.com/kwsch/PKHeX/master/PKHeX.Core/Resources/text/"
NAME_FILES = {
    "species": "other/{l}/text_Species_{l}.txt",
    "moves": "other/{l}/text_Moves_{l}.txt",
    "abilities": "other/{l}/text_Abilities_{l}.txt",
    "items": "items/text_Items_{l}.txt",
}

POKEAPI = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/"
EN_TO_ES = {
    "normal": "normal", "fire": "fuego", "water": "agua", "electric": "electrico",
    "grass": "planta", "ice": "hielo", "fighting": "lucha", "poison": "veneno",
    "ground": "tierra", "flying": "volador", "psychic": "psiquico", "bug": "bicho",
    "rock": "roca", "ghost": "fantasma", "dragon": "dragon", "dark": "siniestro",
    "steel": "acero", "fairy": "hada",
}
MAX_SPECIES = 1025  # los pokemon_id <= 1025 son las formas base (= Species ID)


def get(url: str) -> str:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read().decode("utf-8-sig")


def build_names() -> None:
    out = {}
    for lang in ("es", "en"):
        out[lang] = {
            k: get(PKHEX + v.format(l=lang)).replace("\r", "").split("\n") for k, v in NAME_FILES.items()
        }
    (DATA / "names.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("names.json OK")


def build_types() -> None:
    rows = lambda n: list(csv.DictReader(io.StringIO(get(POKEAPI + n))))  # noqa: E731
    type_names = {int(r["id"]): r["identifier"] for r in rows("types.csv")}
    by_species: dict[int, dict[int, str]] = {}
    for r in rows("pokemon_types.csv"):
        pid = int(r["pokemon_id"])
        if pid <= MAX_SPECIES:
            by_species.setdefault(pid, {})[int(r["slot"])] = EN_TO_ES[type_names[int(r["type_id"])]]
    out = {str(p): [s.get(1), s.get(2)] for p, s in sorted(by_species.items())}
    assert len(out) == MAX_SPECIES, len(out)
    (DATA / "types.json").write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print("types.json OK", len(out), "especies")


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    build_names()
    build_types()
