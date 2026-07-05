"""Tests for the graph-memory NPC Brain."""
from mnemos.brain import MnemosBrain, GraphStore, PLAYER


def make_brain():
    b = MnemosBrain()
    for npc, dist in [("npc:mira", "market"), ("npc:sela", "market"),
                      ("npc:dorin", "forge")]:
        b.ensure_npc(npc, name=npc.split(":")[1], district=dist)
    return b


def test_graph_edge_idempotent_reinforces():
    g = GraphStore()
    g.upsert_node("a", "NPC"); g.upsert_node("b", "NPC")
    e1 = g.add_edge("helped", "a", "b", weight=1.0)
    e2 = g.add_edge("helped", "a", "b", weight=1.0)
    assert e1.id == e2.id           # same edge, no duplicate
    assert e2.weight == 2.0         # reinforced


def test_remember_writes_edges_and_favor():
    b = make_brain()
    out = b.remember(actor=PLAYER, target="npc:mira", deed="helped",
                     summary="paid debt", creates_favor=True)
    assert out["event"].startswith("event:")
    assert b.g.find_edge("helped", PLAYER, "npc:mira")
    assert b.g.find_edge("trusts", "npc:mira", PLAYER)
    assert b.g.find_edge("owes-favor", "npc:mira", PLAYER)


def test_harm_lowers_trust_more_than_help_raises():
    b = make_brain()
    b.remember(actor=PLAYER, target="npc:mira", deed="helped", summary="favor")
    up = b.disposition("npc:mira")["trust"]
    b2 = make_brain()
    b2.remember(actor=PLAYER, target="npc:mira", deed="harmed", summary="wrong")
    down = b2.disposition("npc:mira")["trust"]
    assert up > 0 and down < 0
    assert abs(down) > abs(up)   # betrayal weighed heavier


def test_recall_returns_direct_and_disposition():
    b = make_brain()
    b.remember(actor=PLAYER, target="npc:mira", deed="helped",
               summary="paid debt", creates_favor=True)
    r = b.recall(subject="npc:mira", about=PLAYER, topic="debt")
    assert r["disposition"]["owes_favor"] is True
    assert r["disposition"]["mood"] in ("warm", "friendly")
    assert any(d["edge"] == "helped" for d in r["direct"])


def test_improve_propagates_rumor_to_same_district():
    b = make_brain()
    # mira and sela share 'market' district -> gossip should reach sela
    b.remember(actor=PLAYER, target="npc:mira", deed="helped", summary="paid debt")
    res = b.improve(scope="npc:mira", propagate=True)
    assert res["rumors_spread"] >= 1
    told = b.g.find_edge("told-about", "npc:mira", "npc:sela")
    assert told is not None
    # sela's disposition now nudged by hearsay even without direct contact
    assert b.disposition("npc:sela")["trust"] > 0


def test_improve_does_not_gossip_across_unconnected_npcs_only_via_link():
    b = make_brain()
    b.remember(actor=PLAYER, target="npc:mira", deed="helped", summary="x")
    b.improve(scope="npc:mira")
    # dorin is in 'forge', not market, and shares no faction here -> no told-about
    assert b.g.find_edge("told-about", "npc:mira", "npc:dorin") is None


def test_derives_kind_hearted_trait():
    b = make_brain()
    for npc in ["npc:mira", "npc:sela", "npc:dorin"]:
        b.remember(actor=PLAYER, target=npc, deed="helped", summary="help")
    b.improve(scope="npc:mira")
    assert any(n.props.get("label") == "Kind-hearted"
               for n in b.g.nodes_of_type("Trait"))


def test_forget_is_surgical():
    b = make_brain()
    b.remember(actor=PLAYER, target="npc:mira", deed="helped", summary="good",
               creates_favor=True)
    b.remember(actor=PLAYER, target="npc:mira", deed="harmed", summary="bad deed")
    b.improve(scope="npc:mira")  # spreads a rumor about the harm too
    assert b.disposition("npc:mira")["trust"] < 0.5

    res = b.forget(target_subject="npc:mira", edges=["harmed", "distrusts"],
                   cascade_rumors=True)
    assert res["removed_edges"] >= 1
    # the good edge survives -- surgical, not a nuke
    assert b.g.find_edge("helped", PLAYER, "npc:mira") is not None
    assert b.g.find_edge("harmed", PLAYER, "npc:mira") is None
    assert res["disposition_after"]["trust"] >= 0
