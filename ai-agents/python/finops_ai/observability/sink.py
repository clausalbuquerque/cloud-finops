from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol


class ObservabilitySink(Protocol):
    def emit(self, event_name: str, payload: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class LoggingObservabilitySink:
    logger_name: str = "finops_ai.observability"

    def emit(self, event_name: str, payload: dict[str, Any]) -> None:
        logger = logging.getLogger(self.logger_name)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_name": event_name,
            **payload,
        }
        logger.info(json.dumps(entry, separators=(",", ":"), ensure_ascii=True))


class InMemoryObservabilitySink:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def emit(self, event_name: str, payload: dict[str, Any]) -> None:
        self.events.append({"event_name": event_name, **payload})
