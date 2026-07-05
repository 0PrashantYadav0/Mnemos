"use strict";
// Mnemos client on Phaser 3. Top-down RPG with a follow-camera (no more
// full-map upscaling), a larger walkable town, procedural decor, and a minimap.

const TILE = 32;
let MAPW = 44, MAPH = 30;
const ZOOM = 2.4;                       // camera zoom: cozy + crisp, not stretched
const ICONS = { help: "+", harm: "x", coin: "$", ignore: "\u2013", talk: ">" };
const DIR_ROW = { down: 0, left: 1, right: 2, up: 3 };
const MOOD_HEX = { warm: 0xe8a33d, friendly: 0x5fa86e, neutral: 0x6b6288,
  wary: 0x6f8fd6, hostile: 0xd6604a };

let state = null, sessionId = null;
let scene = null, player = null, keys = null, cam = null;
let npcSprites = {};                    // id -> { sprite, ring, mark, name, fav, data }
let nearNpc = null, dialogueOpen = false;
let lastTile = { x: -1, y: -1 }, moveLock = false;
let facing = "down";

const $ = (id) => document.getElementById(id);

// ------------------------- networking -------------------------
async function api(path, method = "GET", body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "request failed");
  }
  return res.json();
}

// ------------------------- Phaser scene -------------------------
function preload() {
  scene = this;
  this.load.spritesheet("tiles", "/ui/assets/tiles.png", { frameWidth: TILE, frameHeight: TILE });
  const keysList = ["player", ...state.npcs.map((n) => n.id.split(":")[1])];
  for (const k of keysList) {
    this.load.spritesheet("char-" + k, "/ui/assets/char_" + k + ".png",
      { frameWidth: TILE, frameHeight: TILE });
  }
}

