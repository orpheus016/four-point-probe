"""Shared factory helpers for constructing backbone implementations.

Keeping the selection logic in one place avoids duplicated branching across
`main.py`, `scripts/evaluate.py`, and `scripts/integrate.py`.
"""

from __future__ import annotations

from typing import Any

from ..backbones.baseline import BaselineBackbone
from ..backbones.hysteresis import HysteresisBackbone
from ..backbones.running_stat import RunningStatBackbone
from ..backbones.stddev_window import StdDevWindowBackbone


def create_backbone(name: str, sim_config: Any, args: Any = None) -> object:
    window_samples = max(1, int(sim_config.snapshot_window_s * sim_config.sample_rate_hz))
    min_stable_samples = max(1, int(sim_config.snapshot_min_duration_s * sim_config.sample_rate_hz))
    min_recording_samples = max(1, int(sim_config.snapshot_min_recording_s * sim_config.sample_rate_hz))

    if name == "stddev_window":
        return StdDevWindowBackbone(max(2, window_samples), sim_config.snapshot_std_threshold_v, min_stable_samples, min_recording_samples)

    if name == "baseline":
        return BaselineBackbone(max(2, window_samples), sim_config.snapshot_std_threshold_v, min_stable_samples, min_recording_samples)

    if name == "running_stat":
        return RunningStatBackbone(max(2, window_samples), sim_config.snapshot_std_threshold_v, min_stable_samples, min_recording_samples)

    if name == "hysteresis":
        enter = getattr(args, "hysteresis_enter", 1.0) if args is not None else 1.0
        exit_t = getattr(args, "hysteresis_exit", 0.8) if args is not None else 0.8
        return HysteresisBackbone(max(1, window_samples), enter, exit_t, min_stable_samples, min_recording_samples)

    raise ValueError(f"unknown backbone: {name}")