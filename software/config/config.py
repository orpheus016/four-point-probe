"""Configuration defaults for voltage simulation and streaming."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class SimulationConfig:
    sample_rate_hz: float = 50.0
    window_seconds: float = 10.0
    current_source_a: float = 0.010
    sample_resistance_ohm: float = 1.0
    transient_model: str = "first_order"
    tau_s: float = 0.5
    damping_ratio: float = 0.4
    noise_sigma_v: float = 0.0005
    drift_amplitude_v: float = 0.0002
    drift_frequency_hz: float = 0.05
    line_interference_hz: float = 50.0
    line_interference_v: float = 0.0003
    adc_full_scale_v: float = 2.5
    adc_bits: int = 24
    moving_average_window: int = 5
    low_pass_alpha: float = 0.2
    enable_low_pass: bool = False
    snapshot_window_s: float = 1.0
    snapshot_std_threshold_v: float = 0.0002
    snapshot_min_duration_s: float = 1.5


@dataclass(frozen=True)
class StreamMarkersConfig:
    stream_start: str = "*STREAM_START"
    stream_stop: str = "*STREAM_STOP"


@dataclass(frozen=True)
class SerialProtocolConfig:
    reset_command: str = "R"
    stream_command: str = "C"
    stop_command: str = "s"
    stage_command_prefix: str = "i"
    stage_command_min: int = 0
    stage_command_max: int = 3
    stream_startup_delay_s: float = 2.0
    stream_restart_delay_s: float = 0.07
    line_timeout_s: float = 1.0


@dataclass(frozen=True)
class CurrentSwitchConfig:
    current_mA_by_stage: Tuple[float, float, float, float] = (4.0, 8.0, 12.0, 20.0)
    power_limit_mw: float = 5.0
    min_voltage_v: float = 0.001
    headroom_v: float = 2.0
    stage0_raise_threshold_v: float = 0.3
    stage1_raise_threshold_v: float = 0.25
    stage2_raise_threshold_v: float = 0.15
    stage3_raise_threshold_v: float = 0.0


@dataclass(frozen=True)
class OutputConfig:
    ads_dir: str = "software/output/ads"
    testbench_dir: str = "software/output/testbench"


@dataclass(frozen=True)
class CLIConfig:
    source: str = "dummy"
    backbone: str = "stddev_window"
    csv_path: str = "software/output/testbench/input.csv"
    sample_rate_hz: float = SimulationConfig.sample_rate_hz
    window_seconds: float = SimulationConfig.window_seconds
    current_source_a: float = SimulationConfig.current_source_a
    sample_resistance_ohm: float = SimulationConfig.sample_resistance_ohm
    transient_model: str = SimulationConfig.transient_model
    tau_s: float = SimulationConfig.tau_s
    damping_ratio: float = SimulationConfig.damping_ratio
    noise_sigma_v: float = SimulationConfig.noise_sigma_v
    drift_amplitude_v: float = SimulationConfig.drift_amplitude_v
    drift_frequency_hz: float = SimulationConfig.drift_frequency_hz
    line_interference_hz: float = SimulationConfig.line_interference_hz
    line_interference_v: float = SimulationConfig.line_interference_v
    adc_full_scale_v: float = SimulationConfig.adc_full_scale_v
    adc_bits: int = SimulationConfig.adc_bits
    moving_average_window: int = SimulationConfig.moving_average_window
    low_pass: bool = SimulationConfig.enable_low_pass
    low_pass_alpha: float = SimulationConfig.low_pass_alpha
    snapshot_window_s: float = SimulationConfig.snapshot_window_s
    snapshot_std_threshold_v: float = SimulationConfig.snapshot_std_threshold_v
    snapshot_min_duration_s: float = SimulationConfig.snapshot_min_duration_s
    snapshot_mode: str = "first"
    plot_mode: str = "comparison"
    stop_on_snapshot: bool = True
    output_dir: str = "software/output"
    port: str = "COM12"
    baud: int = 115200


@dataclass(frozen=True)
class SerialConfig:
    port: str = "COM12"
    baud_rate: int = 115200
    timeout_s: float = 1.0
    markers: StreamMarkersConfig = StreamMarkersConfig()
    protocol: SerialProtocolConfig = SerialProtocolConfig()
    current_switch: CurrentSwitchConfig = CurrentSwitchConfig()


def build_arg_parser() -> argparse.ArgumentParser:
    defaults = CLIConfig()
    parser = argparse.ArgumentParser(description="Simulated ADS1256 voltage acquisition")
    parser.add_argument("--source", choices=["dummy", "serial", "csv", "settling", "worst_case"], default=defaults.source)
    parser.add_argument("--backbone", choices=["stddev_window"], default=defaults.backbone)
    parser.add_argument("--csv-path", type=str, default=defaults.csv_path)
    parser.add_argument("--sample-rate", type=float, default=defaults.sample_rate_hz)
    parser.add_argument("--window-seconds", type=float, default=defaults.window_seconds)
    parser.add_argument("--current", type=float, default=defaults.current_source_a)
    parser.add_argument("--resistance", type=float, default=defaults.sample_resistance_ohm)
    parser.add_argument("--transient-model", choices=["first_order", "underdamped"], default=defaults.transient_model)
    parser.add_argument("--tau", type=float, default=defaults.tau_s)
    parser.add_argument("--damping", type=float, default=defaults.damping_ratio)
    parser.add_argument("--noise", type=float, default=defaults.noise_sigma_v)
    parser.add_argument("--drift-amp", type=float, default=defaults.drift_amplitude_v)
    parser.add_argument("--drift-freq", type=float, default=defaults.drift_frequency_hz)
    parser.add_argument("--line-freq", type=float, default=defaults.line_interference_hz)
    parser.add_argument("--line-amp", type=float, default=defaults.line_interference_v)
    parser.add_argument("--adc-full-scale", type=float, default=defaults.adc_full_scale_v)
    parser.add_argument("--adc-bits", type=int, default=defaults.adc_bits)
    parser.add_argument("--moving-average", type=int, default=defaults.moving_average_window)
    parser.add_argument("--low-pass", action=argparse.BooleanOptionalAction, default=defaults.low_pass)
    parser.add_argument("--low-pass-alpha", type=float, default=defaults.low_pass_alpha)
    parser.add_argument("--snapshot-window", type=float, default=defaults.snapshot_window_s)
    parser.add_argument("--snapshot-threshold", type=float, default=defaults.snapshot_std_threshold_v)
    parser.add_argument("--snapshot-min-duration", type=float, default=defaults.snapshot_min_duration_s)
    parser.add_argument("--snapshot-mode", choices=["first", "continuous"], default=defaults.snapshot_mode)
    parser.add_argument("--plot-mode", choices=["comparison", "full"], default=defaults.plot_mode)
    parser.add_argument("--stop-on-snapshot", action=argparse.BooleanOptionalAction, default=defaults.stop_on_snapshot)
    parser.add_argument("--output-dir", type=str, default=defaults.output_dir)
    parser.add_argument("--port", type=str, default=defaults.port)
    parser.add_argument("--baud", type=int, default=defaults.baud)
    return parser


def build_simulation_config(args: argparse.Namespace) -> SimulationConfig:
    return SimulationConfig(
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


def build_serial_config(args: argparse.Namespace) -> SerialConfig:
    return SerialConfig(port=args.port, baud_rate=args.baud)
