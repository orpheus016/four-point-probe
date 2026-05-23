"""Small math utilities used across backbones and scripts.

Provide stable, single implementations for common operations so callers
don't duplicate near-identical helpers.
"""

from __future__ import annotations

import math
from typing import Iterable, Optional, Tuple


def mean_rms(values: Iterable[float]) -> Tuple[Optional[float], Optional[float]]:
	"""Return (mean, rms) for the provided values or (None, None) when empty.

	RMS is defined as sqrt(mean(x^2)).
	"""
	vals = list(values)
	if not vals:
		return None, None
	mean = sum(vals) / len(vals)
	rms = math.sqrt(sum(v * v for v in vals) / len(vals))
	return mean, rms


def mean_std(values: Iterable[float]) -> Tuple[Optional[float], Optional[float]]:
	"""Return (mean, std) for the provided values using population variance.

	Uses the simple two-pass algorithm (sufficient here for small windows).
	"""
	vals = list(values)
	if not vals:
		return None, None
	mean = sum(vals) / len(vals)
	variance = sum((v - mean) ** 2 for v in vals) / len(vals)
	return mean, math.sqrt(variance)