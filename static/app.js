(() => {
  "use strict";

  // Sprites desde PokéAPI (sin alojar imágenes localmente)
  const SPRITE_BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/";
  const spriteUrl = (id, shiny) => SPRITE_BASE + (shiny ? "shiny/" : "") + id + ".png";

  const params = new URLSearchParams(location.search);
  if (params.get("bg") === "1") document.body.classList.add("preview");
  if (params.get("controls") === "0") document.body.classList.add("nocontrols");

  const $ = (id) => document.getElementById(id);
  const teamEl = $("team");
  const statusEl = $("status");
  const livesEl = $("lives-value");
  let version = -1;

  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;   // textContent: seguro con motes raros
    return e;
  };

  // ---- Colores por tipo (clave = slug del tipo = nombre del PNG en /static/tipos/) ----
  const TYPE_COLORS = {
    normal: "#A8A77A", fuego: "#EE8130", agua: "#6390F0", electrico: "#F7D02C",
    planta: "#7AC74C", hielo: "#96D9D6", lucha: "#C22E28", veneno: "#A33EA1",
    tierra: "#E2BF65", volador: "#A98FF3", psiquico: "#F95587", bicho: "#A6B91A",
    roca: "#B6A136", fantasma: "#735797", dragon: "#6F35FC", siniestro: "#705746",
    acero: "#B7B7CE", hada: "#D685AD",
  };
  const TYPE_LABELS = {
    normal: "Normal", fuego: "Fuego", agua: "Agua", electrico: "Eléctrico", planta: "Planta",
    hielo: "Hielo", lucha: "Lucha", veneno: "Veneno", tierra: "Tierra", volador: "Volador",
    psiquico: "Psíquico", bicho: "Bicho", roca: "Roca", fantasma: "Fantasma", dragon: "Dragón",
    siniestro: "Siniestro", acero: "Acero", hada: "Hada",
  };
  const NEUTRAL = "#5b6275";

  // Mezcla un color #rrggbb con blanco (amt>0) o negro (amt<0)
  function shade(hex, amt) {
    const n = parseInt(hex.slice(1), 16);
    const t = amt < 0 ? 0 : 255, a = Math.abs(amt);
    const ch = [n >> 16, (n >> 8) & 255, n & 255].map((c) => Math.round(c + (t - c) * a));
    return `rgb(${ch[0]}, ${ch[1]}, ${ch[2]})`;
  }

  // Un tipo: gradiente con dos tonos del mismo elemento.
  // Dos tipos: diagonal 135deg, mitad superior izquierda = tipo 1, inferior derecha = tipo 2.
  function typeBackground(types) {
    const [t1, t2] = types;
    const c1 = TYPE_COLORS[t1] || NEUTRAL;
    if (t2 && TYPE_COLORS[t2]) {
      const c2 = TYPE_COLORS[t2];
      return `linear-gradient(135deg, ${c1} 0%, ${c1} 49%, ${c2} 51%, ${c2} 100%)`;
    }
    return `linear-gradient(135deg, ${shade(c1, 0.3)} 0%, ${shade(c1, -0.35)} 100%)`;
  }

  function typeIcon(t) {
    const img = el("img", "type-icon");
    img.src = `/static/tipos/${t}.png`;
    img.alt = TYPE_LABELS[t] || t;
    img.title = TYPE_LABELS[t] || t;
    img.onerror = () => {                       // PNG aún no descargado -> etiqueta de texto
      const tag = el("span", "type-tag", TYPE_LABELS[t] || t);
      tag.style.background = TYPE_COLORS[t] || NEUTRAL;
      img.replaceWith(tag);
    };
    return img;
  }

  function infoRow(k, v) {
    const row = el("div", "row");
    row.append(el("span", "k", k), el("span", "v", v || "—"));
    return row;
  }

  function renderCard(p) {
    const card = el("div", "card" + (p.shiny ? " shiny" : ""));
    card.style.background = typeBackground(p.is_egg ? [] : (p.types || []));

    if (p.is_egg) {
      card.append(el("div", "egg", "🥚"), el("div", "nick", "Huevo"));
      return card;
    }

    const spriteId = p.sprite_id || p.species_id;   // forma de Alola -> id propio en PokéAPI
    const img = el("img", "sprite");
    img.alt = p.nickname;
    img.loading = "lazy";
    img.src = spriteUrl(spriteId, p.shiny);
    img.onerror = () => {                       // fallback: shiny -> normal -> oculto
      if (img.src.includes("/shiny/")) img.src = spriteUrl(spriteId, false);
      else img.style.visibility = "hidden";
    };

    const nick = el("div", "nick", p.nickname);
    if (p.shiny) nick.append(el("span", "star", "★"));

    card.append(img, nick);
    const speciesLabel = p.is_alola ? p.species + " de Alola" : p.species;
    if (p.nickname.toLowerCase() !== p.species.toLowerCase() || p.is_alola) {
      card.append(el("div", "species", speciesLabel));
    }
    if (p.level) card.append(el("div", "lvl", "Nv. " + p.level));

    // Íconos de tipo, debajo del nivel
    const types = el("div", "types");
    (p.types || []).filter(Boolean).forEach((t) => types.append(typeIcon(t)));
    card.append(types);

    // Caja interna oscura semitransparente: garantiza legibilidad sobre cualquier fondo
    const panel = el("div", "panel");
    const info = el("div", "info");
    info.append(infoRow("Habilidad", p.ability), infoRow("Objeto", p.item));
    const moves = el("div", "moves");
    for (let i = 0; i < 4; i++) {
      const m = p.moves[i];
      moves.append(el("div", "move" + (m ? "" : " none"), m || "—"));
    }
    panel.append(info, moves);
    card.append(panel);
    return card;
  }

  function renderTeam(team) {
    teamEl.replaceChildren();
    for (let i = 0; i < 6; i++) {
      const p = team.find((t) => t.slot === i);
      teamEl.append(p ? renderCard(p) : el("div", "card empty", "Vacío"));
    }
  }

  async function poll() {
    try {
      const s = await (await fetch("/api/state", { cache: "no-store" })).json();
      livesEl.textContent = s.lives;
      if (s.version !== version) {
        version = s.version;
        renderTeam(s.team);
        if (document.activeElement !== $("save-path")) $("save-path").value = s.save_path || "";
        $("language").value = s.language || "es";
      }
      statusEl.textContent = s.error || "";
    } catch (e) {
      statusEl.textContent = "Sin conexión con el backend…";
    }
  }

  // ---- Vidas ----
  async function changeLives(action) {
    const r = await fetch("/api/lives/" + action, { method: "POST" });
    livesEl.textContent = (await r.json()).lives;
  }
  $("lives-plus").onclick = () => changeLives("increment");
  $("lives-minus").onclick = () => changeLives("decrement");

  // ---- Ajustes ----
  $("settings-btn").onclick = () => { $("settings").hidden = !$("settings").hidden; };
  $("save-settings").onclick = async () => {
    await fetch("/api/config", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ save_path: $("save-path").value, language: $("language").value }),
    });
    $("settings").hidden = true;
    version = -1;
    setTimeout(poll, 600);
  };

  poll();
  setInterval(poll, 1500);
})();
