# cagent

`cagent` is a production-oriented coding agent CLI with policy gates, annotation-based context targeting, graphify integration, and project scaffolding.

## Runtime Options

`cagent` supports two backend modes so users can choose:

- `claude_code`: uses `claude-agent-sdk` transport with local `claude` CLI.
- `independent`: uses direct Anthropic API (no `claude` binary required for chat/vision workflow).

Select backend at run time using `--backend`, or set it via `cagent config --backend ...`.

## Core Capabilities

- First-run onboarding for API key + defaults
- Dual backend runtime (`claude_code` or `independent`)
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

## First Run

```bash
cagent --backend claude_code
# or
cagent --backend independent
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
cagent --backend claude_code --mode ask
cagent --backend claude_code --mode agent
cagent --backend independent --mode ask
cagent --backend independent --mode agent
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
- `/backend status|switch <claude_code|independent>`
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
- `/mcp ...` commands are available in `claude_code` backend.
- `independent` backend still supports policy gates, annotations, scaffolding, graphify, and vision flow.

## Approval Workflow

When enabled, risky requests go through:

1. Plan approval
2. Implementation approval (`deny|once|task|session`)
3. Commit approval (if commit intent detected)
4. Push approval (if push/deploy intent detected)

Each approved stage requires re-entering a signed short-lived token.

## Annotation Syntax

- `@file:src/app/main.py`
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
  - no local `claude` binary required for chat/vision flow

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

- Windows terminal notes
  - use `py` instead of `python3` where needed
  - once PATH is set, commands work in CMD/PowerShell/IDE terminal

- Welcome still shows `\help` or no boot animation
  - your shell is probably using an **old installed** `cagent`, not the repo you edited
  - run `which -a cagent` — another binary named `cagent` (for example under `/usr/local/bin`) can shadow this project
  - check: `cagent --version` or `cagent version` in the **shell** (not at the `you:` REPL prompt); expect `0.2.16` or newer after upgrading
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
