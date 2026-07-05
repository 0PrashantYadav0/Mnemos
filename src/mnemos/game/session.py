"""Game session: interprets story data, drives the Brain, tracks world state.

One :class:`Session` per player. The session owns a :class:`MnemosBrain` and
translates player actions (talk, choose, use potion) into memory writes and
narrative outcomes. Story *content* lives in :mod:`mnemos.game.story`; this is
purely the interpreter.
"""
from __future__ import annotations

from ..brain import MnemosBrain, PLAYER
from . import world
from . import advisor
from .story import SCENES, ACT_REQUIREMENTS, ACT_INTRO
from .tasks import tasks_for_act

ITEM_NAMES = {
    "item:coin_purse": "Coin Purse",
    "item:archive_key": "Archive Key",
    "item:district_seal": "Stolen District Seal",
    "item:memory_potion": "Memory Potion",
    "item:forge_salt": "Forge-Salt",
    "item:tongs": "Dorin's Tongs",
}

ENDINGS = {
    "A": {
        "title": "The Town That Remembers",
        "kind": "good",
        "text": "As the Archon claws at the town's memory, the people you helped "
                "resist the erasure. Mira's gossip re-seeds every kindness faster "
                "than he can delete it. Dorin's forged lock holds against him. The "
                "spared and the trusted converge to disarm him. Every favour you "
                "earned returns at once to save you. You are reinstated as "
                "Archivist. The town remembers -- and so, at last, do you.",
    },
    "B": {
        "title": "Hollow Victory",
        "kind": "neutral",
        "text": "You defeat the Archon, but stand mostly alone. The town tolerates "
                "you without warmth. Fragments of memory return -- but not your "
                "place among these people.",
    },
    "C": {
        "title": "The Stranger, Forgotten",
        "kind": "bad",
        "text": "The town remembers only your cruelty. One by one they turn away, "
                "or side with the Archon outright. The ultimate irony for a former "
                "keeper of memory: the town that never forgets chooses, at last, to "
                "forget YOU.",
    },
    "D": {
        "title": "The Amnesiac's Mercy",
        "kind": "secret",
        "text": "You spent your one potion not to hide your own past, but to free "
                "Renna from a memory the Archon weaponised against her. You face "
                "the finale with a grudge still on your head -- and win anyway, on "
                "the strength of a mercy no one asked you to give. Memory, you "
                "learn, is both a burden and a gift.",
    },
}


