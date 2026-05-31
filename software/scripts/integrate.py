"""Integration helpers exposing a small programmatic API for downstream use.

Provides factory functions for backbones/commanders and a `Pipeline` context manager
that wires a source iterator to a backbone, logger, and optional visualizer.
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Iterator, Optional

from ..command.serial_commander import SerialCommander
from ..config.config import CurrentSwitchConfig, SerialConfig
from ..utils.backbone_factory import create_backbone
from ..utils.logger import CsvLogger
from ..utils.math import compute_resistance_ohm
from ..utils.types import Snapshot

__all__ = ["create_backbone", "create_commander", "Pipeline", "run_pipeline"]


def create_commander(serial_config: SerialConfig) -> SerialCommander:
    return SerialCommander(serial_config)


@contextlib.contextmanager
def Pipeline(source_iter: Iterator, backbone, out_dir: str, visualizer=None, commander: Optional[SerialCommander] = None):
    logger = CsvLogger(out_dir)
    try:
        yield (source_iter, backbone, logger, visualizer, commander)
    finally:
        try:
            logger.close()
        except Exception:
            pass
        if commander is not None:
            try:
                commander.stop_stream()
            except Exception:
                pass
            try:
                commander.close()
            except Exception:
                pass


def run_pipeline(
    source_iter: Iterator,
    backbone,
    logger: CsvLogger,
    visualizer=None,
    commander: Optional[SerialCommander] = None,
    stop_on_snapshot: bool = True,
    switch_policy: Optional[CurrentSwitchConfig] = None,
    gain: float = 1.0,
):
    last_snapshot = None
    stage_start_t = None
    blanking_until_t = None
    force_snapshot_at_t = None
    stage_snapshot_seen = False
    for sample in source_iter:
        t, v, i = sample
        if switch_policy is not None and stage_start_t is None:
            stage_start_t = t
            blanking_until_t = stage_start_t + switch_policy.blanking_s
            force_snapshot_at_t = stage_start_t + switch_policy.max_settle_s

        in_blanking = False
        force_snapshot_due = False
        if switch_policy is not None and stage_start_t is not None:
            assert blanking_until_t is not None
            assert force_snapshot_at_t is not None
            in_blanking = t < blanking_until_t
            force_snapshot_due = (not stage_snapshot_seen) and (t >= force_snapshot_at_t)

        snap: Snapshot | None = None
        if not in_blanking:
            snap = backbone.update((t, v, i))
        if snap is None and force_snapshot_due and not in_blanking:
            resistance = compute_resistance_ohm(v, i, gain)
            snap = Snapshot(timestamp=t, voltage=v, current_mA=i, resistance=resistance, std_dev=None)
        # log with current wall-clock timestamp and the sample elapsed time
        try:
            logger.log_sample(datetime.now(), t, v, i, snap)
        except Exception:
            # best-effort logging: ignore failures to avoid pipeline crash
            pass
        if snap is not None:
            stage_snapshot_seen = True
            last_snapshot = snap
            if commander is not None:
                try:
                    decision = commander.decide_stage(snap.voltage, snap.current_mA)
                    if decision.switched and switch_policy is not None:
                        stage_start_t = t
                        blanking_until_t = stage_start_t + switch_policy.blanking_s
                        force_snapshot_at_t = stage_start_t + switch_policy.max_settle_s
                        stage_snapshot_seen = False
                        backbone.reset()
                except Exception:
                    pass
            if stop_on_snapshot:
                break
    return last_snapshot
