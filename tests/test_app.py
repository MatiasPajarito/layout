"""Pruebas: python tests/test_app.py"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from make_test_save import make_save  # noqa: E402
from save_reader import SaveReadError, get_types, read_party  # noqa: E402


def test_reader(path):
    team = read_party(path, "es")
    assert len(team) == 6, team
    koko, pika, necro, zard, alola, vapo = team
    assert (koko.species_id, koko.nickname, koko.species) == (785, "Koko", "Tapu Koko"), koko
    assert koko.move_ids == [1, 2, 3, 4] and not koko.shiny and koko.level == 50
    assert pika.species_id == 25 and pika.shiny and pika.move_ids == [85, 98], pika
    assert necro.species_id == 800 and necro.move_ids == [100, 200, 300, 400]
    assert zard.species_id == 6 and zard.nickname == "Charizard"
    assert koko.types == ["electrico", "hada"], koko.types
    assert pika.types == ["electrico", None] and necro.types == ["psiquico", None]
    assert zard.types == ["fuego", "volador"]
    assert alola.is_alola and alola.types == ["electrico", "psiquico"] and alola.sprite_id == 10100
    assert not zard.is_alola and zard.sprite_id == 6
    assert vapo.types == ["agua", None]
    assert get_types(26) == ["electrico", None] and get_types(1) == ["planta", "veneno"]
    print("reader OK:", [(m.nickname, m.species, m.ability, m.item, m.moves, m.types, m.shiny) for m in team])


def test_wrong_size():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"\x00" * 100)
    try:
        read_party(f.name)
    except SaveReadError as e:
        print("tamaño inválido OK:", e)
    else:
        raise AssertionError("debió fallar")


def test_api(path, tmp):
    import app as appmod
    appmod.CONFIG_FILE = tmp / "config.json"
    appmod.config.update(lives=3, save_path=str(path))
    appmod.save_config(appmod.config)
    appmod.reload_save()
    c = appmod.app.test_client()
    s = c.get("/api/state").get_json()
    assert len(s["team"]) == 6 and s["lives"] == 3 and s["error"] is None
    assert c.post("/api/lives/increment").get_json()["lives"] == 4
    assert c.post("/api/lives/decrement").get_json()["lives"] == 3
    assert c.post("/api/lives", json={"delta": -10}).get_json()["lives"] == 0  # no baja de 0
    assert json.loads((tmp / "config.json").read_text())["lives"] == 0          # persistido
    assert c.get("/").status_code == 200
    print("api OK")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        save = d / "main"
        make_save(save)
        test_reader(save)
        test_wrong_size()
        test_api(save, d)
    print("TODO OK")
