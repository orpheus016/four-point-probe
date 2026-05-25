"""Derivative integration backbone placeholder.

Algorithm reference: Derivative Integration Algorithm for Proximity Sensing,
David Wang, TI, 2015 (internal reference document).
"""

from __future__ import annotations

from typing import Optional

from .base import BaseBackbone
from ..utils.types import Sample, Snapshot


class DerivativeIntegrationBackbone(BaseBackbone):
	"""Placeholder for a derivative-integration snapshot detector."""

	def update(self, sample: Sample) -> Optional[Snapshot]:
		self._mark_sample()
		return None
