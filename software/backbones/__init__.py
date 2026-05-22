"""Snapshot backbone implementations."""

from .base import BaseBackbone
from .stddev_window import StdDevWindowBackbone

__all__ = ["BaseBackbone", "StdDevWindowBackbone"]