function create() {
  scene = this;
  MAPW = state.map.w; MAPH = state.map.h;

  // ---- ground tilemap: grass base -> districts -> paths ----
  const data = [];
  for (let y = 0; y < MAPH; y++) data.push(new Array(MAPW).fill(1));
  for (const d of Object.values(state.map.districts)) {
    const t = d.tile ?? 1;
    for (let y = d.y0; y <= d.y1; y++)
      for (let x = d.x0; x <= d.x1; x++) if (data[y]?.[x] !== undefined) data[y][x] = t;
  }
  for (const p of (state.map.paths || [])) {
    for (let y = p.y0; y <= p.y1; y++)
      for (let x = p.x0; x <= p.x1; x++) if (data[y]?.[x] !== undefined) data[y][x] = 0;
  }
  const map = this.make.tilemap({ data, tileWidth: TILE, tileHeight: TILE });
  const tiles = map.addTilesetImage("tiles");
  map.createLayer(0, tiles, 0, 0).setDepth(0);

  // subtle district labels
  for (const d of Object.values(state.map.districts)) {
    this.add.text(d.x0 * TILE + 6, d.y0 * TILE + 5, d.label.toUpperCase(),
      { fontSize: "10px", color: "#b3a9d6", fontFamily: "system-ui", fontStyle: "bold" })
      .setDepth(1).setAlpha(0.7);
  }

  // ---- procedural decor ----
  makeDotTexture(this, "spark", 0xffe08a, 6);
  makeDotTexture(this, "gossip", 0xc9a227, 8);
  makeDotTexture(this, "magic", 0xb06fd6, 7);
  for (const dec of (state.map.decor || [])) drawDecor(this, dec);

  // ---- animations ----
  const keysList = ["player", ...state.npcs.map((n) => n.id.split(":")[1])];
  for (const k of keysList) {
    for (const [dir, r] of Object.entries(DIR_ROW)) {
      this.anims.create({
        key: `${k}-${dir}`,
        frames: this.anims.generateFrameNumbers("char-" + k, { frames: [r*4, r*4+1, r*4+2, r*4+3] }),
        frameRate: 8, repeat: -1,
      });
    }
  }

  // ---- NPC sprites ----
  for (const n of state.npcs) {
    const key = n.id.split(":")[1];
    const px = n.spawn[0] * TILE + TILE / 2, py = n.spawn[1] * TILE + TILE / 2;
    const ring = this.add.circle(px, py + 10, 13).setStrokeStyle(2, 0x6b6288).setDepth(2).setAlpha(0.9);
    const sprite = this.add.sprite(px, py, "char-" + key).setFrame(0);
    const name = this.add.text(px, py + 14, n.name,
      { fontSize: "9px", color: "#e8e3f2", fontFamily: "system-ui", fontStyle: "bold",
        stroke: "#14101f", strokeThickness: 3 }).setOrigin(0.5, 0).setDepth(9999);
    const fav = this.add.text(px, py + 24, "", { fontSize: "8px", color: "#7fa8e6",
      stroke: "#14101f", strokeThickness: 3 }).setOrigin(0.5, 0).setDepth(9999);
    const mark = this.add.text(px, py - 22, "!", { fontSize: "16px", color: "#ffd24a",
      fontStyle: "bold", stroke: "#14101f", strokeThickness: 4 }).setOrigin(0.5).setDepth(9999).setVisible(false);
    this.tweens.add({ targets: mark, y: py - 28, duration: 600, yoyo: true, repeat: -1 });
    sprite.setInteractive({ useHandCursor: true });
    sprite.on("pointerdown", () => {
      const d = Phaser.Math.Distance.Between(player.x, player.y, sprite.x, sprite.y);
      if (d < 90) talk(n);
    });
    npcSprites[n.id] = { sprite, ring, mark, name, fav, data: n };
  }

  // ---- player ----
  const start = state.pos;
  player = this.physics.add.sprite(start[0] * TILE + 16, start[1] * TILE + 16, "char-player");
  player.setCollideWorldBounds(true).setBodySize(16, 12).setOffset(8, 18);
  this.physics.world.setBounds(0, 0, MAPW * TILE, MAPH * TILE);

  // ---- camera: follow + zoom + bounds (this fixes the "magnified" feel) ----
  cam = this.cameras.main;
  cam.setBounds(0, 0, MAPW * TILE, MAPH * TILE);
  cam.startFollow(player, true, 0.12, 0.12);
  cam.setZoom(ZOOM);
  cam.setRoundPixels(true);

  keys = this.input.keyboard.addKeys("W,A,S,D,UP,DOWN,LEFT,RIGHT,E,ESC,M");
  this.input.keyboard.on("keydown-E", () => { if (nearNpc && !dialogueOpen) talk(nearNpc); });
  this.input.keyboard.on("keydown-ESC", () => { closeDialogue(); $("graph-modal").hidden = true; });

  buildMinimap();
  refreshNpcs();
}

function update() {
  if (!player) return;
  const speed = 150;
  let vx = 0, vy = 0;
  if (!dialogueOpen) {
    if (keys.A.isDown || keys.LEFT.isDown) vx = -speed;
    else if (keys.D.isDown || keys.RIGHT.isDown) vx = speed;
    if (keys.W.isDown || keys.UP.isDown) vy = -speed;
    else if (keys.S.isDown || keys.DOWN.isDown) vy = speed;
  }
  if (vx && vy) { vx *= 0.707; vy *= 0.707; }
  player.setVelocity(vx, vy);
  if (vx < 0) { player.anims.play("player-left", true); facing = "left"; }
  else if (vx > 0) { player.anims.play("player-right", true); facing = "right"; }
  else if (vy < 0) { player.anims.play("player-up", true); facing = "up"; }
  else if (vy > 0) { player.anims.play("player-down", true); facing = "down"; }
  else { player.anims.stop(); }

  // depth sort by feet Y so sprites overlap correctly
  player.setDepth(player.y);
  for (const o of Object.values(npcSprites)) {
    o.sprite.setDepth(o.sprite.y);
    o.name.setPosition(o.sprite.x, o.sprite.y + 14);
    o.fav.setPosition(o.sprite.x, o.sprite.y + 24);
  }

  // proximity
  nearNpc = null; let best = 999;
  for (const o of Object.values(npcSprites)) {
    const d = Phaser.Math.Distance.Between(player.x, player.y, o.sprite.x, o.sprite.y);
    if (d < 52 && d < best) { best = d; nearNpc = o.data; }
  }
  const prompt = $("talk-prompt");
  if (nearNpc && !dialogueOpen) { prompt.hidden = false; prompt.textContent = `Talk to ${nearNpc.name}  [E]`; }
  else prompt.hidden = true;

  // sync tile pos to server on change
  const tx = Math.floor(player.x / TILE), ty = Math.floor(player.y / TILE);
  if ((tx !== lastTile.x || ty !== lastTile.y) && !moveLock) {
    lastTile = { x: tx, y: ty }; moveLock = true;
    drawMinimap();
    api(`/api/session/${sessionId}/move`, "POST", { pos: [tx, ty] }).finally(() => { moveLock = false; });
  }
}

