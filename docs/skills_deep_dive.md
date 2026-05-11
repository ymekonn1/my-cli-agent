# Skills Deep Dive

This document covers everything about the skills system in `my-cli-agent`: what a skill is, how the registry works, how skills are exposed to the LLM, both invocation paths, and how to write your own.

For the lower-level tool calling mechanism that skills build on top of, see [tool_calling_deep_dive.md](./tool_calling_deep_dive.md).

---

## 1. What is a Skill?

A **skill** is a named, pre-programmed workflow — a Python function that chains together one or more tool calls (or any other logic) to accomplish a specific, well-known task reliably and deterministically.

The key distinction from raw tool calls:

| | Raw Tool Call | Skill |
|---|---|---|
| **Sequence decided by** | The LLM at runtime | The programmer at write-time |
| **Steps** | One atomic action | Multiple actions chained together |
| **Reliability** | Depends on model reasoning | Fully deterministic |
| **Flexibility** | Handles arbitrary tasks | Fixed to one well-defined workflow |
| **Cost** | Multiple LLM turns | Zero LLM involvement in execution |
| **Debuggability** | Hard — depends on model | Easy — it's just Python code |

A skill is the right choice when you find yourself prompting the model to do the same multi-step sequence repeatedly. Instead of hoping the model picks the right tools in the right order every time, you encode that sequence once as a skill.

---

## 2. The Registry Pattern

Skills use a simple **global registry** backed by a dictionary:

```python
# skills/__init__.py

_SKILL_REGISTRY: dict[str, callable] = {}

def skill(fn):
    """Decorator that registers a function as a named skill."""
    _SKILL_REGISTRY[fn.__name__] = fn
    return fn

def get_skill_registry() -> dict[str, callable]:
    return _SKILL_REGISTRY

# Import builtins last to trigger @skill registration
from skills import builtins
```

The `@skill` decorator is applied at **module import time**. The moment Python imports the `skills` package, the import statement at the bottom of `__init__.py` automatically triggers the evaluation of `builtins.py`. Every decorated function is then registered into `_SKILL_REGISTRY` using its function name as the key.

```python
# skills/builtins.py
@skill
def git_status_report() -> str:
    ...
# At this point, _SKILL_REGISTRY["git_status_report"] = <function git_status_report>
```

The registry is accessed via `get_skill_registry()` rather than directly, which keeps the internals encapsulated. Any module in the project can call this to see all currently registered skills.

### Why a dictionary keyed by function name?

When the LLM requests a tool call, it sends back the **function name as a string** (e.g., `"git_status_report"`). The registry is a fast O(1) lookup from that string to the callable. The same name is used both as the schema identifier sent to the model and as the registry key, keeping them in perfect sync.

---

## 3. How a Skill is Defined

A skill is just an ordinary Python function with two requirements:

1. **The `@skill` decorator** — registers it automatically
2. **A Google-style docstring** — used to build the tool schema sent to the LLM

```python
@skill
def scaffold_python_module(module_name: str, description: str) -> str:
    """Creates a new Python module file with standard boilerplate.
                                   ↑
                       First line → used as the LLM-facing description

    Args:
        module_name: The filename for the new module, e.g. 'utils.py'.
                                               ↑
                                Used as the parameter description in the schema
        description: A one-line description of what the module does.
    """
    content = f'"""\n{description}\n"""\n\n\ndef main():\n    pass\n\n\nif __name__ == "__main__":\n    main()\n'
    return write_file(module_name, content)
```

Inside the function body, you can call any tool from `tools.py`, run Python logic, or call other skills.

### Optional parameters

Parameters with defaults become **optional** in the schema — the `required` list excludes them. Parameters without defaults are **required**:

```python
@skill
def show_recent_files(n: str = "10") -> str:  # n is optional
    ...
```

---

## 4. How Skills are Exposed to the LLM

At agent startup, skills are pulled from the registry and converted to tool schemas using the **exact same `_build_openai_tool_schema` function** used for raw tools (see the tool calling deep dive). The model sees skills and tools as identical in structure — it has no idea which is a "skill" and which is a "tool".

```python
# agent.py — inside Agent.__init__() for Ollama

all_callables = list(TOOL_MAP.values()) + list(get_skill_registry().values())
self.openai_tools = [_build_openai_tool_schema(fn) for fn in all_callables]
```

The full list of schemas sent to the model for this project looks like:

```
Tools:
  read_file           ← raw tool
  write_file          ← raw tool
  run_shell_command   ← raw tool
  summarize_project   ← skill
  git_status_report   ← skill
  scaffold_python_module ← skill
  show_recent_files   ← skill
```

From the model's perspective, it picks from this unified list based on which option best matches the user's request.

---

## 5. The Two Invocation Paths

Skills can reach `_execute_tool` via two completely different paths:

### Path A: LLM-Driven (via ReAct loop)

This is the normal path. The user asks something in natural language, the model reasons about it, and chooses to invoke a skill by name as part of the ReAct loop.

```
User: "Show me a summary of this project."
  ↓
LLM reasons → chooses "summarize_project" tool call
  ↓
_execute_tool("summarize_project", {}) is called
  ↓
Skill runs deterministically (no further LLM involvement)
  ↓
Result fed back to LLM → LLM formats final response
```

The model chose the skill, but the skill itself ran without any LLM reasoning.

### Path B: Direct REPL Invocation (`/skill <name>`)

