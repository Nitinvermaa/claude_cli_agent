# cagent

`cagent` is a production-oriented coding agent CLI with policy gates, annotation-based context targeting, graphify integration, and project scaffolding.

## Runtime Options

`cagent` supports multiple backends:

- `independent` (**default**): direct Anthropic API with host file tools.
- `claude_code`: `claude-agent-sdk` + local `claude` CLI (Write, Bash, MCP).
- `copilot_sdk`: [GitHub Copilot SDK](https://github.com/github/copilot-sdk) (install `[copilot]` extra; `GITHUB_TOKEN` / PAT).
- `langchain_copilot`: LangChain + GitHub Copilot chat (install `[langchain-copilot]` extra).

**Default:** `independent` backend with **`ANTHROPIC_API_KEY`** — just run `cagent` after setting your key.  
Other backends: `cagent --backend copilot_sdk`, etc. See **[USAGE.md](USAGE.md)** (usage guide) and [SETUP.md](SETUP.md) (install).

## Core Capabilities

- First-run onboarding for API key + defaults
- Pluggable backends (`claude_code`, `independent`, `copilot_sdk`, `langchain_copilot`)
- Keyring-backed credential storage (with fallback)
- Modes: `agent`, `plan`, `ask`, `debug`
- Strict approval workflow (plan/implement/commit/push gates)
- Signed short-lived approval tokens
- Session + subagent handling
- File/folder annotations (`@file`, `@dir`, `@glob`)
- Interactive annotation picker (`\pick`, `\pick --multi`, `\pick --block`)
- App scaffolding by language/framework
- Graphify auto-update + query-first context
- Vision command and voice/vision scaffold stubs

## Installation (Any Terminal / IDE / CMD / PowerShell)

Use one of the two methods below.

### Option A (Recommended): `pipx` global app install

Best for running `cagent` from any terminal without activating a virtualenv.

#### 1) Install Python 3.11+

- macOS: `brew install python`
- Ubuntu/Debian: `sudo apt install python3 python3-pip`
- Windows: install Python from [python.org](https://www.python.org/downloads/) and enable "Add Python to PATH".

#### 2) Install pipx

- macOS:
  ```bash
  brew install pipx
  pipx ensurepath
  ```
- Linux:
  ```bash
  python3 -m pip install --user pipx
  python3 -m pipx ensurepath
  ```
- Windows (PowerShell):
  ```powershell
  py -m pip install --user pipx
  py -m pipx ensurepath
  ```

Restart terminal after `ensurepath`.

#### 3) Install cagent from local project path

```bash
pipx install "/Users/nitinverma/AI_Project/claude_cli_agent"
```

Windows example:

```powershell
pipx install "C:\path\to\claude_cli_agent"
```

#### 4) Verify

```bash
cagent --help
```

### Option B: user-level pip install

```bash
python3 -m pip install --user "/Users/nitinverma/AI_Project/claude_cli_agent"
```

Ensure user scripts folder is on `PATH`:

- macOS/Linux usually: `~/.local/bin`
- Windows usually: `%APPDATA%\Python\Python3x\Scripts`

Verify:

```bash
cagent --help
```

### Optional graphify support

For editable install:

```bash
pip install -e ".[graphify]"
```

For pipx:

```bash
pipx uninstall claude-cli-agent
pipx install --spec "/Users/nitinverma/AI_Project/claude_cli_agent[graphify]" claude-cli-agent
```

## Documentation

| Doc | Contents |
|-----|----------|
| **[USAGE.md](USAGE.md)** | **Usage guide** — default Anthropic backend, commands, backends, examples |
| [SETUP.md](SETUP.md) | Install, API keys, first run, troubleshooting |

## Setup (API key, install, first run)

See **[SETUP.md](SETUP.md)** for:

- Installing with **pipx** or `pip install -e .`
- Setting **`ANTHROPIC_API_KEY`** (`.env`, shell export, `cagent config`, or `/apikey`)
- Choosing a backend (**independent**, **claude_code**, **copilot_sdk**, **langchain_copilot**)
- Write permissions and optional env vars

## First Run

```bash
cagent
# or explicitly:
cagent --backend independent
cagent --backend claude_code
cagent --backend copilot_sdk          # pip install 'claude-cli-agent[copilot]'
cagent --backend langchain_copilot    # pip install 'claude-cli-agent[langchain-copilot]'
```

On first run, cagent asks for:

- Anthropic API key
- default model
- graphify preferences
- policy preferences
- annotation support preference

Saved config path:

- `~/.config/cagent/config.json`

Audit/session paths:

- `~/.config/cagent/approvals.jsonl`
- `~/.config/cagent/sessions.json`

### Terminal colors (white, gray, or blue-tint profiles)

cagent defaults to **`CAGENT_CLI_THEME=auto`**: it treats the terminal as “light” when `COLORFGBG` looks like a pale or cyan/blue-tint background (common in Terminal.app). Then all welcome text, tips, and footers use **dark ink** (no low-contrast `dim` gray).

If anything still looks washed out, force it explicitly (e.g. in `~/.zshrc`):

```bash
export CAGENT_CLI_THEME=light   # always dark-on-light styling
# or leave theme on auto and only force ink:
export CAGENT_USE_DARK_INK=1   # dark text even if background detection misses
# to force dark UI regardless of readability safeguards:
export CAGENT_FORCE_DARK_UI=1
```

## Usage

### Start agent

```bash
cagent
cagent --mode ask
cagent --backend claude_code
cagent --backend claude_code --mode agent
```

### New project / scaffold app

```bash
cagent new my-project --backend independent
cagent bootstrap --language python --name myapp
cagent bootstrap --language typescript --framework next --name webapp --vision --voice
```

### Refresh web framework catalog

```bash
cagent web-tech --update
```

### Graphify

```bash
cagent graphify update
cagent graphify query "How does auth flow to db?"
```

### Change backend preference

```bash
cagent config --backend claude_code
# or
cagent config --backend independent
```

### Textual UI

```bash
cagent tui
```

## Shortcuts (Claude Code–style)

At the `you:` prompt:

- Type **`?`** (or **`/shortcuts`**) for a three-column cheat sheet: `@` context, `/btw`, Tab completion on `/`, approvals, and links to docs.
- After startup, the footer reminds you: **`?` for shortcuts**.

## Claude Code CLI: sign in and API key

These steps are for **Anthropic’s Claude Code** tool (the `claude` CLI), not for cagent itself. cagent’s **`claude_code`** backend shells out to / talks to that ecosystem, so auth must work there too.

1. **Install Claude Code** using the current instructions in [Claude Code documentation](https://docs.anthropic.com/en/docs/claude-code/overview).
2. **Subscription / Console login (recommended for Claude Pro/Max):**
   - Run: `claude auth login` (or the login command shown in your installed version’s `--help`).
   - Complete the browser flow. Check status with `claude auth status` if available.
3. **API key instead of (or alongside) interactive login:**
   - Create a key in the [Anthropic Console](https://console.anthropic.com/) API keys section.
   - Export it in the shell **before** starting Claude Code or cagent, e.g.  
     `export ANTHROPIC_API_KEY='sk-ant-api03-...'`  
     Add that line to `~/.zshrc` / `~/.bashrc` if you want it persistent.
4. **Switching accounts:** there is no universal multi-profile switcher; use **`claude auth logout`** then **`claude auth login`**, or separate terminals / **`direnv`** projects with different `ANTHROPIC_API_KEY` values.

Official reference: [Claude Code overview](https://docs.anthropic.com/en/docs/claude-code/overview) and CLI help: `claude --help`.

## REPL Commands

- `/shortcuts` or `?` — shortcut overview
- `/help`
- `/quit`
- `/mode <agent|plan|ask|debug>`
- `/session list|new|switch <session-id>`
- `/chat list|new <name>|switch <name>` (named conversation aliases)
- `/bwt <name>` (quick alias for `/chat switch <name>`)
- `/backend status|switch <claude_code|independent|copilot_sdk|langchain_copilot>`
- `/subagent list|add <name> <description>|run <name> <task>`
- `/mcp status|toggle <name> <on|off>|reconnect <name>`
- `/context`
- `/vision <image_path> <question>`
- `/approve status|task|session|revoke`
- `/approvals [n]`
- `/annotations`
- `/pick <query>`
- `/pick --multi <query>`
- `/pick --block <query>`
- `/pick --multi --block <query>`
- `/authcheck` (backend/auth probe + verification guidance)
- `/apikey set <key>|show` (add/override runtime API key)
- `/theme show|set <prompt|accent> <color|#RRGGBB>`

Backend notes:
- `independent` backend uses the Anthropic Messages API with host-side `read_file`, `write_file`, and `delete_path` under `--cwd` (mutations disabled in **ask** mode; **plan/agent/debug** use tools when full access is on — **on by default** in config).
- `/mcp ...` commands are available in `claude_code` backend only.

## Approval Workflow

When enabled, risky requests go through:

1. Plan approval
2. Implementation approval (`deny|once|task|session`)
3. Commit approval (if commit intent detected)
4. Push approval (if push/deploy intent detected)

Each approved stage requires re-entering a signed short-lived token.

## Annotation Syntax

Type **`@`** in the prompt, then **Tab** for paths from the current working directory (Cursor-style). You can still use explicit prefixes.

- `@HawkEyeUI/` or `@dir:HawkEyeUI/` — folder
- `@README.md` or `@file:README.md` — file
- `@file:src/app/main.py#L10-80`
- `@dir:src/components/`
- `@glob:src/**/*.ts`
- `@glob:src/**/*.ts!**/*.test.ts`
- `@relative/path/to/file.py`

Example:

`Update @file:src/app/main.py#L20-70 to add retries and keep API unchanged.`

## Cost + Context Tips

1. Use `ask`/`plan` first; switch to `agent` only for execution.
2. Keep graph fresh with `graphify update .`.
3. Use annotation targeting to avoid broad context loading.
4. Reuse sessions for related tasks.
5. Use `/context` regularly to watch context pressure.

## Backend Requirements

- `claude_code` backend:
  - requires local Claude Code CLI (`claude`) on PATH
- `independent` backend:
  - direct Anthropic API (no local `claude` binary required); **read/write workspace files** via built-in tools under `--cwd` when policy allows writes

## Troubleshooting

- `cagent: command not found`
  - restart terminal
  - run `pipx ensurepath`
  - verify with `pipx list`

- Wrong backend in use
  - set explicitly:
    ```bash
    cagent config --backend independent
    ```
    or:
    ```bash
    cagent config --backend claude_code
    ```

- Independent backend: `400` + `tool_use` / `tool_result` (invalid request)
  - not an API key auth failure (those are usually **401**); upgrade to **0.2.23+**; if it persists, start a fresh chat (`/chat new …`) or a new session so the in-memory transcript is not stuck mid-tool.

- Independent backend: `Stopped after … tool rounds` / huge token counts
  - large “read everything” tasks hit the tool-step cap or context size; raise **`CAGENT_INDEPENDENT_MAX_TOOL_ROUNDS`** (e.g. `256`, max **512**) and optionally **`CAGENT_INDEPENDENT_MAX_TOKENS`** (e.g. `32768`, max **65536**), or narrow the analysis scope, or use **`--backend claude_code`** for big repo sweeps.

- Claude Code: “you haven't granted it yet” on Write after cagent approval
  - **`.claude/` is a protected path** — `acceptEdits` still blocks creating it via Claude tools. cagent **0.2.28+** writes `.claude/settings.json` **host-side** and uses SDK **`permission_mode=bypassPermissions`** when full access is on. Upgrade, restart `cagent`, run `/approve session`, `/mode agent`. You should see: `Claude Code permissions ready: .../settings.json`.
  - In VS Code, set mode to **Bypass permissions** (or enable “Allow dangerously skip permissions” in the Claude Code extension), not only “Edit automatically”.
  - One-time manual fix in the project (if needed before upgrade):
    ```bash
    mkdir -p .claude && cat > .claude/settings.json <<'EOF'
    { "permissions": { "defaultMode": "bypassPermissions", "allow": ["Read(**)", "Write(**)", "Edit(**)", "Bash(**)"] } }
    EOF
    ```

- Responses feel slow before the model answers
  - each prompt may run **`graphify query`** first (subprocess); set **`graphify_query_first": false`** in `~/.config/cagent/config.json` or re-run `cagent config` and disable “graphify query-first”, or cap wait with **`CAGENT_GRAPHIFY_QUERY_TIMEOUT=6`** in the shell / `.env`.
  - after file writes, **`graphify update`** can run up to **`CAGENT_GRAPHIFY_UPDATE_TIMEOUT`** seconds; set **`graphify_auto_update": false`** to skip post-write graph rebuilds during heavy sessions.
  - **approval workflow + signed tokens** add human time; relax those in config for local-only work.
  - **independent** + huge repo = many tool rounds and a very long transcript; narrow scope, or use **`--backend claude_code`**.

- Windows terminal notes
  - use `py` instead of `python3` where needed
  - once PATH is set, commands work in CMD/PowerShell/IDE terminal

- Welcome still shows `\help` or no boot animation
  - your shell is probably using an **old installed** `cagent`, not the repo you edited
  - run `which -a cagent` — another binary named `cagent` (for example under `/usr/local/bin`) can shadow this project
  - check: `cagent --version` or `cagent version` in the **shell** (not at the `you:` REPL prompt); expect `0.2.28` or newer after upgrading
  - refresh install: `pipx install -e /path/to/claude_cli_agent --force` or from the repo: `pip install -e .`
  - optional full-screen figlet boot: `CAGENT_ASCIIMATICS_BOOT=1 cagent`

- `cagent --version` printed Claude JSON or “docker agent” text
  - you typed it at the **`you:`** chat prompt (that sends text to the model). Quit or use a new shell line and run `cagent --version` **before** starting the REPL, or use `python -m claude_cli_agent --version`
  - if you see “docker agent”: a different `cagent` binary is earlier on `PATH`; fix `which -a cagent` order or rename that binary

- CLI colors on a light terminal look too bright
  - set `CAGENT_CLI_THEME=light` for Rich’s default palette, or use `/theme` inside the REPL
- quick presets in REPL: `/theme preset readable|dark|terminal-dark|light|auto` (session-only; add env vars in `~/.zshrc` to persist)
  - if `CAGENT_CLI_THEME=dark`, cagent now auto-applies terminal-dark behavior for that session (`CAGENT_FORCE_DARK_UI=1`, cyan prompt + magenta accent defaults)

## Legacy Scripts

Older scripts were moved into:

- `src/claude_cli_agent/legacy_scripts/`

Root wrappers are kept for backward compatibility.
