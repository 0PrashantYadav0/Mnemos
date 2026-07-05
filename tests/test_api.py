"""HTTP-level tests: the game API and the decoupled Brain microservice."""
from fastapi.testclient import TestClient

from mnemos.api import app

client = TestClient(app)


def test_full_http_flow_new_talk_choose():
    st = client.post("/api/session/new").json()
    sid = st["session_id"]
    assert st["act"] == 1
    assert len(st["npcs"]) == 8

    # talk to Mira
    t = client.post(f"/api/session/{sid}/talk", json={"npc_id": "npc:mira"}).json()
    assert t["scene"]["id"] == "1A"
    assert t["choices"]

    # choose to pay her debt (index 0)
    c = client.post(f"/api/session/{sid}/choose",
                    json={"npc_id": "npc:mira", "scene_id": "1A",
                          "choice_index": 0}).json()
    assert "result" in c
    assert c["state"]["reputation"]["favors"] == 1

    # graph endpoint reflects the write
    g = client.get(f"/api/session/{sid}/graph").json()
    assert any(e["type"] == "owes-favor" for e in g["edges"])


def test_move_endpoint():
    sid = client.post("/api/session/new").json()["session_id"]
    r = client.post(f"/api/session/{sid}/move", json={"pos": [5, 5]}).json()
    assert r["pos"] == [5, 5]


def test_potion_endpoint_requires_potion():
    sid = client.post("/api/session/new").json()["session_id"]
    r = client.post(f"/api/session/{sid}/potion", json={"target": "npc:voss"})
    assert r.status_code == 400


def test_unknown_session_404():
    r = client.get("/api/session/nope/state")
    assert r.status_code == 404


def test_index_and_static_served():
    assert client.get("/").status_code == 200
    assert client.get("/ui/app.js").status_code == 200
    assert client.get("/ui/styles.css").status_code == 200


# --- the decoupled 4-verb Brain microservice ---
def test_brain_microservice_round_trip():
    client.post("/brain/remember", json={
        "target": "npc:demo", "deed": "helped",
        "summary": "player helped demo npc", "creates_favor": True})
    r = client.post("/brain/recall", json={
        "subject": "npc:demo", "topic": "help"}).json()
    assert r["disposition"]["owes_favor"] is True

    client.post("/brain/improve", json={"scope": "npc:demo"})
    f = client.post("/brain/forget", json={
        "target_subject": "npc:demo", "edges": ["helped", "trusts"]}).json()
    assert "removed_edges" in f
