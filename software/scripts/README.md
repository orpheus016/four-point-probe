# Scripts Guide

This folder contains the repository's developer-facing entrypoints.

## `evaluate.py`

Offline evaluation over CSV testbench data.

Typical single-dataset, single-backbone run:

```powershell
python -m software.scripts.evaluate --input software/output/testbench/stable20mA.csv --backbones baseline --out software/output/evaluate/baseline-stable20mA
```

Batch run over the full testbench folder:

```powershell
python -m software.scripts.evaluate --input software/output/testbench --backbones stddev_window,baseline,hysteresis --out software/output/evaluate/batch
```

The script reads CSV replay data from `software/utils/csv_replay.py`, runs each backbone in isolation, and writes PNG and CSV summary outputs.

## `integrate.py`

Programmatic API for downstream use.

Example imports:

```python
from software.scripts.integrate import create_backbone, create_commander, run_pipeline
```

Use `create_backbone(...)` when you need a repository-consistent backbone factory, `create_commander(...)` when you need hardware control, and `run_pipeline(...)` for a small streaming loop that writes snapshots through `CsvLogger`.

## `ci_compliance.py`

Lightweight architecture check used by CI.

Run it directly:

```powershell
python software/scripts/ci_compliance.py
```

The checker validates the current repository shape against `copilot-instructions.md`, including `Snapshot`, backbone inheritance, CSV replay imports, and duplicate helper cleanup.