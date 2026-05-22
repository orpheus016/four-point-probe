"""Backbone base class for snapshot algorithms."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..utils.types import Sample, Snapshot


class BaseBackbone(ABC):
    """Abstract backbone interface for streaming snapshot detection."""

    @abstractmethod
    def update(self, sample: Sample) -> Optional[Snapshot]:
        """Process (timestamp, voltage, current_mA) and return a Snapshot if stable."""
        raise NotImplementedError

    def reset(self) -> None:
        """Reset internal state between runs or stages."""
        return None
