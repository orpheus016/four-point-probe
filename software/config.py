"""Configuration defaults for voltage simulation and streaming."""

from dataclasses import dataclass


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
class SerialConfig:
    port: str = "COM3"
    baud_rate: int = 115200
    timeout_s: float = 1.0
