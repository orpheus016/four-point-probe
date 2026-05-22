"""Main execution loop for voltage simulation and streaming."""

from __future__ import annotations

import argparse
import math
import time
from collections import deque
from datetime import datetime
from typing import Deque, Optional

from .config.config import SerialConfig, SimulationConfig
from .data_source.serial_ads1256 import VoltageSample, dummy_voltage_generator, serial_ads1256_reader
from .utils.filters import LowPassFilter, MovingAverageFilter
from .utils.logger import CsvLogger
from .utils.visualization import LivePlot


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simulated ADS1256 voltage acquisition")
    parser.add_argument("--source", choices=["dummy", "serial"], default="dummy")
    parser.add_argument("--sample-rate", type=float, default=SimulationConfig.sample_rate_hz)
    parser.add_argument("--window-seconds", type=float, default=SimulationConfig.window_seconds)
    parser.add_argument("--current", type=float, default=SimulationConfig.current_source_a)
    parser.add_argument("--resistance", type=float, default=SimulationConfig.sample_resistance_ohm)
    parser.add_argument("--transient-model", choices=["first_order", "underdamped"], default=SimulationConfig.transient_model)
    parser.add_argument("--tau", type=float, default=SimulationConfig.tau_s)
    parser.add_argument("--damping", type=float, default=SimulationConfig.damping_ratio)
    parser.add_argument("--noise", type=float, default=SimulationConfig.noise_sigma_v)
    parser.add_argument("--drift-amp", type=float, default=SimulationConfig.drift_amplitude_v)
    parser.add_argument("--drift-freq", type=float, default=SimulationConfig.drift_frequency_hz)
    parser.add_argument("--line-freq", type=float, default=SimulationConfig.line_interference_hz)
    parser.add_argument("--line-amp", type=float, default=SimulationConfig.line_interference_v)
    parser.add_argument("--adc-full-scale", type=float, default=SimulationConfig.adc_full_scale_v)
    parser.add_argument("--adc-bits", type=int, default=SimulationConfig.adc_bits)
    parser.add_argument("--moving-average", type=int, default=SimulationConfig.moving_average_window)
    parser.add_argument("--low-pass", action="store_true", default=SimulationConfig.enable_low_pass)
    parser.add_argument("--low-pass-alpha", type=float, default=SimulationConfig.low_pass_alpha)
    parser.add_argument("--snapshot-window", type=float, default=SimulationConfig.snapshot_window_s)
    parser.add_argument("--snapshot-threshold", type=float, default=SimulationConfig.snapshot_std_threshold_v)
    parser.add_argument("--snapshot-min-duration", type=float, default=SimulationConfig.snapshot_min_duration_s)
    parser.add_argument("--snapshot-mode", choices=["first", "continuous"], default="first")
    parser.add_argument("--plot-mode", choices=["comparison", "full"], default="comparison")
    parser.add_argument("--stop-on-snapshot", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--output-dir", type=str, default="software/output")
    parser.add_argument("--port", type=str, default=SerialConfig.port)
    parser.add_argument("--baud", type=int, default=SerialConfig.baud_rate)
    return parser


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


def main() -> None:
    args = build_arg_parser().parse_args()

    sim_config = SimulationConfig(
        sample_rate_hz=args.sample_rate,
        window_seconds=args.window_seconds,
        current_source_a=args.current,
        sample_resistance_ohm=args.resistance,
        transient_model=args.transient_model,
        tau_s=args.tau,
        damping_ratio=args.damping,
        noise_sigma_v=args.noise,
        drift_amplitude_v=args.drift_amp,
        drift_frequency_hz=args.drift_freq,
        line_interference_hz=args.line_freq,
        line_interference_v=args.line_amp,
        adc_full_scale_v=args.adc_full_scale,
        adc_bits=args.adc_bits,
        moving_average_window=args.moving_average,
        low_pass_alpha=args.low_pass_alpha,
        enable_low_pass=args.low_pass,
        snapshot_window_s=args.snapshot_window,
        snapshot_std_threshold_v=args.snapshot_threshold,
        snapshot_min_duration_s=args.snapshot_min_duration,
    )

    window_samples = max(2, int(sim_config.window_seconds * sim_config.sample_rate_hz))
    buffer: Deque[float] = deque(maxlen=window_samples)
    snapshot_buffer: Deque[float] = deque(maxlen=max(2, int(sim_config.snapshot_window_s * sim_config.sample_rate_hz)))

    moving_average = MovingAverageFilter(sim_config.moving_average_window)
    low_pass = LowPassFilter(sim_config.low_pass_alpha) if sim_config.enable_low_pass else None

    plotter = LivePlot(sim_config.window_seconds, window_samples, plot_mode=args.plot_mode)
    logger = CsvLogger(args.output_dir)

    if args.source == "dummy":
        source_iter = dummy_voltage_generator(sim_config)
    else:
        serial_config = SerialConfig(port=args.port, baud_rate=args.baud)
        source_iter = serial_ads1256_reader(serial_config)

    start = time.perf_counter()
    dt_s = 1.0 / sim_config.sample_rate_hz
    sample_index = 0
    stable_samples = 0
    snapshot_value: Optional[float] = None
    min_stable_samples = max(1, int(sim_config.snapshot_min_duration_s * sim_config.sample_rate_hz))
    stop_requested = False
    last_true_v = 0.0

    try:
        while True:
            target_time = start + sample_index * dt_s
            now = time.perf_counter()
            sleep_s = target_time - now
            if sleep_s > 0:
                time.sleep(sleep_s)

            elapsed_s = time.perf_counter() - start
            sample: VoltageSample = next(source_iter)
            raw_voltage = sample.measured_v
            last_true_v = sample.true_v
            filtered = moving_average.update(raw_voltage)
            if low_pass is not None:
                filtered = low_pass.update(filtered)

            buffer.append(filtered)
            mean, rms = compute_stats(buffer)

            snapshot_buffer.append(filtered)
            if len(snapshot_buffer) == snapshot_buffer.maxlen:
                window_mean, window_std = compute_mean_std(snapshot_buffer)
                is_stable_window = window_std is not None and window_std <= sim_config.snapshot_std_threshold_v
                if is_stable_window:
                    stable_samples += 1
                else:
                    stable_samples = 0

                if window_mean is not None and stable_samples >= min_stable_samples:
                    if args.snapshot_mode == "continuous":
                        snapshot_value = window_mean
                    elif snapshot_value is None:
                        snapshot_value = window_mean
                elif args.snapshot_mode == "continuous":
                    snapshot_value = None
            else:
                stable_samples = 0

            is_stable = snapshot_value is not None

            plotter.update(elapsed_s, filtered, sample.true_v, snapshot_value, mean, rms, is_stable)
            logger.log(datetime.now(), elapsed_s, filtered, sample.true_v, snapshot_value, mean, rms)

            if snapshot_value is not None and args.stop_on_snapshot:
                stop_requested = True
                break

            sample_index += 1
    except KeyboardInterrupt:
        pass
    finally:
        if stop_requested:
            plotter.show_final_comparison(last_true_v, snapshot_value)
        plotter.close()
        logger.close()


if __name__ == "__main__":
    main()
