# cagent usage guide

This guide is the day-to-day reference for running cagent. For install and first-time API key setup, see [SETUP.md](SETUP.md).

## Default behavior (Anthropic API)

**Unless you pass `--backend` or change config, cagent uses:**

| Setting | Default |
|---------|---------|
| Backend | `independent` |
| Credential | **`ANTHROPIC_API_KEY`** (or `CLAUDE_API_KEY`, `CAGENT_ANTHROPIC_API_KEY`) |
| Model | `claude-sonnet-4-6` (override with `ANTHROPIC_MODEL`, `CAGENT_MODEL`, etc.) |

You do **not** need GitHub Copilot or the Copilot SDK for the default path—only an Anthropic API key.

### Quick start (default backend)

```bash
cd /path/to/your/project
export ANTHROPIC_API_KEY='sk-ant-api03-...'
# optional:
export ANTHROPIC_MODEL='claude-sonnet-4-6'

cagent --cwd .
```

Or put keys in the project `.env` (see [SETUP.md](SETUP.md)):

```env
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
ANTHROPIC_MODEL=claude-sonnet-4-6
```

```bash
cagent --cwd /path/to/your/project
```

Inside the REPL:

```text
/backend status          # should show: independent
/authcheck               # verifies Anthropic key path
/mode agent
you: List the main entry points in this repo
```

---

## Backends at a glance

| Backend | Auth | Install | Best for |
|---------|------|---------|----------|
| **`independent`** (default) | `ANTHROPIC_API_KEY` | Core package | Direct API, host file tools, no `claude` binary required |
| `claude_code` | Anthropic + local `claude` CLI | Core + Claude Code | Write, Bash, MCP, full Claude Code toolset |
| `copilot_sdk` | `GITHUB_TOKEN` / PAT | `pip install 'claude-cli-agent[copilot]'` | Official Copilot agent runtime |
| `langchain_copilot` | `GITHUB_TOKEN` / PAT | `pip install 'claude-cli-agent[langchain-copilot]'` | LangChain + Copilot models + host file tools |

### Switch backend for one run

```bash
cagent --backend independent          # default (Anthropic)
cagent --backend claude_code
cagent --backend copilot_sdk
cagent --backend langchain_copilot
```

### Set default backend in config

```bash
cagent config --backend independent   # recommended default (Anthropic)
cagent config --backend claude_code
cagent config --backend copilot_sdk
```

In the REPL:

```text
/backend status
/backend switch independent
/backend switch copilot_sdk
```

---

## Credentials by backend

### Anthropic (default: `independent` and `claude_code`)

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Primary API key (recommended) |
| `CLAUDE_API_KEY` | Alias |
| `CAGENT_ANTHROPIC_API_KEY` | cagent alias |
| `ANTHROPIC_MODEL` / `CAGENT_MODEL` / `CLAUDE_MODEL` | Model id |

```bash
cagent config --api-key 'sk-ant-...'
```

REPL:

```text
/apikey anthropic show
/apikey anthropic set sk-ant-...
/apikey set sk-ant-...              # same as anthropic set
```

### GitHub Copilot (`copilot_sdk`, `langchain_copilot`)

| Variable | Purpose |
|----------|---------|
| `GITHUB_TOKEN` | GitHub PAT with Copilot access (recommended) |
| `GH_TOKEN` | Alias |
| `COPILOT_GITHUB_TOKEN` | Alias |
| `CAGENT_COPILOT_MODEL` | Model for Copilot backends (e.g. `gpt-4.1`) |

```bash
export GITHUB_TOKEN='ghp_...'
pipx install '/path/to/claude-cli-agent[copilot]' --force
cagent --backend copilot_sdk --cwd .
```

REPL:

```text
/apikey github set ghp_...
/apikey github show
/authcheck
```

---

## CLI commands

