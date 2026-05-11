# my-cli-agent — AI CLI Agent

A terminal-based AI agent with a ReAct loop that can read/write files, execute shell commands, and run pre-defined skill workflows. Supports both Google Gemini and locally-hosted models via Ollama.

## Features

- 🤖 **Multi-provider** — switch between Google Gemini and any Ollama model with a flag
- 🔧 **Tool calling** — reads files, writes files, runs shell commands via a ReAct loop
- ⚡ **Skills** — pre-defined, deterministic workflows for common tasks (zero token cost)
- 📟 **REPL commands** — `/skills`, `/skill <name>`, `/help` for direct skill invocation
- 📝 **Rich output** — Markdown rendering and syntax highlighting in the terminal

## Quick Start

```bash
# 1. Set up the environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Add your Gemini API key (skip for Ollama)
cp .env.example .env
# edit .env and fill in GEMINI_API_KEY

# 3. Run
python main.py                                              # Gemini (default: gemini-2.5-flash)
python main.py --provider ollama                            # local Ollama (default: gemma4:latest)
python main.py --provider ollama --model qwen2.5-coder:14b  # override model
```

## Project Structure

```
my-cli-agent/
├── main.py          # REPL entry point
├── agent.py         # ReAct loop and provider abstraction
├── tools.py         # Low-level tools (file I/O, shell)
├── config.py        # Centralized constants and model defaults
├── skills/
│   ├── __init__.py  # Registry and @skill decorator
│   └── builtins.py  # Built-in skill definitions
└── docs/
    ├── tool_calling_deep_dive.md
    └── skills_deep_dive.md
```

## Built-in Skills

| Skill | Description |
|---|---|
| `summarize_project` | Scans all Python files and shows line counts + previews |
| `git_status_report` | Formats recent commits, status, and diff stats |
| `scaffold_python_module` | Creates a new `.py` file with standard boilerplate |
| `show_recent_files` | Lists N most recently modified files |

Run `/skills` inside the REPL to see all available skills.

## Adding a Custom Skill

Add a function to `skills/builtins.py` (or a new file in `skills/`):

```python
@skill
def my_workflow(target: str) -> str:
    """One-line description the LLM uses to decide when to call this skill.

    Args:
        target: Description of this parameter.
    """
    result = run_shell_command(f"wc -l {target}")
    return f"Line count: {result}"
```

No other changes needed — it auto-registers and appears in `/skills`.

## Documentation

- [Walkthrough](./walkthrough.md) — setup, commands, and provider reference
- [Tool Calling Deep Dive](./docs/tool_calling_deep_dive.md) — schema generation, ReAct loop internals
- [Skills Deep Dive](./docs/skills_deep_dive.md) — registry pattern, invocation paths, design guide
