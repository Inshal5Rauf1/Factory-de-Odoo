"""JSONL metrics logger for per-module generation telemetry."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ModuleMetrics:
    """Telemetry record for a single module generation run."""

    module_name: str
    odoo_version: str
    started_at: str  # ISO 8601
    duration_seconds: float = 0.0
    pylint_fix_iterations: int = 0
    docker_fix_iterations: int = 0
    pylint_violations_initial: int = 0
    pylint_violations_remaining: int = 0
    docker_errors_initial: int = 0
    docker_errors_remaining: int = 0
    semantic_errors: int = 0
    semantic_warnings: int = 0
    files_generated: int = 0
    validation_passed: bool = False
    error_categories: list[str] = field(default_factory=list)


def append_metrics(metrics: ModuleMetrics, output_dir: Path) -> None:
    """Append a metrics record to .planning/metrics.jsonl.

    Creates parent directories if needed. Appends (does not overwrite).
    """
    metrics_file = output_dir / ".planning" / "metrics.jsonl"
    metrics_file.parent.mkdir(parents=True, exist_ok=True)
    with metrics_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(metrics), default=str) + "\n")
