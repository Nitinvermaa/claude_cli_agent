# cagent setup guide

This guide covers installation, **Anthropic API key** configuration, and a first successful run.

## Requirements

- Python **3.11+**
- An [Anthropic API key](https://console.anthropic.com/) (starts with `sk-ant-`)
- Optional for `claude_code` backend: [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code/overview) (`claude` on your `PATH`)

## Install cagent

### Recommended: pipx

```bash
brew install pipx
pipx ensurepath
# Restart terminal, then:
pipx install /path/to/claude_cli_agent
pipx install /path/to/claude_cli_agent --force   # upgrade after pulling changes
cagent --version
```

### Editable install (development)

```bash
cd /path/to/claude_cli_agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cagent --version
```

## Anthropic API key

cagent reads your key from (first match wins):

1. `--api-key` on the CLI  
2. Environment variables  
3. Project **`.env`** in the directory passed as `--cwd`  
4. macOS **Keyring** (saved during `cagent config` or first-run onboarding)  
5. Interactive first-run prompt  

### Supported environment variable names

| Variable | Notes |
|----------|--------|
| `ANTHROPIC_API_KEY` | Standard Anthropic name (recommended) |
| `CLAUDE_API_KEY` | Alias |
| `CAGENT_ANTHROPIC_API_KEY` | cagent-specific alias |

### Option A: Project `.env` file (recommended for per-repo keys)

In the **project you analyze** (not necessarily the cagent source repo), create `.env`:

```bash
cd /path/to/your/project
cp /path/to/claude_cli_agent/.env.example .env
```

Edit `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
ANTHROPIC_MODEL=claude-sonnet-4-6
# or: CLAUDE_API_KEY=...
# or: CLAUDE_MODEL=claude-sonnet-4-6
```

Run cagent with that folder as the workspace:

```bash
cagent --cwd /path/to/your/project
```

**Do not commit `.env`** — it is listed in `.gitignore`.

### Option B: Shell export (all terminals in this session)

```bash
export ANTHROPIC_API_KEY='sk-ant-api03-your-key-here'
export ANTHROPIC_MODEL='claude-sonnet-4-6'
cagent
```

Persist in `~/.zshrc` or `~/.bashrc` if you want it every login.

### Option C: `cagent config` (saves to Keyring + config)

```bash
cagent config --api-key 'sk-ant-api03-your-key-here'
```

Optional backend preference:

```bash
cagent config --backend independent
# or
cagent config --backend claude_code
```

Config file: `~/.config/cagent/config.json`  
The API key is stored in the **system keyring** when possible (not in plaintext unless you opt in during onboarding).

### Option D: Inside the REPL

```text
/apikey set sk-ant-api03-your-key-here
/authcheck
```

## First run

```bash
cd /path/to/your/project
cagent --cwd .
```

On first run without a key, cagent runs **interactive onboarding** (model, graphify, permissions, etc.).

Useful checks:

```bash
cagent --version
cagent config
```

In the REPL:

```text
/approve status
/mode agent
/backend status
```

## Choose a backend

| Backend | Command | When to use |
|---------|---------|-------------|
| **independent** (default) | `cagent` or `cagent --backend independent` | Direct Anthropic API; host `read_file` / `write_file` tools |
| **claude_code** | `cagent --backend claude_code` | Full Claude Code tools (Write, Bash, MCP); needs `claude` CLI |

```bash
cagent config --backend independent
```

## File write permissions (`claude_code` backend)

After you approve full access (`full_access_project` or `/approve session`), cagent **0.2.28+**:

- Writes `.claude/settings.json` in your project **from the host** (not via Claude tools)
- Uses SDK `permission_mode=bypassPermissions` so Write/Edit/Bash work without per-file prompts

In VS Code, set Claude Code mode to **Bypass permissions** if prompts still appear.

```text
/approve session
/mode agent
```

## Optional environment variables

Add to `.env` or export in the shell:

```bash
# Claude Code max output tokens (default 32000; max often 64000)
export CLAUDE_CODE_MAX_OUTPUT_TOKENS=64000

# Independent backend tool loop (large repos)
export CAGENT_INDEPENDENT_MAX_TOOL_ROUNDS=256
export CAGENT_INDEPENDENT_MAX_TOKENS=64000

# Graphify timeouts (seconds)
export CAGENT_GRAPHIFY_QUERY_TIMEOUT=8
export CAGENT_GRAPHIFY_UPDATE_TIMEOUT=20
```

## Troubleshooting

| Problem | What to do |
|---------|------------|
| `cagent: command not found` | `pipx ensurepath`, new terminal, or `~/.local/bin/cagent` |
| Auth / 401 errors | Check key at [Anthropic Console](https://console.anthropic.com/); run `/authcheck` |
| Write denied | `/approve session`, `/mode agent`, confirm `.claude/settings.json` exists in project |
| Output token limit | `export CLAUDE_CODE_MAX_OUTPUT_TOKENS=64000`; write HTML with **Write** tool, not in chat |

See also [README.md](README.md) for commands, annotations (`@` + Tab), and REPL reference.