// ------------------------- decor -------------------------
function drawDecor(sc, dec) {
  const x = dec.x * TILE + 16, y = dec.y * TILE + 16;
  const g = sc.add.graphics();
  const put = (depth) => g.setDepth(depth);
  switch (dec.type) {
    case "tree":
      g.fillStyle(0x2a1c12, 1).fillRect(x - 2, y + 4, 4, 8);
      g.fillStyle(0x2f6b39, 1).fillCircle(x, y - 2, 11);
      g.fillStyle(0x3f8a4c, 1).fillCircle(x - 4, y - 5, 7);
      g.fillStyle(0x4fa85e, 0.9).fillCircle(x + 4, y - 6, 6); put(y + 6); break;
    case "water": {
      g.fillStyle(0x214a6b, 1).fillCircle(x, y, 13);
      g.fillStyle(0x2f6fa0, 1).fillCircle(x, y, 10);
      g.fillStyle(0x8fc7e8, 0.7).fillCircle(x - 3, y - 3, 3); put(1);
      sc.tweens.add({ targets: g, alpha: 0.85, duration: 1500, yoyo: true, repeat: -1 }); break;
    }
    case "lamp":
      g.fillStyle(0x2a2438, 1).fillRect(x - 1, y - 2, 2, 12);
      g.fillStyle(0xffd76a, 1).fillCircle(x, y - 6, 4); put(y);
      ambientGlow(sc, x, y - 6, 0xffcf5a, 22); break;
    case "stall":
      g.fillStyle(0x6b3f22, 1).fillRect(x - 12, y - 2, 24, 12);
      g.fillStyle(0xc0473a, 1).fillRect(x - 14, y - 8, 28, 6);
      g.fillStyle(0xe8c07a, 1).fillRect(x - 14, y - 8, 28, 2); put(y); break;
    case "anvil":
      g.fillStyle(0x3a3a44, 1).fillRect(x - 7, y, 14, 6);
      g.fillStyle(0x55555f, 1).fillRect(x - 9, y - 4, 18, 4); put(y);
      ambientGlow(sc, x, y, 0xe8703c, 20); break;
    case "pillar":
      g.fillStyle(0x4a3a6b, 1).fillRect(x - 6, y - 14, 12, 22);
      g.fillStyle(0x6b54a0, 1).fillRect(x - 8, y - 16, 16, 4);
      g.fillStyle(0x6b54a0, 1).fillRect(x - 8, y + 6, 16, 4); put(y + 4);
      ambientGlow(sc, x, y - 20, 0x8f6fd6, 16); break;
    case "crate":
      g.fillStyle(0x6b4a2a, 1).fillRect(x - 7, y - 7, 14, 14);
      g.lineStyle(1, 0x3a2814).strokeRect(x - 7, y - 7, 14, 14); put(y); break;
    case "flowers":
      for (const [dx, dy, c] of [[-4,0,0xe86a9a],[4,-2,0xffd24a],[0,4,0x6fb0e8]])
        g.fillStyle(c, 1).fillCircle(x + dx, y + dy, 2.5);
      put(y); break;
  }
}
function ambientGlow(sc, x, y, color, r) {
  const c = sc.add.circle(x, y, r, color, 0.12).setDepth(1);
  sc.tweens.add({ targets: c, alpha: 0.24, scale: 1.15, duration: 1400, yoyo: true, repeat: -1 });
}
function makeDotTexture(sc, key, color, size) {
  if (sc.textures.exists(key)) return;
  const g = sc.add.graphics();
  g.fillStyle(color, 1); g.fillCircle(size, size, size);
  g.generateTexture(key, size * 2, size * 2); g.destroy();
}

