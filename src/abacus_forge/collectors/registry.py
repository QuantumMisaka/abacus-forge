"""Simple metric extractor registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

MetricExtractor = Callable[[str], dict[str, Any]]


class MetricRegistry:
    def __init__(self) -> None:
        self._extractors: list[MetricExtractor] = []

    def register(self, extractor: MetricExtractor) -> None:
        self._extractors.append(extractor)

    def extract(self, content: str) -> dict[str, Any]:
        metrics: dict[str, Any] = {}
        for extractor in self._extractors:
            metrics.update(extractor(content))
        return metrics
