# Tool Calling & Schema Deep Dive

This document explains how tool calling works in the `my-cli-agent` CLI — from defining a Python function, to the schema that gets sent to the model, to the full ReAct loop that drives multi-step task completion.

---

## 1. What is Tool Calling?

Tool calling (also called **function calling**) is a structured protocol that allows an LLM to request the execution of a real function rather than just generating text. The model does **not** execute code itself — it outputs a structured description of a function it wants called, the host application executes it, then feeds the result back.

This is how the model goes from *"I know how to answer"* to *"I need to act"*.

---

## 2. The OpenAI Tool Schema Format

Both Ollama's OpenAI-compatible endpoint and the OpenAI API use the same **JSON Schema** format to describe tools. Every tool is declared as an object with this shape:

```json
{
  "type": "function",
  "function": {
    "name": "function_name",
    "description": "A plain-English description of what this function does.",
    "parameters": {
      "type": "object",
      "properties": {
        "param_name": {
          "type": "string",
          "description": "What this parameter is for."
        }
      },
      "required": ["param_name"]
    }
  }
}
```

The model reads this schema at inference time and uses it to decide *when* and *how* to invoke a tool. The `description` fields are the most important part — they're what the model uses to reason about which tool to pick.

---

## 3. How This Project Builds Schemas Automatically

Instead of writing the JSON schema by hand, `agent.py` generates it automatically from each Python function's **type annotations** and **docstring**. This keeps the schema always in sync with the implementation.

The process uses two helper functions:

### `_python_type_to_json_schema(annotation)`

Maps a Python type annotation to its JSON Schema equivalent:

```python
def _python_type_to_json_schema(annotation) -> dict:
    if annotation is inspect.Parameter.empty or annotation is str:
        return {"type": "string"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is bool:
        return {"type": "boolean"}
    return {"type": "string"}  # safe fallback
```

| Python Annotation | JSON Schema Type |
|---|---|
| `str` (or no annotation) | `"string"` |
| `int` | `"integer"` |
| `bool` | `"boolean"` |
| anything else | `"string"` (fallback) |

### `_build_openai_tool_schema(fn)`

This is the main schema builder. It uses Python's `inspect` module to read a function at runtime:

```python
def _build_openai_tool_schema(fn) -> dict:
    sig = inspect.signature(fn)      # reads the parameter list + annotations
    doc = inspect.getdoc(fn) or ""   # reads the cleaned docstring
    ...
```

**Step 1 — Parse the `Args:` section of the docstring** to extract per-parameter descriptions:

```
"""Reads the contents of a file.

Args:
    path: The absolute or relative path to the file to read.
"""
```

The parser walks line-by-line, flipping an `in_args` flag when it sees `"Args:"`, then splits each line on the first `:` to get `param_name → description`.

**Step 2 — Walk the function's parameters** via `sig.parameters` and build the `properties` dict. For each parameter:
- Call `_python_type_to_json_schema()` on its annotation for the JSON type
- Look up its description from the parsed docstring
- Add it to `required` if it has no default value (`inspect.Parameter.empty`)

**Step 3 — Return the complete schema dict** in the OpenAI format.

---

## 4. Concrete Schema Output for Each Tool

Here's what `_build_openai_tool_schema` produces for each function in `tools.py`:

### `read_file`
```python
def read_file(path: str) -> str:
    """Reads the contents of a file.
    Args:
        path: The absolute or relative path to the file to read.
    """
```
↓ generates:
```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "Reads the contents of a file.",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {
          "type": "string",
          "description": "The absolute or relative path to the file to read."
        }
      },
      "required": ["path"]
    }
  }
}
```

### `write_file`
```python
def write_file(path: str, content: str) -> str:
    """Writes content to a file, overwriting it if it exists.
    Args:
        path: The path to the file to write.
        content: The content to write into the file.
    """
```
↓ generates:
```json
{
  "type": "function",
  "function": {
    "name": "write_file",
    "description": "Writes content to a file, overwriting it if it exists.",
    "parameters": {
      "type": "object",
      "properties": {
        "path":    { "type": "string", "description": "The path to the file to write." },
        "content": { "type": "string", "description": "The content to write into the file." }
      },
      "required": ["path", "content"]
    }
  }
}
```

