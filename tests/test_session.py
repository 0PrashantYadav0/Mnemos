"""End-to-end tests driving full playthroughs through the Session engine."""
import pytest

from mnemos.game import Session


def talk_scene(s: Session, npc_id: str):
    data = s.talk(npc_id)
    return data


def choose(s: Session, npc_id: str, choice_index: int):
    """Talk to find the current scene, then make a choice by raw story index."""
    data = s.talk(npc_id)
    assert data["scene"] is not None, f"no active scene for {npc_id}"
    scene_id = data["scene"]["id"]
    res = s.choose(npc_id, scene_id, choice_index)
    assert "error" not in res, res
    return res


def do_act1(s):
    choose(s, "npc:mira", 0)   # pay debt
    choose(s, "npc:dorin", 0)  # return tongs
    choose(s, "npc:voss", 0)   # return seal
    assert s.act == 2


def test_act1_advances_and_writes_memory():
    s = Session("t")
    do_act1(s)
    assert s.brain.g.find_edge("owes-favor", "npc:mira", "player:stranger")
    assert "paid_mira_debt" in s.flags
    assert s.reputation()["helped"] == 3


def test_rumor_reaches_unmet_npc():
    s = Session("t")
    choose(s, "npc:mira", 0)  # pay debt -> improve mira -> gossip to market NPCs
    # Sela is in the market district: she should now lean positive by hearsay
    disp = s.brain.disposition("npc:sela")
    assert disp["trust"] > 0
    # and the graph literally has the told-about edge
    assert s.brain.g.find_edge("told-about", "npc:mira", "npc:sela")


def test_good_karma_full_playthrough():
    s = Session("good")
    do_act1(s)
    # Act 2
    choose(s, "npc:sela", 0)     # accept recipe (rumor made her warm)
    choose(s, "npc:crier", 1)    # free market
    choose(s, "npc:crispin", 1)  # expose crispin
    assert s.act == 3
    # Act 3
    choose(s, "npc:dorin", 1)    # key + forge-salt
    choose(s, "npc:renna", 0)    # keep faith
    choose(s, "npc:crispin", 0)  # spare
    assert s.act == 4
    # Act 4: brew potion, then pass the gate via trust
    choose(s, "npc:sela", 0)     # brew potion (has recipe + forge-salt)
    assert any(i["id"] == "item:memory_potion" for i in s.state()["inventory"])
    choose(s, "npc:voss", 0)     # trusted -> walk through
    assert s.act == 5
    # Act 5 finale
    res = choose(s, "npc:archon", 0)
    assert res["ending"]["code"] == "A"
    assert res["ending"]["kind"] == "good"


def test_bad_karma_full_playthrough():
    s = Session("bad")
    # Act 1 - all cruelty
    choose(s, "npc:mira", 1)   # seize ring
    choose(s, "npc:dorin", 1)  # keep tongs
    choose(s, "npc:voss", 1)   # steal seal
    assert s.act == 2
    # Act 2
    choose(s, "npc:sela", 0)     # overcharge scene (bad), still done_sela
    choose(s, "npc:crier", 0)    # watch
    choose(s, "npc:crispin", 0)  # lie for crispin (harms sela)
    assert s.act == 3
    # Act 3 - dorin refuses (distrust), betray renna
    choose(s, "npc:dorin", 0)    # refuse scene -> done_dorinkey
    choose(s, "npc:renna", 1)    # betray
    choose(s, "npc:crispin", 0)  # skip scene
    assert s.act == 4
    # Act 4 - forge entry with stolen seal
    choose(s, "npc:voss", 2)     # forge entry with seal
    assert s.act == 5
    res = choose(s, "npc:archon", 0)
    assert res["ending"]["code"] == "C"
    assert res["ending"]["kind"] == "bad"


def test_potion_forget_flips_hostile_npc():
    s = Session("potion")
    # steal seal -> voss hostile
    choose(s, "npc:mira", 0)
    choose(s, "npc:dorin", 0)
    choose(s, "npc:voss", 1)   # steal seal -> harmed + distrust + rumor
    assert s.brain.disposition("npc:voss")["mood"] == "hostile"
    # give the player a potion directly and use it
    s.inventory.add("item:memory_potion")
    res = s.use_potion("npc:voss")
    assert "error" not in res
    assert res["after"]["trust"] >= res["before"]["trust"]
    assert s.brain.disposition("npc:voss")["mood"] != "hostile"
    assert "voss_forgiven" in s.flags


def test_secret_ending_altruistic_potion():
    s = Session("secret")
    do_act1(s)
    choose(s, "npc:sela", 0)
    choose(s, "npc:crier", 2)    # independent
    choose(s, "npc:crispin", 1)  # expose
    choose(s, "npc:dorin", 1)    # key + salt
    choose(s, "npc:renna", 0)    # keep faith (ally)
    choose(s, "npc:crispin", 0)  # spare
    assert s.act == 4
    choose(s, "npc:sela", 0)     # brew potion
    # use potion altruistically on Renna instead of Voss
    choose(s, "npc:renna", 0)    # free Renna scene -> used_potion_altruistic
    assert "used_potion_altruistic" in s.flags
    # now reach the gate another way: Dorin's key
    choose(s, "npc:voss", 1)     # unlock with archive key
    assert s.act == 5
    res = choose(s, "npc:archon", 0)
    assert res["ending"]["code"] == "D"


def test_use_potion_requires_potion():
    s = Session("nopotion")
    res = s.use_potion("npc:voss")
    assert "error" in res
