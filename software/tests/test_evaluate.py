from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg", force=True)


def test_evaluate_single_dataset_smoke(tmp_path):
    from software.scripts.evaluate import evaluate_file, plot_results, write_summary
    from software.config.config import SimulationConfig

    csv_path = Path("software/output/testbench/stable20mA.csv")
    assert csv_path.exists(), "expected bundled testbench CSV fixture"

    class Args:
        hysteresis_enter = 1.0
        hysteresis_exit = 0.8

    sim_config = SimulationConfig()
    data = evaluate_file(str(csv_path), ["baseline"], sim_config, Args())

    assert "results" in data
    assert "baseline" in data["results"]

    out_dir = tmp_path / "evaluate"
    out_dir.mkdir(parents=True, exist_ok=True)
    plot_results(out_dir, str(csv_path), data, show=False)
    write_summary(out_dir, str(csv_path), data)

    assert (out_dir / "stable20mA.png").exists()
    assert (out_dir / "stable20mA-metrics.csv").exists()
