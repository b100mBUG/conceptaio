"""
models/simulation_engine.py

Pure Python traffic simulation over the node/edge graph. No UI imports.

Improvements over the original engine:

* Nodes are processed in topological order (Kahn), so load accumulates
  correctly even on diamond-shaped graphs: no exponential re-walks and no
  double counting. Nodes trapped in a cycle are processed once at the end
  in deterministic order, so cyclic graphs degrade gracefully instead of
  recursing forever.
* Outgoing traffic is *split* across a node's children (a load balancer in
  front of two app servers sends each half the traffic), instead of every
  child receiving the full stream.
* `replica_count` actually matters: effective capacity is per-replica
  capacity times the replica count.
* Caches absorb `cache_hit_pct` percent of the traffic they serve and only
  forward the misses downstream, so adding a cache visibly protects the
  database in the numbers.
* P99 latency is the *sum* of latencies along the slowest path, not the
  single slowest node.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from models.node import Edge, Node, NodeType


@dataclass
class NodeMetrics:
    node_id: str
    title: str
    node_type: NodeType
    incoming_qps: float
    capacity_qps: float
    utilization_pct: float
    latency_ms: float
    dropped_qps: float
    is_bottleneck: bool = False


@dataclass
class SimulationResult:
    throughput_rps: float
    p99_latency_ms: float
    failure_rate_pct: float
    bottleneck_node_id: Optional[str]
    bottleneck_reason: str
    node_metrics: list[NodeMetrics] = field(default_factory=list)
    spof_node_ids: list[str] = field(default_factory=list)


# Utilization at or above this percentage marks a node as a bottleneck.
BOTTLENECK_UTILIZATION_PCT = 90.0

# Latency blow-up guard: never let headroom fall below this fraction.
MIN_HEADROOM = 0.02


class SimulationEngine:
    """Evaluates system behaviour under a given client QPS."""

    def __init__(self, nodes: list[Node], edges: list[Edge]):
        self.nodes: dict[str, Node] = {n.node_id: n for n in nodes}
        # Keep only edges whose endpoints both exist, and drop duplicates.
        seen: set[tuple[str, str]] = set()
        self.edges: list[Edge] = []
        for e in edges:
            pair = (e.source_id, e.target_id)
            if (
                e.source_id in self.nodes
                and e.target_id in self.nodes
                and e.source_id != e.target_id
                and pair not in seen
            ):
                seen.add(pair)
                self.edges.append(e)

        self._children: dict[str, list[str]] = {nid: [] for nid in self.nodes}
        self._parents: dict[str, list[str]] = {nid: [] for nid in self.nodes}
        for e in self.edges:
            self._children[e.source_id].append(e.target_id)
            self._parents[e.target_id].append(e.source_id)

    # ------------------------------------------------------------------ order
    def _processing_order(self) -> list[str]:
        """Kahn's topological sort; cycle members appended deterministically."""
        indegree = {nid: len(self._parents[nid]) for nid in self.nodes}
        queue = deque(sorted(nid for nid, d in indegree.items() if d == 0))
        order: list[str] = []
        while queue:
            nid = queue.popleft()
            order.append(nid)
            for child in self._children[nid]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
        # Any leftovers are part of a cycle. Process them once, in stable order.
        leftovers = sorted(nid for nid in self.nodes if nid not in set(order))
        return order + leftovers

    # -------------------------------------------------------------------- run
    def run(self, client_qps: float) -> SimulationResult:
        if not self.nodes:
            return SimulationResult(
                throughput_rps=0.0,
                p99_latency_ms=0.0,
                failure_rate_pct=0.0,
                bottleneck_node_id=None,
                bottleneck_reason="No nodes on the canvas yet.",
            )

        client_ids = [
            n.node_id for n in self.nodes.values() if n.node_type == NodeType.CLIENT
        ]
        inflow: dict[str, float] = {nid: 0.0 for nid in self.nodes}
        if client_ids:
            share = client_qps / len(client_ids)
            for cid in client_ids:
                inflow[cid] = share
        else:
            # No explicit client: seed every source node so the sim still teaches.
            sources = [nid for nid in self.nodes if not self._parents[nid]] or list(
                self.nodes
            )
            for nid in sources:
                inflow[nid] = client_qps / len(sources)

        latency_at: dict[str, float] = {}
        path_latency: dict[str, float] = {}
        dropped_at: dict[str, float] = {}
        served_at: dict[str, float] = {}

        order = self._processing_order()
        for nid in order:
            node = self.nodes[nid]
            incoming = inflow[nid]

            if node.node_type == NodeType.CLIENT:
                capacity = float("inf")
                served = incoming
                dropped = 0.0
                node_latency = 0.0
            else:
                capacity = max(node.effective_capacity_qps, 1.0)
                served = min(incoming, capacity)
                dropped = max(incoming - capacity, 0.0)
                utilization = incoming / capacity
                if incoming > 0:
                    headroom = max(1.0 - utilization, MIN_HEADROOM)
                    node_latency = node.base_latency_ms / headroom
                else:
                    node_latency = node.base_latency_ms

            served_at[nid] = served
            dropped_at[nid] = dropped
            latency_at[nid] = node_latency

            # Path latency: this node's latency plus the slowest parent path.
            parent_paths = [path_latency.get(p, 0.0) for p in self._parents[nid]]
            path_latency[nid] = node_latency + (max(parent_paths) if parent_paths else 0.0)

            # Forward traffic: caches absorb their hit ratio; only misses go on.
            forward = served
            if node.node_type == NodeType.CACHE:
                hit = min(max(node.params.cache_hit_pct, 0), 100) / 100.0
                forward = served * (1.0 - hit)

            children = self._children[nid]
            if children and forward > 0:
                per_child = forward / len(children)
                for child in children:
                    inflow[child] += per_child

        # ----------------------------------------------------------- metrics
        metrics: list[NodeMetrics] = []
        bottleneck: Optional[NodeMetrics] = None
        total_dropped = 0.0

        for nid, node in self.nodes.items():
            is_client = node.node_type == NodeType.CLIENT
            capacity = 0.0 if is_client else max(node.effective_capacity_qps, 1.0)
            incoming = inflow[nid]
            utilization = (incoming / capacity * 100.0) if capacity else 0.0
            dropped = dropped_at.get(nid, 0.0)
            total_dropped += dropped

            is_bottleneck = capacity > 0 and utilization >= BOTTLENECK_UTILIZATION_PCT
            m = NodeMetrics(
                node_id=nid,
                title=node.title,
                node_type=node.node_type,
                incoming_qps=round(incoming, 1),
                capacity_qps=capacity,
                utilization_pct=round(utilization, 1),
                latency_ms=round(latency_at.get(nid, node.base_latency_ms), 2),
                dropped_qps=round(dropped, 1),
                is_bottleneck=is_bottleneck,
            )
            metrics.append(m)
            if is_bottleneck and (
                bottleneck is None or utilization > bottleneck.utilization_pct
            ):
                bottleneck = m

        throughput = max(client_qps - total_dropped, 0.0)
        failure_rate = (total_dropped / client_qps * 100.0) if client_qps > 0 else 0.0
        p99 = max(path_latency.values(), default=0.0)

        spof_ids = [
            n.node_id
            for n in self.nodes.values()
            if n.node_type
            in (NodeType.APP_SERVER, NodeType.DATABASE, NodeType.CACHE, NodeType.QUEUE)
            and n.params.replica_count <= 1
            and inflow[n.node_id] > 0
        ]

        if bottleneck:
            reason = (
                f"{bottleneck.title} is at {bottleneck.utilization_pct:.0f}% capacity "
                f"({bottleneck.incoming_qps:,.0f} QPS vs "
                f"{bottleneck.capacity_qps:,.0f} QPS limit)."
            )
            bottleneck_id = bottleneck.node_id
        elif spof_ids:
            spof_title = self.nodes[spof_ids[0]].title
            reason = (
                f"No node is over capacity, but {spof_title} has no replicas, so "
                f"it's a single point of failure."
            )
            bottleneck_id = spof_ids[0]
        else:
            reason = "No bottleneck detected at this load level."
            bottleneck_id = None

        return SimulationResult(
            throughput_rps=round(throughput, 1),
            p99_latency_ms=round(p99, 2),
            failure_rate_pct=round(failure_rate, 2),
            bottleneck_node_id=bottleneck_id,
            bottleneck_reason=reason,
            node_metrics=metrics,
            spof_node_ids=spof_ids,
        )