// ------------------------- minimap -------------------------
let miniCtx = null, miniScale = 4;
function buildMinimap() {
  const c = $("minimap"); if (!c) return;
  miniScale = Math.max(2, Math.floor(150 / MAPW));
  c.width = MAPW * miniScale; c.height = MAPH * miniScale;
  miniCtx = c.getContext("2d");
  drawMinimap();
}
function drawMinimap() {
  if (!miniCtx) return;
  const s = miniScale;
  miniCtx.fillStyle = "#171226"; miniCtx.fillRect(0, 0, MAPW * s, MAPH * s);
  const dcol = { market: "#4a4234", forge: "#5a2e1e", gate: "#2e4054", archive: "#3c2c54", plaza: "#4a4234" };
  for (const [k, d] of Object.entries(state.map.districts)) {
    miniCtx.fillStyle = dcol[k] || "#333";
    miniCtx.fillRect(d.x0 * s, d.y0 * s, (d.x1 - d.x0 + 1) * s, (d.y1 - d.y0 + 1) * s);
  }
  for (const o of Object.values(npcSprites)) {
    const n = o.data;
    miniCtx.fillStyle = MOOD_HEX[n.mood] ? "#" + MOOD_HEX[n.mood].toString(16).padStart(6, "0") : "#888";
    miniCtx.fillRect(n.spawn[0] * s - 1, n.spawn[1] * s - 1, s + 1, s + 1);
  }
  if (player) {
    miniCtx.fillStyle = "#fff";
    const px = Math.floor(player.x / TILE) * s, py = Math.floor(player.y / TILE) * s;
    miniCtx.fillRect(px - 1, py - 1, s + 2, s + 2);
  }
}

// ------------------------- npcs / effects -------------------------
function refreshNpcs() {
  if (!scene) return;
  const byId = Object.fromEntries(state.npcs.map((n) => [n.id, n]));
  for (const [id, o] of Object.entries(npcSprites)) {
    const n = byId[id]; if (!n) continue; o.data = n;
    o.ring.setStrokeStyle(2, MOOD_HEX[n.mood] || 0x6b6288);
    o.mark.setVisible(!!n.available);
    o.fav.setText(n.owes_favor ? "owes you" : "");
  }
  drawMinimap();
}
function burstRemember(x, y) {
  if (!scene) return;
  const p = scene.add.particles(x, y, "spark", { speed: { min: 40, max: 120 },
    angle: { min: 0, max: 360 }, scale: { start: 0.9, end: 0 }, lifespan: 700,
    quantity: 16, emitting: false }).setDepth(99999);
  p.explode(16); floatText(x, y - 20, "Mnemos remembers", "#f2eef7");
  scene.time.delayedCall(900, () => p.destroy());
}
function spreadRumor(fromId) {
  if (!scene) return;
  const src = npcSprites[fromId]; if (!src) return;
  for (const o of Object.values(npcSprites)) {
    if (o.data.id === fromId || o.data.district !== src.data.district) continue;
    const dot = scene.add.image(src.sprite.x, src.sprite.y, "gossip").setDepth(99999);
    scene.tweens.add({ targets: dot, x: o.sprite.x, y: o.sprite.y, duration: 900,
      onComplete: () => dot.destroy() });
  }
}
function potionSwirl(id) {
  if (!scene) return;
  const o = npcSprites[id]; if (!o) return;
  const p = scene.add.particles(o.sprite.x, o.sprite.y, "magic", { speed: 60,
    scale: { start: 1, end: 0 }, lifespan: 900, quantity: 20, emitting: false }).setDepth(99999);
  p.explode(20); floatText(o.sprite.x, o.sprite.y - 24, "forget()", "#d6a0f0");
  scene.time.delayedCall(1000, () => p.destroy());
}
function floatText(x, y, text, color) {
  const t = scene.add.text(x, y, text, { fontSize: "12px", color, fontFamily: "system-ui",
    fontStyle: "bold", stroke: "#14101f", strokeThickness: 3 }).setOrigin(0.5).setDepth(99999);
  scene.tweens.add({ targets: t, y: y - 28, alpha: 0, duration: 1200, onComplete: () => t.destroy() });
}
function focusNpcMarker(id) {
  const o = npcSprites[id]; if (!o || !cam) return;
  cam.pan(o.sprite.x, o.sprite.y, 500, "Sine.easeInOut");
  const arrow = scene.add.text(o.sprite.x, o.sprite.y - 30, "\u25BC",
    { fontSize: "18px", color: "#ffd24a", fontStyle: "bold", stroke: "#14101f", strokeThickness: 4 })
    .setOrigin(0.5).setDepth(99999);
  scene.tweens.add({ targets: arrow, y: o.sprite.y - 40, duration: 400, yoyo: true, repeat: 4,
    onComplete: () => { arrow.destroy(); if (player) cam.startFollow(player, true, 0.12, 0.12); } });
}

