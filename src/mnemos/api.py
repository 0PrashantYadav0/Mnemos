"""FastAPI app: the game/sim server, the decoupled NPC Brain microservice,
and static hosting for the web client. All local, one process.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .brain import MnemosBrain, PLAYER
from .game import Session

UI_DIR = Path(__file__).parent / "ui"

app = FastAPI(title="Mnemos", version="0.1.0")

# In-memory session store (transient scene state). Memory of record is the graph.
SESSIONS: dict[str, Session] = {}

# A standalone Brain instance to demo the decoupled microservice via curl/tests.
DEMO_BRAIN = MnemosBrain()


# ============================ GAME API ==================================
def _get(session_id: str) -> Session:
    s = SESSIONS.get(session_id)
    if s is None:
        raise HTTPException(404, "session not found")
    return s


@app.post("/api/session/new")
def new_session():
    sid = uuid.uuid4().hex[:12]
    SESSIONS[sid] = Session(sid)
    return SESSIONS[sid].state()


@app.get("/api/session/{sid}/state")
def get_state(sid: str):
    return _get(sid).state()


class MoveReq(BaseModel):
    pos: list[int]


@app.post("/api/session/{sid}/move")
def move(sid: str, req: MoveReq):
    s = _get(sid)
    s.pos = req.pos[:2]
    return {"pos": s.pos}


class TalkReq(BaseModel):
    npc_id: str


@app.post("/api/session/{sid}/talk")
def talk(sid: str, req: TalkReq):
    return _get(sid).talk(req.npc_id)


class ChooseReq(BaseModel):
    npc_id: str
    scene_id: str
    choice_index: int


@app.post("/api/session/{sid}/choose")
def choose(sid: str, req: ChooseReq):
    res = _get(sid).choose(req.npc_id, req.scene_id, req.choice_index)
    if "error" in res:
        raise HTTPException(400, res["error"])
    return res


class PotionReq(BaseModel):
    target: str


@app.post("/api/session/{sid}/potion")
def potion(sid: str, req: PotionReq):
    res = _get(sid).use_potion(req.target)
    if "error" in res:
        raise HTTPException(400, res["error"])
    return res


@app.get("/api/session/{sid}/graph")
def graph(sid: str):
    return _get(sid).brain.snapshot()


@app.get("/api/session/{sid}/advice")
def advice(sid: str):
    return _get(sid).advice()


# =================== DECOUPLED NPC BRAIN MICROSERVICE ===================
# Four HTTP verbs. Drop-in for any game. Operates on DEMO_BRAIN.
class RememberReq(BaseModel):
    actor: str = PLAYER
    target: str
    deed: str
    summary: str
    act: str = "act1"
    creates_favor: bool = False
    witnessed_by: list[str] | None = None


@app.post("/brain/remember")
def brain_remember(req: RememberReq):
    return DEMO_BRAIN.remember(**req.model_dump())


class RecallReq(BaseModel):
    subject: str
    about: str = PLAYER
    topic: str = ""
    k: int = 8


@app.post("/brain/recall")
def brain_recall(req: RecallReq):
    return DEMO_BRAIN.recall(**req.model_dump())


class ImproveReq(BaseModel):
    scope: str
    propagate: bool = True


@app.post("/brain/improve")
def brain_improve(req: ImproveReq):
    return DEMO_BRAIN.improve(**req.model_dump())


class ForgetReq(BaseModel):
    target_subject: str
    target_about: str = PLAYER
    edges: list[str] | None = None
    events: list[str] | None = None
    cascade_rumors: bool = True


@app.post("/brain/forget")
def brain_forget(req: ForgetReq):
    return DEMO_BRAIN.forget(**req.model_dump())


@app.get("/brain/graph")
def brain_graph():
    return DEMO_BRAIN.snapshot()


# ============================ STATIC UI =================================
@app.get("/")
def index():
    return FileResponse(UI_DIR / "index.html")


app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")
