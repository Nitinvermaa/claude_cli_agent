"""Usage and cost telemetry for cagent runtime requests."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .usage_dashboard_html import build_usage_dashboard_html


MODEL_PRICING_USD_PER_MTOKEN: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-sonnet-4-5-20250929": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-1": (15.0, 75.0),
}


@dataclass
class UsageEvent:
    timestamp: str
    backend_mode: str
    session_id: str | None
    model: str
    prompt_chars: int
    response_chars: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    approx_tokens: bool
    success: bool
    error: str | None = None


class UsageTracker:
    def __init__(self, *, log_path: Path, model: str) -> None:
        self.log_path = log_path
        self.model = model
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        in_rate, out_rate = MODEL_PRICING_USD_PER_MTOKEN.get(model, (3.0, 15.0))
        return (input_tokens / 1_000_000.0) * in_rate + (output_tokens / 1_000_000.0) * out_rate

    def append(
        self,
        *,
        backend_mode: str,
        session_id: str | None,
        model: str,
        prompt_chars: int,
        response_chars: int,
        input_tokens: int,
        output_tokens: int,
        approx_tokens: bool,
        success: bool,
        error: str | None = None,
    ) -> UsageEvent:
        event = UsageEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            backend_mode=backend_mode,
            session_id=session_id,
            model=model,
            prompt_chars=prompt_chars,
            response_chars=response_chars,
            input_tokens=max(0, input_tokens),
            output_tokens=max(0, output_tokens),
            cost_usd=round(self.estimate_cost(model, input_tokens, output_tokens), 6),
            approx_tokens=approx_tokens,
            success=success,
            error=error,
        )
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=True) + "\n")
        return event

    def read_events(self) -> list[UsageEvent]:
        if not self.log_path.exists():
            return []
        events: list[UsageEvent] = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                events.append(UsageEvent(**raw))
            except Exception:
                continue
        return events

    def render_terminal_table(self, console: Console, *, limit: int = 10) -> None:
        events = self.read_events()
        if not events:
            console.print("[dim]No usage events recorded yet.[/dim]")
            return
        table = Table(title=f"cagent usage (last {min(limit, len(events))})")
        table.add_column("Time (UTC)")
        table.add_column("Backend")
        table.add_column("Session")
        table.add_column("Model")
        table.add_column("In Tok", justify="right")
        table.add_column("Out Tok", justify="right")
        table.add_column("Cost USD", justify="right")
        table.add_column("Approx")
        table.add_column("Status")
        for ev in events[-limit:]:
            table.add_row(
                ev.timestamp.replace("T", " ")[:19],
                ev.backend_mode,
                ev.session_id or "-",
                ev.model,
                str(ev.input_tokens),
                str(ev.output_tokens),
                f"{ev.cost_usd:.6f}",
                "yes" if ev.approx_tokens else "no",
                "ok" if ev.success else "error",
            )
        console.print(table)

    def export_html_dashboard(self, output_path: Path) -> Path:
        events = [asdict(ev) for ev in self.read_events()]
        total_cost = sum(float(e.get("cost_usd", 0.0)) for e in events)
        out = output_path.expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        html = build_usage_dashboard_html(events, total_cost)
        out.write_text(html, encoding="utf-8")
        return out
