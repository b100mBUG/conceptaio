"""
components/design_canvas.py

The drag-and-drop canvas. Three stacked layers:

1. A background rectangle wrapped in a PointerEventListener (press = deselect).
2. An SVG layer (rio.Html) drawing a dot grid plus all edges with arrowheads.
   The SVG viewBox matches the canvas size in layout units 1:1, so edge
   coordinates line up exactly with node positions.
3. One CanvasNode per node, absolutely positioned via alignment + margins,
   draggable through pointer drag events.
"""

from __future__ import annotations

import typing as t

import rio

from app_state import CANVAS_H, CANVAS_W, NODE_H, NODE_W
from components.canvas_node import CanvasNode
from models.node import Edge, Node


def _clip_to_rect(
    cx: float, cy: float, from_x: float, from_y: float, w: float, h: float
) -> tuple[float, float]:
    """
    Point where the segment (from -> rect center) crosses the rect border.
    Used to land arrowheads on the edge of the target card instead of its
    center.
    """
    dx = cx - from_x
    dy = cy - from_y
    if dx == 0 and dy == 0:
        return cx, cy
    half_w, half_h = w / 2, h / 2
    scale = 1.0
    if dx != 0:
        scale = min(scale, (half_w / abs(dx)) if abs(dx) > half_w else scale)
    if dy != 0:
        scale = min(scale, (half_h / abs(dy)) if abs(dy) > half_h else scale)
    # Walk back from the center toward the source until we exit the rect.
    tx = max(abs(dx) / half_w if half_w else 0, abs(dy) / half_h if half_h else 0)
    if tx <= 1:
        return cx, cy
    return cx - dx / tx, cy - dy / tx


