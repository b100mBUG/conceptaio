"""
components/metrics_hud.py

Floating card over the canvas showing the latest simulation results.
"""

from __future__ import annotations

import rio


class MetricsHUD(rio.Component):
    throughput_rps: float
    p99_latency_ms: float
    failure_rate_pct: float
    bottleneck_text: str
    has_result: bool
    version: int

    def _stat(self, label: str, value: str, color: rio.Color) -> rio.Component:
        return rio.Column(
            rio.Text(
                label,
                style=rio.TextStyle(font_size=0.7),
            ),
            rio.Text(
                value,
                style=rio.TextStyle(font_size=1.1, font_weight="bold", fill=color),
            ),
            spacing=0.15,
        )

    def build(self) -> rio.Component:
        theme = self.session.theme

        if not self.has_result:
            content: rio.Component = rio.Text(
                "Run a simulation to see live metrics.",
                style="dim",
                margin=0.9,
            )
        else:
            if self.failure_rate_pct >= 15:
                failure_color = theme.danger_color
            elif self.failure_rate_pct >= 1:
                failure_color = theme.warning_color
            else:
                failure_color = theme.success_color

            content = rio.Column(
                rio.Row(
                    self._stat(
                        "THROUGHPUT", f"{self.throughput_rps:,.0f} rps", theme.success_color
                    ),
                    self._stat(
                        "P99 LATENCY", f"{self.p99_latency_ms:,.1f} ms", theme.secondary_color
                    ),
                    self._stat(
                        "FAILURES", f"{self.failure_rate_pct:.1f}%", failure_color
                    ),
                    spacing=1.4,
                ),
                rio.Text(
                    self.bottleneck_text,
                    style="dim",
                    overflow="wrap",
                ),
                spacing=0.6,
                margin=0.9,
            )

        return rio.Rectangle(
            content=content,
            fill=theme.neutral_color.replace(opacity=0.95),
            corner_radius=0.8,
            shadow_radius=1.0,
            min_width=24,
        )
