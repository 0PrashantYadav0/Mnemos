"""The Mnemos Oracle: a local, graph-analyzing recommendation engine.

This is the "AI" that decides which task is best for the player next. It does
NOT call any external model -- it reasons directly over the Cognee-style memory
graph the player is building: disposition edges, favours owed, faction ties,
inventory, and act progress. It forecasts the likely ending and recommends the
open task that most improves the player's trajectory, with a human explanation.
"""
from __future__ import annotations

from ..brain import PLAYER
from .tasks import tasks_for_act


def forecast(session) -> dict:
    """Project the likely ending from the current graph, with a karma score."""
    g = session.brain.g
    helped = len(g.edges_from(PLAYER, "helped"))
    harmed = len([e for e in g.edges.values() if e.type == "harmed"])
    favors = len(g.edges_to(PLAYER, "owes-favor"))
    renna_ok = "renna_ally" in session.flags and "betrayed_renna" not in session.flags

    # a simple, legible trajectory score in [-1, 1]
    raw = (helped * 1.0 - harmed * 1.4) + favors * 0.6 + (0.8 if renna_ok else 0.0)
    score = max(-1.0, min(1.0, raw / 8.0))

    if "used_potion_altruistic" in session.flags:
        likely, kind = "D", "secret"
    elif favors >= 3 and renna_ok:
        likely, kind = "A", "good"
    elif "betrayed_renna" in session.flags or harmed >= 3:
        likely, kind = "C", "bad"
    else:
        likely, kind = "B", "neutral"

    labels = {"A": "The Town That Remembers", "B": "Hollow Victory",
              "C": "The Stranger, Forgotten", "D": "The Amnesiac's Mercy"}
    return {
        "score": round(score, 2), "likely_ending": likely,
        "likely_label": labels[likely], "kind": kind,
        "helped": helped, "harmed": harmed, "favors": favors,
        "renna_ally": renna_ok,
    }


def _score_task(session, task: dict, fc: dict) -> tuple[float, str]:
    """Score how valuable pursuing this task is right now, + a reason."""
    g = session.brain.g
    npc = task["npc"]
    disp = session.brain.disposition(npc) if npc != "npc:archon" else None
    score = 1.0
    reason = task["hint"]

    if task["category"] == "finale":
        # finale/gate tasks are terminal -- always the priority once reachable
        score = 10.0
        reason = "This opens the path to the ending. Handle it."
        return score, reason

    # A hostile/wary NPC blocking a payoff is high-value to address
    if disp and disp["mood"] in ("hostile", "wary"):
        score += 2.0
        reason = (f"{_name(session, npc)} is {disp['mood']} toward you -- mending "
                  "this now stops a rumour from spreading further.")

    # If we're trending badly, prioritise reputation-repair tasks
    if fc["kind"] in ("bad", "neutral") and task["category"] == "reputation":
        score += 2.5
        if disp and disp["mood"] not in ("hostile", "wary"):
            reason = (f"You're drifting toward '{fc['likely_label']}'. A kindness to "
                      f"{_name(session, npc)} pulls you back.")

    # Items gate the finale -- weight them up in later acts
    if task["category"] == "item":
        score += 1.5
        if task["id"] == "t_sela" and "has_recipe" not in session.flags:
            reason = "The Memory Potion recipe unlocks the game's signature move. Get it."
        if task["id"] == "t_dorinkey":
            if g.find_edge("owes-favor", "npc:dorin", PLAYER):
                score += 1.5
                reason = "Dorin owes you -- collect the Archive Key while it's free."
            else:
                reason = "Dorin may refuse the key. Have a backup way through the gate."

    # Faction choice: nudge toward independence when trajectory is uncertain
    if task["category"] == "faction":
        score += 0.5
        reason = "Staying independent keeps every ending on the table."

    # Building toward the good ending: favours matter
    if fc["favors"] < 3 and task["category"] == "reputation" and disp \
            and disp["mood"] in ("neutral", "friendly", "warm"):
        score += 1.0
        reason = (f"You have {fc['favors']} favour(s); the true ending wants 3+. "
                  f"Helping {_name(session, npc)} earns another.")

    return score, reason


def recommend(session) -> dict:
    """Return the Oracle's forecast + the single best next task + full list."""
    fc = forecast(session)
    open_tasks = [t for t in tasks_for_act(session.act)
                  if t["done_flag"] is None or t["done_flag"] not in session.flags]

    scored = []
    for t in open_tasks:
        s, why = _score_task(session, t, fc)
        scored.append({"id": t["id"], "title": t["title"], "npc": t["npc"],
                       "desc": t["desc"], "score": round(s, 2), "reason": why})
    scored.sort(key=lambda x: x["score"], reverse=True)

    best = scored[0] if scored else None
    advice = _advice_line(session, fc, best)
    return {
        "forecast": fc,
        "recommended": best,
        "candidates": scored,
        "advice": advice,
    }


def _advice_line(session, fc: dict, best) -> str:
    if best is None:
        return "The threads of this act are all resolved. Press on."
    tail = ""
    if fc["kind"] == "good":
        tail = " You're on course for the true ending -- keep it up."
    elif fc["kind"] == "bad":
        tail = " The town is turning against you. There is still time to change that."
    elif fc["kind"] == "secret" :
        tail = " A rare path is opening to you."
    return f"Oracle: Seek out '{best['title']}'. {best['reason']}{tail}"


def _name(session, npc_id: str) -> str:
    n = session.brain.g.get_node(npc_id)
    return n.props.get("name", npc_id) if n else npc_id
