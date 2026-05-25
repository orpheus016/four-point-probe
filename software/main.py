"""Main execution loop for voltage simulation and streaming."""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime
from typing import Deque, Optional

from .config.config import build_arg_parser, build_serial_config, build_simulation_config
from .data_source.ads1256 import ads1256_reader
from .command.serial_commander import SerialCommander
from .utils.csv_replay import csv_logged_reader, csv_replay_reader
from .data_source.dummy import dummy_voltage_generator
from .data_source.settling import settling_signal_generator
from .data_source.worst_case import worst_case_signal_generator
from .utils.filters import LowPassFilter, MovingAverageFilter
from .utils.logger import CsvLogger
import os
from pathlib import Path
from .utils.types import Sample, Snapshot
from .utils.backbone_factory import create_backbone
from .utils.math import mean_rms
from .utils.evaluate_helpers import evaluate_samples


def _parse_backbone_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _resolve_output_root(args) -> str:
    # route outputs per source to keep hardware/testbench logs separate
    if args.source == "serial":
        return os.path.join(args.output_dir, "ads1256")
    if args.source in ("csv", "settling", "worst_case"):
        return os.path.join(args.output_dir, "testbench")
    return os.path.join(args.output_dir, args.source)


def _build_run_name(now: datetime) -> str:
    return f"volt_log_{now.strftime('%Y%m%d_%H%M%S')}"


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


def main() -> None:
    args = build_arg_parser().parse_args()
    sim_config = build_simulation_config(args)

    if args.plot_backend:
        import matplotlib

        matplotlib.use(args.plot_backend, force=True)

    from .utils.visualization import AsyncVisualizer, LiveTransientVisualizer, render_evaluation_results, save_final_comparison_image

    window_samples = max(2, int(sim_config.window_seconds * sim_config.sample_rate_hz))
    buffer: Deque[float] = deque(maxlen=window_samples)

    moving_average = MovingAverageFilter(sim_config.moving_average_window)
    low_pass = LowPassFilter(sim_config.low_pass_alpha) if sim_config.enable_low_pass else None
    live_backbones = _parse_backbone_list(args.live_backbones)
    multi_mode = bool(live_backbones)
    backbone_names = live_backbones if multi_mode else [args.backbone]
    backbone_instances = {name: create_backbone(name, sim_config, args) for name in backbone_names}
    primary_backbone_name = backbone_names[0]

    out_root = _resolve_output_root(args)
    run_name = _build_run_name(datetime.now())
    run_dir, run_filename = CsvLogger.build_run_paths(out_root, run_name)

    plotter = None
    if args.live_plot:
        if multi_mode:
            duration_s = args.live_duration if args.live_duration > 0.0 else sim_config.max_measurement_s
            plot_samples = max(window_samples, int(duration_s * sim_config.sample_rate_hz))
            plotter = LiveTransientVisualizer(
                sim_config.window_seconds,
                plot_samples,
                backbone_names,
                update_hz=args.plot_update_hz,
            )
        else:
            plotter = AsyncVisualizer(
                sim_config.window_seconds,
                window_samples,
                plot_mode=args.plot_mode,
                update_hz=args.plot_update_hz,
            )
    logger = CsvLogger(run_dir, filename=run_filename)

    commander: SerialCommander | None = None
    # for serial source, create a commander and pass it into the reader so main
    # can signal stage changes when a Snapshot is emitted
    if args.source == "serial":
        serial_config = build_serial_config(args)
        commander = SerialCommander(serial_config)
        # do not start the stream here; ads1256_reader will open the port and
        # perform startup sequence when owner=True. We pass the commander so
        # we can call `decide_stage` on snapshot events and also close it later.
        source_iter = ads1256_reader(serial_config, commander=commander, manage_current_switching=False)
    else:
        source_iter = build_source_iterator(args, sim_config)

    start = time.perf_counter()
    dt_s = 1.0 / sim_config.sample_rate_hz
    sample_index = 0
    stop_requested = False
    interrupted = False
    last_snapshot_value: Optional[float] = None
    last_snapshots: dict[str, Optional[Snapshot]] = {name: None for name in backbone_names}
    snapshots_by_backbone: dict[str, list[Snapshot]] = {name: [] for name in backbone_names}
    duration_s = None
    if multi_mode:
        duration_s = args.live_duration if args.live_duration > 0.0 else sim_config.max_measurement_s

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

            buffer.append(filtered)
            mean, rms = mean_rms(buffer)

            if multi_mode:
                for name, backbone in backbone_instances.items():
                    snapshot = backbone.update((elapsed_sample_s, filtered, current_mA))
                    if snapshot is not None:
                        snapshots_by_backbone[name].append(snapshot)
                        last_snapshots[name] = snapshot

                primary_snapshot = last_snapshots.get(primary_backbone_name)
                if primary_snapshot is not None and commander is not None:
                    try:
                        commander.decide_stage(primary_snapshot.voltage, primary_snapshot.current_mA)
                    except Exception:
                        pass

                is_stable = primary_snapshot is not None
                if plotter is not None:
                    plotter.submit_update(elapsed_s, filtered, snapshots_by_backbone)
                logger.log_sample(datetime.now(), elapsed_s, filtered, current_mA, primary_snapshot)

                if duration_s is not None and elapsed_s >= duration_s:
                    stop_requested = True
                    break
            else:
                snapshot = backbone_instances[primary_backbone_name].update((elapsed_sample_s, filtered, current_mA))

                if snapshot is not None:
                    last_snapshot_value = snapshot.voltage
                    # if using serial hardware, let the commander decide stage based
                    # on the frozen snapshot value so hardware switching happens
                    # only when a stable snapshot is observed.
                    if commander is not None:
                        try:
                            commander.decide_stage(snapshot.voltage, snapshot.current_mA)
                        except Exception:
                            # do not crash acquisition if stage decision fails
                            pass

                is_stable = snapshot is not None

                if plotter is not None:
                    plotter.submit_update(elapsed_s, filtered, None, last_snapshot_value, mean, rms, is_stable)
                logger.log_sample(datetime.now(), elapsed_s, filtered, current_mA, snapshot)

                if snapshot is not None and args.stop_on_snapshot:
                    stop_requested = True
                    break

            sample_index += 1
    except KeyboardInterrupt:
        interrupted = True
    finally:
        should_save_final = stop_requested or (interrupted and args.save_plot_on_interrupt)
        if should_save_final:
            csv_path = Path(logger.path)
            if multi_mode:
                for name, snapshot in last_snapshots.items():
                    if snapshot is None:
                        continue
                    output_path = csv_path.with_name(f"{csv_path.stem}_{name}_final.png")
                    save_final_comparison_image(output_path, sim_config.window_seconds, snapshot.voltage)
            elif last_snapshot_value is not None:
                output_path = csv_path.with_name(f"{csv_path.stem}_final.png")
                save_final_comparison_image(output_path, sim_config.window_seconds, last_snapshot_value)

        if plotter is not None:
            if stop_requested and not multi_mode:
                # show a blocking final comparison
                plotter.show_final_comparison(None, last_snapshot_value)
            plotter.close()
        logger.close()

        if args.source == "serial":
            csv_path = Path(logger.path)
            samples = list(csv_logged_reader(str(csv_path)))
            if samples:
                try:
                    data = evaluate_samples(samples, backbone_names, sim_config, args)
                    render_evaluation_results(
                        csv_path.parent,
                        f"{csv_path.stem}_transient",
                        data,
                        show=False,
                        plot_mode="transient",
                    )
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


if __name__ == "__main__":
    main()