class DesignCanvas(rio.Component):
    nodes: list[Node]
    edges: list[Edge]
    selected_node_id: t.Optional[str]
    link_source_id: t.Optional[str]
    link_mode: bool
    bottleneck_node_id: t.Optional[str]
    has_result: bool
    utilization_by_id: dict[str, float]
    version: int

    on_press_node: t.Callable[[str], None]
    # Mutation-only position update (no page refresh); the canvas refreshes
    # itself during drags so the rest of the UI doesn't rebuild per tick.
    on_move_node: t.Callable[[str, float, float], None]
    # Fired once when a drag finishes, so the page can sync side panels.
    on_drag_committed: t.Callable[[], None]
    on_press_background: t.Callable[[], None]
    on_delete_edge: t.Callable[[str], None]

    # ----------------------------------------------------------------- svg
    def _edge_svg(self) -> str:
        theme = self.session.theme
        grid_color = "#ffffff14" if not theme.is_light_theme else "#00000012"
        edge_color = theme.primary_color.replace(opacity=0.7).hexa
        danger_color = theme.danger_color.hexa

        by_id = {n.node_id: n for n in self.nodes}
        lines: list[str] = []
        for edge in self.edges:
            src = by_id.get(edge.source_id)
            dst = by_id.get(edge.target_id)
            if src is None or dst is None:
                continue
            sx, sy = src.x + NODE_W / 2, src.y + NODE_H / 2
            tx_c, ty_c = dst.x + NODE_W / 2, dst.y + NODE_H / 2
            # Land the arrow on the border of the target card.
            ex, ey = _clip_to_rect(tx_c, ty_c, sx, sy, NODE_W + 1.2, NODE_H + 1.2)
            hot = self.bottleneck_node_id in (edge.source_id, edge.target_id)
            color = danger_color if hot else edge_color
            marker = "url(#arrow-hot)" if hot else "url(#arrow)"
            lines.append(
                f'<line x1="{sx:.2f}" y1="{sy:.2f}" x2="{ex:.2f}" y2="{ey:.2f}" '
                f'stroke="#{color}" stroke-width="0.28" marker-end="{marker}" />'
            )

        return f"""
<svg width="100%" height="100%" viewBox="0 0 {CANVAS_W:.0f} {CANVAS_H:.0f}"
     preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg"
     style="display:block">
  <defs>
    <pattern id="dots" width="4" height="4" patternUnits="userSpaceOnUse">
      <circle cx="0.5" cy="0.5" r="0.12" fill="{grid_color}" />
    </pattern>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="5" markerHeight="5" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#{edge_color}" />
    </marker>
    <marker id="arrow-hot" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="5" markerHeight="5" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#{danger_color}" />
    </marker>
  </defs>
  <rect x="0" y="0" width="{CANVAS_W:.0f}" height="{CANVAS_H:.0f}" fill="url(#dots)" />
  {''.join(lines)}
</svg>
"""

    # ---------------------------------------------------------------- drag
    def _handle_drag(self, node_id: str, dx: float, dy: float) -> None:
        # Only the canvas subtree rebuilds while dragging; this is what
        # keeps dragging smooth.
        self.on_move_node(node_id, dx, dy)
        self.force_refresh()

    def _handle_drag_end(self) -> None:
        self.on_drag_committed()

    def _edge_delete_handler(self, edge_id: str) -> t.Callable[[rio.PointerEvent], None]:
        def handler(_: rio.PointerEvent) -> None:
            self.on_delete_edge(edge_id)

        return handler

    # --------------------------------------------------------------- build
    def _on_background_press(self, _: rio.PointerEvent) -> None:
        self.on_press_background()

    def build(self) -> rio.Component:
        theme = self.session.theme

        background = rio.PointerEventListener(
            rio.Rectangle(
                fill=theme.background_color,
                corner_radius=0.0,
            ),
            on_press=self._on_background_press,
        )

        edge_layer = rio.Webview(
            self._edge_svg(),
            enable_pointer_events=False,
            resize_to_fit_content=False,
        )

        node_widgets: list[rio.Component] = []
        for node in self.nodes:
            node_widgets.append(
                CanvasNode(
                    node_id=node.node_id,
                    node_type_value=node.node_type.value,
                    title=node.title,
                    subtitle=f"{node.effective_capacity_qps:,.0f} QPS"
                    + (
                        f" · x{node.params.replica_count}"
                        if node.params.replica_count > 1
                        else ""
                    ),
                    utilization_pct=self.utilization_by_id.get(node.node_id, 0.0),
                    health_value=node.health.value,
                    is_selected=node.node_id == self.selected_node_id,
                    is_link_source=node.node_id == self.link_source_id,
                    show_utilization=self.has_result,
                    on_press_node=self.on_press_node,
                    on_drag_node=self._handle_drag,
                    on_drag_end=self._handle_drag_end,
                    align_x=0.0,
                    align_y=0.0,
                    margin_left=node.x,
                    margin_top=node.y,
                    key=node.node_id,
                )
            )

        chip_widgets: list[rio.Component] = []
        by_id = {n.node_id: n for n in self.nodes}
        for edge in self.edges:
            src = by_id.get(edge.source_id)
            dst = by_id.get(edge.target_id)
            if src is None or dst is None:
                continue
            mx = (src.x + dst.x) / 2 + NODE_W / 2
            my = (src.y + dst.y) / 2 + NODE_H / 2
            chip_widgets.append(
                rio.Tooltip(
                    rio.PointerEventListener(
                        rio.Rectangle(
                            content=rio.Icon(
                                "material/close",
                                fill=theme.danger_color,
                                min_width=0.9,
                                min_height=0.9,
                                align_x=0.5,
                                align_y=0.5,
                            ),
                            fill=theme.neutral_color.replace(opacity=0.9),
                            hover_fill=theme.danger_color.replace(opacity=0.2),
                            stroke_color=theme.danger_color.replace(opacity=0.4),
                            stroke_width=0.06,
                            corner_radius=99,
                            cursor="pointer",
                            transition_time=0.1,
                            min_width=1.5,
                            min_height=1.5,
                        ),
                        on_press=self._edge_delete_handler(edge.edge_id),
                    ),
                    tip="Remove this connection",
                    align_x=0.0,
                    align_y=0.0,
                    margin_left=max(mx - 0.75, 0.0),
                    margin_top=max(my - 0.75, 0.0),
                    key=f"chip-{edge.edge_id}",
                )
            )

        return rio.Stack(
            background,
            edge_layer,
            *node_widgets,
            *chip_widgets,
            min_width=CANVAS_W,
            min_height=CANVAS_H,
        )
