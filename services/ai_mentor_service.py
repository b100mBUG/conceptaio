"""
services/ai_mentor_service.py

Generates Socratic-style critique of the user's architecture: targeted
questions instead of handed-over fixes. The logic is a local rule engine
driven by SimulationResult + graph topology, so the app works fully offline.

Swap `AIMentorService.critique` for a hosted-model call later if you want
richer, model-generated prompts. Keep the same return contract
(list[str] of hint strings) so the UI layer never has to change.
"""

from __future__ import annotations

import random

from models.node import Node, NodeType
from models.simulation_engine import (
    BOTTLENECK_UTILIZATION_PCT,
    NodeMetrics,
    SimulationResult,
)


class AIMentorService:
    def diagnose(
        self,
        result: SimulationResult,
        nodes: list[Node],
        edges: list,
    ) -> list[str]:
        """
        Concrete, causal explanations of why the design does not work:
        as opposed to `critique`, which asks guiding questions. Ordered
        roughly by severity.
        """
        problems: list[str] = []
        if not nodes:
            return problems

        node_by_id = {n.node_id: n for n in nodes}
        metrics_by_id = {m.node_id: m for m in result.node_metrics}
        has_outgoing = {e.source_id for e in edges}

        clients = [n for n in nodes if n.node_type == NodeType.CLIENT]
        if not clients:
            problems.append(
                "There's no Client node, so no traffic ever enters the system. "
                "The simulation seeds your source nodes instead, but a real "
                "design starts with who is calling you."
            )
        else:
            dead_clients = [c for c in clients if c.node_id not in has_outgoing]
            if len(dead_clients) == len(clients):
                problems.append(
                    "Your Client isn't connected to anything, so every request "
                    "has nowhere to go. 100% of traffic fails before your "
                    "system even sees it."
                )

        # Overloaded nodes: the direct cause of failed requests.
        for m in sorted(
            result.node_metrics, key=lambda x: x.utilization_pct, reverse=True
        ):
            if m.node_type == NodeType.CLIENT:
                continue
            if m.utilization_pct >= 100:
                problems.append(
                    f"{m.title} receives {m.incoming_qps:,.0f} QPS but can only "
                    f"serve {m.capacity_qps:,.0f}. The extra "
                    f"{m.dropped_qps:,.0f} QPS are dropped. Those are real "
                    f"users seeing errors and timeouts."
                )
            elif m.utilization_pct >= BOTTLENECK_UTILIZATION_PCT:
                problems.append(
                    f"{m.title} is running at {m.utilization_pct:.0f}% "
                    f"utilization. Nothing is failing *yet*, but its latency "
                    f"has inflated to ~{m.latency_ms:,.0f} ms. Queueing "
                    f"delay eats you long before hard errors do."
                )

        # Nodes that exist but never see traffic: dead weight or a wiring bug.
        for n in nodes:
            if n.node_type == NodeType.CLIENT:
                continue
            m = metrics_by_id.get(n.node_id)
            if m is not None and m.incoming_qps == 0:
                problems.append(
                    f"{n.title} never receives any traffic. Nothing routes "
                    f"to it. Either wire it into a path or delete it; right "
                    f"now it's paying rent and doing nothing."
                )

        # SPOFs: works today, gone tomorrow.
        for nid in result.spof_node_ids:
            n = node_by_id.get(nid)
            if n is not None:
                problems.append(
                    f"{n.title} runs as a single replica. The day that one "
                    f"instance crashes or restarts, everything depending on "
                    f"it goes down with it. That is a single point of failure."
                )

        return problems

    def critique(self, result: SimulationResult, nodes: list[Node]) -> list[str]:
        hints: list[str] = []

        if not nodes:
            return [
                "Drop a few nodes on the canvas, then run a simulation so I have "
                "something to interrogate."
            ]

        node_by_id = {n.node_id: n for n in nodes}
        metrics_by_id = {m.node_id: m for m in result.node_metrics}

        if result.bottleneck_node_id:
            bottleneck_node = node_by_id.get(result.bottleneck_node_id)
            bottleneck_metrics = metrics_by_id.get(result.bottleneck_node_id)
            if bottleneck_node and bottleneck_metrics:
                hints.append(self._hint_for_bottleneck(bottleneck_node, bottleneck_metrics))

        if result.spof_node_ids:
            spof = node_by_id.get(result.spof_node_ids[0])
            if spof:
                hints.append(
                    f"{spof.title} is running with a single replica. What happens to "
                    f"every request in flight the moment that instance restarts or "
                    f"crashes?"
                )

        if result.failure_rate_pct > 20:
            hints.append(
                f"You're dropping {result.failure_rate_pct:.0f}% of requests at this "
                f"load. Is that a raw capacity problem, or is traffic just not spread "
                f"evenly across your nodes?"
            )

        caches = [n for n in nodes if n.node_type == NodeType.CACHE]
        has_db = any(n.node_type == NodeType.DATABASE for n in nodes)
        if has_db and not caches and result.p99_latency_ms > 20:
            hints.append(
                "Every read in this design goes straight to the database. What's "
                "actually varying between requests that hit it? Could a cache in "
                "front absorb most of that traffic?"
            )

        for cache in caches:
            if cache.params.cache_hit_pct < 50 and metrics_by_id.get(
                cache.node_id, NodeMetrics(cache.node_id, "", cache.node_type, 0, 0, 0, 0, 0)
            ).incoming_qps > 0:
                hints.append(
                    f"{cache.title} only hits {cache.params.cache_hit_pct}% of the "
                    f"time, so most traffic still falls through. Is the working set "
                    f"too big, or is the eviction policy "
                    f"({cache.params.cache_strategy}) fighting your access pattern?"
                )

        has_lb = any(n.node_type == NodeType.LOAD_BALANCER for n in nodes)
        app_servers = [n for n in nodes if n.node_type == NodeType.APP_SERVER]
        if len(app_servers) > 1 and not has_lb:
            hints.append(
                "You've got multiple app servers but nothing distributing traffic "
                "across them. How is a client supposed to know which one to talk to?"
            )

        if not hints:
            hints.append(
                random.choice(
                    [
                        "Throughput and latency look healthy at this load. What "
                        "happens if you triple the QPS?",
                        "This holds up under current load. Where's the next weakest "
                        "link once traffic doubles?",
                        "No bottleneck yet. Which single node, if it failed right "
                        "now, would hurt the most?",
                    ]
                )
            )

        return hints

    def _hint_for_bottleneck(self, node: Node, m: NodeMetrics) -> str:
        detail = (
            f"{m.utilization_pct:.0f}% utilization "
            f"({m.incoming_qps:,.0f} of {m.capacity_qps:,.0f} QPS)"
        )
        type_prompts = {
            NodeType.DATABASE: (
                f"Your app tier is fine, but {node.title} is maxing out at {detail}. "
                f"Think about read replicas or a cache layer. Do all these requests "
                f"really need to hit primary storage?"
            ),
            NodeType.APP_SERVER: (
                f"{node.title} is saturated at {detail}. Is this a raw compute limit, "
                f"or could connection pooling and horizontal scaling buy you more "
                f"headroom before you touch the database?"
            ),
            NodeType.CACHE: (
                f"Interesting: your cache layer itself is the bottleneck at {detail}. "
                f"What's your eviction strategy ({node.params.cache_strategy}), and is "
                f"a single cache tier ever going to keep up with this traffic shape?"
            ),
            NodeType.LOAD_BALANCER: (
                f"{node.title} can't keep up: {detail}. Before adding more app "
                f"servers, ask: is the load balancer itself sized for this QPS?"
            ),
            NodeType.QUEUE: (
                f"{node.title} is backing up at {detail}. Are consumers keeping pace "
                f"with producers, or is this queue just delaying an overload instead "
                f"of preventing one?"
            ),
        }
        return type_prompts.get(
            node.node_type,
            f"{node.title} is the current bottleneck at {detail}. What's the cheapest "
            f"change you could make here before scaling it out?",
        )
