"""
components/inspector_panel.py

Right-hand panel editing the selected node: title, capacity, replicas,
type-specific parameters, plus that node's connections (deletable) and a
delete-node action. All edits apply live, so there is no Apply button to forget.
"""

from __future__ import annotations

import typing as t

import rio

from models.node import Node, NodeType

CACHE_STRATEGIES = ["LRU", "LFU", "write-through", "write-back"]


class InspectorPanel(rio.Component):
    node: t.Optional[Node]
    # (edge_id, description) for every edge touching the selected node.
    connections: list[tuple[str, str]]
    version: int

    on_param_change: t.Callable[[str, t.Any], None]
    on_delete_node: t.Callable[[str], None]
    on_delete_edge: t.Callable[[str], None]

    # ------------------------------------------------------------- handlers
    def _num(self, field: str) -> t.Callable[[rio.NumberInputChangeEvent], None]:
        def handler(event: rio.NumberInputChangeEvent) -> None:
            self.on_param_change(field, int(event.value))

        return handler

    def _text(self, field: str) -> t.Callable[[rio.TextInputChangeEvent], None]:
        def handler(event: rio.TextInputChangeEvent) -> None:
            self.on_param_change(field, event.text)

        return handler

    def _on_strategy(self, event: rio.DropdownChangeEvent) -> None:
        self.on_param_change("cache_strategy", event.value)

    def _on_hit_pct(self, event: rio.SliderChangeEvent) -> None:
        self.on_param_change("cache_hit_pct", int(event.value))

    def _edge_delete_handler(self, edge_id: str) -> t.Callable[[], None]:
        def handler() -> None:
            self.on_delete_edge(edge_id)

        return handler

    # ---------------------------------------------------------------- build
    def build(self) -> rio.Component:
        theme = self.session.theme

        if self.node is None:
            body: rio.Component = rio.Column(
                rio.Icon(
                    "material/design_services",
                    fill=theme.primary_color.replace(opacity=0.6),
                    min_width=3,
                    min_height=3,
                    align_x=0.5,
                ),
                rio.Text(
                    "Select a node on the canvas to edit its parameters.",
                    style="dim",
                    justify="center",
                    overflow="wrap",
                ),
                spacing=1,
                align_y=0.35,
                margin=1,
            )
            return self._frame(body)

        node = self.node
        p = node.params
        controls: list[rio.Component] = [
            rio.TextInput(
                text=node.title,
                label="Name",
                on_change=self._text("title"),
            ),
        ]

        if node.node_type != NodeType.CLIENT:
            controls += [
                rio.NumberInput(
                    value=float(p.capacity_qps),
                    label="Capacity per replica (QPS)",
                    minimum=1,
                    maximum=10_000_000,
                    decimals=0,
                    on_change=self._num("capacity_qps"),
                ),
                rio.NumberInput(
                    value=float(p.replica_count),
                    label="Replica count",
                    minimum=1,
                    maximum=1_000,
                    decimals=0,
                    on_change=self._num("replica_count"),
                ),
                rio.Text(
                    f"Effective capacity: {node.effective_capacity_qps:,.0f} QPS",
                    style="dim",
                ),
            ]

        if node.node_type in (NodeType.APP_SERVER, NodeType.DATABASE):
            controls.append(
                rio.NumberInput(
                    value=float(p.connection_pool_size),
                    label="Connection pool size",
                    minimum=1,
                    maximum=100_000,
                    decimals=0,
                    on_change=self._num("connection_pool_size"),
                ),
            )

        if node.node_type == NodeType.DATABASE:
            controls.append(
                rio.TextInput(
                    text=p.sharding_key,
                    label="Sharding key",
                    on_change=self._text("sharding_key"),
                ),
            )

        if node.node_type == NodeType.CACHE:
            controls += [
                rio.Dropdown(
                    options=CACHE_STRATEGIES,
                    selected_value=p.cache_strategy
                    if p.cache_strategy in CACHE_STRATEGIES
                    else CACHE_STRATEGIES[0],
                    label="Eviction strategy",
                    on_change=self._on_strategy,
                ),
                rio.Text(f"Cache hit ratio: {p.cache_hit_pct}%", style="dim"),
                rio.Slider(
                    minimum=0,
                    maximum=100,
                    step=5,
                    value=float(p.cache_hit_pct),
                    on_change=self._on_hit_pct,
                ),
            ]

        connection_items: list[rio.Component] = []
        if self.connections:
            connection_items.append(
                rio.Text(
                    "CONNECTIONS",
                    style=rio.TextStyle(font_size=0.75, font_weight="bold"),
                    margin_top=0.4,
                ),
            )
            for edge_id, description in self.connections:
                connection_items.append(
                    rio.Row(
                        rio.Text(
                            description,
                            style="dim",
                            overflow="ellipsize",
                            grow_x=True,
                            align_y=0.5,
                        ),
                        rio.IconButton(
                            "material/delete",
                            style="plain-text",
                            min_size=2.0,
                            on_press=self._edge_delete_handler(edge_id),
                        ),
                        spacing=0.4,
                    ),
                )

        body = rio.Column(
            rio.Text("Inspector", style="heading3"),
            *controls,
            *connection_items,
            rio.Separator(margin_y=0.4),
            rio.Button(
                "Delete node",
                icon="material/delete",
                style="minor",
                color="danger",
                on_press=lambda: self.on_delete_node(node.node_id),
            ),
            spacing=0.7,
            margin=1,
        )
        return self._frame(rio.ScrollContainer(body, scroll_x="never"))

    def _frame(self, content: rio.Component) -> rio.Component:
        return rio.Rectangle(
            content=content,
            fill=self.session.theme.neutral_color,
            min_width=20,
        )
