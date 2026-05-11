import os
import argparse
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from agent import Agent
from skills import get_skill_registry
from config import DEFAULT_GEMINI_MODEL, DEFAULT_OLLAMA_MODEL

load_dotenv()

console = Console()

style = Style.from_dict({
    'prompt': 'ansicyan bold',
})

def main():
    parser = argparse.ArgumentParser(description="A local AI CLI agent.")
    parser.add_argument(
        "--provider",
        choices=["gemini", "ollama"],
        default="gemini",
        help="Which model provider to use (default: gemini).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help=f"Model name to use. Defaults to '{DEFAULT_GEMINI_MODEL}' for Gemini or '{DEFAULT_OLLAMA_MODEL}' for Ollama.",
    )
    args = parser.parse_args()

    if args.provider == "gemini" and not os.environ.get("GEMINI_API_KEY"):
        console.print("[bold red]Warning: GEMINI_API_KEY is not set.[/bold red]")
        console.print("Set it in your environment or a .env file and try again.")
        return

    console.print(f"[bold green]AI CLI Agent[/bold green] — provider: [cyan]{args.provider}[/cyan]")
    console.print("Type '/exit' or '/quit' to close.\n")

    agent = Agent(provider=args.provider, model_name=args.model)
    session = PromptSession()

    while True:
        try:
            user_input = session.prompt("You > ", style=style)
            user_input = user_input.strip()

            if not user_input:
                continue
            if user_input.lower() in ['exit', 'quit', '/exit', '/quit']:
                console.print("Goodbye!")
                break

            # ── REPL commands (start with /) ──────────────────────────────
            if user_input.startswith("/"):
                parts = user_input[1:].split(maxsplit=1)
                cmd = parts[0].lower()

                if cmd == "skills":
                    _print_skills_table()
                    continue

                if cmd == "skill" and len(parts) > 1:
                    name = parts[1].strip()
                    registry = get_skill_registry()
                    if name not in registry:
                        console.print(f"[red]Unknown skill '{name}'. Run /skills to list available skills.[/red]")
                    else:
                        console.print(f"[bold magenta]  ⚡ Running skill: {name}[/bold magenta]")
                        try:
                            result = registry[name]()
                            console.print(Markdown(result))
                        except Exception as e:
                            console.print(f"[red]Error:[/red] {e}")
                    continue

                if cmd == "help":
                    console.print(Markdown(
                        "**REPL commands:**\n"
                        "- `/skills` — list all available skills\n"
                        "- `/skill <name>` — run a skill directly (no LLM)\n"
                        "- `/exit` / `/quit` — close the agent"
                    ))
                    continue

                console.print(f"[yellow]Unknown command '/{cmd}'. Type /help for available commands.[/yellow]")
                continue
            # ─────────────────────────────────────────────────────────────

            response_text = agent.process_input(user_input)

            if response_text:
                console.print(Markdown(response_text))
                console.print()

        except KeyboardInterrupt:
            continue
        except EOFError:
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")

def _print_skills_table():
    """Prints a formatted table of all registered skills."""
    import inspect
    registry = get_skill_registry()
    if not registry:
        console.print("[yellow]No skills registered.[/yellow]")
        return

    table = Table(title="Available Skills", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description")
    table.add_column("Parameters", style="dim")

    for name, fn in registry.items():
        doc = inspect.getdoc(fn) or ""
        description = doc.splitlines()[0] if doc else "—"
        sig = inspect.signature(fn)
        params = ", ".join(
            f"{p}{'?' if v.default is not inspect.Parameter.empty else ''}"
            for p, v in sig.parameters.items()
        )
        table.add_row(name, description, params or "none")

    console.print(table)
    console.print("[dim]Run a skill directly with: /skill <name>[/dim]\n")

if __name__ == "__main__":
    main()
