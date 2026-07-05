"""The NPC Brain: remember / recall / improve / forget over the graph.

This is the decoupled "memory engine" from the plan. It speaks four verbs and
nothing else knows how memory is stored. Swap this out for a real Cognee-backed
implementation and the game server would not change.

Edge vocabulary (see MNEMOS_GAME_PLAN.md sec 5):
  helped / harmed        Player -> NPC
  owes-favor             NPC -> Player
  trusts / distrusts     NPC -> Player   (scalar dispositions live in weight)
  witnessed              NPC -> Event    (first-hand)
  told-about             NPC -> NPC      (gossip, second-hand; decays per hop)
  member-of              NPC/Player -> Faction
"""
from __future__ import annotations

import time

from .cognee_sync import CogneeCloudSync
from .graph import GraphStore

PLAYER = "player:stranger"

# How strongly each deed shifts trust, and whether it creates a favor.
DEED_TRUST = {
    "helped": +1.0,
    "harmed": -1.4,   # a betrayal counts more than a favor (severity asym.)
}


class MnemosBrain:
    """Graph-backed memory engine with rumor propagation."""

    def __init__(self, store: GraphStore | None = None, cloud: CogneeCloudSync | None = None) -> None:
        self.g = store or GraphStore()
        self.g.upsert_node(PLAYER, "Player", reputation=0.0)
        # Cognee Cloud mirror (best-effort; None if COGNEE_API_KEY is unset).
        self.cloud = cloud if cloud is not None else CogneeCloudSync.from_env()

    @property
    def cloud_active(self) -> bool:
        return bool(self.cloud and self.cloud.enabled)

    # ---- ensure helpers ----------------------------------------------------
    def ensure_npc(self, npc_id: str, **props) -> None:
        self.g.upsert_node(npc_id, "NPC", **props)

    def ensure_faction(self, faction_id: str, **props) -> None:
        self.g.upsert_node(faction_id, "Faction", **props)

    # ---- REMEMBER ----------------------------------------------------------
    def remember(
        self,
        *,
        actor: str,
        target: str,
        deed: str,
        summary: str,
        act: str = "act1",
        creates_favor: bool = False,
        witnessed_by: list[str] | None = None,
        event_id: str | None = None,
    ) -> dict:
        """Write an event and its typed edges into the graph.

        ``deed`` is one of the edge verbs (helped/harmed/...). Returns the
        created event id and the edges that were written.
        """
        ts = time.time()
        event_id = event_id or f"event:{deed}:{target}:{int(ts * 1000)}"
        self.g.upsert_node(
            event_id, "Event", summary=summary, deed=deed, act=act, timestamp=ts,
            actor=actor, target=target,
        )

        written = []
        if deed in ("helped", "harmed"):
            written.append(self.g.add_edge(deed, actor, target, weight=1.0, act=act,
                                           event=event_id))
            # disposition edge (trusts/distrusts) from target NPC back to actor
            shift = DEED_TRUST[deed]
            dtype = "trusts" if shift > 0 else "distrusts"
            written.append(self.g.add_edge(dtype, target, actor,
                                           weight=abs(shift), event=event_id))
            if creates_favor and deed == "helped":
                written.append(self.g.add_edge("owes-favor", target, actor,
                                               weight=1.0, event=event_id))
        else:
            # generic relationship edge
            written.append(self.g.add_edge(deed, actor, target, weight=1.0,
                                           event=event_id, act=act))

        # who saw it (first-hand). The target always witnesses deeds done to them.
        witnesses = set(witnessed_by or [])
        if self.g.get_node(target) and self.g.get_node(target).type == "NPC":
            witnesses.add(target)
        for w in witnesses:
            self.g.add_edge("witnessed", w, event_id, weight=1.0)

        # Mirror this memory into Cognee Cloud (best-effort; local graph is truth).
        if self.cloud:
            self.cloud.remember(f"[{act}] {summary} (deed={deed}, actor={actor}, target={target})")

        return {"event": event_id, "edges": [e.to_dict() for e in written]}

    def sync_flush(self) -> dict:
        """Push buffered memories to Cognee Cloud (call after a batch of events)."""
        return self.cloud.flush() if self.cloud else {"flushed": 0}

    def join_faction(self, faction_id: str, subject: str = PLAYER) -> dict:
        self.ensure_faction(faction_id)
        e = self.g.add_edge("member-of", subject, faction_id, weight=1.0)
        return {"edge": e.to_dict()}

    # ---- RECALL ------------------------------------------------------------
    def recall(
        self, *, subject: str, about: str = PLAYER, topic: str = "", k: int = 8
    ) -> dict:
        """What does ``subject`` know about ``about``?

        Combines direct edges (first-hand), second-hand rumors (told-about),
        and topic-matched events (the "vector" side). Returns a disposition."""
        g = self.g
        direct = []
        # direct edges either way between subject and about
        for e in g.edges_between(subject, about):
            if e.type in ("helped", "harmed", "trusts", "distrusts", "owes-favor"):
                ev = g.get_node(e.props.get("event", "")) if e.props.get("event") else None
                direct.append({
                    "edge": e.type,
                    "from": e.src,
                    "to": e.dst,
                    "weight": round(e.weight, 3),
                    "event": ev.props.get("summary") if ev else None,
                    "act": ev.props.get("act") if ev else None,
                })

        # second-hand: rumors this subject was told about, concerning `about`
        secondhand = []
        for e in g.edges_to(subject, "told-about"):
            rumor_id = e.props.get("rumor")
            rumor = g.get_node(rumor_id) if rumor_id else None
            if rumor and rumor.props.get("about") in (about, None):
                secondhand.append({
                    "edge": "told-about",
                    "from": e.src,
                    "rumor": rumor.props.get("text"),
                    "confidence": round(e.weight, 3),
                })

        # topic search over events (vector-ish)
        topical = []
        if topic:
            for node, score in g.search_text(topic, node_type="Event", k=k):
                if node.props.get("target") == about or node.props.get("actor") == about:
                    topical.append({"summary": node.props.get("summary"),
                                    "score": round(score, 3),
                                    "act": node.props.get("act")})

        return {
            "subject": subject,
            "about": about,
            "direct": direct[:k],
            "secondhand": secondhand[:k],
            "topical": topical[:k],
            "disposition": self.disposition(subject, about),
        }

    def disposition(self, subject: str, about: str = PLAYER) -> dict:
        """Compute how ``subject`` feels about ``about`` from the graph.

        trust in [-1, 1]; owes_favor bool; mood label for the UI.
        Second-hand rumor nudges trust too (but weaker: it is hearsay)."""
        g = self.g
        trust = 0.0
        for e in g.edges_between(subject, about):
            if e.type == "trusts":
                trust += e.weight
            elif e.type == "distrusts":
                trust -= e.weight
        # hearsay influence
        for e in g.edges_to(subject, "told-about"):
            rumor = g.get_node(e.props.get("rumor", ""))
            if rumor and rumor.props.get("about") in (about, None):
                trust += rumor.props.get("sentiment", 0.0) * e.weight

        owes = g.find_edge("owes-favor", subject, about) is not None
        norm = max(-1.0, min(1.0, trust / 3.0))
        if norm >= 0.4:
            mood = "warm"
        elif norm >= 0.1:
            mood = "friendly"
        elif norm > -0.1:
            mood = "neutral"
        elif norm > -0.4:
            mood = "wary"
        else:
            mood = "hostile"
        return {"trust": round(norm, 3), "owes_favor": owes, "mood": mood}

    # ---- IMPROVE / memify --------------------------------------------------
    def improve(self, *, scope: str, propagate: bool = True) -> dict:
        """Enrich + reweight + propagate rumors.

        - derive a 'kind-hearted'/'ruthless' trait on the player from deed counts
        - spread rumors from witnesses to socially-connected NPCs (told-about)
        """
        g = self.g
        result = {"traits": [], "rumors_spread": 0}

        # derive player traits
        helped = len(g.edges_from(PLAYER, "helped"))
        harmed = len(g.edges_from(PLAYER, "harmed"))
        if helped >= 3 and helped > harmed:
            g.upsert_node("trait:kind_hearted", "Trait", label="Kind-hearted")
            g.add_edge("has-trait", PLAYER, "trait:kind_hearted")
            result["traits"].append("kind_hearted")
        if harmed >= 3 and harmed >= helped:
            g.upsert_node("trait:ruthless", "Trait", label="Ruthless")
            g.add_edge("has-trait", PLAYER, "trait:ruthless")
            result["traits"].append("ruthless")

        # update player reputation scalar
        player = g.get_node(PLAYER)
        if player:
            player.props["reputation"] = round((helped - harmed) * 1.0, 2)

        if propagate:
            result["rumors_spread"] = self._propagate(scope)
        return result

    def _propagate(self, scope: str) -> int:
        """For the scoped NPC's witnessed events, gossip to same-district/faction
        NPCs via told-about edges. Confidence decays per hop; dedup + capped."""
        g = self.g
        spread = 0
        witness_edges = g.edges_from(scope, "witnessed")
        for we in witness_edges:
            event = g.get_node(we.dst)
            if not event:
                continue
            deed = event.props.get("deed")
            if deed not in ("helped", "harmed"):
                continue
            sentiment = 0.5 if deed == "helped" else -0.6
            rumor_id = f"rumor:{event.id}"
            if not g.get_node(rumor_id):
                text = self._rumor_text(scope, event)
                g.upsert_node(rumor_id, "Rumor", text=text, about=PLAYER,
                              sentiment=sentiment, origin=scope,
                              event=event.id, spread_count=0)
            listeners = self._neighbors(scope)
            for listener in listeners:
                # dedup: don't re-tell the same rumor to the same listener
                if g.find_edge("told-about", scope, listener):
                    told = g.find_edge("told-about", scope, listener)
                    if told.props.get("rumor") == rumor_id:
                        continue
                g.add_edge("told-about", scope, listener, weight=0.7,
                           rumor=rumor_id)
                rn = g.get_node(rumor_id)
                rn.props["spread_count"] = rn.props.get("spread_count", 0) + 1
                spread += 1
        return spread

    def _rumor_text(self, origin: str, event) -> str:
        name = (self.g.get_node(origin).props.get("name") if self.g.get_node(origin)
                else origin)
        deed = event.props.get("deed")
        verb = "speaks well of" if deed == "helped" else "warns others about"
        return f"{name} {verb} the stranger: {event.props.get('summary')}"

    def _neighbors(self, npc_id: str) -> list[str]:
        """NPCs socially connected to ``npc_id`` (same district or faction)."""
        g = self.g
        node = g.get_node(npc_id)
        if not node:
            return []
        district = node.props.get("district")
        factions = {e.dst for e in g.edges_from(npc_id, "member-of")}
        out = []
        for other in g.nodes_of_type("NPC"):
            if other.id == npc_id:
                continue
            same_district = district and other.props.get("district") == district
            other_factions = {e.dst for e in g.edges_from(other.id, "member-of")}
            same_faction = bool(factions & other_factions)
            if same_district or same_faction:
                out.append(other.id)
        return out

    # ---- FORGET ------------------------------------------------------------
    def forget(
        self,
        *,
        target_subject: str,
        target_about: str = PLAYER,
        edges: list[str] | None = None,
        events: list[str] | None = None,
        cascade_rumors: bool = True,
    ) -> dict:
        """Surgical deletion: remove specific grudge edges between two nodes,
        optional events, and (optionally) the rumor cascade seeded from them.
        Leaves the rest of the graph intact."""
        g = self.g
        edge_types = set(edges or ["harmed", "distrusts"])
        removed_edges = 0
        removed_rumors = 0
        removed_events = 0

        # collect events referenced by the edges we're about to remove
        seed_events: set[str] = set(events or [])
        to_remove = []
        for e in g.edges_between(target_subject, target_about):
            if e.type in edge_types:
                if e.props.get("event"):
                    seed_events.add(e.props["event"])
                to_remove.append(e)
        removed_edges += g.remove_edges(to_remove)

        # cascade: remove rumors born from these events + the told-about edges
        if cascade_rumors:
            for rumor in list(g.nodes_of_type("Rumor")):
                if rumor.props.get("event") in seed_events:
                    told = [e for e in g.edges.values()
                            if e.type == "told-about"
                            and e.props.get("rumor") == rumor.id]
                    removed_edges += g.remove_edges(told)
                    g.remove_node(rumor.id)
                    removed_rumors += 1

        # remove the seed events themselves + their witnessed edges
        for ev_id in seed_events:
            if g.get_node(ev_id):
                g.remove_node(ev_id)
                removed_events += 1

        # Best-effort cascade to the Cognee Cloud mirror.
        if self.cloud:
            self.cloud.forget(f"grudge between {target_subject} and {target_about}")

        return {
            "removed_edges": removed_edges,
            "removed_rumors": removed_rumors,
            "removed_events": removed_events,
            "disposition_after": self.disposition(target_subject, target_about),
        }

    # ---- introspection -----------------------------------------------------
    def snapshot(self) -> dict:
        return self.g.snapshot()
