"""
skills/builtins.py — Built-in skills shipped with my-cli-agent.

Add new skills here using the @skill decorator. They are automatically
registered and exposed to the LLM when the skills package is imported.
"""

from skills import skill
from tools import read_file, write_file, run_shell_command


@skill
def summarize_project() -> str:
    """Scans the current project directory and produces a summary of all Python source files.

    Finds every .py file (excluding venv), shows its line count and a short
    preview of its contents.
    """
    result = run_shell_command(
        "find . -name '*.py' -not -path './venv/*' -not -name '__pycache__' | sort"
    )
    files = [f.strip() for f in result.splitlines() if f.strip()]
    if not files:
        return "No Python files found in the current directory."

    parts = [f"**Project summary — {len(files)} Python file(s) found:**\n"]
    for filepath in files:
        content = read_file(filepath)
        lines = content.splitlines()
        preview_lines = [l for l in lines if l.strip()][:8]
        preview = "\n".join(preview_lines)
        parts.append(
            f"### `{filepath}` ({len(lines)} lines)\n```python\n{preview}\n```"
        )
    return "\n\n".join(parts)


@skill
def git_status_report() -> str:
    """Generates a formatted git report: the 10 most recent commits, working tree status, and diff stats."""
    log = run_shell_command("git log --oneline -10 2>&1")
    status = run_shell_command("git status --short 2>&1")
    diff_stat = run_shell_command("git diff --stat 2>&1")

    return (
        "## Recent Commits\n"
        f"```\n{log.strip() or 'No commits yet.'}\n```\n\n"
        "## Working Tree Status\n"
        f"```\n{status.strip() or 'Clean — nothing to commit.'}\n```\n\n"
        "## Diff Stats\n"
        f"```\n{diff_stat.strip() or 'No unstaged changes.'}\n```"
    )


@skill
def scaffold_python_module(module_name: str, description: str) -> str:
    """Creates a new Python module file with standard boilerplate (module docstring and a main function).

    Args:
        module_name: The filename for the new module, e.g. 'utils.py'.
        description: A one-line description of what the module does.
    """
    content = (
        f'"""\n{description}\n"""\n\n\n'
        'def main():\n    pass\n\n\n'
        'if __name__ == "__main__":\n    main()\n'
    )
    return write_file(module_name, content)


@skill
def show_recent_files(n: str = "10") -> str:
    """Lists the N most recently modified files in the current directory (excluding venv and .git).

    Args:
        n: How many files to show (default: 10).
    """
    result = run_shell_command(
        f"find . -not -path './venv/*' -not -path './.git/*' -type f | "
        f"xargs ls -t 2>/dev/null | head -{n}"
    )
    return result.strip() or "No files found."
