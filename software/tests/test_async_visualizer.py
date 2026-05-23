import time
from unittest.mock import MagicMock

import pytest


def _patch_matplotlib(monkeypatch):
    import matplotlib.pyplot as plt

    fig = MagicMock()
    canvas = MagicMock()
    fig.canvas = canvas
    ax = MagicMock()
    # make plot return a single-line sequence as matplotlib does
    ax.plot = lambda *a, **k: (MagicMock(),)
    ax.text = lambda *a, **k: MagicMock()

    monkeypatch.setattr(plt, "ion", lambda: None)
    monkeypatch.setattr(plt, "ioff", lambda: None)
    monkeypatch.setattr(plt, "show", lambda *args, **kwargs: None)
    monkeypatch.setattr(plt, "pause", lambda *args, **kwargs: None)
    monkeypatch.setattr(plt, "close", lambda *args, **kwargs: None)
    monkeypatch.setattr(plt, "subplots", lambda: (fig, ax))

    return fig, ax


def test_async_visualizer_processes_queue(monkeypatch):
    # Patch matplotlib before importing AsyncVisualizer to avoid GUI operations
    fig, ax = _patch_matplotlib(monkeypatch)

    from software.utils.visualization import AsyncVisualizer

    vis = AsyncVisualizer(window_seconds=1.0, max_samples=10)

    # submit a few updates and allow worker to process
    for i in range(3):
        vis.submit_update(i * 0.1, 0.01 * i, None, None, None, None, False)

    time.sleep(0.2)

    # Close should stop the worker and flush
    vis.close()

    # draw_idle should have been called at least once via LivePlot.update
    assert fig.canvas.draw_idle.called or fig.canvas.flush_events.called