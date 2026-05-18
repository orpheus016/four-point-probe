# four-point-probe
Four point probe for semiconductor instrumentation system

## Software: voltage simulation pipeline

This repo includes a modular Python simulation for voltage-vs-time acquisition with
filters, live plotting, and CSV logging. It is designed to be swapped later with
ADS1256 serial input from Arduino.

### Setup

Install dependencies:

```bash
pip install matplotlib
```

Optional (for future ADS1256 serial input):

```bash
pip install pyserial
```

### Run

From the repo root:

```bash
python -m software.main
```

Example with custom settings:

```bash
python -m software.main --sample-rate 100 --window-seconds 8 --noise 0.0005 --step
```
