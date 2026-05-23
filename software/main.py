"""Main execution loop for voltage simulation and streaming."""

from __future__ import annotations

import math
import time
from collections import deque
from datetime import datetime
from typing import Deque, Optional

from .backbones.stddev_window import StdDevWindowBackbone
from .backbones.baseline import BaselineBackbone
from .backbones.hysteresis import HysteresisBackbone
from .config.config import build_arg_parser, build_serial_config, build_simulation_config
from .data_source.ads1256 import ads1256_reader
from .tests.csv_replay import csv_replay_reader
from .data_source.dummy import dummy_voltage_generator
from .data_source.settling import settling_signal_generator
from .data_source.worst_case import worst_case_signal_generator
from .utils.filters import LowPassFilter, MovingAverageFilter
from .utils.logger import CsvLogger
from .utils.visualization import LivePlot, AsyncVisualizer
import os
from .utils.types import Sample


def compute_stats(values: Deque[float]) -> tuple[Optional[float], Optional[float]]:
    if not values:
        return None, None
    mean = sum(values) / len(values)
    rms = math.sqrt(sum(v * v for v in values) / len(values))
    return mean, rms


def compute_mean_std(values: Deque[float]) -> tuple[Optional[float], Optional[float]]:
    if not values:
        return None, None
    count = len(values)
    mean = sum(values) / count
    variance = sum((v - mean) ** 2 for v in values) / count
    return mean, math.sqrt(variance)


def build_source_iterator(args, sim_config):
    if args.source == "dummy":
        return dummy_voltage_generator(sim_config)
    if args.source == "serial":
        serial_config = build_serial_config(args)
        return ads1256_reader(serial_config)
    if args.source == "csv":
        return csv_replay_reader(args.csv_path, sample_rate_hz=sim_config.sample_rate_hz)
    if args.source == "settling":
        return settling_signal_generator(sim_config)
    if args.source == "worst_case":
        return worst_case_signal_generator(sim_config)
    raise ValueError(f"unsupported source: {args.source}")


def build_backbone(args, sim_config):
    window_samples = max(1, int(sim_config.snapshot_window_s * sim_config.sample_rate_hz))
    min_stable_samples = max(1, int(sim_config.snapshot_min_duration_s * sim_config.sample_rate_hz))

    if args.backbone == "stddev_window":
        # StdDevWindow expects at least 2 samples for variance computation
        ws = max(2, window_samples)
        return StdDevWindowBackbone(ws, sim_config.snapshot_std_threshold_v, min_stable_samples)

    if args.backbone == "baseline":
        ws = max(2, window_samples)
        return BaselineBackbone(ws, sim_config.snapshot_std_threshold_v, min_stable_samples)

    if args.backbone == "hysteresis":
        # Hysteresis thresholds come from CLI flags --hysteresis-enter/exit
        enter = getattr(args, "hysteresis_enter", None)
        exit_t = getattr(args, "hysteresis_exit", None)
        if enter is None or exit_t is None:
            raise ValueError("hysteresis thresholds not provided")
        ws = max(1, window_samples)
        return HysteresisBackbone(ws, enter, exit_t, min_stable_samples)

    raise ValueError(f"unsupported backbone: {args.backbone}")


def main() -> None:
    args = build_arg_parser().parse_args()
    sim_config = build_simulation_config(args)

    window_samples = max(2, int(sim_config.window_seconds * sim_config.sample_rate_hz))
    buffer: Deque[float] = deque(maxlen=window_samples)

    moving_average = MovingAverageFilter(sim_config.moving_average_window)
    low_pass = LowPassFilter(sim_config.low_pass_alpha) if sim_config.enable_low_pass else None
    backbone = build_backbone(args, sim_config)

    # route outputs per source to keep hardware/testbench logs separate
    if args.source == "serial":
        out_dir = os.path.join(args.output_dir, "ads1256")
    elif args.source in ("csv", "settling", "worst_case"):
        out_dir = os.path.join(args.output_dir, "testbench")
    else:
        out_dir = os.path.join(args.output_dir, args.source)

    plotter = AsyncVisualizer(sim_config.window_seconds, window_samples, plot_mode=args.plot_mode)
    logger = CsvLogger(out_dir)
    source_iter = build_source_iterator(args, sim_config)

    start = time.perf_counter()
    dt_s = 1.0 / sim_config.sample_rate_hz
    sample_index = 0
    stop_requested = False
    last_snapshot_value: Optional[float] = None

    try:
        while True:
            target_time = start + sample_index * dt_s
            now = time.perf_counter()
            sleep_s = target_time - now
            if sleep_s > 0:
                time.sleep(sleep_s)

            elapsed_s = time.perf_counter() - start
            sample: Sample = next(source_iter)
            elapsed_sample_s, raw_voltage, current_mA = sample
            filtered = moving_average.update(raw_voltage)
            if low_pass is not None:
                filtered = low_pass.update(filtered)

            snapshot = backbone.update((elapsed_sample_s, filtered, current_mA))

            buffer.append(filtered)
            mean, rms = compute_stats(buffer)

            if snapshot is not None:
                last_snapshot_value = snapshot.voltage

            is_stable = snapshot is not None

            plotter.submit_update(elapsed_s, filtered, None, last_snapshot_value, mean, rms, is_stable)
            logger.log_sample(datetime.now(), elapsed_s, filtered, current_mA, snapshot)

            if snapshot is not None and args.stop_on_snapshot:
                stop_requested = True
                break

            sample_index += 1
    except KeyboardInterrupt:
        pass
    finally:
        if stop_requested:
            # show a blocking final comparison
            plotter.show_final_comparison(None, last_snapshot_value)
        plotter.close()
        logger.close()


if __name__ == "__main__":
    main()
