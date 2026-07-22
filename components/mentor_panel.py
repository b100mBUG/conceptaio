"""
components/mentor_panel.py

The "AI Tech Lead" panel: Socratic hints reacting to the last simulation.
"""

from __future__ import annotations

import rio


class MentorPanel(rio.Component):
    problems: tuple[str, ...]
    hints: tuple[str, ...]
    has_result: bool
    version: int

    def _accent_row(self, text: str, accent: rio.Color) -> rio.Component:
        return rio.Row(
            rio.Rectangle(
                fill=accent,
                corner_radius=0.1,
                min_width=0.2,
            ),
            rio.Text(
                text,
                overflow="wrap",
                grow_x=True,
            ),
            spacing=0.6,
        )

    def _section_label(self, text: str, accent: rio.Color) -> rio.Component:
        return rio.Text(
            text,
            style=rio.TextStyle(font_size=0.72, font_weight="bold", fill=accent),
        )

    def build(self) -> rio.Component:
        theme = self.session.theme

        hint_widgets: list[rio.Component] = []
        if self.problems:
            hint_widgets.append(
                self._section_label("WHY THIS BREAKS", theme.danger_color)
            )
            hint_widgets += [
                self._accent_row(p, theme.danger_color) for p in self.problems
            ]
        elif self.has_result:
            hint_widgets.append(
                self._accent_row(
                    "No structural problems detected in the last run.",
                    theme.success_color,
                )
            )

        if self.hints:
            hint_widgets.append(
                self._section_label("THINK ABOUT", theme.primary_color)
            )
            hint_widgets += [
                self._accent_row(h, theme.primary_color) for h in self.hints
            ]

        return rio.Rectangle(
            content=rio.Column(
                rio.Row(
                    rio.Icon(
                        "material/psychology",
                        fill=theme.primary_color,
                        min_width=1.6,
                        min_height=1.6,
                        align_y=0.5,
                    ),
                    rio.Text("AI Tech Lead", style="heading3", align_y=0.5),
                    spacing=0.5,
                    align_x=0.0,
                ),
                rio.ScrollContainer(
                    rio.Column(*hint_widgets, spacing=0.8, align_y=0.0),
                    scroll_x="never",
                    grow_y=True,
                ),
                spacing=0.8,
                margin=1,
            ),
            fill=self.session.theme.neutral_color,
            min_width=20,
        )
