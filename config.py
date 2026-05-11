"""
config.py — Centralized configuration and constants for my-cli-agent.

Import from here instead of hardcoding values in agent.py or main.py.
"""

# ── Model Providers ──────────────────────────────────────────────────────────

OLLAMA_BASE_URL = "http://localhost:11434/v1"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OLLAMA_MODEL = "gemma4:latest"

# ── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_INSTRUCTION = (
    "You are a helpful CLI assistant operating inside a terminal. "
    "You have access to low-level tools (read_file, write_file, run_shell_command) "
    "and higher-level skills (pre-defined workflows for common tasks). "
    "Prefer skills when the user's request matches a known workflow. "
    "Use tools for everything else."
)
