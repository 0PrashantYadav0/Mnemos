# Mnemos: The Town That Never Forgets

A narrative RPG where the townsfolk are powered by a real, typed **knowledge
graph**. Every NPC genuinely remembers what you did, who told them about it, and
how they feel about you — and that memory spreads between characters as **gossip
across graph edges**, something flat vector memory cannot model.

You wake in Mnemos with total amnesia. The town, however, remembers you
perfectly. Rebuild your reputation choice by choice, watch kindness and cruelty
compound into wildly different endings, and drink a "Memory Potion" that calls
`forget()` to surgically erase an NPC's grudge.

> **Runs local by default; mirrors to Cognee Cloud when you opt in.** The
> decoupled graph-memory "NPC Brain" (`remember / recall / improve / forget` +
> rumor propagation) is the deterministic source of truth for gameplay. When a
> Cognee Cloud key is present, every event is ALSO mirrored into Cognee Cloud so
> the town's memory genuinely lives there and can be queried semantically.

## Demo:

**Watch the presentation video: [docs/mnemos-presentation.mp4](docs/mnemos-presentation.mp4)** — a ~4 min narrated walkthrough of the deck plus live gameplay footage.

- Slides: [docs/presentation.html](docs/presentation.html)
- Narration / captions: [docs/mnemos-video-script.txt](docs/mnemos-video-script.txt)

## Cognee Cloud

The game plays fully without it (the header badge reads "Cognee Cloud: off").
To light it up:

```bash
uv pip install -e ".[cognee]"          # add the Cognee SDK
export COGNEE_API_KEY=your_cloud_key   # from platform.cognee.ai
uv run uvicorn mnemos.api:app --port 8140
# open http://127.0.0.1:8140/  -> badge turns "Cognee Cloud: live"
```

Every choice mirrors that turn's new memories into Cognee Cloud (best-effort;
if the cloud is unreachable the game keeps running on the local graph). The
local typed graph remains authoritative for trust weights, rumor propagation
and endings, because those need deterministic math.

## Run

```bash
./run.sh 8140          # install, test, serve, open browser (auto-detects COGNEE_API_KEY)
# or manually:
uv venv --python 3.11 && uv pip install -e ".[dev]"
uv run uvicorn mnemos.api:app --port 8140
```

Controls: move with WASD / arrows, talk with E (or click an NPC), click a task
to pan the camera to that character. The camera follows you with a proper zoom
and there is a live minimap top-right.

## Architecture

```
  Web client (Phaser 3, vendored)      <- WASD move, dialogue, graph peek
        |  REST
  Game/sim server (FastAPI)            <- scenes, choice resolver, act state
        |  4 verbs
  NPC Brain (pure Python)              <- remember / recall / improve / forget
        |
  Knowledge graph (typed nodes+edges)  <- the single source of truth for memory
```

The **NPC Brain is fully decoupled** — the game only knows four HTTP verbs
(`/brain/remember`, `/recall`, `/improve`, `/forget`). Swap the client or drop
the Brain into any game; it is untouched. That decoupling is the whole pitch.

### The graph (why not just vectors?)

Nodes: `Player, NPC, Event, Item, Location, Faction, Rumor, Trait`.
Edges: `helped, harmed, owes-favor, trusts, distrusts, witnessed, told-about,
member-of, has-trait`.

The star is `told-about` (NPC → NPC gossip). Vector search finds *similar text*;
it cannot represent that NPC B learned about an event *from* NPC A, that the
belief is second-hand (and distortable), and that it travelled a specific social
path. That is a graph relationship — and it is what makes Mnemos feel like a
living town instead of a set of independent chatbots.

## Run it

```bash
cd mnemos
uv venv --python 3.11
uv pip install -e ".[dev]"

# (optional) regenerate sprite sheets + tileset -- they're pre-committed
uv pip install pillow && uv run python scripts/gen_assets.py

# tests + verification
uv run pytest -q
uv run python -m mnemos.verify        # headless full-playthrough checks

# play in the browser
uv run uvicorn mnemos.api:app --port 8123
# open http://127.0.0.1:8123/
```

Or the one-shot: `./run.sh` (installs, tests, verifies, serves, opens browser).

## Game client

The client runs on **Phaser 3** (the open-source MIT 2D game engine), vendored
locally at `ui/vendor/phaser.min.js` so nothing loads from the internet at
runtime. It renders a real tilemap, sprite-**animated** characters (4-direction,
4-frame walk cycles), arcade-physics movement, and particle effects (a gold
"Mnemos remembers" burst, travelling gossip dots, a `forget()` swirl).

All art is **procedurally generated** by `scripts/gen_assets.py` with Pillow --
character sprite sheets (`ui/assets/char_*.png`) and a tileset
(`ui/assets/tiles.png`). No downloaded assets, no CDNs.

## How to play

- **Move** with `WASD` / arrow keys. A gold ring means an NPC has something for
  you right now; the coloured ring shows their mood toward you.
- **Talk** with `E` (or click an adjacent NPC). The dialogue shows a
  *"They remember..."* line — the actual `recall()` from the graph.
- **Choose.** Every choice writes a typed edge. Watch the **Rumour Ticker** —
  that's `told-about` propagation travelling the graph in real time.
- **Graph Peek** (top right) renders the live memory graph.
- Later acts `recall()` your earlier edges to branch the story. Kindnesses
  converge into the good-karma ending; cruelty gets you forgotten.
- In Act 4, brew and use the **Memory Potion** to `forget()` an NPC's grudge —
  the on-theme showpiece.

## Five acts, four endings

1. **The Waking** — first imprints (Mira's debt, Dorin's tongs, Voss's seal).
2. **Reputation Travels** — rumors from Act 1 change how strangers greet you.
3. **The Reckoning** — early favours pay off (Dorin forges you a key); Renna
   reveals your erased past.
4. **The Town That Remembers** — reach the Archive; the Memory Potion `forget()`.
5. **Restoration or Ruin** — the graph you built decides your fate:
   - **A — The Town That Remembers** (good karma): favours converge to save you.
   - **B — Hollow Victory** (neutral).
   - **C — The Stranger, Forgotten** (bad karma): the town forgets *you*.
   - **D — The Amnesiac's Mercy** (secret): spend the potion to free Renna.

## Project layout

```
src/mnemos/
  brain/        graph.py (typed graph + lexical search)  engine.py (4 verbs)
  game/         world.py (map/NPCs)  story.py (all acts, as data)  session.py
  ui/           index.html  styles.css  app.js   (zero-CDN client)
  api.py        FastAPI: game API + Brain microservice + static hosting
  verify.py     headless full-run verification
tests/          brain, session (all endings), and HTTP tests
```

## Tests

`uv run pytest` covers: graph idempotency, all four Brain verbs, rumor
propagation to unmet NPCs, surgical `forget()`, full good/bad/secret
playthroughs to their endings, the potion flip, and every HTTP endpoint
including the decoupled Brain microservice.

---
*Mnemos: the town that never forgets — and now, neither will your game.*
