"""Offline evaluation tool: run multiple backbones over CSV testbench data.

Produces per-file PNG overlays and a CSV summary of simple metrics (RMSE, MAE, MaxAbs)
for snapshot voltages when available. The decided snapshot is highlighted with a star
and written into the metrics CSV.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

from ..config.config import build_simulation_config, build_arg_parser
from ..utils.evaluate_helpers import (
	build_source_iterator_eval as build_source_iterator,
	evaluate_file,
	evaluate_samples,
	plot_results,
	write_summary,
)
from ..utils.types import Sample, Snapshot






def main(argv: Optional[List[str]] = None) -> None:
	parser = build_arg_parser()
	args = parser.parse_args(argv)

	sim_config = build_simulation_config(args)
	out_dir = Path(args.out)
	out_dir.mkdir(parents=True, exist_ok=True)

	files: List[Path] = []
	if args.source == "csv":
		input_path = Path(args.input)
		if input_path.is_dir():
			for p in sorted(input_path.glob("*.csv")):
				files.append(p)
		else:
			files.append(input_path)

	backbones = [b.strip() for b in args.backbones.split(",") if b.strip()]

	if args.source == "csv":
		for f in files:
			data = evaluate_file(str(f), backbones, sim_config, args)
			plot_results(out_dir, str(f), data, show=args.show)
			write_summary(out_dir, str(f), data)
	else:
		samples = build_source_iterator(args.source, sim_config, args)
		data = evaluate_samples(samples, backbones, sim_config, args)
		output_name = f"{args.source}-{Path(args.input).stem if args.input else args.source}"
		plot_results(out_dir, output_name, data, show=args.show)
		write_summary(out_dir, output_name, data)


if __name__ == "__main__":
	main()