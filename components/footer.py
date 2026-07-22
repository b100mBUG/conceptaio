"""
components/footer.py

Slim footer shown on every page: company credit on the left, a link to the
source code on the right.
"""

from __future__ import annotations

import rio

GITHUB_URL = "https://github.com/b100mBUG/conceptaio"


class Footer(rio.Component):
    def build(self) -> rio.Component:
        theme = self.session.theme

        return rio.Rectangle(
            content=rio.Row(
                rio.Text(
                    "Neptune Developers And Consultants",
                    style=rio.TextStyle(font_size=0.78),
                    align_y=0.5,
                ),
                rio.Spacer(),
                rio.Link(
                    rio.Row(
                        rio.Icon(
                            "brand/github",
                            min_width=1.2,
                            min_height=1.2,
                            align_y=0.5,
                        ),
                        rio.Text(
                            "GitHub",
                            style=rio.TextStyle(font_size=0.78),
                            align_y=0.5,
                        ),
                        spacing=0.35,
                    ),
                    target_url=GITHUB_URL,
                    open_in_new_tab=True,
                ),
                margin_x=1.0,
                margin_y=0.4,
            ),
            fill=theme.neutral_color,
        )
