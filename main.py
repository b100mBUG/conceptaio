"""
main.py

Entry point for Concepta.io. Wires up the pages, the teal light and dark
themes, and the shared session state. Run with:

    rio run          # dev server with hot reload
    python main.py   # plain server, opens your browser
"""

from __future__ import annotations

from pathlib import Path

import rio

from app_state import AppState, ThemeSettings
from components.footer import Footer
from pages.challenges_page import ChallengesPage
from pages.playground_page import PlaygroundPage
from theme import DARK_THEME, LIGHT_THEME, theme_for

# One shared state instance. This is a local, single user tool, so the
# canvas survives page reloads for free.
_shared_state = AppState()

ASSETS_DIR = Path(__file__).parent / "assets"


def _on_session_start(session: rio.Session) -> None:
    """Apply the user's saved dark or light preference."""
    settings = session[ThemeSettings]
    session.theme = theme_for(settings.dark_mode)


class AppRoot(rio.Component):
    """
    Custom root: the current page fills the screen, with our own footer
    underneath. Defining this replaces Rio's default navigation sidebar.
    """

    def build(self) -> rio.Component:
        return rio.Column(
            rio.PageView(grow_y=True),
            Footer(),
        )


app = rio.App(
    name="Concepta.io",
    description=(
        "Sketch a backend on a canvas, push traffic through it, and find "
        "out where it breaks before production does."
    ),
    icon=ASSETS_DIR / "icon.png",
    build=AppRoot,
    pages=[
        rio.ComponentPage(
            name="Challenges",
            url_segment="",
            build=ChallengesPage,
        ),
        rio.ComponentPage(
            name="Playground",
            url_segment="playground",
            build=PlaygroundPage,
        ),
    ],
    theme=(LIGHT_THEME, DARK_THEME),
    default_attachments=[ThemeSettings(), _shared_state],
    on_session_start=_on_session_start,
)


if __name__ == "__main__":
    app.run_in_browser()
