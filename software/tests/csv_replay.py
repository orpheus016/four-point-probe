"""CSV testbench replay generator for voltage,current_mA rows."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator

from ..config.config import SimulationConfig
from ..utils.types import Sample


def csv_replay_reader(csv_path: str, sample_rate_hz: float = SimulationConfig.sample_rate_hz) -> Iterator[Sample]:
    """Yield (timestamp_s, voltage_v, current_mA) tuples from a CSV file.

    The expected input columns are `voltage,current_mA`.
    A `timestamp` column is accepted but not required.
    """
    path = Path(csv_path)
    with path.open("r", newline="", encoding="utf-8") as handle:
        first_line = handle.readline()
        handle.seek(0)

        has_header = "voltage" in first_line and "current_mA" in first_line
        if has_header:
            reader = csv.DictReader(handle)
            for index, row in enumerate(reader):
                voltage_v = float(row["voltage"])
                current_mA = float(row["current_mA"])
                timestamp_s = float(row.get("timestamp", index / sample_rate_hz))
                yield (timestamp_s, voltage_v, current_mA)
        else:
            reader = csv.reader(handle)
            for index, row in enumerate(reader):
                if len(row) < 2:
                    continue
                voltage_v = float(row[0])
                current_mA = float(row[1])
                timestamp_s = index / sample_rate_hz
                yield (timestamp_s, voltage_v, current_mA)