// ------------------------- HUD -------------------------
function drawHUD() {
  const r = state.reputation;
  $("act-label").textContent = `Act ${state.act}`;
  $("act-intro").textContent = state.act_intro;
  $("act-tag").textContent = `Act ${state.act}`;
  $("rep-score").textContent = r.score;
  $("n-helped").textContent = r.helped; $("n-harmed").textContent = r.harmed; $("n-favor").textContent = r.favors;
  const max = Math.max(4, r.helped, r.harmed, r.favors);
  $("bar-helped").style.width = (r.helped / max * 100) + "%";
  $("bar-harmed").style.width = (r.harmed / max * 100) + "%";
  $("bar-favor").style.width = (r.favors / max * 100) + "%";
  const factions = $("factions"); factions.innerHTML = "";
  for (const l of Object.values(r.factions)) factions.appendChild(tag(l, "tag"));
  const traits = $("traits"); traits.innerHTML = "";
  for (const t of r.traits) traits.appendChild(tag(t, "tag trait"));
  const inv = $("inventory"); inv.innerHTML = "";
  if (!state.inventory.length) inv.innerHTML = "<li>(empty)</li>";
  for (const it of state.inventory) { const li = document.createElement("li"); li.textContent = it.name; inv.appendChild(li); }
  fillList("ticker", state.ticker); fillList("log", [...state.log].reverse());
  const badge = $("cloud-badge");
  if (badge) { badge.classList.toggle("on", !!state.cloud);
    badge.textContent = state.cloud ? "Cognee Cloud: live" : "Cognee Cloud: off"; }
  renderOracle(); renderTasks(); refreshNpcs();
  if (state.ending) showEnding(state.ending);
}
function renderOracle() {
  const o = state.oracle; if (!o) return;
  $("oracle-advice").textContent = o.advice;
  $("forecast-bar").style.width = ((o.forecast.score + 1) / 2 * 100) + "%";
  $("forecast-label").textContent = o.forecast.likely_label;
}
function renderTasks() {
  const reco = state.oracle && state.oracle.recommended ? state.oracle.recommended.id : null;
  const ul = $("tasks"); ul.innerHTML = "";
  for (const t of state.tasks) {
    const li = document.createElement("li");
    li.className = "task" + (t.done ? " done" : "") + (t.id === reco && !t.done ? " reco" : "");
    li.innerHTML = `<span class="check">${t.done ? "\u2713" : ""}</span>` +
      `<span><span class="t-title"></span><br><span class="t-desc"></span></span>`;
    li.querySelector(".t-title").textContent = `${t.title} \u2014 ${t.npc_name}`;
    li.querySelector(".t-desc").textContent = t.desc;
    li.title = "Click to locate " + t.npc_name;
    li.onclick = () => focusNpcMarker(t.npc);
    ul.appendChild(li);
  }
}
function tag(text, cls) { const s = document.createElement("span"); s.className = cls; s.textContent = text; return s; }
function fillList(id, items) {
  const ul = $(id); ul.innerHTML = "";
  for (const t of items) { const li = document.createElement("li"); li.textContent = t; ul.appendChild(li); }
}

