"""Approval workflow audit logging."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ApprovalEvent:
    stage: str
    decision: str
    prompt: str
    mode: str
    session_id: str | None


class ApprovalAuditStore:
    """Append-only JSONL audit log for approvals."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, event: ApprovalEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": event.stage,
            "decision": event.decision,
            "prompt_preview": event.prompt[:200],
            "mode": event.mode,
            "session_id": event.session_id,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")

    def tail(self, n: int = 20) -> list[dict]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        out: list[dict] = []
        for line in lines[-n:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out