class Session:
    def __init__(self, session_id: str) -> None:
        self.id = session_id
        self.brain = MnemosBrain()
        self.act = 1
        self.flags: set[str] = set()
        self.inventory: set[str] = {"item:coin_purse"}
        self.done_scenes: set[str] = set()
        self.log: list[str] = [
            "You wake in Mnemos with no memory of who you are.",
            "Your first tasks await in Market Row. Consult the Oracle panel for guidance.",
        ]
        self.ticker: list[str] = []
        self.ending: str | None = None
        self.pos = [21, 20]  # start on the spine just south of the plaza
        self._seen_rumors: set[str] = set()
        self._seed()

    # ---- seeding -----------------------------------------------------------
    def _seed(self) -> None:
        for f, meta in world.FACTIONS.items():
            self.brain.ensure_faction(f, label=meta["label"])
        for npc in world.NPCS:
            self.brain.ensure_npc(
                npc["id"], name=npc["name"], role=npc["role"],
                district=npc["district"],
            )
            if npc.get("faction"):
                self.brain.g.add_edge("member-of", npc["id"], npc["faction"])

    # ---- condition + effect DSL -------------------------------------------
    def _check(self, conditions: list[dict] | None) -> bool:
        if not conditions:
            return True
        for c in conditions:
            if "flag" in c and c["flag"] not in self.flags:
                return False
            if "not_flag" in c and c["not_flag"] in self.flags:
                return False
            if "item" in c and c["item"] not in self.inventory:
                return False
            if "not_item" in c and c["not_item"] in self.inventory:
                return False
            if "faction" in c and not self.brain.g.find_edge(
                    "member-of", PLAYER, c["faction"]):
                return False
            if "scene_done" in c and c["scene_done"] not in self.done_scenes:
                return False
            if "not_scene_done" in c and c["not_scene_done"] in self.done_scenes:
                return False
            if "owes_favor" in c and not self.brain.g.find_edge(
                    "owes-favor", c["owes_favor"], PLAYER):
                return False
            if "trust_gte" in c:
                npc, thr = c["trust_gte"]
                if self.brain.disposition(npc)["trust"] < thr:
                    return False
            if "trust_lte" in c:
                npc, thr = c["trust_lte"]
                if self.brain.disposition(npc)["trust"] > thr:
                    return False
        return True

    def _apply(self, effects: list[dict]) -> None:
        for e in effects:
            if "remember" in e:
                r = e["remember"]
                self.brain.remember(
                    actor=PLAYER, target=r["target"], deed=r["deed"],
                    summary=r["summary"], act=f"act{self.act}",
                    creates_favor=r.get("creates_favor", False),
                    witnessed_by=r.get("witnessed_by"),
                )
            elif "flag" in e:
                self.flags.add(e["flag"])
            elif "clear_flag" in e:
                self.flags.discard(e["clear_flag"])
            elif "item_add" in e:
                self.inventory.add(e["item_add"])
            elif "item_remove" in e:
                self.inventory.discard(e["item_remove"])
            elif "faction" in e:
                self.brain.join_faction(e["faction"])
            elif "improve" in e:
                self.brain.improve(scope=e["improve"], propagate=True)
                self._collect_rumors()
            elif "forget" in e:
                f = e["forget"]
                self.brain.forget(
                    target_subject=f["target_subject"],
                    edges=f.get("edges"),
                    cascade_rumors=f.get("cascade_rumors", True),
                )
            elif "ending" in e:
                self._resolve_ending()
            elif "note" in e:
                self.log.append(e["note"])

    def _collect_rumors(self) -> None:
        for rumor in self.brain.g.nodes_of_type("Rumor"):
            if rumor.id not in self._seen_rumors:
                self._seen_rumors.add(rumor.id)
                self.ticker.append(f"Word spreads: {rumor.props.get('text')}")

    # ---- scene selection ---------------------------------------------------
    def _scene_for(self, npc_id: str) -> dict | None:
        for scene in SCENES.get(npc_id, []):
            if self.act < scene.get("act", 1):
                continue
            if "max_act" in scene and self.act > scene["max_act"]:
                continue
            key = f"{npc_id}:{scene['id']}"
            if scene.get("once") and key in self.done_scenes:
                continue
            if not self._check(scene.get("gate")):
                continue
            return scene
        return None

    def _greeting(self, npc_id: str, scene: dict, mood: str) -> str:
        greet = scene.get("greet")
        if greet and mood in greet:
            return greet[mood]
        return scene["prompt"]

    # ---- public actions ----------------------------------------------------
    def talk(self, npc_id: str) -> dict:
        npc = world.npc_by_id(npc_id)
        if not npc:
            return {"error": "no such npc"}
        recall = self.brain.recall(subject=npc_id, about=PLAYER,
                                   topic="reputation deeds debts")
        mood = recall["disposition"]["mood"]
        scene = self._scene_for(npc_id)
        if scene is None:
            return {
                "npc": self._npc_view(npc),
                "recall": recall,
                "scene": None,
                "line": self._idle_line(npc, mood),
                "choices": [],
            }
        choices = []
        for i, ch in enumerate(scene.get("choices", [])):
            if self._check(ch.get("gate")):
                choices.append({"index": i, "label": ch["label"],
                                "icon": ch.get("icon", "talk")})
        return {
            "npc": self._npc_view(npc),
            "recall": recall,
            "scene": {"id": scene["id"], "prompt": self._greeting(npc_id, scene, mood)},
            "line": self._greeting(npc_id, scene, mood),
            "choices": choices,
        }

    def choose(self, npc_id: str, scene_id: str, choice_index: int) -> dict:
        scene = next((s for s in SCENES.get(npc_id, []) if s["id"] == scene_id), None)
        if scene is None:
            return {"error": "no such scene"}
        try:
            choice = scene["choices"][choice_index]
        except (IndexError, KeyError):
            return {"error": "no such choice"}
        if not self._check(choice.get("gate")):
            return {"error": "choice not available"}

        self._apply(choice.get("effects", []))
        if scene.get("once"):
            self.done_scenes.add(f"{npc_id}:{scene['id']}")
        self._advance_acts()
        # Mirror this turn's new memories into Cognee Cloud (best-effort).
        self.brain.sync_flush()

        return {
            "result": choice.get("result", ""),
            "state": self.state(),
            "ending": self.ending_view(),
        }

    def use_potion(self, target_npc: str) -> dict:
        """The Memory Potion: surgical forget() on an NPC's grudge (the
        on-theme showpiece). Requires the brewed potion in inventory."""
        if "item:memory_potion" not in self.inventory:
            return {"error": "You have no Memory Potion."}
        npc = world.npc_by_id(target_npc)
        if not npc:
            return {"error": "no such npc"}
        before = self.brain.disposition(target_npc)
        res = self.brain.forget(
            target_subject=target_npc,
            edges=["harmed", "distrusts"],
            cascade_rumors=True,
        )
        self.inventory.discard("item:memory_potion")
        self.flags.add("used_potion_offensive")
        if target_npc == "npc:voss":
            self.flags.add("voss_forgiven")
        self.log.append(f"You slipped the Memory Potion to {npc['name']}. "
                        "Their grudge dissolves.")
        self.ticker.append(f"A grudge fades: {npc['name']} forgets an old wrong.")
        return {
            "result": f"{npc['name']} blinks. \"...Do I know you?\" The grudge is "
                      "gone -- surgically erased, the rest of their memory intact.",
            "before": before,
            "after": res["disposition_after"],
            "removed": res,
            "state": self.state(),
        }

    # ---- act progression + ending -----------------------------------------
    def _advance_acts(self) -> None:
        while self.act in ACT_REQUIREMENTS:
            if ACT_REQUIREMENTS[self.act].issubset(self.flags):
                self.act += 1
                intro = ACT_INTRO.get(self.act)
                if intro:
                    self.log.append(f"--- Act {self.act} ---")
                    self.log.append(intro)
                    self.ticker.append(f"Act {self.act} begins.")
            else:
                break

    def _resolve_ending(self) -> None:
        favors = len(self.brain.g.edges_to(PLAYER, "owes-favor"))
        harmed = len(self.brain.g.edges_from(PLAYER, "helped"))  # placeholder
        harmed = len([e for e in self.brain.g.edges.values() if e.type == "harmed"])
        renna_ok = "renna_ally" in self.flags and "betrayed_renna" not in self.flags

        if "used_potion_altruistic" in self.flags:
            self.ending = "D"
        elif favors >= 3 and renna_ok:
            self.ending = "A"
        elif "betrayed_renna" in self.flags or harmed >= 3:
            self.ending = "C"
        else:
            self.ending = "B"
        self.log.append(f"=== ENDING: {ENDINGS[self.ending]['title']} ===")

    def ending_view(self) -> dict | None:
        if not self.ending:
            return None
        e = ENDINGS[self.ending]
        return {"code": self.ending, "title": e["title"], "kind": e["kind"],
                "text": e["text"]}

    # ---- views -------------------------------------------------------------
    def _npc_view(self, npc: dict) -> dict:
        disp = self.brain.disposition(npc["id"])
        return {
            "id": npc["id"], "name": npc["name"], "role": npc["role"],
            "district": npc["district"], "color": npc["color"],
            "spawn": npc["spawn"], "mood": disp["mood"],
            "trust": disp["trust"], "owes_favor": disp["owes_favor"],
            "available": self._scene_for(npc["id"]) is not None,
        }

    def _idle_line(self, npc: dict, mood: str) -> str:
        lines = {
            "warm": f"{npc['name']} nods warmly. \"Good to see you again.\"",
            "friendly": f"{npc['name']} gives a small smile. \"Stranger.\"",
            "neutral": f"{npc['name']} regards you. \"Nothing for you here now.\"",
            "wary": f"{npc['name']} keeps their distance. \"...What do you want?\"",
            "hostile": f"{npc['name']} turns away. \"Haven't you done enough?\"",
        }
        return lines.get(mood, lines["neutral"])

    def tasks_view(self) -> list[dict]:
        """Objectives for the current act, with done status + target NPC."""
        out = []
        for t in tasks_for_act(self.act):
            done = bool(t["done_flag"]) and t["done_flag"] in self.flags
            npc = world.npc_by_id(t["npc"])
            out.append({
                "id": t["id"], "title": t["title"], "desc": t["desc"],
                "done": done, "npc": t["npc"],
                "npc_name": npc["name"] if npc else t["npc"],
                "category": t["category"],
            })
        return out

    def advice(self) -> dict:
        return advisor.recommend(self)

    def reputation(self) -> dict:
        player = self.brain.g.get_node(PLAYER)
        factions = {}
        for e in self.brain.g.edges_from(PLAYER, "member-of"):
            factions[e.dst] = world.FACTIONS.get(e.dst, {}).get("label", e.dst)
        return {
            "score": player.props.get("reputation", 0.0) if player else 0.0,
            "helped": len(self.brain.g.edges_from(PLAYER, "helped")),
            "harmed": len([e for e in self.brain.g.edges.values()
                           if e.type == "harmed"]),
            "favors": len(self.brain.g.edges_to(PLAYER, "owes-favor")),
            "factions": factions,
            "traits": [n.props.get("label") for n in
                       self.brain.g.nodes_of_type("Trait")],
        }

    def state(self) -> dict:
        return {
            "session_id": self.id,
            "act": self.act,
            "act_intro": ACT_INTRO.get(self.act, ""),
            "flags": sorted(self.flags),
            "inventory": [{"id": i, "name": ITEM_NAMES.get(i, i)}
                          for i in sorted(self.inventory)],
            "log": self.log[-30:],
            "ticker": self.ticker[-12:],
            "reputation": self.reputation(),
            "tasks": self.tasks_view(),
            "oracle": self.advice(),
            "npcs": [self._npc_view(n) for n in world.NPCS],
            "ending": self.ending_view(),
            "map": {"w": world.MAP_W, "h": world.MAP_H,
                    "districts": world.DISTRICTS,
                    "paths": world.PATHS, "decor": world.DECOR},
            "pos": self.pos,
            "cloud": self.brain.cloud_active,
        }