// ------------------------- dialogue -------------------------
async function talk(npc) {
  const data = await api(`/api/session/${sessionId}/talk`, "POST", { npc_id: npc.id });
  dialogueOpen = true; if (player) player.setVelocity(0);
  const d = $("dialogue"); d.hidden = false;
  $("d-portrait").textContent = npc.name[0]; $("d-portrait").style.background = npc.color;
  $("d-name").textContent = npc.name; $("d-role").textContent = npc.role;
  const mood = data.npc.mood; const moodEl = $("d-mood");
  moodEl.textContent = `Mood: ${mood}${data.npc.owes_favor ? " \u00b7 owes you a favour" : ""}`;
  moodEl.className = "d-mood mood-" + mood;
  renderRemember(data.recall); $("d-line").textContent = data.line;
  const choicesEl = $("d-choices"); choicesEl.innerHTML = "";
  if (data.scene && data.choices.length) {
    for (const ch of data.choices) {
      const btn = document.createElement("button"); btn.className = "choice";
      btn.innerHTML = `<span class="icon ${ch.icon}">${ICONS[ch.icon] || ">"}</span><span></span>`;
      btn.querySelector("span:last-child").textContent = ch.label;
      btn.onclick = () => choose(npc.id, data.scene.id, ch.index);
      choicesEl.appendChild(btn);
    }
  } else {
    const p = document.createElement("p"); p.style.color = "#c3bad6";
    p.textContent = "(Nothing more to discuss right now.)"; choicesEl.appendChild(p);
  }
  if (state.inventory.some((i) => i.id === "item:memory_potion")) {
    const pb = document.createElement("button"); pb.className = "choice potion";
    pb.innerHTML = `<span class="icon harm">*</span><span></span>`;
    pb.querySelector("span:last-child").textContent = `Use Memory Potion on ${npc.name} (forget their grudge)`;
    pb.onclick = () => usePotion(npc.id); choicesEl.appendChild(pb);
  }
  choicesEl.querySelector("button")?.focus();
}
function renderRemember(recall) {
  const box = $("d-remember"); const parts = [];
  for (const d of recall.direct) parts.push(d.event ? `<b>${d.edge}</b>: ${d.event}` : `<b>${d.edge}</b> (w ${d.weight})`);
  for (const s of recall.secondhand) parts.push(`heard from ${short(s.from)}: "${s.rumor}" (conf ${s.confidence})`);
  box.hidden = false;
  box.innerHTML = parts.length ? "They remember... " + parts.join(" &middot; ")
    : "They remember... <i>nothing about you yet.</i>";
}
function short(id) { return (id || "").replace("npc:", ""); }

async function choose(npcId, sceneId, idx) {
  const prev = state.ticker.length;
  const res = await api(`/api/session/${sessionId}/choose`, "POST",
    { npc_id: npcId, scene_id: sceneId, choice_index: idx });
  state = res.state;
  if (player) burstRemember(player.x, player.y);
  if (state.ticker.length > prev) spreadRumor(npcId);
  if (res.result) {
    $("d-line").textContent = res.result; $("d-choices").innerHTML = "";
    const cont = document.createElement("button"); cont.className = "btn primary"; cont.textContent = "Continue";
    cont.onclick = () => closeDialogue(); $("d-choices").appendChild(cont); cont.focus();
  } else closeDialogue();
  drawHUD();
}
async function usePotion(target) {
  try {
    const res = await api(`/api/session/${sessionId}/potion`, "POST", { target });
    state = res.state; potionSwirl(target);
    $("d-line").textContent = res.result;
    $("d-remember").innerHTML = `forget() removed ${res.removed.removed_edges} edge(s), ` +
      `${res.removed.removed_rumors} rumour(s). Trust ${res.before.trust} \u2192 ${res.after.trust}.`;
    $("d-choices").innerHTML = "";
    const cont = document.createElement("button"); cont.className = "btn primary"; cont.textContent = "Continue";
    cont.onclick = () => closeDialogue(); $("d-choices").appendChild(cont); cont.focus();
    drawHUD();
  } catch (e) { alert(e.message); }
}
function closeDialogue() {
  $("dialogue").hidden = true; dialogueOpen = false;
  if (scene) scene.game.canvas.focus();
}

