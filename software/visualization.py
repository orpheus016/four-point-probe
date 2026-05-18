"""Live visualization of voltage vs time using matplotlib."""

from __future__ import annotations

from collections import deque
from typing import Deque, Optional

import matplotlib.pyplot as plt


class LivePlot:
    """Realtime rolling plot for voltage vs time."""

    def __init__(self, window_seconds: float, max_samples: int, plot_mode: str = "comparison") -> None:
        self._window_seconds = window_seconds
        self._plot_mode = plot_mode
        self._times: Deque[float] = deque(maxlen=max_samples)
        self._measured: Deque[float] = deque(maxlen=max_samples)
        self._true: Deque[float] = deque(maxlen=max_samples)
        self._last_true: Optional[float] = None
        self._last_snapshot: Optional[float] = None

        plt.ion()
        self._fig, self._ax = plt.subplots()
        (self._measured_line,) = self._ax.plot([], [], lw=1.5, label="measured")
        (self._true_line,) = self._ax.plot([], [], lw=1.2, linestyle="--", label="true")
        (self._snapshot_line,) = self._ax.plot([], [], lw=1.2, linestyle=":", label="snapshot")
        self._stats_text = self._ax.text(0.02, 0.98, "", transform=self._ax.transAxes, va="top")

        self._ax.set_title("Four-Point Probe Voltage vs Time")
        self._ax.set_xlabel("Time (s)")
        self._ax.set_ylabel("Voltage (V)")
        self._ax.grid(True, alpha=0.3)
        self._ax.legend(loc="upper right")
        self._fig.tight_layout()
        plt.show(block=False)

    def update(
        self,
        t_s: float,
        measured_v: float,
        true_v: float,
        snapshot_v: Optional[float],
        mean: Optional[float],
        rms: Optional[float],
        is_stable: bool,
    ) -> None:
        self._last_true = true_v
        self._last_snapshot = snapshot_v

        if self._plot_mode == "full":
            self._times.append(t_s)
            self._measured.append(measured_v)
            self._true.append(true_v)

            self._measured_line.set_data(self._times, self._measured)
            self._true_line.set_data(self._times, self._true)

            if snapshot_v is not None:
                x_min = max(0.0, t_s - self._window_seconds)
                x_max = max(self._window_seconds, t_s)
                self._snapshot_line.set_data([x_min, x_max], [snapshot_v, snapshot_v])
            else:
                self._snapshot_line.set_data([], [])
            x_min = max(0.0, t_s - self._window_seconds)
            x_max = max(self._window_seconds, t_s)
            self._ax.set_xlim(x_min, x_max)

            if self._measured:
                v_min = min(min(self._measured), min(self._true))
                v_max = max(max(self._measured), max(self._true))
                margin = (v_max - v_min) * 0.1 if v_max != v_min else 1e-6
                self._ax.set_ylim(v_min - margin, v_max + margin)
        else:
            self._render_comparison(true_v, snapshot_v)

        stats_parts = ["stable" if is_stable else "transient"]
        if mean is not None:
            stats_parts.append(f"mean={mean:.6f} V")
        if rms is not None:
            stats_parts.append(f"rms={rms:.6f} V")
        if snapshot_v is not None:
            stats_parts.append(f"snapshot={snapshot_v:.6f} V")
        self._stats_text.set_text("  ".join(stats_parts))

        self._fig.canvas.draw_idle()
        self._fig.canvas.flush_events()
        plt.pause(0.001)

    def show_final_comparison(self, true_v: float, snapshot_v: Optional[float]) -> None:
        self._plot_mode = "comparison"
        self._render_comparison(true_v, snapshot_v)
        plt.ioff()
        plt.show(block=True)

    def _render_comparison(self, true_v: float, snapshot_v: Optional[float]) -> None:
        if snapshot_v is None:
            self._measured_line.set_data([], [])
            self._snapshot_line.set_data([], [])
            self._true_line.set_data([], [])
            return

        x_min = 0.0
        x_max = max(self._window_seconds, 1.0)
        self._ax.set_xlim(x_min, x_max)

        self._measured_line.set_data([], [])
        self._true_line.set_data([x_min, x_max], [true_v, true_v])
        self._snapshot_line.set_data([x_min, x_max], [snapshot_v, snapshot_v])

        v_min = min(true_v, snapshot_v)
        v_max = max(true_v, snapshot_v)
        margin = (v_max - v_min) * 0.1 if v_max != v_min else 1e-6
        self._ax.set_ylim(v_min - margin, v_max + margin)

    def close(self) -> None:
        plt.ioff()
        plt.close(self._fig)
