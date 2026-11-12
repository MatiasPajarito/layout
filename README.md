# Randomlocke Tracker – Pokémon Ultra Sol/Luna (Gen 7)

Overlay/tracker local (Flask + HTML/CSS/JS) que lee el `main` de Citra/Lime3DS y muestra tu equipo en una cuadrícula 3×2.

## Uso

```powershell
pip install -r requirements.txt
python tools/build_data.py      # solo la 1ª vez: genera data/names.json y data/types.json (requiere internet)
python app.py --save "C:\ruta\a\tu\main"      # la ruta queda guardada en config.json
```

Abre http://127.0.0.1:5000 (en OBS: **Fuente > Navegador**; el fondo es transparente).
También puedes poner la ruta desde el botón ⚙.

URL: `?bg=1` fondo oscuro · `?controls=0` oculta ⚙ y los botones +/−.

Ruta típica en Citra para wsl (Ultra Sol `001b5000`, Ultra Luna `001b5100`):
`.../sdmc/Nintendo 3DS/00000000000000000000000000000000/00000000000000000000000000000000/title/00040000/001b5000/data/00000001/`

Ruta típica en Citra para powershell (Ultra Sol `001b5000`, Ultra Luna `001b5100`)
`sdmc\Nintendo 3DS\00000000000000000000000000000000\00000000000000000000000000000000\title\00040000\001b5000\data\00000001` 
## Estructura

| Pieza | Archivo |
|---|---|
| Backend Flask, file watcher (sondeo de mtime/tamaño cada 1 s), API de vidas | `app.py` |
| Lectura binaria USUM + descifrado PK7 (party en `0x1600`) | `save_reader.py` |
| Nombres ES/EN y tipos por Species ID (slugs: `agua`, `electrico`…) | `data/names.json`, `data/types.json` (`tools/build_data.py`) |
| Frontend | `templates/index.html`, `static/app.js`, `static/style.css` |
| Íconos de tipo (los pones tú; nombres en `static/tipos/LEEME.txt`) | `static/tipos/{tipo}.png` |
| Vidas persistentes | `config.json` |

API: `GET /api/state`, `POST /api/lives/increment`, `POST /api/lives/decrement`, `POST /api/lives {"delta"|"set"}`, `POST /api/config`.

## Pruebas

```powershell
python tests/test_app.py                       # round-trip con un save sintético cifrado
python tools/make_test_save.py test_main.bin   # save falso para ver la UI
```

## Notas

- El juego escribe el party solo al guardar la partida.
- Solo Ultra Sol/Luna (`main` de 0x6CC00 bytes). Las formas de Alola se detectan (tipos y sprite); otras formas usan el sprite base.
