"""
pages/challenges_page.py

Landing page: pick a preset challenge or open the freeform sandbox.
"""

from __future__ import annotations

import rio

from app_state import CHALLENGES, AppState, Challenge, ThemeSettings
from components.top_bar import TopBar
from models.lessons import lesson_for
from theme import theme_for


class ChallengesPage(rio.Component):
    def _open_challenge(self, challenge: Challenge, guided: bool) -> None:
        state = self.session[AppState]
        state.start_challenge(challenge, guided=guided)
        self.session.navigate_to("/playground")

    def _toggle_theme(self) -> None:
        settings = self.session[ThemeSettings]
        settings.dark_mode = not settings.dark_mode
        self.session.attach(settings)
        self.session.theme = theme_for(settings.dark_mode)
        self.force_refresh()

    def _challenge_card(self, challenge: Challenge) -> rio.Component:
        theme = self.session.theme
        lesson = lesson_for(challenge.title)

        if lesson is not None:
            actions: rio.Component = rio.Row(
                rio.Button(
                    "Learn it, guided",
                    icon="material/school",
                    style="major",
                    on_press=lambda c=challenge: self._open_challenge(c, guided=True),
                ),
                rio.Button(
                    "Do it yourself",
                    style="colored-text",
                    on_press=lambda c=challenge: self._open_challenge(c, guided=False),
                ),
                spacing=0.6,
                align_x=0.0,
            )
        else:
            actions = rio.Button(
                "Open sandbox",
                icon="material/design_services",
                style="major",
                align_x=0.0,
                on_press=lambda c=challenge: self._open_challenge(c, guided=False),
            )

        return rio.Card(
            rio.Column(
                rio.Row(
                    rio.Rectangle(
                        content=rio.Icon(
                            challenge.icon,
                            fill=theme.primary_color,
                            min_width=1.8,
                            min_height=1.8,
                            align_x=0.5,
                            align_y=0.5,
                        ),
                        fill=theme.primary_color.replace(opacity=0.12),
                        corner_radius=0.7,
                        min_width=3.2,
                        min_height=3.2,
                    ),
                    rio.Text(
                        challenge.title,
                        style=rio.TextStyle(font_size=1.05, font_weight="bold"),
                        overflow="wrap",
                        grow_x=True,
                        align_y=0.5,
                    ),
                    spacing=0.8,
                ),
                rio.Text(challenge.brief, style="dim", overflow="wrap"),
                rio.Row(
                    rio.Icon(
                        "material/speed",
                        fill=theme.secondary_color,
                        min_width=1.1,
                        min_height=1.1,
                        align_y=0.5,
                    ),
                    rio.Text(
                        f"Target: {challenge.target_qps:,} QPS",
                        style=rio.TextStyle(
                            font_size=0.8, fill=theme.secondary_color
                        ),
                        align_y=0.5,
                    ),
                    *(
                        [
                            rio.Text(
                                f"·  Guided lesson, {len(lesson.steps)} steps",
                                style=rio.TextStyle(
                                    font_size=0.8, fill=theme.primary_color
                                ),
                                align_y=0.5,
                            )
                        ]
                        if lesson is not None
                        else []
                    ),
                    spacing=0.3,
                    align_x=0.0,
                ),
                actions,
                spacing=0.7,
                margin=1.1,
            ),
            elevate_on_hover=True,
            min_width=24,
        )

    def build(self) -> rio.Component:
        settings = self.session[ThemeSettings]

        cards = [self._challenge_card(c) for c in CHALLENGES]
        rows: list[rio.Component] = []
        for i in range(0, len(cards), 2):
            rows.append(rio.Row(*cards[i : i + 2], spacing=1.2, align_x=0.5))

        return rio.Column(
            TopBar(
                title="Concepta.io",
                subtitle="Sketch it, load it, break it, learn from it",
                dark_mode=settings.dark_mode,
                show_back=False,
                show_canvas_actions=False,
                on_back=lambda: None,
                on_save=lambda: None,
                on_load=lambda: None,
                on_clear=lambda: None,
                on_toggle_theme=self._toggle_theme,
            ),
            rio.ScrollContainer(
                rio.Column(
                    rio.Text(
                        "Pick a challenge",
                        style="heading1",
                        justify="center",
                        margin_top=2.0,
                    ),
                    rio.Text(
                        "Each challenge sets a target load. Build the architecture, "
                        "run the simulation, and let the AI Tech Lead interrogate "
                        "your design.",
                        style="dim",
                        justify="center",
                        overflow="wrap",
                        margin_bottom=1.0,
                    ),
                    *rows,
                    spacing=1.2,
                    align_x=0.5,
                    align_y=0.0,
                    margin=2.0,
                ),
                grow_y=True,
            ),
        )
