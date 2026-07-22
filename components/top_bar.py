"""
components/top_bar.py

App bar: back navigation, current challenge title, save/load/clear actions,
and the dark/light mode toggle.
"""

from __future__ import annotations

import typing as t

import rio


class TopBar(rio.Component):
    title: str
    subtitle: str
    dark_mode: bool
    show_back: bool
    show_canvas_actions: bool

    on_back: t.Callable[[], None]
    on_save: t.Callable[[], None]
    on_load: t.Callable[[], None]
    on_clear: t.Callable[[], None]
    on_toggle_theme: t.Callable[[], None]

    def build(self) -> rio.Component:
        theme = self.session.theme

        left: list[rio.Component] = []
        if self.show_back:
            left.append(
                rio.IconButton(
                    "material/arrow_back",
                    style="plain-text",
                    min_size=2.6,
                    on_press=lambda: self.on_back(),
                )
            )
        left.append(
            rio.Column(
                rio.Text(
                    self.title,
                    style=rio.TextStyle(font_size=1.05, font_weight="bold"),
                    overflow="ellipsize",
                ),
                rio.Text(
                    self.subtitle,
                    style="dim",
                    overflow="ellipsize",
                ),
                spacing=0.05,
                align_y=0.5,
            )
        )

        actions: list[rio.Component] = []
        if self.show_canvas_actions:
            actions += [
                rio.Tooltip(
                    rio.IconButton(
                        "material/save",
                        style="plain-text",
                        min_size=2.6,
                        on_press=lambda: self.on_save(),
                    ),
                    tip="Save design",
                ),
                rio.Tooltip(
                    rio.IconButton(
                        "material/folder_open",
                        style="plain-text",
                        min_size=2.6,
                        on_press=lambda: self.on_load(),
                    ),
                    tip="Load design",
                ),
                rio.Tooltip(
                    rio.IconButton(
                        "material/delete_sweep",
                        style="plain-text",
                        min_size=2.6,
                        on_press=lambda: self.on_clear(),
                    ),
                    tip="Clear canvas",
                ),
            ]
        actions.append(
            rio.Tooltip(
                rio.IconButton(
                    "material/light_mode" if self.dark_mode else "material/dark_mode",
                    style="plain-text",
                    min_size=2.6,
                    on_press=lambda: self.on_toggle_theme(),
                ),
                tip="Switch to light mode" if self.dark_mode else "Switch to dark mode",
            )
        )

        return rio.Rectangle(
            content=rio.Row(
                *left,
                rio.Spacer(),
                *actions,
                spacing=0.6,
                margin_x=1.0,
                margin_y=0.5,
            ),
            fill=theme.neutral_color,
            shadow_radius=0.4,
            shadow_color=rio.Color.BLACK.replace(opacity=0.2),
        )
