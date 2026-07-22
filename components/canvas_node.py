"""
components/canvas_node.py

A single draggable node card on the design canvas. Receives only scalar
state from the parent, so Rio's reconciler can detect changes by value.
"""

from __future__ import annotations

import typing as t

import rio

from app_state import NODE_H, NODE_W
from models.node import HealthStatus, NodeType

NODE_ICONS: dict[str, str] = {
    NodeType.CLIENT.value: "material/smartphone",
    NodeType.LOAD_BALANCER.value: "material/alt_route",
    NodeType.APP_SERVER.value: "material/dns",
    NodeType.CACHE.value: "material/bolt",
    NodeType.DATABASE.value: "material/storage",
    NodeType.QUEUE.value: "material/sync",
}


class CanvasNode(rio.Component):
    node_id: str
    node_type_value: str
    title: str
    subtitle: str
    utilization_pct: float
    health_value: str
    is_selected: bool
    is_link_source: bool
    show_utilization: bool

    on_press_node: t.Callable[[str], None]
    on_drag_node: t.Callable[[str, float, float], None]
    on_drag_end: t.Callable[[], None]

    def _health_color(self) -> rio.Color:
        theme = self.session.theme
        return {
            HealthStatus.HEALTHY.value: theme.success_color,
            HealthStatus.DEGRADED.value: theme.warning_color,
            HealthStatus.FAILED.value: theme.danger_color,
        }.get(self.health_value, theme.success_color)

    def _on_press(self, _: rio.PointerEvent) -> None:
        self.on_press_node(self.node_id)

    def _on_drag_move(self, event: rio.PointerMoveEvent) -> None:
        self.on_drag_node(self.node_id, event.relative_x, event.relative_y)

    def _on_drag_end(self, _: rio.PointerEvent) -> None:
        self.on_drag_end()

    def build(self) -> rio.Component:
        theme = self.session.theme
        health_color = self._health_color()

        if self.is_link_source:
            stroke_color = theme.secondary_color
            stroke_width = 0.25
        elif self.is_selected:
            stroke_color = theme.primary_color
            stroke_width = 0.22
        else:
            stroke_color = health_color.replace(opacity=0.55)
            stroke_width = 0.12

        rows: list[rio.Component] = [
            rio.Row(
                rio.Icon(
                    NODE_ICONS.get(self.node_type_value, "material/dns"),
                    fill=theme.primary_color,
                    min_width=1.8,
                    min_height=1.8,
                    align_y=0.5,
                ),
                rio.Column(
                    rio.Text(
                        self.title,
                        style=rio.TextStyle(font_weight="bold", font_size=0.95),
                        overflow="ellipsize",
                    ),
                    rio.Text(
                        self.subtitle,
                        style="dim",
                        font_size=0.78,
                        overflow="ellipsize",
                    ),
                    spacing=0.1,
                    grow_x=True,
                    align_y=0.5,
                ),
                spacing=0.7,
            ),
        ]

        if self.show_utilization:
            bar_total = NODE_W - 2.2
            fraction = min(max(self.utilization_pct / 100.0, 0.0), 1.0)
            rows.append(
                rio.Stack(
                    rio.Rectangle(
                        fill=theme.neutral_color.brighter(0.06),
                        corner_radius=0.15,
                        min_height=0.35,
                    ),
                    rio.Rectangle(
                        fill=health_color,
                        corner_radius=0.15,
                        min_height=0.35,
                        min_width=max(bar_total * fraction, 0.001),
                        align_x=0.0,
                        align_y=0.5,
                    ),
                    min_height=0.35,
                ),
            )
            rows.append(
                rio.Text(
                    f"{self.utilization_pct:.0f}% utilization",
                    font_size=0.72,
                    fill=health_color,
                ),
            )

        card = rio.Rectangle(
            content=rio.Column(
                *rows,
                spacing=0.35,
                margin=0.7,
                align_y=0.5,
            ),
            fill=theme.neutral_color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            corner_radius=0.8,
            shadow_radius=1.2 if self.is_selected else 0.4,
            shadow_color=theme.primary_color.replace(opacity=0.35)
            if self.is_selected
            else rio.Color.BLACK.replace(opacity=0.25),
            transition_time=0.15,
            cursor="move",
            min_width=NODE_W,
            min_height=NODE_H,
        )

        return rio.PointerEventListener(
            card,
            on_press=self._on_press,
            on_drag_move=self._on_drag_move,
            on_drag_end=self._on_drag_end,
        )