// ------------------------- ending + graph -------------------------
function showEnding(e) {
  $("ending-modal").hidden = false;
  const k = $("e-kind"); k.textContent = e.kind + " ending"; k.className = "e-kind " + e.kind;
  $("e-title").textContent = e.title; $("e-text").textContent = e.text;
}
async function showGraph() { const g = await api(`/api/session/${sessionId}/graph`); $("graph-modal").hidden = false; drawGraph(g); }
function drawGraph(g) {
  const gc = $("graph-canvas"); const gx = gc.getContext("2d"); gx.clearRect(0, 0, gc.width, gc.height);
  const colors = { Player: "#f2eef7", NPC: "#e8a33d", Event: "#5fa86e", Rumor: "#d6604a",
    Faction: "#6f8fd6", Trait: "#c9a227", Item: "#888" };
  const cx = gc.width / 2, cy = gc.height / 2; const pos = {}; const byType = {};
  for (const n of g.nodes) (byType[n.type] ||= []).push(n);
  pos["player:stranger"] = { x: cx, y: cy };
  const rings = { NPC: 150, Faction: 220, Event: 250, Rumor: 300, Trait: 90, Item: 190 };
  for (const [type, nodes] of Object.entries(byType)) {
    if (type === "Player") continue; const r = rings[type] || 260;
    nodes.forEach((n, i) => { const a = (i / nodes.length) * 6.28 + type.length; pos[n.id] = { x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r }; });
  }
  const ec = { helped: "#5fa86e", harmed: "#d6604a", "owes-favor": "#6f8fd6", trusts: "#5fa86e",
    distrusts: "#d6604a", "told-about": "#c9a227", "member-of": "#6f8fd6", witnessed: "#555", "has-trait": "#c9a227" };
  for (const e of g.edges) {
    const a = pos[e.src], b = pos[e.dst]; if (!a || !b) continue;
    gx.beginPath(); gx.moveTo(a.x, a.y); gx.lineTo(b.x, b.y);
    gx.strokeStyle = ec[e.type] || "#444"; gx.lineWidth = e.type === "told-about" ? 1.5 : 1;
    if (e.type === "told-about") gx.setLineDash([4, 3]); else gx.setLineDash([]); gx.stroke();
  }
  gx.setLineDash([]);
  for (const n of g.nodes) {
    const p = pos[n.id]; if (!p) continue; const isP = n.type === "Player";
    gx.beginPath(); gx.arc(p.x, p.y, isP ? 11 : 7, 0, 6.28); gx.fillStyle = colors[n.type] || "#999"; gx.fill();
    gx.fillStyle = "#e8e3f2"; gx.font = "10px system-ui";
    gx.fillText((n.props.name || n.props.label || n.id.split(":").pop() || "").slice(0, 16), p.x + 9, p.y + 3);
  }
}

// ------------------------- boot -------------------------
let game = null;
async function newGame() {
  state = await api("/api/session/new", "POST");
  sessionId = state.session_id;
  $("ending-modal").hidden = true; closeDialogue();
  if (game) { game.destroy(true); npcSprites = {}; player = null; }
  const wrap = $("game");
  game = new Phaser.Game({
    type: Phaser.AUTO, parent: "game",
    width: wrap.clientWidth || 900, height: wrap.clientHeight || 620,
    pixelArt: true, backgroundColor: "#0d0b14",
    scale: { mode: Phaser.Scale.RESIZE, autoCenter: Phaser.Scale.NO_CENTER },
    physics: { default: "arcade", arcade: { debug: false } },
    scene: { preload, create, update },
  });
  drawHUD();
}

$("btn-new").onclick = newGame;
$("btn-graph").onclick = showGraph;
$("g-close").onclick = () => { $("graph-modal").hidden = true; };
$("d-close").onclick = closeDialogue;
$("e-restart").onclick = newGame;

newGame();
