"""Запись трассы выполнения в JSONL и в память."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class TraceRecorder:
    """Хранит события и, при необходимости, пишет их в JSONL-файл."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.events: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._file = None
        if path is not None:
            target = Path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            self._file = target.open("w", encoding="utf-8")

    def event(self, kind: str, **data: Any) -> dict[str, Any]:
        record = {"kind": kind, **data}
        with self._lock:
            self.events.append(record)
            if self._file is not None:
                self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
                self._file.flush()
        return record

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    def __enter__(self) -> "TraceRecorder":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
