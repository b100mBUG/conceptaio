"""
components/guide_panel.py

The guided-lesson panel: one step at a time, with the teaching text, a
"senior dev note" callout for edge cases, the task, a live check against
the canvas, and optional one-click reference builds.
"""

from __future__ import annotations

import typing as t

import rio


class GuidePanel(rio.Component):
    lesson_title: str
    step_index: int
    total_steps: int
    step_title: str
    body_md: str
    task_md: str
    note_md: str
    has_check: bool
    check_done: bool
    check_feedback: str
    has_autobuild: bool
    autobuild_label: str
    is_last_step: bool
    version: int

    on_prev: t.Callable[[], None]
    on_next: t.Callable[[], None]
    on_autobuild: t.Callable[[], None]
    on_exit: t.Callable[[], None]

    def _callout(
        self,
        icon: str,
        title: str,
        body: str,
        accent: rio.Color,
    ) -> rio.Component:
        return rio.Rectangle(
            content=rio.Column(
                rio.Row(
                    rio.Icon(
                        icon,
                        fill=accent,
                        min_width=1.3,
                        min_height=1.3,
                        align_y=0.5,
                    ),
                    rio.Text(
                        title,
                        style=rio.TextStyle(font_size=0.78, font_weight="bold", fill=accent),
                        align_y=0.5,
                    ),
                    spacing=0.4,
                    align_x=0.0,
                ),
                rio.Markdown(body),
                spacing=0.4,
                margin=0.8,
            ),
            fill=accent.replace(opacity=0.08),
            stroke_color=accent.replace(opacity=0.35),
            stroke_width=0.08,
            corner_radius=0.6,
        )

    def build(self) -> rio.Component:
        theme = self.session.theme

        blocks: list[rio.Component] = [
            rio.Row(
                rio.Text(
                    f"STEP {self.step_index + 1} / {self.total_steps}",
                    style=rio.TextStyle(
                        font_size=0.72,
                        font_weight="bold",
                        fill=theme.primary_color,
                    ),
                    align_y=0.5,
                ),
                rio.Spacer(),
                rio.Tooltip(
                    rio.IconButton(
                        "material/close",
                        style="plain-text",
                        min_size=2.0,
                        on_press=lambda: self.on_exit(),
                    ),
                    tip="Exit guided mode",
                ),
                spacing=0.4,
            ),
            rio.ProgressBar(
                progress=(self.step_index + 1) / max(self.total_steps, 1),
            ),
            rio.Text(
                self.step_title,
                style=rio.TextStyle(font_size=1.05, font_weight="bold"),
                overflow="wrap",
            ),
            rio.Markdown(self.body_md),
        ]

        if self.note_md:
            blocks.append(
                self._callout(
                    "material/psychology",
                    "SENIOR DEV NOTE: EDGE CASES",
                    self.note_md,
                    theme.secondary_color,
                )
            )

        if self.task_md:
            blocks.append(
                self._callout(
                    "material/design_services",
                    "YOUR TURN",
                    self.task_md,
                    theme.primary_color,
                )
            )

        if self.has_check:
            if self.check_done:
                blocks.append(
                    rio.Banner(
                        text=f"✓ {self.check_feedback}",
                        style="success",
                    )
                )
            else:
                blocks.append(
                    rio.Text(
                        "The guide checks your canvas live. Next unlocks "
                        "when the task is done.",
                        style="dim",
                        overflow="wrap",
                    )
                )

        if self.has_autobuild:
            blocks.append(
                rio.Button(
                    self.autobuild_label,
                    icon="material/school",
                    style="colored-text",
                    on_press=lambda: self.on_autobuild(),
                )
            )

        next_enabled = (not self.has_check) or self.check_done
        if self.is_last_step and next_enabled:
            nav: rio.Component = rio.Banner(
                text="Lesson complete. Stay and keep stress-testing, or head "
                "back and pick the next challenge.",
                style="success",
            )
        else:
            nav = rio.Row(
                rio.Button(
                    "Back",
                    style="minor",
                    is_sensitive=self.step_index > 0,
                    on_press=lambda: self.on_prev(),
                ),
                rio.Button(
                    "Next",
                    style="major",
                    is_sensitive=next_enabled and not self.is_last_step,
                    on_press=lambda: self.on_next(),
                ),
                spacing=0.6,
            )
        blocks.append(nav)

        return rio.Rectangle(
            content=rio.ScrollContainer(
                rio.Column(*blocks, spacing=0.8, margin=1, align_y=0.0),
                scroll_x="never",
            ),
            fill=theme.neutral_color,
            min_width=22,
        )
