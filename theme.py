"""
theme.py

Central place for the app's visual identity: a teal-first Material palette
with a matched light/dark theme pair. The toggle in the top bar switches
between the two at runtime; the choice is persisted via ThemeSettings.
"""

from __future__ import annotations

import rio

PRIMARY = rio.Color.from_hex("0d9488")  # teal-600
SECONDARY = rio.Color.from_hex("2dd4bf")  # teal-400

LIGHT_THEME, DARK_THEME = rio.Theme.pair_from_colors(
    primary_color=PRIMARY,
    secondary_color=SECONDARY,
)


def theme_for(dark_mode: bool) -> rio.Theme:
    return DARK_THEME if dark_mode else LIGHT_THEME