| Command | Description |
|---------|-------------|
| `cagent` | Start REPL in current directory (default backend + Anthropic key) |
| `cagent --cwd <dir>` | Use `<dir>` as workspace; load `<dir>/.env` |
| `cagent --backend <id>` | Override backend for this run |
| `cagent --api-key <key>` | Override Anthropic key for this run |
| `cagent --mode agent\|plan\|ask\|debug` | Runtime mode |
| `cagent --version` | Package version |
| `cagent config` | Onboarding / update config |
| `cagent config --api-key … --backend independent` | Save preferences |
| `cagent usage report` | Usage table + HTML dashboard |
| `cagent graphify update` | Refresh graphify graph for project |

---

## REPL essentials

| Command | Description |
|---------|-------------|
| `?` or `/shortcuts` | Shortcut help |
| `/help` | All host commands |
| `/backend status` | Active backend |
| `/backend switch <id>` | Change backend (reconnects) |
| `/mode agent` | Enable writes (with full access) |
| `/approve session` | Full access for session |
| `/authcheck` | Test credentials for current backend |
| `/apikey anthropic show\|set` | Anthropic key |
| `/apikey github show\|set` | GitHub PAT (Copilot backends) |
| `/context` | Context / token usage summary |
| `/btw <question>` | Side-channel Anthropic answer (no main transcript) |
| `/vision <path> <question>` | Image Q&A (`independent` backend) |
| `/quit` | Exit |

### Annotations (Cursor-style)

Type `@` then **Tab** to complete paths from the workspace:

```text
you: Summarize @src/claude_cli_agent/session.py
you: What lives under @backends/?
```

See `/annotations` and `/pick <query>` for more patterns.

---

## Modes

| Mode | Writes | Typical use |
|------|--------|-------------|
| `agent` | Yes (if full access) | Default coding agent |
| `plan` | Policy-dependent | Planning before edits |
| `ask` | No (read-only tools on `independent`) | Questions only |
| `debug` | Yes (if full access) | Debugging |

```text
/mode ask
/mode agent
```

---

## Examples

### 1. Default: analyze a repo with Anthropic

```bash
export ANTHROPIC_API_KEY='sk-ant-...'
cd ~/my-app
cagent --cwd .
```

```text
you: Find how authentication is implemented and list the main files.
```

### 2. Claude Code tools (Bash, Write, MCP)

```bash
export ANTHROPIC_API_KEY='sk-ant-...'
# Ensure `claude` CLI is installed and authenticated
cagent --backend claude_code --cwd ~/my-app
```

```text
/approve session
/mode agent
you: Add a unit test for the login module and run it.
```

### 3. GitHub Copilot SDK (optional)

```bash
export GITHUB_TOKEN='ghp_...'
cagent --backend copilot_sdk --cwd ~/my-app
```

### 4. Persist defaults

```bash
cagent config --api-key 'sk-ant-...' --backend independent
```

Config file: `~/.config/cagent/config.json`  
Anthropic key: macOS Keyring (`cagent` / `default`) when available.

---

## Optional environment variables

```bash
# Independent / default backend tool loop (large repos)
export CAGENT_INDEPENDENT_MAX_TOOL_ROUNDS=256
export CAGENT_INDEPENDENT_MAX_TOKENS=64000

# Claude Code backend output limit
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=64000

# Graphify subprocess timeouts (seconds)
export CAGENT_GRAPHIFY_QUERY_TIMEOUT=8
export CAGENT_GRAPHIFY_UPDATE_TIMEOUT=20
```

---

## Troubleshooting

| Problem | What to do |
|---------|------------|
| Wrong backend active | `/backend status`; use `cagent config --backend independent` |
| 401 / auth errors on default path | Set `ANTHROPIC_API_KEY`; `/apikey anthropic show`; `/authcheck` |
| Copilot backend fails | Install `[copilot]` extra; set `GITHUB_TOKEN`; `copilot --version` |
| Write denied (`claude_code`) | `/approve session`, `/mode agent`; see [SETUP.md](SETUP.md) |
| `Stopped after N tool rounds` | Raise `CAGENT_INDEPENDENT_MAX_TOOL_ROUNDS` or narrow scope |

---

## Related docs

- [SETUP.md](SETUP.md) — install, API keys, first run  
- [README.md](README.md) — features, scaffolding, graphify  
- [.env.example](.env.example) — copy-paste env template  
