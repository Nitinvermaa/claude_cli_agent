"""Session runtime and REPL orchestration."""

from __future__ import annotations

import asyncio
import base64
import os
import re
import shlex
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import anthropic
from claude_agent_sdk import ClaudeSDKClient
from claude_agent_sdk.types import AgentDefinition, AssistantMessage, ResultMessage, ToolUseBlock
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.text import Text
from rich.prompt import Prompt

from .annotations import expand_prompt_annotations
from .approval_audit import ApprovalAuditStore, ApprovalEvent
from .approval_token import ApprovalTokenManager
from .config import AgentConfig, load_or_init_config, persist_config
from .console_theme import use_dark_ink
from .graphify_integration import GraphifyManager
from .options_build import AgentMode, build_options
from .policy import needs_change_confirmation, needs_commit_confirmation, needs_push_confirmation
from .render import (
    render_btw_reply,
    render_context_usage,
    render_message,
    render_shortcuts_help,
    render_welcome,
)
from .scaffolding import detect_scaffold_request, scaffold_project
from .state_store import PersistedState, StateStore
from .ux import asciimatics_splash, boot_splash, cartoon_loader, textual_hint
from .usage_tracking import UsageTracker

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
except Exception:  # pragma: no cover - optional dependency fallback
    PromptSession = None  # type: ignore[assignment]
    AutoSuggestFromHistory = None  # type: ignore[assignment]

from .host_commands import COMMAND_META, HOST_COMMANDS, HostCommandCompleter


@dataclass
class SessionState:
    known_session_ids: list[str] = field(default_factory=list)
    active_session_id: str | None = None
    active_mode: AgentMode = "agent"
    agents: dict[str, AgentDefinition] = field(default_factory=dict)
    session_aliases: dict[str, str] = field(default_factory=dict)
    session_full_access: bool = False
    next_task_full_access: bool = False

    def to_persisted(self) -> PersistedState:
        return PersistedState(
            known_session_ids=self.known_session_ids,
            active_session_id=self.active_session_id,
            active_mode=self.active_mode,
            agents=self.agents,
            session_aliases=self.session_aliases,
        )


