"""Randomlocke Tracker / Overlay para Pokémon Ultra Sol/Luna (Citra / Lime3DS).

Uso:
    python app.py                     # usa save_path de config.json
    python app.py --save "C:\\ruta\\al\\main"
Luego abre http://127.0.0.1:5000  (en OBS: Fuente > Navegador con esa URL).
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from save_reader import SaveReadError, read_party

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
DEFAULT_CONFIG = {
    "lives": 3,
    "save_path": "",
    "language": "es",  # "es" | "en"
    "host": "127.0.0.1",
    "port": 5000,
}

# --------------------------------------------------------------------------- #
# Configuración persistente (config.json)
# --------------------------------------------------------------------------- #
_config_lock = threading.Lock()


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
    return cfg


def save_config(cfg: dict) -> None:
    tmp = CONFIG_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, CONFIG_FILE)  # escritura atómica


config = load_config()
if not CONFIG_FILE.exists():
    save_config(config)

# --------------------------------------------------------------------------- #
# Estado compartido + File Watcher
# --------------------------------------------------------------------------- #
state_lock = threading.Lock()
state = {
    "version": 0,
    "team": [],
    "error": None,
    "last_update": None,
    "save_found": False,
}
_reload_event = threading.Event()


def _set_state(**kwargs) -> None:
    with state_lock:
        changed = any(state.get(k) != v for k, v in kwargs.items() if k != "last_update")
        state.update(kwargs)
        if changed:
            state["version"] += 1


def reload_save() -> None:
    path = config.get("save_path", "")
    if not path:
        _set_state(team=[], error="Configura la ruta del archivo `main` (⚙).", save_found=False)
        return
    if not Path(path).is_file():
        _set_state(team=[], error=f"No se encuentra el archivo: {path}", save_found=False)
        return
    try:
        team = [m.to_dict() for m in read_party(path, config.get("language", "es"))]
        _set_state(team=team, error=None, save_found=True, last_update=time.strftime("%H:%M:%S"))
    except SaveReadError as e:
        _set_state(error=str(e), save_found=True)
    except OSError as e:  # archivo bloqueado mientras Citra escribe -> se reintenta
        _set_state(error=f"No se pudo leer el archivo: {e}", save_found=True)


def watcher_loop(poll_interval: float = 1.0) -> None:
    """Vigila mtime/tamaño del save y lo relee cuando cambia."""
    last_sig = None
    last_path = None
    while True:
        path = config.get("save_path", "")
        sig = None
        try:
            if path:
                st = os.stat(path)
                sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            sig = None

        forced = _reload_event.is_set()
        if forced or sig != last_sig or path != last_path:
            _reload_event.clear()
            last_sig, last_path = sig, path
            if sig is not None:
                time.sleep(0.3)  # deja que el emulador termine de escribir
            reload_save()
        time.sleep(poll_interval)


# --------------------------------------------------------------------------- #
# Flask
# --------------------------------------------------------------------------- #
app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def api_state():
    with state_lock:
        snap = dict(state)
    snap["lives"] = config["lives"]
    snap["save_path"] = config.get("save_path", "")
    snap["language"] = config.get("language", "es")
    return jsonify(snap)


@app.post("/api/lives")
def api_lives():
    body = request.get_json(silent=True) or {}
    with _config_lock:
        if "set" in body:
            config["lives"] = int(body["set"])
        else:
            config["lives"] = config["lives"] + int(body.get("delta", 0))
        config["lives"] = max(0, config["lives"])
        save_config(config)
        lives = config["lives"]
    return jsonify({"lives": lives})


@app.post("/api/lives/increment")
def api_lives_inc():
    with _config_lock:
        config["lives"] += 1
        save_config(config)
        return jsonify({"lives": config["lives"]})


@app.post("/api/lives/decrement")
def api_lives_dec():
    with _config_lock:
        config["lives"] = max(0, config["lives"] - 1)
        save_config(config)
        return jsonify({"lives": config["lives"]})


@app.post("/api/config")
def api_config():
    body = request.get_json(silent=True) or {}
    with _config_lock:
        if "save_path" in body:
            config["save_path"] = str(body["save_path"]).strip().strip('"')
        if body.get("language") in ("es", "en"):
            config["language"] = body["language"]
        save_config(config)
    _reload_event.set()
    return jsonify({"ok": True})


def main() -> None:
    parser = argparse.ArgumentParser(description="Randomlocke Tracker USUM")
    parser.add_argument("--save", help="Ruta al archivo `main` del save")
    parser.add_argument("--port", type=int, help="Puerto HTTP")
    args = parser.parse_args()

    if args.save:
        config["save_path"] = args.save.strip('"')
        save_config(config)
    port = args.port or int(config.get("port", 5000))

    threading.Thread(target=watcher_loop, daemon=True).start()
    print(f"Tracker en http://{config['host']}:{port}")
    app.run(host=config["host"], port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
