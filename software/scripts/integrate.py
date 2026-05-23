"""Integration helpers exposing a small programmatic API for downstream use.

Provides factory functions for backbones/commanders and a `Pipeline` context manager
that wires a source iterator to a backbone, logger, and optional visualizer.
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Iterator, Optional

from ..command.serial_commander import SerialCommander
from ..config.config import SerialConfig
from ..utils.backbone_factory import create_backbone
from ..utils.logger import CsvLogger
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


def run_pipeline(source_iter: Iterator, backbone, logger: CsvLogger, visualizer=None, commander: Optional[SerialCommander] = None, stop_on_snapshot: bool = True):
    last_snapshot = None
    for sample in source_iter:
        t, v, i = sample
        snap: Snapshot | None = backbone.update((t, v, i))
        # log with current wall-clock timestamp and the sample elapsed time
        try:
            logger.log_sample(datetime.now(), t, v, i, snap)
        except Exception:
            # best-effort logging: ignore failures to avoid pipeline crash
            pass
        if snap is not None:
            last_snapshot = snap
            if commander is not None:
                try:
                    commander.decide_stage(snap.voltage, snap.current_mA)
                except Exception:
                    pass
            if stop_on_snapshot:
                break
    return last_snapshot