The user explicitly invokes a skill by name from the command line, bypassing the LLM entirely:

```
User types: /skill summarize_project
  ↓
main.py intercepts the "/" prefix
  ↓
Looks up "summarize_project" directly in get_skill_registry()
  ↓
Calls skill function directly
  ↓
Output printed to terminal (no LLM, no ReAct loop)
```

This path is faster, cheaper (zero token cost), and more predictable — useful when you know exactly which workflow you want.

---

## 6. Execution Priority in `_execute_tool`

When the agent receives any function call from the model (whether it's a skill or a raw tool), it goes through `_execute_tool`. Skills are checked **first**, before the raw tool map:

```python
def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
    args_str = ", ".join(f"{k}={v!r}" for k, v in tool_args.items())
    skill_registry = get_skill_registry()

    # 1. Check skills first (shown in magenta with ⚡)
    if tool_name in skill_registry:
        console.print(f"[bold magenta]  ⚡ skill: {tool_name}({args_str})[/bold magenta]")
        try:
            return skill_registry[tool_name](**tool_args)
        except Exception as e:
            return f"Error executing skill '{tool_name}': {e}"

    # 2. Fall back to raw tools (shown in dim cyan with →)
    console.print(f"[dim cyan]  → {tool_name}({args_str})[/dim cyan]")
    if tool_name in TOOL_MAP:
        try:
            return TOOL_MAP[tool_name](**tool_args)
        except Exception as e:
            return f"Error executing {tool_name}: {e}"

    return f"Error: Unknown tool or skill '{tool_name}'"
```

You can tell skills and tool calls apart visually in the terminal:
- **`⚡ skill: summarize_project()`** — magenta, bold → a skill ran
- **`→ run_shell_command(...)`** — dim cyan → a raw tool ran

---

## 7. Built-in Skills Reference

### `summarize_project()`
**No parameters.**

Finds all `.py` files in the current directory (excluding `venv/`), reads each one, and returns a formatted summary with line counts and 8-line previews.

Internally chains: `run_shell_command` → `read_file` × N

---

### `git_status_report()`
**No parameters.**

Runs three git commands and formats the output as a structured markdown report:
- `git log --oneline -10`
- `git status --short`
- `git diff --stat`

Internally chains: `run_shell_command` × 3

---

### `scaffold_python_module(module_name, description)`
**Parameters:**
- `module_name` *(required)* — e.g. `"utils.py"`
- `description` *(required)* — one-line module description

Creates a new `.py` file with a module docstring, a `main()` function, and the `if __name__ == "__main__"` guard.

Internally uses: `write_file`

---

### `show_recent_files(n="10")`
**Parameters:**
- `n` *(optional, default `"10"`)* — number of files to show

Lists the N most recently modified files, excluding `venv/` and `.git/`.

Internally uses: `run_shell_command`

---

## 8. Adding Your Own Skill

You only need to edit `skills.py`. No changes to `agent.py` or `main.py` are required — the registry and schema generation are fully automatic.

**Template:**

```python
@skill
def my_skill_name(param_one: str, param_two: str = "default") -> str:
    """One-line description shown to the LLM when it picks this skill.

    A longer explanation of what this skill does (optional, not sent to model).

    Args:
        param_one: Description of this required parameter.
        param_two: Description of this optional parameter.
    """
    # Use any combination of tools or plain Python
    data = read_file(param_one)
    result = run_shell_command(f"wc -l {param_one}")
    return f"File has {result.strip()} lines.\n\nContent:\n{data}"
```

After saving, the skill is immediately:
- Available to the LLM as a callable tool schema
- Listed in `/skills`
- Invokable via `/skill my_skill_name`

---

## 9. Design Principles for Good Skills

### ✅ Do: Encode well-known, multi-step workflows
If you find yourself prompting the agent with the same multi-step request repeatedly, it's a good skill candidate.

### ✅ Do: Write clear, specific docstrings
The first line of the docstring is the description the LLM sees. It must be specific enough that the model knows exactly when to choose this skill over others.

```python
# Bad — too vague, model won't know when to use it
"""Does some stuff with files."""

# Good — model knows exactly what this is for
"""Scans the current project directory and produces a summary of all Python source files."""
```

### ✅ Do: Return formatted markdown
Both invocation paths (`/skill` and LLM-driven) render the output with `rich.Markdown`. Structure your output with headings, code blocks, and lists.

### ❌ Don't: Put open-ended reasoning inside a skill
A skill should know exactly what to do upfront. If the steps depend on the content of a file you haven't read yet, that's what the ReAct loop is for — use a raw tool call instead.

### ❌ Don't: Make skills too granular
A skill wrapping a single `run_shell_command` call adds no value over a raw tool call. Skills shine when they **compose** multiple operations.

---

## 10. Skills vs Tool Calls — Decision Guide

```
"Do I need a skill or a raw tool call?"

Is the sequence of steps always the same for this task?
├── YES → Skill
│         (encode the workflow, get reliability + zero token cost)
└── NO → Tool Call
          (let the LLM reason about which steps to take)

Do I know all the data I need upfront (from parameters)?
├── YES → Skill
└── NO → Tool Call
          (the LLM needs to inspect intermediate results to decide next steps)

Will this exact workflow be triggered many times?
├── YES → Skill (amortize the prompting overhead)
└── MAYBE → Tool Call (don't over-engineer)
```
