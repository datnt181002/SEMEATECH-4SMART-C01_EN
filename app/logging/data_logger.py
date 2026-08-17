"""CSV measurement logger."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app.protocol.models import GasReading, ModuleInfo


class DataLogger:
    def __init__(self) -> None:
        self._file = None
        self._writer: csv.DictWriter | None = None
        self.path: Path | None = None
        self.samples = 0

    @property
    def active(self) -> bool:
        return self._file is not None

    def start(
        self,
        directory: str | Path,
        *,
        module_info: ModuleInfo | None,
        com_port: str,
        interval_ms: int,
        simulation: bool,
    ) -> Path:
        if self.active:
            raise RuntimeError("Logging is already active")
        log_dir = Path(directory)
        log_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = "_SIMULATION" if simulation else ""
        self.path = log_dir / f"4smart_c01_{stamp}{suffix}.csv"
        metadata_path = self.path.with_suffix(".metadata.json")

        metadata = {
            "created_at": datetime.now().isoformat(timespec="milliseconds"),
            "module_info": asdict(module_info) if module_info else None,
            "com_port": com_port,
            "acquisition_interval_ms": interval_ms,
            "simulation": simulation,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        self._file = self.path.open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(
            self._file,
            fieldnames=["timestamp", "sensor_type", "address", "value", "unit", "status", "simulation"],
        )
        self._writer.writeheader()
        self._file.flush()
        self.samples = 0
        return self.path

    def write(self, reading: GasReading) -> None:
        if not self._writer or not self._file:
            return
        self._writer.writerow(
            {
                "timestamp": reading.timestamp.isoformat(timespec="milliseconds"),
                "sensor_type": reading.sensor_type,
                "address": reading.address,
                "value": f"{reading.value:.2f}",
                "unit": reading.unit,
                "status": reading.status,
                "simulation": "YES" if reading.simulated else "NO",
            }
        )
        self._file.flush()
        self.samples += 1

    def stop(self) -> None:
        if self._file:
            self._file.close()
        self._file = None
        self._writer = None

