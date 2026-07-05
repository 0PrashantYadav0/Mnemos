"""In-memory knowledge graph store.

A tiny, dependency-free stand-in for a hybrid graph+vector memory (the role
Cognee plays in the original plan). It keeps typed nodes and typed, weighted,
directed edges, plus a naive lexical similarity search over text that acts as
our "vector index". Everything is deterministic and local -- no network, no
embeddings service, no build step.

The public surface intentionally mirrors what a graph memory needs:
add/get nodes, add/find/remove edges, and a text search. The higher-level
``remember / recall / improve / forget`` verbs live in :mod:`mnemos.brain.engine`.
"""
from __future__ import annotations

import itertools
import re
import time
from dataclasses import dataclass, field
from typing import Iterable


_WORD = re.compile(r"[a-z0-9']+")


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall((text or "").lower()))


@dataclass
class Node:
    """A typed graph node (Player, NPC, Event, Item, Location, Faction, Rumor)."""

    id: str
    type: str
    props: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "type": self.type, "props": dict(self.props)}


@dataclass
class Edge:
    """A typed, weighted, directed relationship between two nodes."""

    id: int
    type: str
    src: str
    dst: str
    weight: float = 1.0
    props: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "src": self.src,
            "dst": self.dst,
            "weight": round(self.weight, 4),
            "props": dict(self.props),
        }


class GraphStore:
    """Deterministic, in-memory typed property graph."""

    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}
        self.edges: dict[int, Edge] = {}
        self._edge_ids = itertools.count(1)

    # ---- nodes -------------------------------------------------------------
    def upsert_node(self, node_id: str, type: str, **props) -> Node:
        node = self.nodes.get(node_id)
        if node is None:
            node = Node(id=node_id, type=type, props=dict(props))
            self.nodes[node_id] = node
        else:
            node.type = type or node.type
            node.props.update(props)
        return node

    def get_node(self, node_id: str) -> Node | None:
        return self.nodes.get(node_id)

    def nodes_of_type(self, type: str) -> list[Node]:
        return [n for n in self.nodes.values() if n.type == type]

    # ---- edges -------------------------------------------------------------
    def add_edge(
        self, type: str, src: str, dst: str, weight: float = 1.0, **props
    ) -> Edge:
        """Add an edge. Idempotent for (type, src, dst): existing edge is
        reinforced (weight accumulated, props merged) rather than duplicated."""
        existing = self.find_edge(type, src, dst)
        if existing is not None:
            existing.weight += weight
            existing.props.update(props)
            existing.props["reinforced_at"] = time.time()
            return existing
        edge = Edge(
            id=next(self._edge_ids),
            type=type,
            src=src,
            dst=dst,
            weight=weight,
            props={"created_at": time.time(), **props},
        )
        self.edges[edge.id] = edge
        return edge

    def find_edge(self, type: str, src: str, dst: str) -> Edge | None:
        for e in self.edges.values():
            if e.type == type and e.src == src and e.dst == dst:
                return e
        return None

    def edges_from(self, src: str, type: str | None = None) -> list[Edge]:
        return [
            e
            for e in self.edges.values()
            if e.src == src and (type is None or e.type == type)
        ]

    def edges_to(self, dst: str, type: str | None = None) -> list[Edge]:
        return [
            e
            for e in self.edges.values()
            if e.dst == dst and (type is None or e.type == type)
        ]

    def edges_between(self, a: str, b: str) -> list[Edge]:
        return [
            e
            for e in self.edges.values()
            if (e.src == a and e.dst == b) or (e.src == b and e.dst == a)
        ]

    def remove_edges(self, edges: Iterable[Edge]) -> int:
        removed = 0
        for e in list(edges):
            if e.id in self.edges:
                del self.edges[e.id]
                removed += 1
        return removed

    def remove_node(self, node_id: str) -> None:
        self.nodes.pop(node_id, None)
        self.remove_edges(
            [e for e in self.edges.values() if e.src == node_id or e.dst == node_id]
        )

    # ---- "vector" search (naive lexical similarity) ------------------------
    def search_text(self, query: str, node_type: str | None = None, k: int = 8):
        """Return up to ``k`` (node, score) pairs whose ``props['text']`` or
        ``props['summary']`` best overlaps the query. This is our local,
        deterministic stand-in for vector similarity."""
        q = _tokens(query)
        if not q:
            return []
        scored: list[tuple[Node, float]] = []
        for node in self.nodes.values():
            if node_type and node.type != node_type:
                continue
            text = node.props.get("summary") or node.props.get("text") or ""
            toks = _tokens(text)
            if not toks:
                continue
            overlap = len(q & toks)
            if overlap:
                score = overlap / len(q | toks)  # Jaccard
                scored.append((node, score))
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored[:k]

    # ---- serialization -----------------------------------------------------
    def snapshot(self) -> dict:
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
        }
