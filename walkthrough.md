# AI CLI Agent — Walkthrough

A terminal-based AI agent with a ReAct loop, supporting both Google Gemini and locally-hosted models via Ollama. Includes a skills system for pre-defined, deterministic workflows.

## Project Structure

| File | Purpose |
|---|---|
| `main.py` | Interactive REPL entry point (`prompt-toolkit` + `rich`) |
| `agent.py` | `Agent` class — provider selection, ReAct loop, tool/skill dispatch |
| `tools.py` | Low-level tool implementations (file I/O, shell execution) |
| `skills.py` | Skill registry and built-in skills (higher-level workflows) |
| `requirements.txt` | Python dependencies |

## Documentation

| File | What it covers |
|---|---|
| `docs/tool_calling_deep_dive.md` | How tool schemas are built, the ReAct loop internals, Gemini vs Ollama differences |
| `docs/skills_deep_dive.md` | The skills registry pattern, both invocation paths, built-in skills reference, design guide |

---

## Tools

Low-level, single-action functions the model can call:

| Tool | Description |
|---|---|
| `read_file(path)` | Reads a file from the filesystem |
| `write_file(path, content)` | Writes/overwrites a file |
| `run_shell_command(command)` | Executes a shell command and returns stdout/stderr |

## Skills

Pre-defined, deterministic multi-step workflows. Skills are faster and more reliable than raw tool calls for known tasks because no LLM reasoning is needed during execution.

| Skill | Parameters | Description |
|---|---|---|
| `summarize_project` | none | Finds all `.py` files and shows line counts + previews |
| `git_status_report` | none | Formats recent commits, working tree status, and diff stats |
| `scaffold_python_module` | `module_name`, `description` | Creates a new `.py` file with standard boilerplate |
| `show_recent_files` | `n` (default: 10) | Lists N most recently modified files |

Both tools and skills are exposed to the model as tool schemas. The model chooses between them. Skills can also be invoked directly from the REPL (see below).

---

## Supported Providers

### Google Gemini
Uses the `google-genai` SDK. Requires a `GEMINI_API_KEY` in your environment or `.env` file.

### Ollama (local)
Uses the `openai` SDK pointed at Ollama's OpenAI-compatible endpoint (`http://localhost:11434/v1`). No API key required.

| Model | Size | Tool-calling support |
|---|---|---|
| `gemma4:latest` | 9.6 GB | Good (fits in 20 GB M4 Mac Mini) |
| `qwen2.5-coder:14b` | 9.0 GB | Excellent (recommended for reliability) |

---

## REPL Commands

In addition to natural language, the REPL supports slash commands:

| Command | Description |
|---|---|
| `/skills` | List all registered skills with descriptions and parameters |
| `/skill <name>` | Run a skill directly — bypasses the LLM entirely |
| `/help` | Show available REPL commands |
| `exit` / `quit` | Close the agent |

---

## How to Run

**Setup (one-time):**
```bash
git clone https://github.com/ymekonn1/my-cli-agent.git
cd my-cli-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# For Gemini only — create a .env with your key
echo "GEMINI_API_KEY=your_key_here" > .env
```

**Run with Gemini:**
```bash
source venv/bin/activate
python main.py --provider gemini
```

**Run with a local Ollama model:**
```bash
ollama pull gemma4       # one-time pull
python main.py --provider ollama --model gemma4:latest
```

**Run a skill directly without the LLM:**
```bash
# Inside the REPL:
/skills                        # see all available skills
/skill summarize_project       # runs immediately, zero tokens used
/skill git_status_report       # formats a git report instantly
```

> [!TIP]
> `qwen2.5-coder:14b` has excellent, well-tested tool-calling support and is the most reliable choice if `gemma4` doesn't invoke tools as expected.

> [!NOTE]
> `gemma4:latest` (9.6 GB) fits comfortably within the 20 GB unified memory on an M4 Mac Mini, leaving ~7–8 GB headroom for the OS.
