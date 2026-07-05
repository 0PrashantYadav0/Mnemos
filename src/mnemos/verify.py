"""Headless verification: run full playthroughs and assert the whole feature
set works end to end without a browser. Run: ``python -m mnemos.verify``.

Exits non-zero on any failure so it can gate CI / the run script.
"""
from __future__ import annotations

import sys

from .game import Session
from .brain import PLAYER


class Check:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def ok(self, cond: bool, label: str) -> None:
        mark = "PASS" if cond else "FAIL"
        print(f"  [{mark}] {label}")
        if cond:
            self.passed += 1
        else:
            self.failed += 1


def _choose(s: Session, npc_id: str, idx: int):
    data = s.talk(npc_id)
    assert data["scene"], f"no scene for {npc_id}"
    return s.choose(npc_id, data["scene"]["id"], idx)


def run() -> int:
    c = Check()

    print("\n== Brain: remember/recall/improve/forget ==")
    s = Session("v")
    _choose(s, "npc:mira", 0)  # pay debt
    c.ok(bool(s.brain.g.find_edge("owes-favor", "npc:mira", PLAYER)),
         "remember() wrote owes-favor edge")
    c.ok(s.brain.disposition("npc:mira")["mood"] in ("warm", "friendly"),
         "recall()/disposition reads warm after help")
    c.ok(bool(s.brain.g.find_edge("told-about", "npc:mira", "npc:sela")),
         "improve() propagated a told-about rumor to same-district NPC")
    c.ok(s.brain.disposition("npc:sela")["trust"] > 0,
         "unmet NPC (Sela) leans positive purely from gossip")

    print("\n== Act progression ==")
    _choose(s, "npc:dorin", 0)  # return tongs
    _choose(s, "npc:voss", 0)   # return seal
    c.ok(s.act == 2, "Act advances to 2 after Act-1 milestones")

    print("\n== Good-karma full run ==")
    g = Session("good")
    for npc, i in [("npc:mira", 0), ("npc:dorin", 0), ("npc:voss", 0)]:
        _choose(g, npc, i)
    for npc, i in [("npc:sela", 0), ("npc:crier", 1), ("npc:crispin", 1)]:
        _choose(g, npc, i)
    for npc, i in [("npc:dorin", 1), ("npc:renna", 0), ("npc:crispin", 0)]:
        _choose(g, npc, i)
    _choose(g, "npc:sela", 0)   # brew potion
    c.ok(any(i["id"] == "item:memory_potion" for i in g.state()["inventory"]),
         "Memory Potion brewed from recipe + forge-salt")
    _choose(g, "npc:voss", 0)   # trusted -> gate
    c.ok(g.act == 5, "Reached Act 5")
    res = _choose(g, "npc:archon", 0)
    c.ok(res["ending"]["code"] == "A", "Good-karma ending A unlocked")

    print("\n== Bad-karma full run ==")
    b = Session("bad")
    for npc, i in [("npc:mira", 1), ("npc:dorin", 1), ("npc:voss", 1)]:
        _choose(b, npc, i)
    for npc, i in [("npc:sela", 0), ("npc:crier", 0), ("npc:crispin", 0)]:
        _choose(b, npc, i)
    for npc, i in [("npc:dorin", 0), ("npc:renna", 1), ("npc:crispin", 0)]:
        _choose(b, npc, i)
    _choose(b, "npc:voss", 2)   # forge entry with stolen seal
    res = _choose(b, "npc:archon", 0)
    c.ok(res["ending"]["code"] == "C", "Bad-karma ending C unlocked")

    print("\n== forget() potion flips a hostile NPC ==")
    p = Session("potion")
    _choose(p, "npc:mira", 0)
    _choose(p, "npc:dorin", 0)
    _choose(p, "npc:voss", 1)   # steal seal -> hostile
    before = p.brain.disposition("npc:voss")["mood"]
    p.inventory.add("item:memory_potion")
    p.use_potion("npc:voss")
    after = p.brain.disposition("npc:voss")["mood"]
    c.ok(before == "hostile" and after != "hostile",
         f"Voss went {before} -> {after} after forget()")

    print("\n== Secret ending (altruistic potion) ==")
    d = Session("secret")
    for npc, i in [("npc:mira", 0), ("npc:dorin", 0), ("npc:voss", 0)]:
        _choose(d, npc, i)
    for npc, i in [("npc:sela", 0), ("npc:crier", 2), ("npc:crispin", 1)]:
        _choose(d, npc, i)
    for npc, i in [("npc:dorin", 1), ("npc:renna", 0), ("npc:crispin", 0)]:
        _choose(d, npc, i)
    _choose(d, "npc:sela", 0)   # brew
    _choose(d, "npc:renna", 0)  # spend potion to free Renna
    _choose(d, "npc:voss", 1)   # enter with Dorin's key
    res = _choose(d, "npc:archon", 0)
    c.ok(res["ending"]["code"] == "D", "Secret ending D unlocked")

    print(f"\n=== {c.passed} passed, {c.failed} failed ===")
    return 1 if c.failed else 0


if __name__ == "__main__":
    sys.exit(run())
