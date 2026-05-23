"""Offline evaluation tool: run multiple backbones over CSV testbench data.

Produces per-file PNG overlays and a CSV summary of simple metrics (RMSE, MAE, MaxAbs)
for snapshot voltages when available. The decided snapshot is highlighted with a star
and written into the metrics CSV.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import matplotlib.pyplot as plt

from ..config.config import build_arg_parser, build_simulation_config
from ..utils.csv_replay import csv_replay_reader
from ..utils.backbone_factory import create_backbone
from ..utils.types import Snapshot


@dataclass
class Metrics:
	rmse: float
	mae: float
	maxabs: float


def compute_metrics(errors: List[float]) -> Metrics:
	if not errors:
		return Metrics(math.nan, math.nan, math.nan)
	mse = sum(e * e for e in errors) / len(errors)
	rmse = math.sqrt(mse)
	mae = sum(abs(e) for e in errors) / len(errors)
	maxabs = max(abs(e) for e in errors)
	return Metrics(rmse=rmse, mae=mae, maxabs=maxabs)


def evaluate_file(csv_path: str, backbones: Iterable[str], sim_config, args) -> dict:
	# read full trace into memory for plotting and for evaluation reference
	times: List[float] = []
	voltages: List[float] = []
	currents: List[float] = []
	for t, v, i in csv_replay_reader(csv_path, sample_rate_hz=sim_config.sample_rate_hz):
		times.append(t)
		voltages.append(v)
		currents.append(i)

	results = {}
	for bname in backbones:
		bb = create_backbone(bname, sim_config, args)
		snapshots: List[Snapshot] = []
		# we'll use a simple reference for each snapshot: mean of last window_samples
		window_samples = max(1, int(sim_config.snapshot_window_s * sim_config.sample_rate_hz))
		# iterate through samples
		for t, v, i in zip(times, voltages, currents):
			snap = bb.update((t, v, i))
			if snap is not None:
				snapshots.append(snap)

		decided_snapshot = snapshots[0] if snapshots else None

		# compute errors per snapshot vs last-window-mean reference
		errors: List[float] = []
		refs: List[float] = []
		if decided_snapshot is not None:
			candidate_snapshots = [decided_snapshot]
		else:
			candidate_snapshots = []

		for snap in candidate_snapshots:
			# find index closest to snapshot.timestamp
			idx = min(range(len(times)), key=lambda k: abs(times[k] - snap.timestamp))
			start = max(0, idx - window_samples + 1)
			ref_mean = sum(voltages[start: idx + 1]) / max(1, idx - start + 1)
			refs.append(ref_mean)
			errors.append(snap.voltage - ref_mean)

		metrics = compute_metrics(errors)
		results[bname] = {
			"snapshots": snapshots,
			"decided_snapshot": decided_snapshot,
			"metrics": metrics,
			"refs": refs,
		}
	return {"times": times, "voltages": voltages, "currents": currents, "results": results}


def plot_results(base_out: Path, name: str, data: dict, show: bool = False) -> None:
	voltages = data["voltages"]
	currents = data["currents"]
	results = data["results"]

	plt.figure(figsize=(9, 4))
	plt.plot(currents, voltages, label="measured", lw=1.2)

	for bname, info in results.items():
		snaps: List[Snapshot] = info["snapshots"]
		decided_snapshot: Optional[Snapshot] = info.get("decided_snapshot")
		if snaps:
			plt.scatter(
				[s.current_mA for s in snaps],
				[s.voltage for s in snaps],
				label=f"{bname} snapshots",
				s=18,
			)
		if decided_snapshot is not None:
			plt.scatter(
				[decided_snapshot.current_mA],
				[decided_snapshot.voltage],
				marker="*",
				s=180,
				label=f"{bname} decided snapshot",
				zorder=5,
			)

	plt.xlabel("Current (mA)")
	plt.ylabel("Voltage (V)")
	plt.title(f"IV comparison: {name}")
	plt.legend()
	out_png = base_out / f"{Path(name).stem}.png"
	plt.tight_layout()
	plt.savefig(out_png)
	if show:
		plt.show()
	plt.close()


def write_summary(base_out: Path, name: str, data: dict) -> None:
	out_csv = base_out / f"{Path(name).stem}-metrics.csv"
	with out_csv.open("w", newline="", encoding="utf-8") as fh:
		writer = csv.writer(fh)
		writer.writerow([
			"backbone",
			"decided_snapshot",
			"decided_timestamp",
			"decided_voltage",
			"decided_current_mA",
			"decided_resistance",
			"decided_std_dev",
			"decided_stage",
			"rmse",
			"mae",
			"maxabs",
			"num_snapshots",
		])
		for bname, info in data["results"].items():
			m = info["metrics"]
			decided_snapshot: Optional[Snapshot] = info.get("decided_snapshot")
			if decided_snapshot is None:
				decided_values = ["", "", "", "", "", "", ""]
				selected_marker = ""
			else:
				selected_marker = "*"
				decided_values = [
					f"{decided_snapshot.timestamp:.6f}",
					f"{decided_snapshot.voltage:.8f}",
					f"{decided_snapshot.current_mA:.8f}",
					"" if decided_snapshot.resistance is None else f"{decided_snapshot.resistance:.8f}",
					"" if decided_snapshot.std_dev is None else f"{decided_snapshot.std_dev:.8f}",
					"" if decided_snapshot.stage is None else decided_snapshot.stage,
				]
			writer.writerow([
				bname,
				selected_marker,
				*decided_values,
				m.rmse,
				m.mae,
				m.maxabs,
				len(info["snapshots"]),
			])


def build_parser() -> argparse.ArgumentParser:
	p = build_arg_parser()
	p.description = "Evaluate backbones against CSV testbench data"
	p.add_argument("--input", type=str, default="software/output/testbench", help="file or directory to read CSVs from")
	p.add_argument("--out", type=str, default="software/output/evaluate", help="output directory for plots and summaries")
	p.add_argument("--backbones", type=str, default="stddev_window,baseline,hysteresis", help="comma-separated backbone names to evaluate")
	p.add_argument("--show", action="store_true", help="show interactive plots")
	return p


def main(argv: Optional[List[str]] = None) -> None:
	parser = build_parser()
	args = parser.parse_args(argv)

	sim_config = build_simulation_config(args)
	out_dir = Path(args.out)
	out_dir.mkdir(parents=True, exist_ok=True)

	# resolve input files
	input_path = Path(args.input)
	files: List[Path] = []
	if input_path.is_dir():
		for p in sorted(input_path.glob("*.csv")):
			files.append(p)
	else:
		files.append(input_path)

	backbones = [b.strip() for b in args.backbones.split(",") if b.strip()]

	for f in files:
		data = evaluate_file(str(f), backbones, sim_config, args)
		plot_results(out_dir, str(f), data, show=args.show)
		write_summary(out_dir, str(f), data)


if __name__ == "__main__":
	main()