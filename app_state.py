"""
app_state.py

Shared application state, attached to the Rio session. Pages and components
read from it in their `build` methods and mutate it exclusively through the
methods below, then trigger a refresh on the owning page.

`ThemeSettings` is a `rio.UserSettings`, so the dark/light choice survives
restarts without any backend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import rio

from models.node import Edge, HealthStatus, Node, NodeType
from models.simulation_engine import SimulationEngine, SimulationResult
from services.ai_mentor_service import AIMentorService
from services.storage_service import StorageService

# Logical canvas size and node card size, in Rio layout units.
CANVAS_W = 130.0
CANVAS_H = 72.0
NODE_W = 12.0
NODE_H = 5.6


class ThemeSettings(rio.UserSettings):
    """Persisted per-user preferences."""

    dark_mode: bool = True


@dataclass
class Challenge:
    title: str
    brief: str
    target_qps: int
    icon: str


CHALLENGES: list[Challenge] = [
    Challenge(
        title="Design a URL Shortener",
        brief="Handle a high read:write ratio with low-latency redirects.",
        target_qps=5_000,
        icon="material/link",
    ),
    Challenge(
        title="Design a Rate Limiter",
        brief="Protect app servers from bursty clients without adding much latency.",
        target_qps=10_000,
        icon="material/speed",
    ),
    Challenge(
        title="Design a News Feed",
        brief="Fan-out writes vs fan-out reads at scale, with a cache-heavy read path.",
        target_qps=20_000,
        icon="material/monitoring",
    ),
    Challenge(
        title="Design a Chat System",
        brief="Persistent connections, message ordering, and delivery guarantees.",
        target_qps=15_000,
        icon="material/hub",
    ),
    Challenge(
        title="Freeform Sandbox",
        brief="No constraints. Build and simulate whatever you like.",
        target_qps=1_000,
        icon="material/design_services",
    ),
]


@dataclass
class AppState:
    """Everything the playground needs, in one mutable place."""

    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    client_qps: int = 1_000
    challenge_title: str = "Freeform Sandbox"

    selected_node_id: Optional[str] = None
    link_mode: bool = False
    link_source_id: Optional[str] = None

    last_result: Optional[SimulationResult] = None
    mentor_hints: list[str] = field(
        default_factory=lambda: [
            "Drop some nodes, wire them up, and run a simulation to get feedback."
        ]
    )
    mentor_problems: list[str] = field(default_factory=list)

    # Guided-lesson progress.
    guide_enabled: bool = False
    lesson_step: int = 0
    right_tab: str = "inspect"  # "guide" | "inspect"

    # Bumped on every mutation so components can rely on value inequality
    # to detect change even though lists are mutated in place.
    version: int = 0

    def __post_init__(self) -> None:
        self._storage = StorageService()
        self._mentor = AIMentorService()

    # ------------------------------------------------------------- helpers
    def _touch(self) -> None:
        self.version += 1

    def node_by_id(self, node_id: Optional[str]) -> Optional[Node]:
        if node_id is None:
            return None
        return next((n for n in self.nodes if n.node_id == node_id), None)

    # ------------------------------------------------------------- challenge
    def start_challenge(self, challenge: Challenge, guided: bool = False) -> None:
        from models.lessons import lesson_for

        self.clear_canvas()
        self.challenge_title = challenge.title
        self.client_qps = challenge.target_qps
        self.guide_enabled = guided and lesson_for(challenge.title) is not None
        self.lesson_step = 0
        self.right_tab = "guide" if self.guide_enabled else "inspect"
        self._touch()

    # ------------------------------------------------------------- palette
    def spawn_node(self, node_type: NodeType) -> Node:
        x, y = self._free_spawn_position()
        node = Node(node_type=node_type, x=x, y=y)
        self.nodes.append(node)
        self.selected_node_id = node.node_id
        self._touch()
        return node

    def _free_spawn_position(self) -> tuple[float, float]:
        """First grid slot not too close to an existing node."""
        for row in range(6):
            for col in range(8):
                x = 4.0 + col * (NODE_W + 3.0)
                y = 4.0 + row * (NODE_H + 3.5)
                if all(
                    abs(n.x - x) > NODE_W * 0.7 or abs(n.y - y) > NODE_H * 0.7
                    for n in self.nodes
                ):
                    return x, y
        return 6.0, 6.0

    # ------------------------------------------------------------- canvas
    def move_node(self, node_id: str, dx: float, dy: float) -> None:
        node = self.node_by_id(node_id)
        if node is None:
            return
        node.x = min(max(node.x + dx, 0.0), CANVAS_W - NODE_W)
        node.y = min(max(node.y + dy, 0.0), CANVAS_H - NODE_H)
        self._touch()

    def press_node(self, node_id: str) -> None:
        if self.link_mode:
            if self.link_source_id is None:
                self.link_source_id = node_id
            elif self.link_source_id != node_id:
                self.add_edge(self.link_source_id, node_id)
                self.link_source_id = None
                self.link_mode = False
            self._touch()
            return
        self.selected_node_id = node_id
        self._touch()

    def press_background(self) -> None:
        self.selected_node_id = None
        if self.link_mode:
            self.link_mode = False
            self.link_source_id = None
        self._touch()

    def toggle_link_mode(self) -> None:
        self.link_mode = not self.link_mode
        self.link_source_id = None
        self._touch()

    def add_edge(self, source_id: str, target_id: str) -> None:
        if source_id == target_id:
            return
        if any(
            e.source_id == source_id and e.target_id == target_id for e in self.edges
        ):
            return
        self.edges.append(Edge(source_id=source_id, target_id=target_id))
        self._touch()

    def delete_edge(self, edge_id: str) -> None:
        self.edges = [e for e in self.edges if e.edge_id != edge_id]
        self._touch()

    def delete_node(self, node_id: str) -> None:
        self.nodes = [n for n in self.nodes if n.node_id != node_id]
        self.edges = [
            e for e in self.edges if node_id not in (e.source_id, e.target_id)
        ]
        if self.selected_node_id == node_id:
            self.selected_node_id = None
        if self.link_source_id == node_id:
            self.link_source_id = None
        self._touch()

    # ------------------------------------------------------------- simulation
    def run_simulation(self) -> None:
        engine = SimulationEngine(nodes=list(self.nodes), edges=list(self.edges))
        result = engine.run(client_qps=float(self.client_qps))
        self.last_result = result

        metrics_by_id = {m.node_id: m for m in result.node_metrics}
        for node in self.nodes:
            m = metrics_by_id.get(node.node_id)
            if m is None or node.node_type == NodeType.CLIENT:
                node.health = HealthStatus.HEALTHY
            elif m.utilization_pct >= 100:
                node.health = HealthStatus.FAILED
            elif m.dropped_qps > 0 or m.is_bottleneck:
                node.health = HealthStatus.DEGRADED
            else:
                node.health = HealthStatus.HEALTHY

        self.mentor_hints = self._mentor.critique(result, list(self.nodes))
        self.mentor_problems = self._mentor.diagnose(
            result, list(self.nodes), list(self.edges)
        )
        self._touch()

    # ------------------------------------------------------------- persistence
    def save_design(self, name: str = "autosave") -> None:
        self._storage.save_canvas(name, list(self.nodes), list(self.edges), self.client_qps)
        self._touch()

    def load_design(self, name: str = "autosave") -> bool:
        nodes, edges, qps = self._storage.load_canvas(name)
        if not nodes:
            return False
        self.clear_canvas()
        self.nodes = nodes
        self.edges = edges
        self.client_qps = qps
        self._touch()
        return True

    def clear_canvas(self) -> None:
        self.nodes = []
        self.edges = []
        self.selected_node_id = None
        self.link_mode = False
        self.link_source_id = None
        self.last_result = None
        self.mentor_hints = [
            "Drop some nodes, wire them up, and run a simulation to get feedback."
        ]
        self.mentor_problems = []
        self._touch()
