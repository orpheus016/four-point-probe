"""Live visualization of voltage vs time using matplotlib."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Deque, Optional

import matplotlib.pyplot as plt
from matplotlib import animation as mpl_animation
import numpy as np
import threading
import queue
import time


_EVALUATION_COLORS = (
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
)


def get_backbone_style(index: int) -> dict[str, str]:
    color = _EVALUATION_COLORS[index % len(_EVALUATION_COLORS)]
    return {"color": color}


def _render_evaluation_legend() -> None:
    plt.legend()


def _add_snapshot_annotation(axis, snapshot, label: str, color: str, index: int) -> None:
    axis.annotate(
        label,
        (snapshot.current_mA, snapshot.voltage),
        textcoords="offset points",
        xytext=(8, 10 + (index % 3) * 10),
        ha="left",
        fontsize=8,
        color=color,
        arrowprops={"arrowstyle": "-", "color": color, "lw": 0.7},
    )


def _plot_evaluation_comparison(currents, voltages, results, name: str) -> None:
    plt.figure(figsize=(9, 4))
    plt.plot(currents, voltages, label="measured", lw=1.2, color="#444444")

    for index, (bname, info) in enumerate(results.items()):
        style = get_backbone_style(index)
        snaps = info["snapshots"]
        decided_snapshot = info.get("decided_snapshot")
        if snaps:
            plt.scatter(
                [s.current_mA for s in snaps],
                [s.voltage for s in snaps],
                label=f"{bname} snapshots",
                s=28,
                color=style["color"],
            )
            for snap_index, snap in enumerate(snaps, start=1):
                _add_snapshot_annotation(plt.gca(), snap, f"{bname} #{snap_index}", style["color"], snap_index)
        if decided_snapshot is not None:
            plt.scatter(
                [decided_snapshot.current_mA],
                [decided_snapshot.voltage],
                marker="*",
                s=180,
                color=style["color"],
                edgecolors="black",
                linewidths=0.6,
                label=f"{bname} decided snapshot",
                zorder=5,
            )
            _add_snapshot_annotation(plt.gca(), decided_snapshot, f"{bname} decided", style["color"], 0)

    plt.xlabel("Current (mA)")
    plt.ylabel("Voltage (V)")
    plt.title(f"IV comparison: {name}")
    _render_evaluation_legend()
    plt.tight_layout()


def _plot_evaluation_transient(times, voltages, results, name: str, base_out: Path, animate: bool, show: bool, animation_output: str, fps: int) -> None:
    plt.figure(figsize=(10, 4.5))
    line, = plt.plot([], [], label="measured", lw=1.2, color="#444444")
    plt.xlabel("Time (s)")
    plt.ylabel("Voltage (V)")
    plt.title(f"Transient evaluation: {name}")
    plt.grid(True, alpha=0.3)

    snapshot_marks = []
    for index, (bname, info) in enumerate(results.items()):
        style = get_backbone_style(index)
        snaps = info["snapshots"]
        if snaps:
            artist = plt.scatter([], [], label=f"{bname} snapshots", s=28, color=style["color"])
            snapshot_marks.append((bname, snaps, artist, style["color"]))
        decided_snapshot = info.get("decided_snapshot")
        if decided_snapshot is not None:
            decided_artist = plt.scatter(
                [decided_snapshot.timestamp],
                [decided_snapshot.voltage],
                marker="*",
                s=180,
                color=style["color"],
                edgecolors="black",
                linewidths=0.6,
                label=f"{bname} decided snapshot",
                zorder=5,
            )
            _add_snapshot_annotation(plt.gca(), decided_snapshot, f"{bname} decided", style["color"], 0)

    plt.legend()
    plt.tight_layout()

    def update(frame_index: int):
        if not times:
            return (line,)

        line.set_data(times[:frame_index], voltages[:frame_index])
        for backbone_name, snapshots, artist, color in snapshot_marks:
            current_time = times[min(max(frame_index - 1, 0), len(times) - 1)]
            active_points = [(snap.current_mA, snap.voltage) for snap in snapshots if snap.timestamp <= current_time]
            if active_points:
                artist.set_offsets(np.asarray(active_points, dtype=float))
            else:
                artist.set_offsets(np.empty((0, 2), dtype=float))
        plt.xlim(0.0, max(times[-1], 1.0) if times else 1.0)
        if voltages[:frame_index]:
            v_min = min(voltages[:frame_index])
            v_max = max(voltages[:frame_index])
            margin = (v_max - v_min) * 0.1 if v_max != v_min else 1e-6
            plt.ylim(v_min - margin, v_max + margin)
        return (line,)

    if animate:
        if animation_output == "screen":
            for index in range(1, len(times) + 1):
                update(index)
                plt.pause(0.001)
        else:
            writer = None
            if animation_output == "gif":
                try:
                    writer = mpl_animation.PillowWriter(fps=max(1, fps))
                except Exception as exc:
                    raise RuntimeError("GIF export requires Pillow support") from exc
            elif animation_output == "video":
                try:
                    writer = mpl_animation.FFMpegWriter(fps=max(1, fps))
                except Exception as exc:
                    raise RuntimeError("Video export requires ffmpeg support") from exc
            else:
                raise ValueError(f"unsupported animation output: {animation_output}")

            if writer is not None:
                anim = mpl_animation.FuncAnimation(plt.gcf(), update, frames=range(1, len(times) + 1), interval=max(1, int(1000 / max(1, fps))), blit=False, repeat=False)
                anim.save(str(base_out / f"{Path(name).stem}.{animation_output}"), writer=writer)
    else:
        update(len(times))


def render_evaluation_results(base_out: Path, name: str, data: dict, show: bool = False, plot_mode: str = "comparison", animate: bool = False, animation_output: str = "screen", animation_fps: int = 12) -> None:
    times = data["times"]
    voltages = data["voltages"]
    currents = data["currents"]
    results = data["results"]

    if plot_mode == "transient":
        _plot_evaluation_transient(times, voltages, results, name, base_out, animate=animate, show=show, animation_output=animation_output, fps=animation_fps)
    else:
        _plot_evaluation_comparison(currents, voltages, results, name)

    out_png = base_out / f"{Path(name).stem}.png"
    plt.savefig(out_png)
    if show:
        plt.show()
    plt.close()


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
        true_v: Optional[float],
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
            self._measured_line.set_data(self._times, self._measured)

            if true_v is not None:
                self._true.append(true_v)
                self._true_line.set_data(self._times, self._true)
            else:
                self._true_line.set_data([], [])

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
                if self._true:
                    v_min = min(min(self._measured), min(self._true))
                    v_max = max(max(self._measured), max(self._true))
                else:
                    v_min = min(self._measured)
                    v_max = max(self._measured)
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

    def show_final_comparison(self, true_v: Optional[float], snapshot_v: Optional[float]) -> None:
        self._plot_mode = "comparison"
        self._render_comparison(true_v, snapshot_v)
        plt.ioff()
        plt.show(block=True)

    def _render_comparison(self, true_v: Optional[float], snapshot_v: Optional[float]) -> None:
        if snapshot_v is None:
            self._measured_line.set_data([], [])
            self._snapshot_line.set_data([], [])
            self._true_line.set_data([], [])
            return

        x_min = 0.0
        x_max = max(self._window_seconds, 1.0)
        self._ax.set_xlim(x_min, x_max)

        self._measured_line.set_data([], [])
        if true_v is not None:
            self._true_line.set_data([x_min, x_max], [true_v, true_v])
        else:
            self._true_line.set_data([], [])
        self._snapshot_line.set_data([x_min, x_max], [snapshot_v, snapshot_v])

        if true_v is not None:
            v_min = min(true_v, snapshot_v)
            v_max = max(true_v, snapshot_v)
        else:
            v_min = snapshot_v
            v_max = snapshot_v
        margin = (v_max - v_min) * 0.1 if v_max != v_min else 1e-6
        self._ax.set_ylim(v_min - margin, v_max + margin)

    def close(self) -> None:
        plt.ioff()
        plt.close(self._fig)


class AsyncVisualizer:
    """Background visualizer that accepts updates via a queue and renders them
    on a worker thread to avoid blocking the acquisition loop.

    Note: Matplotlib is not fully thread-safe across all backends; this class
    keeps painting simple and uses short timeouts to reduce contention.
    """

    def __init__(self, window_seconds: float, max_samples: int, plot_mode: str = "comparison") -> None:
        self._live = LivePlot(window_seconds, max_samples, plot_mode=plot_mode)
        self._q: "queue.Queue[tuple]" = queue.Queue()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._running = True
        self._thread.start()

    def _worker(self) -> None:
        while self._running:
            try:
                item = self._q.get(timeout=0.2)
            except queue.Empty:
                # allow periodic UI refresh
                continue
            if item is None:
                break
            try:
                self._live.update(*item)
            except Exception:
                # swallow plotting errors so the acquisition loop isn't affected
                pass

    def submit_update(
        self,
        t_s: float,
        measured_v: float,
        true_v: Optional[float],
        snapshot_v: Optional[float],
        mean: Optional[float],
        rms: Optional[float],
        is_stable: bool,
    ) -> None:
        # non-blocking put; if queue is full this will block briefly
        try:
            self._q.put_nowait((t_s, measured_v, true_v, snapshot_v, mean, rms, is_stable))
        except queue.Full:
            # fall back to blocking put to ensure eventual delivery
            self._q.put((t_s, measured_v, true_v, snapshot_v, mean, rms, is_stable))

    def show_final_comparison(self, true_v: Optional[float], snapshot_v: Optional[float]) -> None:
        # stop worker to allow final blocking display
        self._running = False
        # flush queue then call final render on main thread
        try:
            while True:
                item = self._q.get_nowait()
                if item is None:
                    break
        except queue.Empty:
            pass
        self._live.show_final_comparison(true_v, snapshot_v)

    def close(self) -> None:
        # signal worker to exit
        self._running = False
        try:
            self._q.put_nowait(None)
        except Exception:
            pass
        self._thread.join(timeout=1.0)
        self._live.close()