### `run_shell_command`
```python
def run_shell_command(command: str) -> str:
    """Runs a shell command and returns the output.
    Args:
        command: The shell command to execute.
    """
```
↓ generates:
```json
{
  "type": "function",
  "function": {
    "name": "run_shell_command",
    "description": "Runs a shell command and returns the output.",
    "parameters": {
      "type": "object",
      "properties": {
        "command": {
          "type": "string",
          "description": "The shell command to execute."
        }
      },
      "required": ["command"]
    }
  }
}
```

---

## 5. The Full ReAct Loop (Ollama)

**ReAct** = **Re**ason + **Act**. The model alternates between thinking about what to do and calling tools to do it. Here's the complete message flow for a single user request:

```
User: "What files are in the current directory?"
```

### Turn 1 — User → Model

The agent appends the user message and sends the full history + tool schemas to the model:

```json
messages: [
  { "role": "system",  "content": "You are a helpful CLI assistant..." },
  { "role": "user",    "content": "What files are in the current directory?" }
]
tools: [ ...all three tool schemas... ]
```

### Turn 1 — Model Response (tool call)

The model doesn't answer directly. Instead it responds with a `tool_calls` array:

```json
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "run_shell_command",
        "arguments": "{\"command\": \"ls -la\"}"
      }
    }
  ]
}
```

> [!NOTE]
> `arguments` is a **JSON string**, not an object. The agent parses it with `json.loads()` before passing it to the Python function.

### Tool Execution (host side)

The agent calls `_execute_tool("run_shell_command", {"command": "ls -la"})`, which calls the real Python function and captures the output string.

### Turn 2 — Tool Result → Model

The result is appended as a `"tool"` role message, keyed by `tool_call_id`:

```json
messages: [
  { "role": "system",    "content": "..." },
  { "role": "user",      "content": "What files are in the current directory?" },
  { "role": "assistant", "content": null, "tool_calls": [...] },
  {
    "role": "tool",
    "tool_call_id": "call_abc123",
    "content": "total 48\ndrwxr-xr-x  agent.py\ndrwxr-xr-x  main.py\n..."
  }
]
```

### Turn 2 — Model Response (final answer)

Now the model synthesizes the tool output into a natural language reply:

```
The current directory contains: agent.py, main.py, tools.py, requirements.txt, venv/
```

The loop exits because `message.tool_calls` is empty (or `None`).

---

## 6. Gemini vs Ollama — Schema Differences

The two providers handle schemas quite differently under the hood:

| | **Gemini** (`google-genai`) | **Ollama** (OpenAI-compatible) |
|---|---|---|
| Tool definition | Pass raw Python functions directly | Must pass JSON schema dicts |
| Schema generation | SDK introspects functions automatically | Done manually in `_build_openai_tool_schema` |
| Tool result format | `types.Part.from_function_response(...)` | `{"role": "tool", "tool_call_id": ..., "content": ...}` |
| History management | SDK manages internally (`chats.create`) | Managed manually in `self.history` |
| Arguments format | Dict object | JSON-encoded string (requires `json.loads`) |

For Gemini, the SDK's `chats.create(tools=[fn1, fn2, ...])` uses its own introspection pipeline, so no manual schema building is needed. For Ollama, we do it ourselves.

---

## 7. Adding a New Tool

To add a new tool to the agent, you only need to touch two files:

**1. Add the function to `tools.py`** with a proper Google-style docstring:

```python
def list_directory(path: str) -> str:
    """Lists all files and folders in a directory.

    Args:
        path: The directory path to list.
    """
    import os
    try:
        entries = os.listdir(path)
        return "\n".join(entries)
    except Exception as e:
        return f"Error listing directory: {e}"
```

**2. Register it in `agent.py`'s `TOOL_MAP`:**

```python
from tools import read_file, write_file, run_shell_command, list_directory

TOOL_MAP = {
    "read_file": read_file,
    "write_file": write_file,
    "run_shell_command": run_shell_command,
    "list_directory": list_directory,   # ← add here
}
```

The schema is generated automatically from the docstring. No JSON to write by hand.

> [!IMPORTANT]
> The `description` fields in your docstring are critical. The model uses them to decide which tool to call. Vague descriptions lead to wrong tool selection or missed tool calls entirely.
