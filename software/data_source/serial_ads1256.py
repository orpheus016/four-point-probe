'''
reference instrument_meas.py logic into this functionalitys
'''

"""Voltage data sources: simulated and (future) ADS1256 serial input."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Iterator

from ..config.config import SerialConfig, SimulationConfig


@dataclass(frozen=True)
class VoltageSample:
    true_v: float
    measured_v: float


def _first_order_settling(v_true: float, t_s: float, tau_s: float) -> float:
    # First-order settling models RC-like probe and sample capacitance effects.
    if tau_s <= 0.0:
        return v_true
    return v_true * (1.0 - math.exp(-t_s / tau_s))


def _underdamped_step(v_true: float, t_s: float, tau_s: float, damping_ratio: float) -> float:
    # Underdamped behavior can appear with probe wiring inductance or control loop dynamics.
    if tau_s <= 0.0:
        return v_true
    zeta = max(0.0, min(damping_ratio, 0.999))
    wn = 1.0 / tau_s
    wd = wn * math.sqrt(1.0 - zeta * zeta)
    phi = math.atan(math.sqrt(1.0 - zeta * zeta) / max(zeta, 1e-6))
    envelope = math.exp(-zeta * wn * t_s)
    return v_true * (1.0 - (envelope / math.sqrt(1.0 - zeta * zeta)) * math.sin(wd * t_s + phi))


def _quantize(value_v: float, full_scale_v: float, bits: int) -> float:
    if bits <= 0 or full_scale_v <= 0.0:
        return value_v
    lsb = (2.0 * full_scale_v) / (2**bits)
    clipped = max(-full_scale_v, min(full_scale_v, value_v))
    return round(clipped / lsb) * lsb


def simulate_voltage_sample(t_s: float, config: SimulationConfig, rng: random.Random) -> VoltageSample:
    """Return the true and measured voltage at time t_s."""
    v_true = config.current_source_a * config.sample_resistance_ohm

    if config.transient_model == "underdamped":
        v_settled = _underdamped_step(v_true, t_s, config.tau_s, config.damping_ratio)
    else:
        v_settled = _first_order_settling(v_true, t_s, config.tau_s)

    drift = config.drift_amplitude_v * math.sin(2.0 * math.pi * config.drift_frequency_hz * t_s)
    line = config.line_interference_v * math.sin(2.0 * math.pi * config.line_interference_hz * t_s)
    noise = rng.gauss(0.0, config.noise_sigma_v)

    measured = v_settled + drift + line + noise
    measured = _quantize(measured, config.adc_full_scale_v, config.adc_bits)

    # Post-settling averaging improves accuracy by suppressing random noise.
    return VoltageSample(true_v=v_true, measured_v=measured)


def dummy_voltage_generator(config: SimulationConfig) -> Iterator[VoltageSample]:
    """Yield simulated voltage samples forever."""
    rng = random.Random()
    t_s = 0.0
    dt_s = 1.0 / config.sample_rate_hz
    while True:
        yield simulate_voltage_sample(t_s, config, rng)
        t_s += dt_s


def serial_ads1256_reader(config: SerialConfig) -> Iterator[VoltageSample]:
    """
    Placeholder for ADS1256 serial reader.

    TODO: Replace this stub with pyserial integration that reads the Arduino stream.
    - Open serial port using config.port/config.baud_rate
    - Read line-based voltage values (e.g., CSV or plain float)
    - Parse to float volts and yield VoltageSample(true_v=<unknown>, measured_v=<value>)
    """
    raise NotImplementedError("ADS1256 serial reader not implemented yet.")
