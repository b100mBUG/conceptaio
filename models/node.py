"""
models/node.py

Pure Python data structures describing an infrastructure node placed on the
canvas. Contains no Rio imports, so this module stays UI-agnostic so it can be
unit tested and reused by the simulation engine in isolation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeType(str, Enum):
    CLIENT = "client"
    LOAD_BALANCER = "load_balancer"
    APP_SERVER = "app_server"
    CACHE = "cache"
    DATABASE = "database"
    QUEUE = "queue"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


# Baseline QPS capacity per node type (per replica), used as sane defaults
# when a node is dropped onto the canvas. Editable via the inspector panel.
DEFAULT_CAPACITY_QPS: dict[NodeType, int] = {
    NodeType.CLIENT: 0,  # clients generate traffic, they don't serve it
    NodeType.LOAD_BALANCER: 50_000,
    NodeType.APP_SERVER: 2_000,
    NodeType.CACHE: 40_000,
    NodeType.DATABASE: 5_000,
    NodeType.QUEUE: 20_000,
}

# Baseline processing latency (ms) contributed by a healthy node of this type.
DEFAULT_BASE_LATENCY_MS: dict[NodeType, float] = {
    NodeType.CLIENT: 0.0,
    NodeType.LOAD_BALANCER: 1.0,
    NodeType.APP_SERVER: 15.0,
    NodeType.CACHE: 0.5,
    NodeType.DATABASE: 8.0,
    NodeType.QUEUE: 3.0,
}

_CAPACITY_SENTINEL = -1


@dataclass
class NodeParams:
    """Configurable engineering parameters, editable from the inspector."""

    connection_pool_size: int = 100
    replica_count: int = 1
    cache_strategy: str = "LRU"  # LRU | LFU | write-through | write-back
    cache_hit_pct: int = 80  # % of traffic a cache absorbs (cache nodes only)
    sharding_key: str = ""
    capacity_qps: int = _CAPACITY_SENTINEL  # per-replica; -1 = use type default


@dataclass
class Node:
    """A single infrastructure node instance placed on the canvas."""

    node_type: NodeType
    x: float = 0.0
    y: float = 0.0
    title: str = ""
    node_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    params: NodeParams = field(default_factory=NodeParams)
    health: HealthStatus = HealthStatus.HEALTHY

    def __post_init__(self) -> None:
        if not self.title:
            self.title = self.node_type.value.replace("_", " ").title()
        if self.params.capacity_qps == _CAPACITY_SENTINEL:
            self.params.capacity_qps = DEFAULT_CAPACITY_QPS.get(self.node_type, 1_000)

    @property
    def base_latency_ms(self) -> float:
        return DEFAULT_BASE_LATENCY_MS.get(self.node_type, 5.0)

    @property
    def effective_capacity_qps(self) -> float:
        """Total capacity across all replicas."""
        return self.params.capacity_qps * max(self.params.replica_count, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value,
            "title": self.title,
            "x": self.x,
            "y": self.y,
            "health": self.health.value,
            "params": {
                "connection_pool_size": self.params.connection_pool_size,
                "replica_count": self.params.replica_count,
                "cache_strategy": self.params.cache_strategy,
                "cache_hit_pct": self.params.cache_hit_pct,
                "sharding_key": self.params.sharding_key,
                "capacity_qps": self.params.capacity_qps,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Node":
        raw_params = dict(data.get("params", {}))
        # Tolerate older save files that predate newer parameters.
        known = {f for f in NodeParams.__dataclass_fields__}
        params = NodeParams(**{k: v for k, v in raw_params.items() if k in known})
        return cls(
            node_type=NodeType(data["node_type"]),
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            title=data.get("title", ""),
            node_id=data.get("node_id", uuid.uuid4().hex[:8]),
            params=params,
            health=HealthStatus(data.get("health", "healthy")),
        )


@dataclass
class Edge:
    """A directed connection between two nodes (traffic flows source -> target)."""

    source_id: str
    target_id: str
    edge_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Edge":
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            edge_id=data.get("edge_id", uuid.uuid4().hex[:8]),
        )
