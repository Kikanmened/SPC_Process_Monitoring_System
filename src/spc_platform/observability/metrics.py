"""In-process Prometheus-text metrics for ops scraping (DEPLOYMENT_PLAN.md §8)."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass
class _Counter:
    name: str
    help_text: str
    value: float = 0.0


@dataclass
class _Gauge:
    name: str
    help_text: str
    value: float = 0.0


@dataclass
class MetricsRegistry:
    """Process-local counters and gauges; no external push required."""

    _lock: Lock = field(default_factory=Lock, repr=False)
    _counters: dict[str, _Counter] = field(default_factory=dict)
    _gauges: dict[str, _Gauge] = field(default_factory=dict)

    def incr(self, name: str, *, help_text: str, amount: float = 1.0) -> None:
        """Increment a counter."""
        with self._lock:
            counter = self._counters.get(name)
            if counter is None:
                counter = _Counter(name=name, help_text=help_text)
                self._counters[name] = counter
            counter.value += amount

    def set_gauge(self, name: str, value: float, *, help_text: str) -> None:
        """Set a gauge."""
        with self._lock:
            self._gauges[name] = _Gauge(name=name, help_text=help_text, value=value)

    def render_prometheus(self) -> str:
        """Render exposition format text."""
        lines: list[str] = []
        with self._lock:
            for counter in sorted(self._counters.values(), key=lambda item: item.name):
                lines.append(f"# HELP {counter.name} {counter.help_text}")
                lines.append(f"# TYPE {counter.name} counter")
                lines.append(f"{counter.name} {counter.value}")
            for gauge in sorted(self._gauges.values(), key=lambda item: item.name):
                lines.append(f"# HELP {gauge.name} {gauge.help_text}")
                lines.append(f"# TYPE {gauge.name} gauge")
                lines.append(f"{gauge.name} {gauge.value}")
        return "\n".join(lines) + ("\n" if lines else "")


METRICS = MetricsRegistry()
