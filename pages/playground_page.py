"""
pages/playground_page.py

The main screen: palette | canvas (+ metrics HUD overlay) | guide/inspector
tabs + tech-lead panel. All state lives in the session-attached AppState;
this page passes data down and routes mutations back up.

Drag performance note: node dragging is handled *inside* DesignCanvas so
only the canvas subtree rebuilds per drag tick; this page only refreshes
when the drag ends (or on any other mutation).
"""

from __future__ import annotations

import typing as t

import rio

from app_state import AppState, ThemeSettings
from components.design_canvas import DesignCanvas
from components.guide_panel import GuidePanel
from components.inspector_panel import InspectorPanel
from components.mentor_panel import MentorPanel
from components.metrics_hud import MetricsHUD
from components.palette import Palette
from components.top_bar import TopBar
from models.lessons import lesson_for
from models.node import NodeType
from theme import theme_for


class PlaygroundPage(rio.Component):
    banner_text: str = ""

    # ------------------------------------------------------------- plumbing
    @property
    def state(self) -> AppState:
        return self.session[AppState]

    def _refresh(self) -> None:
        self.force_refresh()

    # ------------------------------------------------------------- handlers
    def _on_spawn(self, node_type: NodeType) -> None:
        self.state.spawn_node(node_type)
        self.banner_text = ""
        self._refresh()

    def _on_toggle_link(self) -> None:
        self.state.toggle_link_mode()
        self.banner_text = (
            "Link mode: tap the source node, then the target node."
            if self.state.link_mode
            else ""
        )
        self._refresh()

    def _on_qps_change(self, value: int) -> None:
        self.state.client_qps = max(value, 0)
        self.state.version += 1
        self._refresh()

    def _on_run(self) -> None:
        self.state.run_simulation()
        self.banner_text = ""
        self._refresh()

    def _on_press_node(self, node_id: str) -> None:
        state = self.state
        was_linking = state.link_mode
        state.press_node(node_id)
        if was_linking and not state.link_mode:
            self.banner_text = ""
        if not was_linking:
            # Selecting a node is an intent to inspect it.
            state.right_tab = "inspect"
        self._refresh()

    def _on_drag_committed(self) -> None:
        # Canvas already updated itself per tick; sync the rest of the UI once.
        self._refresh()

    def _on_press_background(self) -> None:
        self.state.press_background()
        self.banner_text = ""
        self._refresh()

    def _on_param_change(self, field: str, value: t.Any) -> None:
        node = self.state.node_by_id(self.state.selected_node_id)
        if node is None:
            return
        if field == "title":
            node.title = str(value) or node.title
        elif hasattr(node.params, field):
            setattr(node.params, field, value)
        self.state.version += 1
        self._refresh()

    def _on_delete_node(self, node_id: str) -> None:
        self.state.delete_node(node_id)
        self._refresh()

    def _on_delete_edge(self, edge_id: str) -> None:
        self.state.delete_edge(edge_id)
        self._refresh()

    def _on_save(self) -> None:
        self.state.save_design("autosave")
        self.banner_text = "Design saved."
        self._refresh()

    def _on_load(self) -> None:
        if self.state.load_design("autosave"):
            self.banner_text = "Design loaded."
        else:
            self.banner_text = "No saved design found yet."
        self._refresh()

    def _on_clear(self) -> None:
        self.state.clear_canvas()
        self.banner_text = ""
        self._refresh()

    def _on_back(self) -> None:
        self.session.navigate_to("/")

    def _toggle_theme(self) -> None:
        settings = self.session[ThemeSettings]
        settings.dark_mode = not settings.dark_mode
        self.session.attach(settings)
        self.session.theme = theme_for(settings.dark_mode)
        self._refresh()

    # ------------------------------------------------------------- guide
    def _on_guide_prev(self) -> None:
        self.state.lesson_step = max(self.state.lesson_step - 1, 0)
        self.state.version += 1
        self._refresh()

    def _on_guide_next(self) -> None:
        lesson = lesson_for(self.state.challenge_title)
        if lesson:
            self.state.lesson_step = min(
                self.state.lesson_step + 1, len(lesson.steps) - 1
            )
        self.state.version += 1
        self._refresh()

    def _on_guide_exit(self) -> None:
        self.state.guide_enabled = False
        self.state.right_tab = "inspect"
        self.state.version += 1
        self._refresh()

    def _on_guide_autobuild(self) -> None:
        lesson = lesson_for(self.state.challenge_title)
        if lesson:
            step = lesson.steps[
                min(self.state.lesson_step, len(lesson.steps) - 1)
            ]
            if step.autobuild is not None:
                step.autobuild(self.state)
                self.banner_text = "Reference design built. Study it, then run it."
        self._refresh()

    def _on_tab_change(self, event: rio.SwitcherBarChangeEvent) -> None:
        if event.value is not None:
            self.state.right_tab = event.value
            self.state.version += 1
            self._refresh()

    # ---------------------------------------------------------------- build
    def _build_right_column(self) -> rio.Component:
        state = self.state

        selected_node = state.node_by_id(state.selected_node_id)
        connections: list[tuple[str, str]] = []
        if selected_node is not None:
            titles = {n.node_id: n.title for n in state.nodes}
            for e in state.edges:
                if e.source_id == selected_node.node_id:
                    connections.append(
                        (e.edge_id, f"→  {titles.get(e.target_id, '?')}")
                    )
                elif e.target_id == selected_node.node_id:
                    connections.append(
                        (e.edge_id, f"←  {titles.get(e.source_id, '?')}")
                    )

        inspector = InspectorPanel(
            node=selected_node,
            connections=connections,
            version=state.version,
            on_param_change=self._on_param_change,
            on_delete_node=self._on_delete_node,
            on_delete_edge=self._on_delete_edge,
            grow_y=True,
        )

        lesson = lesson_for(state.challenge_title) if state.guide_enabled else None

        widgets: list[rio.Component] = []
        if lesson is not None:
            step_index = min(state.lesson_step, len(lesson.steps) - 1)
            step = lesson.steps[step_index]
            check_done, check_feedback = False, ""
            if step.check is not None:
                try:
                    check_done, check_feedback = step.check(state)
                except Exception:
                    check_done, check_feedback = False, ""

            guide = GuidePanel(
                lesson_title=lesson.challenge_title,
                step_index=step_index,
                total_steps=len(lesson.steps),
                step_title=step.title,
                body_md=step.body_md,
                task_md=step.task_md,
                note_md=step.note_md,
                has_check=step.check is not None,
                check_done=check_done,
                check_feedback=check_feedback,
                has_autobuild=step.autobuild is not None,
                autobuild_label=step.autobuild_label,
                is_last_step=step_index == len(lesson.steps) - 1,
                version=state.version,
                on_prev=self._on_guide_prev,
                on_next=self._on_guide_next,
                on_autobuild=self._on_guide_autobuild,
                on_exit=self._on_guide_exit,
                grow_y=True,
            )

            widgets.append(
                rio.SwitcherBar(
                    values=["guide", "inspect"],
                    names=["Guide", "Inspector"],
                    icons=["material/school", "material/design_services"],
                    selected_value=state.right_tab
                    if state.right_tab in ("guide", "inspect")
                    else "guide",
                    allow_none=False,
                    on_change=self._on_tab_change,
                    margin_x=0.6,
                    margin_top=0.4,
                )
            )
            widgets.append(guide if state.right_tab == "guide" else inspector)
        else:
            widgets.append(inspector)

        widgets.append(
            MentorPanel(
                problems=tuple(state.mentor_problems),
                hints=tuple(state.mentor_hints),
                has_result=state.last_result is not None,
                version=state.version,
                min_height=14,
            )
        )

        return rio.Column(*widgets, min_width=22)

    def build(self) -> rio.Component:
        state = self.state
        settings = self.session[ThemeSettings]
        result = state.last_result

        utilization_by_id: dict[str, float] = {}
        if result is not None:
            utilization_by_id = {
                m.node_id: m.utilization_pct for m in result.node_metrics
            }

        canvas = DesignCanvas(
            nodes=list(state.nodes),
            edges=list(state.edges),
            selected_node_id=state.selected_node_id,
            link_source_id=state.link_source_id,
            link_mode=state.link_mode,
            bottleneck_node_id=result.bottleneck_node_id if result else None,
            has_result=result is not None,
            utilization_by_id=utilization_by_id,
            version=state.version,
            on_press_node=self._on_press_node,
            on_move_node=state.move_node,
            on_drag_committed=self._on_drag_committed,
            on_press_background=self._on_press_background,
            on_delete_edge=self._on_delete_edge,
        )

        hud = MetricsHUD(
            throughput_rps=result.throughput_rps if result else 0.0,
            p99_latency_ms=result.p99_latency_ms if result else 0.0,
            failure_rate_pct=result.failure_rate_pct if result else 0.0,
            bottleneck_text=result.bottleneck_reason if result else "",
            has_result=result is not None,
            version=state.version,
            align_x=1.0,
            align_y=0.0,
            margin=1.0,
        )

        canvas_area_layers: list[rio.Component] = [
            rio.ScrollContainer(canvas, scroll_x="auto", scroll_y="auto"),
        ]
        if self.banner_text:
            canvas_area_layers.append(
                rio.Banner(
                    text=self.banner_text,
                    style="info",
                    align_y=1.0,
                    margin=1.0,
                )
            )
        canvas_area_layers.append(hud)

        return rio.Column(
            TopBar(
                title=state.challenge_title,
                subtitle=f"Target load: {state.client_qps:,} QPS",
                dark_mode=settings.dark_mode,
                show_back=True,
                show_canvas_actions=True,
                on_back=self._on_back,
                on_save=self._on_save,
                on_load=self._on_load,
                on_clear=self._on_clear,
                on_toggle_theme=self._toggle_theme,
            ),
            rio.Row(
                Palette(
                    link_mode=state.link_mode,
                    client_qps=state.client_qps,
                    version=state.version,
                    on_spawn=self._on_spawn,
                    on_toggle_link=self._on_toggle_link,
                    on_qps_change=self._on_qps_change,
                    on_run=self._on_run,
                ),
                rio.Stack(*canvas_area_layers, grow_x=True),
                self._build_right_column(),
                grow_y=True,
            ),
        )