class Runtime:
    """High-level host runtime for multi-session and subagent workflows."""

    def __init__(self, *, config: AgentConfig, cwd: Path, mode: AgentMode, console: Console) -> None:
        self.config = config
        self.cwd = cwd
        self.console = console
        self.state_store = StateStore(Path(config.session_index_path).expanduser())
        persisted = self.state_store.load()
        self.state = SessionState(
            active_mode=mode,
            active_session_id=persisted.active_session_id,
            known_session_ids=persisted.known_session_ids,
            agents=persisted.agents,
            session_aliases=persisted.session_aliases,
        )
        self.client: ClaudeSDKClient | None = None
        self.backend_mode = config.backend_mode if config.backend_mode in {"claude_code", "independent"} else "claude_code"
        self.independent_client: anthropic.Anthropic | None = None
        self.independent_histories: dict[str, list[dict]] = {}
        self.approval_audit = ApprovalAuditStore(Path(config.approval_audit_path).expanduser())
        self.approval_tokens = ApprovalTokenManager()
        self.graphify = GraphifyManager(
            console=console,
            graphify_cmd=config.graphify_path,
            enabled=config.graphify_auto_update,
        )
        self.usage_tracker = UsageTracker(
            log_path=Path(config.usage_log_path).expanduser(),
            model=config.model,
        )
        defaults = {
            "explorer": AgentDefinition(
                description="Read-only explorer subagent",
                prompt="Explore code and summarize relevant findings with file paths.",
                tools=["Read", "Grep", "Glob"],
                model="sonnet",
            ),
            "implementer": AgentDefinition(
                description="Code implementation subagent",
                prompt="Implement focused code changes and explain verification.",
                model="sonnet",
            ),
        }
        for name, value in defaults.items():
            self.state.agents.setdefault(name, value)
        self._prompt_session = self._build_prompt_session()
        self._persist_state()

    async def start(self) -> None:
        # Auto-apply terminal-dark behavior when user forces dark preset via env.
        # This mirrors `/theme preset terminal-dark` for the running session.
        theme_env = (os.environ.get("CAGENT_CLI_THEME") or "").strip().lower()
        if theme_env in {"dark", "black"}:
            os.environ.setdefault("CAGENT_FORCE_DARK_UI", "1")
            if self.config.prompt_color in {"bright_white", "white", "cyan"}:
                self.config.prompt_color = "bright_cyan"
            if self.config.accent_color in {"bright_cyan", "cyan"}:
                self.config.accent_color = "bright_magenta"
        boot_splash(self.console)
        textual_hint(self.console)
        if os.environ.get("CAGENT_ASCIIMATICS_BOOT", "").lower() in {"1", "true", "yes"}:
            asciimatics_splash(self.console)
        await self._connect()
        render_welcome(
            self.console,
            self.state.active_mode,
            str(self.cwd),
            prompt_color=self.config.prompt_color,
            accent_color=self.config.accent_color,
        )
        if use_dark_ink():
            self.console.print(
                f"[#475569]Backend:[/] [bold #0f172a]{self.backend_mode}[/bold #0f172a]"
            )
            self.console.print(
                "[#475569]Package version:[/] [bold #0f172a]run[/] [bold #0369a1]cagent --version[/] [bold #0f172a]or[/] "
                "[bold #0369a1]cagent version[/] [#475569]in the shell (not at the[/] [bold #0f172a]you:[/] [#475569]prompt).[/]"
            )
            self.console.print("[#475569]? for shortcuts · /help for all commands[/]")
        else:
            self.console.print(f"[bold bright_white]Backend:[/bold bright_white] [bright_cyan]{self.backend_mode}[/bright_cyan]")
            self.console.print(
                "[bright_white]Package version:[/bright_white] run [bold bright_cyan]cagent --version[/bold bright_cyan] "
                "or [bold bright_cyan]cagent version[/bold bright_cyan] "
                "[bright_white]in the shell (not at the[/bright_white] [bold bright_white]you:[/bold bright_white] [bright_white]prompt).[/bright_white]"
            )
            self.console.print("[bold bright_white]?[/bold bright_white] [bright_white]for shortcuts ·[/bright_white] [bold bright_cyan]/help[/bold bright_cyan] [bright_white]for all commands[/bright_white]")
        await self._repl()

    async def stop(self) -> None:
        if self.client:
            await self.client.disconnect()
            self.client = None
        self.independent_client = None
        self._persist_state()

    def _persist_state(self) -> None:
        self.state_store.save(self.state.to_persisted())

    def _effective_full_access(self) -> bool:
        return bool(
            self.config.full_access_project
            or self.state.session_full_access
            or self.state.next_task_full_access
        )

    def _build_prompt_session(self):
        if PromptSession is None or AutoSuggestFromHistory is None:
            return None
        try:
            completer = HostCommandCompleter(COMMAND_META)
        except Exception:
            return None
        return PromptSession(completer=completer, auto_suggest=AutoSuggestFromHistory())

    @staticmethod
    def _normalize_command_token(token: str) -> str:
        if token.startswith("\\"):
            return "/" + token[1:]
        return token

    def _color_is_valid(self, value: str) -> bool:
        sample = value.strip()
        if not sample:
            return False
        base = {"black", "red", "green", "yellow", "blue", "magenta", "cyan", "white", "dim"}
        bright = {f"bright_{c}" for c in base if c != "dim"}
        allowed = base | bright
        if sample.lower() in allowed:
            return True
        # Accept rich hex colors like #aabbcc.
        return bool(re.fullmatch(r"#[0-9a-fA-F]{6}", sample))

    async def _connect(self) -> None:
        if self.client:
            await self.client.disconnect()
            self.client = None

        if self.backend_mode == "claude_code":
            resume_session_id: str | None = None
            if self.state.active_session_id:
                try:
                    uuid.UUID(self.state.active_session_id)
                    resume_session_id = self.state.active_session_id
                except ValueError:
                    resume_session_id = None
            options = build_options(
                config=self.config,
                cwd=self.cwd,
                mode=self.state.active_mode,
                resume_session_id=resume_session_id,
                agents=self.state.agents,
                full_access_override=self._effective_full_access(),
            )
            self.client = ClaudeSDKClient(options=options)
            try:
                await self.client.connect()
            except Exception:
                if resume_session_id is None:
                    raise
                # Resume IDs can become stale across workspaces/logins; retry fresh.
                self.console.print(
                    "[yellow]Previous Claude session could not be resumed; starting a fresh session.[/yellow]"
                )
                await self.client.disconnect()
                self.client = None
                self.state.active_session_id = None
                options = build_options(
                    config=self.config,
                    cwd=self.cwd,
                    mode=self.state.active_mode,
                    resume_session_id=None,
                    agents=self.state.agents,
                    full_access_override=self._effective_full_access(),
                )
                self.client = ClaudeSDKClient(options=options)
                await self.client.connect()
            return

        # Independent backend: local session/thread management.
        if self.independent_client is None:
            self.independent_client = anthropic.Anthropic(api_key=self.config.api_key)
        if not self.state.active_session_id:
            self.state.active_session_id = "local-1"
        self.independent_histories.setdefault(self.state.active_session_id, [])

    async def _prompt_line(self) -> str:
        if self._prompt_session is None:
            prompt_label = f"[bold {self.config.prompt_color}]you[/bold {self.config.prompt_color}]"
            return await asyncio.to_thread(Prompt.ask, prompt_label)

        def _read() -> str:
            return self._prompt_session.prompt("you: ")

        return await asyncio.to_thread(_read)

    async def _repl(self) -> None:
        while True:
            raw = await self._prompt_line()
            line = raw.strip()
            # Users often type `cagent --version` inside the REPL; handle it here.
            lv = line.lower()
            if lv in {"--version", "/version", "\\version", "version"} or lv == "cagent --version" or line.strip() == "-V":
                from claude_cli_agent import __version__

                self.console.print(f"[bright_cyan]cagent[/bright_cyan] [bright_white]{__version__}[/bright_white]")
                self.console.print(
                    "[dim]That is the cagent package version. In your system shell (outside this chat), "
                    "run: [bold]cagent --version[/bold] or [bold]python -m claude_cli_agent --version[/bold][/dim]"
                )
                continue
            if line in {"?", "？"}:
                render_shortcuts_help(self.console)
                continue
            if not line:
                # Ignore blank submits to avoid noisy repeated output on terminal resizes.
                continue
            if line.startswith(("/", "\\")):
                should_continue = await self._handle_host_command(line)
                if not should_continue:
                    break
                continue
            await self._send_and_render(line)

    async def _send_and_render(self, prompt: str) -> None:
        if self.backend_mode == "claude_code":
            assert self.client is not None
        else:
            if self.independent_client is None:
                await self._connect()
            assert self.independent_client is not None
        changed_or_impl = needs_change_confirmation(prompt)
        commit_like = needs_commit_confirmation(prompt)
        push_like = needs_push_confirmation(prompt)

        task_override_activated = False
        if self.config.require_change_confirmation and self.config.approval_workflow_mode:
            approved, task_override_activated = await self._run_approval_workflow(
                prompt=prompt,
                changed_or_impl=changed_or_impl,
                commit_like=commit_like,
                push_like=push_like,
            )
            if not approved:
                return
        elif self.config.require_change_confirmation and (changed_or_impl or push_like):
            approved = await asyncio.to_thread(
                Confirm.ask,
                "This request may modify code or push changes. Proceed?",
                default=not push_like,
            )
            if not approved:
                self.console.print("[yellow]Skipped by approval policy.[/yellow]")
                return

        changed_files = False
        prompt_to_send = prompt
        if self.config.enable_reference_annotations:
            expanded = expand_prompt_annotations(prompt=prompt, cwd=self.cwd, max_total_chars=8000)
            if expanded.matched:
                self.console.print(
                    f"[dim]Expanded annotations: {', '.join('@' + m for m in expanded.matched)}[/dim]"
                )
                prompt_to_send = expanded.prompt
            if expanded.unresolved:
                self.console.print(
                    "[yellow]Unresolved annotations:[/yellow] "
                    + ", ".join("@" + t for t in expanded.unresolved)
                )
                for token in expanded.unresolved:
                    options = expanded.suggestions.get(token, [])
                    if options:
                        self.console.print(f"[dim]Suggestions for @{token}:[/dim]")
                        for opt in options[:6]:
                            prefix = "@dir:" if opt.endswith("/") else "@file:"
                            self.console.print(f"  - {prefix}{opt}")
        if self.state.active_mode == "agent" and self.config.auto_scaffold_on_app_request:
            # If user already specified explicit filesystem paths, avoid creating
            # generic scaffold folders like generated-app and let the model act directly.
            has_explicit_path = bool(re.search(r"(^|\s)/(?:[\w.-]+/)+[\w.-]+", prompt))
            req = detect_scaffold_request(prompt)
            if req and not has_explicit_path:
                if not self.config.enable_web_ui_plugin:
                    req.framework = "none"
                if not self.config.enable_voice_support:
                    req.voice_enabled = False
                if not self.config.enable_vision_support:
                    req.vision_enabled = False
                target = scaffold_project(self.cwd, req, self.console)
                prompt_to_send = (
                    f"A starter scaffold was created at {target}. "
                    f"Now continue implementation based on this user request:\n{prompt}"
                )
        if self.config.graphify_query_first:
            graph_context = await self.graphify.query_context(self.cwd, prompt)
            if graph_context:
                prompt_to_send = (
                    "Use this graph context as guidance, then answer the user request.\n\n"
                    f"{graph_context}\n\n"
                    f"User request:\n{prompt}"
                )
        async with cartoon_loader(
            self.console,
            caption="Linking context and thinking…",
            accent_color=self.config.accent_color,
        ):
            if self.backend_mode == "claude_code":
                assert self.client is not None
                response_chars = 0
                await self.client.query(prompt_to_send)
                async for message in self.client.receive_response():
                    render_message(self.console, message)
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            maybe_text = getattr(block, "text", None)
                            if isinstance(maybe_text, str):
                                response_chars += len(maybe_text)
                            if isinstance(block, ToolUseBlock) and block.name in {
                                "Write",
                                "Edit",
                                "MultiEdit",
                                "NotebookEdit",
                            }:
                                changed_files = True
                    if isinstance(message, ResultMessage):
                        if message.session_id and message.session_id not in self.state.known_session_ids:
                            self.state.known_session_ids.append(message.session_id)
                        if message.session_id:
                            self.state.active_session_id = message.session_id
                            self._persist_state()
                input_tokens = len(prompt_to_send) // 4
                output_tokens = max(1, response_chars // 4) if response_chars else 0
                self.usage_tracker.append(
                    backend_mode=self.backend_mode,
                    session_id=self.state.active_session_id,
                    model=self.config.model,
                    prompt_chars=len(prompt_to_send),
                    response_chars=response_chars,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    approx_tokens=True,
                    success=True,
                )
            else:
                text, input_tokens, output_tokens, success, error = await self._query_independent(prompt_to_send)
                self.console.print(Panel(text, title="Assistant (independent backend)", border_style="cyan"))
                self.usage_tracker.append(
                    backend_mode=self.backend_mode,
                    session_id=self.state.active_session_id,
                    model=self.config.model,
                    prompt_chars=len(prompt_to_send),
                    response_chars=len(text),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    approx_tokens=False,
                    success=success,
                    error=error,
                )
        self.usage_tracker.render_terminal_table(self.console, limit=5)
        await self.graphify.maybe_update(self.cwd, changed=changed_files)
        if task_override_activated:
            self.state.next_task_full_access = False
            await self._connect()

    async def _query_independent(self, prompt: str) -> tuple[str, int, int, bool, str | None]:
        assert self.independent_client is not None
        session_id = self.state.active_session_id or "local-1"
        history = self.independent_histories.setdefault(session_id, [])
        history.append({"role": "user", "content": prompt})

        def _call() -> anthropic.types.Message:
            return self.independent_client.messages.create(
                model=self.config.model,
                max_tokens=2000,
                messages=history,
            )

        try:
            response = await asyncio.to_thread(_call)
        except Exception as exc:
            message = f"Independent backend request failed: {exc}"
            history.append({"role": "assistant", "content": message})
            self._persist_state()
            return message, 0, 0, False, str(exc)
        text_parts: list[str] = []
        input_tokens = 0
        output_tokens = 0
        usage = getattr(response, "usage", None)
        if usage is not None:
            input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
            output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        for block in response.content:
            maybe_text = getattr(block, "text", None)
            if maybe_text:
                text_parts.append(maybe_text)
        answer = "\n".join(text_parts).strip() or "(no text response)"
        history.append({"role": "assistant", "content": answer})
        if session_id not in self.state.known_session_ids:
            self.state.known_session_ids.append(session_id)
        self.state.active_session_id = session_id
        self._persist_state()
        return answer, input_tokens, output_tokens, True, None

    async def _query_independent_vision(self, *, image_path: str, question: str) -> str:
        assert self.independent_client is not None
        target = (self.cwd / image_path).resolve() if not Path(image_path).is_absolute() else Path(image_path)
        if not target.exists() or not target.is_file():
            return f"Image not found: {image_path}"
        mime = "image/png"
        suffix = target.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            mime = "image/jpeg"
        elif suffix == ".webp":
            mime = "image/webp"
        try:
            raw = target.read_bytes()
        except OSError as exc:
            return f"Failed to read image: {exc}"
        b64 = base64.b64encode(raw).decode("utf-8")

        def _call() -> anthropic.types.Message:
            return self.independent_client.messages.create(
                model=self.config.model,
                max_tokens=1200,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": mime,
                                    "data": b64,
                                },
                            },
                            {"type": "text", "text": question},
                        ],
                    }
                ],
            )

        try:
            response = await asyncio.to_thread(_call)
        except Exception as exc:
            return f"Vision request failed: {exc}"
        out: list[str] = []
        for block in response.content:
            maybe_text = getattr(block, "text", None)
            if maybe_text:
                out.append(maybe_text)
        return "\n".join(out).strip() or "(no text response)"

    async def _run_approval_workflow(
        self,
        *,
        prompt: str,
        changed_or_impl: bool,
        commit_like: bool,
        push_like: bool,
    ) -> tuple[bool, bool]:
        """Enforce plan -> implementation -> commit -> push approval gates."""
        needs_any = changed_or_impl or commit_like or push_like
        if not needs_any:
            return True, False

        task_override_activated = False

        plan_ok = await asyncio.to_thread(
            Confirm.ask,
            "Approval gate 1/4 (plan): approve plan to proceed?",
            default=True,
        )
        if plan_ok:
            plan_ok = await self._require_signed_token("plan")
        self._log_approval("plan", "approve" if plan_ok else "deny", prompt)
        if not plan_ok:
            self.console.print("[yellow]Blocked at plan approval gate.[/yellow]")
            return False, False

        if not self._effective_full_access():
            decision = await asyncio.to_thread(
                Prompt.ask,
                "Approval gate 2/4 (implementation): [deny|once|task|session]",
                choices=["deny", "once", "task", "session"],
                default="once",
            )
            self._log_approval("implementation", decision, prompt)
            if decision == "deny":
                self.console.print("[yellow]Blocked at implementation approval gate.[/yellow]")
                return False, False
            if not await self._require_signed_token("implementation"):
                self._log_approval("implementation", "deny_token", prompt)
                self.console.print("[yellow]Blocked at implementation token gate.[/yellow]")
                return False, False
            if decision == "task":
                self.state.next_task_full_access = True
                task_override_activated = True
                await self._connect()
            elif decision == "session":
                self.state.session_full_access = True
                await self._connect()
        else:
            self._log_approval("implementation", "already_granted", prompt)

        if commit_like or push_like:
            commit_ok = await asyncio.to_thread(
                Confirm.ask,
                "Approval gate 3/4 (commit): allow commit operations?",
                default=False,
            )
            if commit_ok:
                commit_ok = await self._require_signed_token("commit")
            self._log_approval("commit", "approve" if commit_ok else "deny", prompt)
            if not commit_ok:
                self.console.print("[yellow]Blocked at commit approval gate.[/yellow]")
                return False, task_override_activated

        if push_like:
            push_ok = await asyncio.to_thread(
                Confirm.ask,
                "Approval gate 4/4 (push): allow push/deploy/release?",
                default=False,
            )
            if push_ok:
                push_ok = await self._require_signed_token("push")
            self._log_approval("push", "approve" if push_ok else "deny", prompt)
            if not push_ok:
                self.console.print("[yellow]Blocked at push approval gate.[/yellow]")
                return False, task_override_activated

        return True, task_override_activated

    def _log_approval(self, stage: str, decision: str, prompt: str) -> None:
        self.approval_audit.append(
            ApprovalEvent(
                stage=stage,
                decision=decision,
                prompt=prompt,
                mode=self.state.active_mode,
                session_id=self.state.active_session_id,
            )
        )

    async def _require_signed_token(self, stage: str) -> bool:
        if not self.config.signed_approval_tokens:
            return True
        challenge = self.approval_tokens.issue(
            stage=stage,
            ttl_seconds=self.config.approval_token_ttl_seconds,
        )
        self.console.print(
            f"[bold yellow]Approval token required[/bold yellow] stage={stage} "
            f"expires_in={challenge.expires_in}s"
        )
        self.console.print(f"Token: [cyan]{challenge.token}[/cyan]")
        provided = await asyncio.to_thread(Prompt.ask, "Re-enter approval token")
        ok = self.approval_tokens.verify(challenge, provided)
        if not ok:
            self.console.print("[yellow]Invalid or expired approval token.[/yellow]")
        return ok

    async def _handle_btw_command(self, parts: list[str]) -> None:
        """One-shot Anthropic answer; does not touch the main SDK session or transcript."""
        question = " ".join(parts[1:]).strip()
        if not question:
            self.console.print(
                "[yellow]Use:[/yellow] /btw [dim]<side question>[/dim]\n"
                "[dim]Quick answer only; main conversation history is unchanged.[/dim]"
            )
            return
        key = (self.config.api_key or "").strip()
        if not key:
            self.console.print("[red]No API key configured.[/red] [dim]Use /apikey set …[/dim]")
            return
        model = (self.config.model or "").strip() or "claude-sonnet-4-20250514"

        def _call() -> str:
            client = anthropic.Anthropic(api_key=key)
            resp = client.messages.create(
                model=model,
                max_tokens=1024,
                system=(
                    "You are a concise assistant. Reply in plain text, under 400 words. "
                    "No tools. If the question needs repository context you do not have, say so briefly."
                ),
                messages=[{"role": "user", "content": question}],
            )
            chunks: list[str] = []
            for block in resp.content:
                if getattr(block, "type", None) == "text" and getattr(block, "text", None):
                    chunks.append(str(block.text))
            return "\n".join(chunks).strip()

        try:
            async with cartoon_loader(
                self.console,
                caption="/btw · side channel",
                accent_color=self.config.accent_color,
            ):
                answer = await asyncio.to_thread(_call)
        except Exception as e:
            self.console.print(Panel(str(e), title="/btw failed", border_style="red"))
            return
        render_btw_reply(self.console, answer or "(empty)")

    async def _handle_host_command(self, line: str) -> bool:
        parts = shlex.split(line, posix=False)
        if not parts:
            return True
        parts[0] = self._normalize_command_token(parts[0])
        cmd = parts[0].lower()

        if cmd == "/quit":
            await self.stop()
            return False

        if cmd == "/shortcuts":
            render_shortcuts_help(self.console)
            return True

        if cmd == "/help":
            self.console.print("[bold]Host commands[/bold] (type [bold]/[/bold] then Tab for hints):\n")
            for name in HOST_COMMANDS:
                desc = COMMAND_META.get(name, "")
                self.console.print(f"  [bright_cyan]{name}[/bright_cyan]  [dim]{desc}[/dim]")
            self.console.print(
                "\n[dim]Examples: ? shortcuts · /shortcuts · /mode agent · /session list · /btw What does JWT mean here?[/dim]"
            )
            return True

        if cmd == "/mode" and len(parts) >= 2:
            mode = parts[1].lower()
            if mode not in {"agent", "plan", "ask", "debug"}:
                self.console.print("[yellow]Invalid mode.[/yellow]")
                return True
            self.state.active_mode = mode  # type: ignore[assignment]
            await self._connect()
            self._persist_state()
            self.console.print(f"[green]Switched mode to {mode}[/green]")
            return True

        if cmd == "/session":
            return await self._handle_session_command(parts)

        if cmd == "/chat":
            return await self._handle_chat_command(parts)

        if cmd == "/bwt":
            bwt_parts = ["/chat", "switch"]
            if len(parts) >= 2:
                bwt_parts.append(parts[1])
            return await self._handle_chat_command(bwt_parts)

        if cmd == "/btw":
            await self._handle_btw_command(parts)
            return True

        if cmd == "/context":
            await self._show_context()
            return True
        if cmd == "/backend":
            await self._handle_backend_command(parts)
            return True

        if cmd == "/subagent":
            await self._handle_subagent_command(parts)
            return True
        if cmd == "/mcp":
            await self._handle_mcp_command(parts)
            return True
        if cmd == "/vision":
            await self._handle_vision_command(parts)
            return True
        if cmd == "/approve":
            await self._handle_approve_command(parts)
            return True
        if cmd == "/approvals":
            await self._handle_approvals_command(parts)
            return True
        if cmd == "/annotations":
            self._show_annotation_help()
            return True
        if cmd == "/pick":
            await self._handle_pick_command(parts)
            return True
        if cmd == "/authcheck":
            await self._handle_authcheck_command()
            return True
        if cmd == "/usage":
            limit = 10
            if len(parts) >= 2:
                try:
                    limit = max(1, min(200, int(parts[1])))
                except ValueError:
                    self.console.print("[yellow]Use: /usage [n][/yellow]")
                    return True
            self.usage_tracker.render_terminal_table(self.console, limit=limit)
            dashboard = self.usage_tracker.export_html_dashboard(Path(self.config.usage_dashboard_path))
            self.console.print(f"[green]Usage dashboard:[/green] {dashboard}")
            return True

        if cmd == "/apikey":
            await self._handle_apikey_command(parts)
            return True

        if cmd == "/theme":
            await self._handle_theme_command(parts)
            return True

        # User typed only "/" or unknown prefix; offer suggestions.
        if cmd == "/":
            self.console.print("[dim]Try /help. Suggestions: " + ", ".join(HOST_COMMANDS[:8]) + "[/dim]")
            return True
        suggestions = [c for c in HOST_COMMANDS if c.startswith(cmd)]
        if suggestions:
            self.console.print("[yellow]Unknown command.[/yellow] Did you mean: " + ", ".join(suggestions[:6]))
        else:
            self.console.print("[yellow]Unknown host command. Use /help[/yellow]")
        return True

    async def _handle_session_command(self, parts: list[str]) -> bool:
        if len(parts) < 2:
            self.console.print("[yellow]Use: /session list|new|switch <id>[/yellow]")
            return True
        sub = parts[1].lower()
        if sub == "list":
            if not self.state.known_session_ids:
                self.console.print("[dim]No known sessions yet.[/dim]")
            for sid in self.state.known_session_ids:
                active = " *" if sid == self.state.active_session_id else ""
                label = next((name for name, value in self.state.session_aliases.items() if value == sid), None)
                if label:
                    self.console.print(f"- {sid} ({label}){active}")
                else:
                    self.console.print(f"- {sid}{active}")
            return True
        if sub == "new":
            self.state.active_session_id = None
            await self._connect()
            self._persist_state()
            self.console.print("[green]Started a new session.[/green]")
            return True
        if sub == "switch" and len(parts) >= 3:
            sid = parts[2]
            self.state.active_session_id = sid
            await self._connect()
            self._persist_state()
            self.console.print(f"[green]Switched to session {sid}[/green]")
            return True
        self.console.print("[yellow]Invalid session command.[/yellow]")
        return True

    async def _handle_chat_command(self, parts: list[str]) -> bool:
        if len(parts) < 2:
            self.console.print("[yellow]Use: /chat list|new <name>|switch <name>[/yellow]")
            return True
        sub = parts[1].lower()
        if sub == "list":
            if not self.state.session_aliases:
                self.console.print("[dim]No named conversations yet. Use /chat new <name>[/dim]")
                return True
            for name, sid in self.state.session_aliases.items():
                active = " *" if sid == self.state.active_session_id else ""
                self.console.print(f"- {name} -> {sid}{active}")
            return True
        if sub == "new" and len(parts) >= 3:
            name = parts[2]
            self.state.active_session_id = None
            await self._connect()
            if self.state.active_session_id:
                self.state.session_aliases[name] = self.state.active_session_id
                self._persist_state()
                self.console.print(
                    f"[green]Started conversation '{name}' ({self.state.active_session_id}).[/green]"
                )
            return True
        if sub == "switch" and len(parts) >= 3:
            name = parts[2]
            sid = self.state.session_aliases.get(name)
            if not sid:
                self.console.print(f"[yellow]Unknown conversation '{name}'.[/yellow]")
                return True
            self.state.active_session_id = sid
            await self._connect()
            self._persist_state()
            self.console.print(f"[green]Switched to conversation '{name}' ({sid}).[/green]")
            return True
        self.console.print("[yellow]Use: /chat list|new <name>|switch <name>[/yellow]")
        return True

    async def _show_context(self) -> None:
        if self.backend_mode == "claude_code":
            assert self.client is not None
            usage = await self.client.get_context_usage()
            render_context_usage(self.console, usage)
        else:
            sid = self.state.active_session_id or "local-1"
            turns = len(self.independent_histories.get(sid, []))
            approx_chars = sum(
                len(str(item.get("content", "")))
                for item in self.independent_histories.get(sid, [])
                if isinstance(item, dict)
            )
            approx_tokens = approx_chars // 4
            self.console.print(
                f"[bold]Independent context:[/bold] session={sid} turns={turns} ~tokens={approx_tokens}"
            )
        self.console.print("[bold]Cost-saving suggestions:[/bold]")
        for tip in self.graphify.suggest_cost_optimizations():
            self.console.print(f"- {tip}")

    async def _handle_apikey_command(self, parts: list[str]) -> None:
        if len(parts) < 2:
            self.console.print("[yellow]Use: /apikey set <key> | /apikey show[/yellow]")
            return
        sub = parts[1].lower()
        if sub == "show":
            key = self.config.api_key or ""
            if not key:
                self.console.print("[yellow]No API key configured.[/yellow]")
                return
            masked = f"{key[:8]}...{key[-6:]}" if len(key) > 18 else "***"
            self.console.print(f"[green]Configured API key:[/green] {masked}")
            return
        if sub == "set":
            key = " ".join(parts[2:]).strip() if len(parts) > 2 else ""
            if not key:
                key = (await asyncio.to_thread(Prompt.ask, "Enter Anthropic API key", password=True)).strip()
            if not key:
                self.console.print("[yellow]API key cannot be empty.[/yellow]")
                return
            self.config = load_or_init_config(
                self.console,
                api_key_override=key,
                backend_override=self.backend_mode,
                cwd=self.cwd.resolve(),
            )
            await self._connect()
            self.console.print("[green]API key updated and backend reconnected.[/green]")
            return
        self.console.print("[yellow]Use: /apikey set <key> | /apikey show[/yellow]")

    async def _handle_theme_command(self, parts: list[str]) -> None:
        ink = use_dark_ink()
        hint = "#475569" if ink else "dim"
        warn = "#b45309" if ink else "yellow"
        ok = "#047857" if ink else "green"
        lab = "bold #0f172a" if ink else "bold"
        val = "bold #0369a1" if ink else "cyan"

        def _show_current() -> None:
            self.console.print(Text("Current theme" if ink else "Theme", style=lab))
            self.console.print(
                Text.assemble(
                    ("  prompt_color = ", hint),
                    (self.config.prompt_color, val),
                    ("\n  accent_color = ", hint),
                    (self.config.accent_color, val),
                )
            )
            preset_env = (os.environ.get("CAGENT_CLI_THEME") or "auto").strip().lower() or "auto"
            force_dark = (os.environ.get("CAGENT_FORCE_DARK_UI") or "").strip().lower() in {
                "1",
                "true",
                "yes",
                "force",
            }
            effective = "readable" if use_dark_ink() else "dark-ui"
            self.console.print(
                Text.assemble(
                    ("\n  preset_env   = ", hint),
                    (preset_env, val),
                    ("\n  force_dark   = ", hint),
                    ("on" if force_dark else "off", val),
                    ("\n  effective_ui = ", hint),
                    (effective, val),
                )
            )
            self.console.print(
                Text.assemble(
                    ("\nExamples:\n", hint),
                    ("  /theme set prompt bright_white\n", hint),
                    ("  /theme set accent magenta\n", hint),
                    ("  /theme set prompt_color=green\n", hint),
                    ("  /theme set accent_color=#0891b2\n", hint),
                    ("  /theme preset readable\n", hint),
                    ("  /theme preset dark\n", hint),
                    ("  /theme preset terminal-dark\n", hint),
                    (
                        "\n(Shorter form uses two words after set; key=value is one token.)",
                        hint,
                    ),
                )
            )

        if len(parts) < 2 or parts[1].lower() == "show":
            _show_current()
            return
        if parts[1].lower() == "preset":
            if len(parts) < 3:
                self.console.print(
                    Text.assemble(
                        ("Use: ", warn),
                        ("/theme preset readable|dark|terminal-dark|light|auto", val),
                    )
                )
                return
            mode = parts[2].strip().lower()
            if mode in {"readable", "safe"}:
                os.environ["CAGENT_CLI_THEME"] = "auto"
                os.environ["CAGENT_USE_DARK_INK"] = "1"
                os.environ.pop("CAGENT_FORCE_DARK_UI", None)
            elif mode in {"dark", "dark-ui"}:
                os.environ["CAGENT_CLI_THEME"] = "dark"
                os.environ["CAGENT_FORCE_DARK_UI"] = "1"
                os.environ.pop("CAGENT_USE_DARK_INK", None)
            elif mode in {"terminal-dark", "claude-dark"}:
                os.environ["CAGENT_CLI_THEME"] = "dark"
                os.environ["CAGENT_FORCE_DARK_UI"] = "1"
                os.environ.pop("CAGENT_USE_DARK_INK", None)
                # Claude-like dark defaults: cyan prompt + magenta accent.
                self.config.prompt_color = "bright_cyan"
                self.config.accent_color = "bright_magenta"
                persist_config(self.config)
            elif mode == "light":
                os.environ["CAGENT_CLI_THEME"] = "light"
                os.environ.pop("CAGENT_FORCE_DARK_UI", None)
                os.environ.pop("CAGENT_USE_DARK_INK", None)
            elif mode == "auto":
                os.environ["CAGENT_CLI_THEME"] = "auto"
                os.environ.pop("CAGENT_FORCE_DARK_UI", None)
                os.environ.pop("CAGENT_USE_DARK_INK", None)
            else:
                self.console.print(
                    Text.assemble(
                        ("Unknown preset ", warn),
                        (repr(mode), val),
                        (". Use readable|dark|terminal-dark|light|auto.", hint),
                    )
                )
                return
            now_ink = use_dark_ink()
            now_effective = "readable" if now_ink else "dark-ui"
            self.console.print(
                Text.assemble(
                    ("Theme preset applied for this session: ", ok),
                    (mode, val),
                    (" (effective ", hint),
                    (now_effective, val),
                    ("). ", hint),
                    ("Tip: add env vars to ~/.zshrc to persist across new terminals.", hint),
                )
            )
            return
        if parts[1].lower() != "set":
            self.console.print(
                Text.assemble(
                    ("Use: ", warn),
                    ("/theme show", val),
                    (" or ", hint),
                    ("/theme set prompt <color>", val),
                    (" / ", hint),
                    ("/theme set prompt_color=<color>", val),
                    ("\n     ", hint),
                    ("/theme preset readable|dark|terminal-dark|light|auto", val),
                )
            )
            return
        if len(parts) < 3:
            self.console.print(
                Text.assemble(
                    ("Missing target/color. ", warn),
                    ("Try: /theme set prompt bright_white", val),
                )
            )
            return

        rest = parts[2:]
        target: str | None = None
        color: str | None = None

        if len(rest) == 1:
            tok = rest[0].strip()
            if "=" in tok:
                raw_key, _, raw_val = tok.partition("=")
                key = raw_key.strip().lower()
                color = raw_val.strip()
                if key in {"prompt", "prompt_color"}:
                    target = "prompt"
                elif key in {"accent", "accent_color"}:
                    target = "accent"
                else:
                    self.console.print(
                        Text.assemble(
                            ("Unknown key ", warn),
                            (repr(key), val),
                            (". Use prompt, accent, prompt_color, or accent_color.", hint),
                        )
                    )
                    return
            else:
                self.console.print(
                    Text.assemble(
                        ("Need a color. Examples: ", hint),
                        ("/theme set prompt green", val),
                        (" or ", hint),
                        ("/theme set prompt_color=green", val),
                    )
                )
                return
        else:
            key = rest[0].strip().lower()
            color = " ".join(rest[1:]).strip()
            if key in {"prompt", "prompt_color"}:
                target = "prompt"
            elif key in {"accent", "accent_color"}:
                target = "accent"
            else:
                self.console.print(
                    Text.assemble(
                        ("First word after set must be ", hint),
                        ("prompt", val),
                        (" or ", hint),
                        ("accent", val),
                        (", not ", warn),
                        (repr(key), val),
                        (".", hint),
                    )
                )
                return

        if target is None:
            self.console.print(Text.assemble(("Could not parse theme target.", warn)))
            return
        if not color:
            self.console.print(Text.assemble(("Color is empty.", warn)))
            return
        if not self._color_is_valid(color):
            self.console.print(
                Text.assemble(
                    ("Invalid color ", warn),
                    (repr(color), val),
                    (". Use a Rich name (e.g. green, bright_cyan) or ", hint),
                    ("#RRGGBB", val),
                    (".", hint),
                )
            )
            return
        if target == "prompt":
            self.config.prompt_color = color
        else:
            self.config.accent_color = color
        persist_config(self.config)
        self.console.print(
            Text.assemble(
                ("Theme saved. ", ok),
                ("prompt_color=", hint),
                (self.config.prompt_color, val),
                ("  accent_color=", hint),
                (self.config.accent_color, val),
            )
        )

    async def _handle_backend_command(self, parts: list[str]) -> None:
        if len(parts) < 2:
            self.console.print("[yellow]Use: /backend status|switch <claude_code|independent>[/yellow]")
            return
        sub = parts[1].lower()
        # Convenience alias: allow `/backend independent` and `/backend claude_code`.
        if sub in {"claude_code", "independent"}:
            parts = [parts[0], "switch", sub]
            sub = "switch"
        if sub == "status":
            self.console.print(f"[bold]Active backend:[/bold] {self.backend_mode}")
            if use_dark_ink():
                self.console.print(
                    "[#475569]claude_code => SDK + local `claude` transport; "
                    "independent => direct Anthropic API[/#475569]"
                )
            else:
                self.console.print(
                    "[#a3b1c6]claude_code => SDK + local `claude` transport; "
                    "independent => direct Anthropic API[/#a3b1c6]"
                )
            return
        if sub == "switch":
            if len(parts) < 3:
                self.console.print("[yellow]Use: /backend switch <claude_code|independent>[/yellow]")
                return
            target = parts[2].lower().strip()
            if target not in {"claude_code", "independent"}:
                self.console.print("[yellow]Backend must be claude_code or independent.[/yellow]")
                return
            if target == self.backend_mode:
                if use_dark_ink():
                    self.console.print(f"[#475569]Backend already set to {target}.[/#475569]")
                else:
                    self.console.print(f"[#a3b1c6]Backend already set to {target}.[/#a3b1c6]")
                return
            self.backend_mode = target
            self.config.backend_mode = target
            await self._connect()
            self.console.print(f"[green]Switched backend to {target}[/green]")
            return
        self.console.print("[yellow]Use: /backend status|switch <claude_code|independent>[/yellow]")

    async def _handle_subagent_command(self, parts: list[str]) -> None:
        if len(parts) < 2:
            self.console.print(
                "[yellow]Use: /subagent list|add <name> <description>|run <name> <task>[/yellow]"
            )
            return
        sub = parts[1].lower()
        if sub == "list":
            for name, agent in self.state.agents.items():
                self.console.print(f"- {name}: {agent.description}")
            return
        if sub == "add" and len(parts) >= 4:
            name = parts[2]
            desc = " ".join(parts[3:])
            self.state.agents[name] = AgentDefinition(description=desc, prompt=desc, model="sonnet")
            await self._connect()
            self._persist_state()
            self.console.print(f"[green]Added subagent profile '{name}'[/green]")
            return
        if sub == "run" and len(parts) >= 4:
            name = parts[2]
            task = " ".join(parts[3:])
            if name not in self.state.agents:
                self.console.print(f"[yellow]Unknown subagent profile: {name}[/yellow]")
                return
            orchestration_prompt = (
                f"Use the configured subagent '{name}' to complete this task, then summarize results:\n{task}"
            )
            await self._send_and_render(orchestration_prompt)
            return
        self.console.print("[yellow]Invalid subagent command.[/yellow]")

    async def _handle_mcp_command(self, parts: list[str]) -> None:
        if self.backend_mode != "claude_code":
            self.console.print("[yellow]MCP controls are only available in claude_code backend.[/yellow]")
            return
        assert self.client is not None
        if len(parts) < 2:
            self.console.print("[yellow]Use: /mcp status|reconnect <name>|toggle <name> <on|off>[/yellow]")
            return
        sub = parts[1].lower()
        if sub == "status":
            status = await self.client.get_mcp_status()
            servers = status.get("mcpServers", [])
            if not servers:
                self.console.print("[dim]No MCP servers configured.[/dim]")
                return
            for srv in servers:
                name = srv.get("name", "unknown")
                s = srv.get("status", "unknown")
                self.console.print(f"- {name}: {s}")
            return
        if sub == "reconnect" and len(parts) >= 3:
            await self.client.reconnect_mcp_server(parts[2])
            self.console.print(f"[green]Reconnected MCP server {parts[2]}[/green]")
            return
        if sub == "toggle" and len(parts) >= 4:
            enabled = parts[3].lower() in {"on", "true", "1", "enable", "enabled"}
            await self.client.toggle_mcp_server(parts[2], enabled=enabled)
            self.console.print(f"[green]Set MCP server {parts[2]} enabled={enabled}[/green]")
            return
        self.console.print("[yellow]Invalid MCP command.[/yellow]")

    async def _handle_vision_command(self, parts: list[str]) -> None:
        if len(parts) < 3:
            self.console.print("[yellow]Use: /vision <image_path> <question>[/yellow]")
            return
        if not self.config.enable_vision_support:
            self.console.print("[yellow]Vision support disabled in config.[/yellow]")
            return
        image_path = parts[1]
        question = " ".join(parts[2:])
        if self.backend_mode == "independent":
            text = await self._query_independent_vision(image_path=image_path, question=question)
            self.console.print(Panel(text, title="Vision (independent backend)", border_style="magenta"))
            return
        prompt = (
            "Analyze the image at this local path using available tooling, then answer:\n"
            f"Image path: {image_path}\n"
            f"Question: {question}"
        )
        await self._send_and_render(prompt)

    async def _handle_approve_command(self, parts: list[str]) -> None:
        if len(parts) < 2:
            self.console.print("[yellow]Use: /approve status|task|session|revoke[/yellow]")
            return
        sub = parts[1].lower()
        if sub == "status":
            self.console.print(
                f"full_access_project={self.config.full_access_project}, "
                f"session_full_access={self.state.session_full_access}, "
                f"next_task_full_access={self.state.next_task_full_access}, "
                f"effective_full_access={self._effective_full_access()}"
            )
            return
        if sub == "task":
            if not await self._require_signed_token("manual_task_grant"):
                return
            self.state.next_task_full_access = True
            await self._connect()
            self.console.print("[green]Granted full permission for next task.[/green]")
            return
        if sub == "session":
            if not await self._require_signed_token("manual_session_grant"):
                return
            self.state.session_full_access = True
            await self._connect()
            self.console.print("[green]Granted full permission for this session.[/green]")
            return
        if sub == "revoke":
            self.state.session_full_access = False
            self.state.next_task_full_access = False
            await self._connect()
            self.console.print("[green]Revoked temporary full permissions.[/green]")
            return
        self.console.print("[yellow]Invalid approve command.[/yellow]")

    async def _handle_approvals_command(self, parts: list[str]) -> None:
        n = 20
        if len(parts) >= 2:
            try:
                n = max(1, min(200, int(parts[1])))
            except ValueError:
                self.console.print("[yellow]Expected integer count, e.g. /approvals 30[/yellow]")
                return
        events = self.approval_audit.tail(n=n)
        if not events:
            self.console.print("[dim]No approval events logged yet.[/dim]")
            return
        self.console.print(f"[bold]Last {len(events)} approval events:[/bold]")
        for ev in events:
            self.console.print(
                f"- {ev.get('timestamp')} stage={ev.get('stage')} decision={ev.get('decision')} "
                f"mode={ev.get('mode')} session={ev.get('session_id')}"
            )

    def _show_annotation_help(self) -> None:
        self.console.print("[bold]Annotation reference syntax[/bold]")
        self.console.print("- @file:src/app/main.py")
        self.console.print("- @file:src/app/main.py#L10-80")
        self.console.print("- @dir:src/components/")
        self.console.print("- @glob:src/**/*.ts")
        self.console.print("- @glob:src/**/*.ts!**/*.test.ts")
        self.console.print("- @relative/path/to/file.py")
        self.console.print()
        self.console.print("[bold]Prompt patterns for file changes[/bold]")
        self.console.print(
            '- "Update @file:src/app/main.py#L20-70 to add retry logic and keep existing API."'
        )
        self.console.print(
            '- "Refactor @dir:src/auth/ to use typed errors and update imports."'
        )
        self.console.print(
            '- "Fix tests from @glob:tests/**/*.py and include a short summary of changed files."'
        )

    async def _handle_pick_command(self, parts: list[str]) -> None:
        if len(parts) < 2:
            self.console.print("[yellow]Use: /pick <query>[/yellow]")
            return
        from .annotations import suggest_annotation_candidates

        is_multi = any(p in {"--multi", "-m"} for p in parts[1:])
        is_block = any(p in {"--block", "-b"} for p in parts[1:])
        query = " ".join(p for p in parts[1:] if p not in {"--multi", "-m", "--block", "-b"}).strip()
        if not query:
            self.console.print(
                "[yellow]Use: /pick <query> | /pick --multi <query> | /pick --block <query>[/yellow]"
            )
            return
        options = suggest_annotation_candidates(query, self.cwd, limit=12)
        if not options:
            self.console.print("[yellow]No matching files/folders found.[/yellow]")
            return
        self.console.print("[bold]Pick an annotation target:[/bold]")
        for idx, opt in enumerate(options, start=1):
            prefix = "@dir:" if opt.endswith("/") else "@file:"
            self.console.print(f"{idx}. {prefix}{opt}")

        if is_multi:
            choice = await asyncio.to_thread(
                Prompt.ask,
                "Select numbers comma-separated (e.g. 1,3,4) or Enter to cancel",
                default="",
            )
            if not choice.strip():
                return
            idxs: list[int] = []
            try:
                for part in choice.split(","):
                    s = part.strip()
                    if not s:
                        continue
                    idx = int(s)
                    if idx < 1 or idx > len(options):
                        raise ValueError
                    if idx not in idxs:
                        idxs.append(idx)
            except ValueError:
                self.console.print("[yellow]Invalid selection list.[/yellow]")
                return
            if not idxs:
                return
            annotations: list[str] = []
            for idx in idxs:
                chosen = options[idx - 1]
                prefix = "@dir:" if chosen.endswith("/") else "@file:"
                annotations.append(f"{prefix}{chosen}")
            if is_block:
                self.console.print("[green]Copy-ready annotation block:[/green]")
                self.console.print("```text")
                for ann in annotations:
                    self.console.print(ann)
                self.console.print("```")
            else:
                self.console.print("[green]Use this merged annotation block:[/green]")
                for ann in annotations:
                    self.console.print(ann)
            return

        choice = await asyncio.to_thread(
            Prompt.ask,
            "Select number to emit annotation (or Enter to cancel)",
            default="",
        )
        if not choice.strip():
            return
        try:
            i = int(choice)
            if i < 1 or i > len(options):
                raise ValueError
        except ValueError:
            self.console.print("[yellow]Invalid selection.[/yellow]")
            return
        chosen = options[i - 1]
        prefix = "@dir:" if chosen.endswith("/") else "@file:"
        annotation = f"{prefix}{chosen}"
        if is_block:
            self.console.print("[green]Copy-ready annotation block:[/green]")
            self.console.print("```text")
            self.console.print(annotation)
            self.console.print("```")
        else:
            self.console.print(f"[green]Use this annotation:[/green] {annotation}")

    async def _handle_authcheck_command(self) -> None:
        self.console.print(f"[bold]Backend:[/bold] {self.backend_mode}")
        key = self.config.api_key or ""
        masked = f"...{key[-6:]}" if len(key) >= 6 else "(short key)"
        self.console.print(f"[bold]Configured API key fingerprint:[/bold] {masked}")

        if self.backend_mode == "independent":
            self.console.print(
                "[green]Independent backend uses direct Anthropic API from cagent config key.[/green]"
            )
            self.console.print(
                "[dim]Verification: run a small prompt, then confirm usage in the intended API account dashboard.[/dim]"
            )
            return

        # claude_code backend: probe + guidance
        if self.client is None:
            await self._connect()
        assert self.client is not None

        probe_prompt = (
            "Auth probe: reply with exactly 'AUTH_PROBE_OK'. "
            "No tool use. No extra words."
        )
        ok = False
        async with cartoon_loader(
            self.console,
            caption="Running auth probe with the cat…",
            accent_color="cyan",
        ):
            await self.client.query(probe_prompt)
            async for message in self.client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if hasattr(block, "text") and getattr(block, "text", "").strip() == "AUTH_PROBE_OK":
                            ok = True
                if isinstance(message, ResultMessage):
                    break

        if ok:
            self.console.print("[green]Auth probe succeeded.[/green]")
        else:
            self.console.print(
                "[yellow]Auth probe returned unexpected content, but backend is reachable.[/yellow]"
            )

        self.console.print(
            "[bold]Important:[/bold] claude_code backend runs through local `claude` transport. "
            "Final billing account depends on Claude Code auth precedence."
        )
        self.console.print(
            "[dim]Recommended verification:[/dim] send one tiny prompt here, then confirm usage appears on the intended account dashboard."
        )
