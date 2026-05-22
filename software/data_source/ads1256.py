"""ADS1256 hardware data generator using the Arduino stream protocol."""

from __future__ import annotations

import time
from typing import Iterator

from ..config.config import SerialConfig
from ..utils.types import Sample
from .serial_commander import SerialCommander


def ads1256_reader(config: SerialConfig, manage_current_switching: bool = True) -> Iterator[Sample]:
    """Yield (timestamp_s, voltage_v, current_mA) tuples from the Arduino stream."""
    commander = SerialCommander(config)
    commander.open()
    start_time_s = time.perf_counter()
    try:
        commander.reset()
        time.sleep(config.protocol.stream_startup_delay_s)
        commander.flush_input()
        commander.start_stream()
        commander.wait_for_marker(config.markers.stream_start)

        while True:
            line = commander.read_line()
            if not line:
                continue

            if line == config.markers.stream_stop:
                return

            if line.startswith("*"):
                raise RuntimeError(f"unexpected stream marker: {line}")

            sample_time_s = time.perf_counter() - start_time_s
            parsed = commander.parse_sample_line(line, sample_time_s)
            yield (parsed.timestamp_s, parsed.voltage_v, parsed.current_mA)

            if manage_current_switching:
                commander.decide_stage(parsed.voltage_v, parsed.current_mA)
    finally:
        try:
            commander.stop_stream()
            time.sleep(config.protocol.stream_restart_delay_s)
        finally:
            commander.close()
