Four-point probe voltage simulation and snapshot capture.

## What is this
This folder contains a modular Python simulation that mimics four-point probe voltage
measurements. It generates a true voltage from current and resistance, applies realistic
transient response and noise, and then detects when the signal stabilizes so it can
capture a frozen snapshot of the measurement.

## File overview
- config.py
   - Simulation defaults and tunables (current, resistance, noise, transient model,
      snapshot thresholds).
- data_source.py
   - Voltage model and generator.
   - V_true = I_source * R_sample, then applies transient response, noise, drift,
      line interference, and ADC quantization.
- filters.py
   - Moving average and optional low-pass filtering.
- main.py
   - Orchestrates sampling, filtering, snapshot detection, plotting, and logging.
   - Orchestration-only: snapshot strategies are implemented inside `backbones/`.
- visualization.py
   - Live plot with comparison (true vs snapshot) or full history mode.
- logger.py
   - CSV logging for measured, true, and snapshot values.
- volt_meas.py
   - Thin entry-point wrapper that calls main().

## Run from repo root
Examples showing common runs. Use `--help` for full CLI options.

1. One-shot measurement using the default `baseline` strategy:
   python -m software.main --source dummy --backbone baseline --current 0.01 --resistance 1.5 \
      --snapshot-threshold 0.0004 --snapshot-window 2.0 --snapshot-min-duration 2.0

2. Hysteresis-based snapshot with explicit enter/exit thresholds:
   python -m software.main --source dummy --backbone hysteresis \
      --hysteresis-enter 0.020 --hysteresis-exit 0.015 --snapshot-window 1.0

3. Replay a CSV testbench dataset and log outputs to `software/output/testbench`:
   python -m software.main --source csv --csv-path software/output/testbench/stable20mA.csv \
      --backbone stddev_window --stop-on-snapshot

4. Use the hardware ADS1256 input (COM port configured via `--port`):
   python -m software.main --source serial --port COM5 --baud 115200 --backbone baseline

Notes:
- Snapshot detection strategies live in `software/backbones/` and implement `update(sample) -> Optional[Snapshot]`.
- Runtime parameters and CLI defaults are centralized in `software/config/config.py`.
- Outputs are routed into `software/output/<source>` to keep hardware and testbench logs separate.

## Snapshot function: where it is and how it works
The core snapshot behavior is implemented in main.py inside the main loop:
- Rolling buffer collects filtered voltages.
- A rolling stddev check decides when the signal is stable.
- When stable long enough, a snapshot voltage is captured and frozen.
- If stop-on-snapshot is enabled, the loop exits and a final comparison view is shown.

Key variables to look for in main.py:
- snapshot_buffer
- compute_mean_std(...)
- snapshot_value
- stable_samples and min_stable_samples

## How to integrate snapshot into the larger FPP software
Use this as the reference pipeline:
1. Identify your measured voltage stream (raw or filtered).
2. Insert a rolling buffer and stddev check (see compute_mean_std in main.py).
3. When stddev <= threshold for a minimum duration, compute a snapshot value.
4. Freeze the snapshot and stop acquisition if desired.
5. Display the snapshot next to the true/reference value.

Suggested integration steps:
1. Port the snapshot block from main.py into your acquisition loop.
2. Feed the block with filtered voltage for better stability.
3. Keep the parameters configurable:
    - snapshot_window_s
    - snapshot_std_threshold_v
    - snapshot_min_duration_s
4. Use stop-on-snapshot when you want a one-shot measurement.
5. For continuous monitoring, switch to snapshot-mode continuous.

## Common tuning tips
- If snapshot never triggers, increase snapshot threshold or enable low-pass filtering.
- If snapshot triggers too early, increase snapshot window or min duration.
- For noisy environments, use a lower low-pass alpha (e.g., 0.05 to 0.2).

## Capture Data

### Manual Capture

```bash
# Execute with default config settings (COM12, 115200 baud)
python -m software.data_source.manual_capture
# Override targets using the integrated arg_parser flags
python -m software.data_source.manual_capture --port COM5 --baud 115200 --filename step_response_test
```

You might want to use manual capture to test the VI capture algorithm on specific datasets, or to collect custom datasets for testing and development. Alternatively, you can use the algorithmic based data_source to generate synthetic data with specific characteristics (e.g. noise, transient response, line interference) to test the snapshot algorithm under controlled conditions.

Use the csv_replay generator to replay existing datasets in the same format as the ads1256 reader, which is what the snapshot algorithm is currently built and tested on.

### Auto Capture

You can use ads1256 capture for more automated data collection. this data_source is going to be integrated into the automated four point probe system measurement