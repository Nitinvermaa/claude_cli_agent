"""Persistent runtime state (sessions and subagent profiles)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from claude_agent_sdk.types import AgentDefinition


@dataclass
class PersistedState:
    known_session_ids: list[str] = field(default_factory=list)
    active_session_id: str | None = None
    active_mode: str = "agent"
    agents: dict[str, AgentDefinition] = field(default_factory=dict)
    session_aliases: dict[str, str] = field(default_factory=dict)


class StateStore:
    """JSON-backed state persistence."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> PersistedState:
        if not self.path.exists():
            return PersistedState()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return PersistedState()
        agents: dict[str, AgentDefinition] = {}
        for name, payload in raw.get("agents", {}).items():
            try:
                agents[name] = AgentDefinition(**payload)
            except TypeError:
                continue
        return PersistedState(
            known_session_ids=list(raw.get("known_session_ids", [])),
            active_session_id=raw.get("active_session_id"),
            active_mode=str(raw.get("active_mode", "agent")),
            agents=agents,
            session_aliases={
                str(k): str(v) for k, v in dict(raw.get("session_aliases", {})).items() if str(v)
            },
        )

    def save(self, state: PersistedState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "known_session_ids": state.known_session_ids,
            "active_session_id": state.active_session_id,
            "active_mode": state.active_mode,
            "agents": {name: asdict(defn) for name, defn in state.agents.items()},
            "session_aliases": state.session_aliases,
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
