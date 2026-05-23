"""Baseline backbone: sliding-window stddev + dwell detection."""

from __future__ import annotations

from collections import deque
from math import sqrt
from typing import Deque, Optional

from .base import BaseBackbone
from ..utils.types import Sample, Snapshot


class BaselineBackbone(BaseBackbone):
    """Emit a Snapshot when a sliding window's stddev stays below a threshold
    for a configured dwell count.

    The backbone maintains a rolling buffer (deque) and running sums so that
    per-sample updates are O(1) and no full-array recomputation occurs.
    """

    def __init__(
        self,
        window_samples: int,
        std_threshold: float,
        min_stable_samples: int,
    ) -> None:
        if window_samples < 2:
            raise ValueError("window_samples must be >= 2")
        if min_stable_samples < 1:
            raise ValueError("min_stable_samples must be >= 1")
        if std_threshold < 0.0:
            raise ValueError("std_threshold must be >= 0")

        self._window_samples = window_samples
        self._std_threshold = std_threshold
        self._min_stable_samples = min_stable_samples

        self._window: Deque[float] = deque(maxlen=window_samples)
        self._sum = 0.0
        self._sum_squares = 0.0
        self._stable_count = 0

    def update(self, sample: Sample) -> Optional[Snapshot]:
        timestamp, voltage, current_mA = sample

        # remove oldest contribution if window full
        if len(self._window) == self._window_samples:
            oldest = self._window[0]
            self._sum -= oldest
            self._sum_squares -= oldest * oldest

        # append new value
        self._window.append(voltage)
        self._sum += voltage
        self._sum_squares += voltage * voltage

        # not enough samples yet
        if len(self._window) < self._window_samples:
            self._stable_count = 0
            return None

        mean = self._sum / self._window_samples
        variance = (self._sum_squares / self._window_samples) - (mean * mean)
        variance = max(0.0, variance)
        std_dev = sqrt(variance)

        if std_dev <= self._std_threshold:
            self._stable_count += 1
        else:
            self._stable_count = 0

        if self._stable_count < self._min_stable_samples:
            return None

        resistance = None
        if current_mA > 0.0:
            resistance = mean / (current_mA / 1000.0)

        # emit snapshot (timestamp of latest sample)
        return Snapshot(
            timestamp=timestamp,
            voltage=mean,
            current_mA=current_mA,
            resistance=resistance,
            std_dev=std_dev,
        )

    def reset(self) -> None:
        self._window.clear()
        self._sum = 0.0
        self._sum_squares = 0.0
        self._stable_count = 0
