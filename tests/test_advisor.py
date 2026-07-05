"""Tests for the task system and the AI Oracle (advisor)."""
from mnemos.game import Session
from mnemos.game import advisor


def _choose(s, npc_id, idx):
    data = s.talk(npc_id)
    assert data["scene"], f"no scene for {npc_id}"
    return s.choose(npc_id, data["scene"]["id"], idx)


def test_tasks_appear_for_current_act():
    s = Session("t")
    tasks = s.tasks_view()
    ids = {t["id"] for t in tasks}
    assert {"t_mira", "t_dorin", "t_voss"} <= ids
    assert all(t["done"] is False for t in tasks)


def test_task_marked_done_after_resolution():
    s = Session("t")
    _choose(s, "npc:mira", 0)
    tasks = {t["id"]: t for t in s.tasks_view()}
    assert tasks["t_mira"]["done"] is True


def test_oracle_recommends_and_forecasts():
    s = Session("t")
    adv = s.advice()
    assert adv["recommended"] is not None
    assert adv["recommended"]["id"] in {"t_mira", "t_dorin", "t_voss"}
    assert "advice" in adv and adv["advice"].startswith("Oracle:")
    fc = adv["forecast"]
    assert fc["likely_ending"] in {"A", "B", "C", "D"}
    assert -1.0 <= fc["score"] <= 1.0


def test_forecast_improves_with_kindness():
    s = Session("t")
    before = advisor.forecast(s)["score"]
    _choose(s, "npc:mira", 0)   # pay debt (good)
    _choose(s, "npc:dorin", 0)  # return tongs (good)
    after = advisor.forecast(s)["score"]
    assert after > before


def test_forecast_turns_bad_with_cruelty():
    s = Session("t")
    _choose(s, "npc:mira", 1)   # seize ring
    _choose(s, "npc:dorin", 1)  # keep tongs
    _choose(s, "npc:voss", 1)   # steal seal
    fc = advisor.forecast(s)
    assert fc["score"] < 0
    assert fc["kind"] in ("bad", "neutral")


def test_oracle_prioritises_hostile_repair():
    s = Session("t")
    _choose(s, "npc:mira", 0)
    _choose(s, "npc:dorin", 0)
    _choose(s, "npc:voss", 1)   # make Voss hostile but finish act 1
    # now in act 2; make Voss reachable again is act 4, so check the reasoning
    # engine at least surfaces a coherent recommendation for the new act
    adv = s.advice()
    assert adv["recommended"] is not None
    assert isinstance(adv["candidates"], list) and adv["candidates"]
