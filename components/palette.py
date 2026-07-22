"""
components/palette.py

Left sidebar: one button per component type, the link-mode toggle, the
client QPS input and the simulation trigger.
"""

from __future__ import annotations

import typing as t

import rio

from components.canvas_node import NODE_ICONS
from models.node import NodeType

PALETTE_TYPES: list[tuple[NodeType, str]] = [
    (NodeType.CLIENT, "Client"),
    (NodeType.LOAD_BALANCER, "Load Balancer"),
    (NodeType.APP_SERVER, "App Server"),
    (NodeType.CACHE, "Cache"),
    (NodeType.DATABASE, "Database"),
    (NodeType.QUEUE, "Queue"),
]


class Palette(rio.Component):
    link_mode: bool
    client_qps: int
    version: int

    on_spawn: t.Callable[[NodeType], None]
    on_toggle_link: t.Callable[[], None]
    on_qps_change: t.Callable[[int], None]
    on_run: t.Callable[[], None]

    def _spawn_handler(self, node_type: NodeType) -> t.Callable[[], None]:
        def handler() -> None:
            self.on_spawn(node_type)

        return handler

    def _on_qps(self, event: rio.NumberInputChangeEvent) -> None:
        self.on_qps_change(int(event.value))

    def build(self) -> rio.Component:
        theme = self.session.theme

        spawn_buttons: list[rio.Component] = [
            rio.Button(
                label,
                icon=NODE_ICONS[node_type.value],
                style="colored-text",
                on_press=self._spawn_handler(node_type),
            )
            for node_type, label in PALETTE_TYPES
        ]

        link_button = rio.Button(
            "Tap source, then target…" if self.link_mode else "Link Nodes",
            icon="material/link",
            style="major" if self.link_mode else "minor",
            color="secondary" if self.link_mode else "primary",
            on_press=lambda: self.on_toggle_link(),
        )

        return rio.Rectangle(
            content=rio.Column(
                rio.Text(
                    "COMPONENTS",
                    style=rio.TextStyle(font_size=0.75, font_weight="bold"),
                    margin_bottom=0.2,
                ),
                *spawn_buttons,
                rio.Separator(margin_y=0.5),
                link_button,
                rio.Spacer(),
                rio.NumberInput(
                    value=float(self.client_qps),
                    label="Client QPS",
                    minimum=0,
                    maximum=10_000_000,
                    decimals=0,
                    on_change=self._on_qps,
                ),
                rio.Button(
                    "Run Simulation",
                    icon="material/play_arrow",
                    style="major",
                    on_press=lambda: self.on_run(),
                ),
                spacing=0.55,
                margin=1.0,
            ),
            fill=theme.neutral_color,
            min_width=15,
        )
