import json
import inspect
from rich.console import Console
from tools import read_file, write_file, run_shell_command
from skills import get_skill_registry
from config import SYSTEM_INSTRUCTION, DEFAULT_GEMINI_MODEL, DEFAULT_OLLAMA_MODEL, OLLAMA_BASE_URL

console = Console()

TOOL_MAP = {
    "read_file": read_file,
    "write_file": write_file,
    "run_shell_command": run_shell_command,
}

def _python_type_to_json_schema(annotation) -> dict:
    """Converts basic Python type annotations to JSON schema types."""
    if annotation is inspect.Parameter.empty or annotation is str:
        return {"type": "string"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is bool:
        return {"type": "boolean"}
    return {"type": "string"}

def _build_openai_tool_schema(fn) -> dict:
    """Builds an OpenAI-compatible tool schema from a Python function's docstring and signature."""
    sig = inspect.signature(fn)
    doc = inspect.getdoc(fn) or ""
    # Parse the Args section of the docstring for parameter descriptions
    param_docs = {}
    in_args = False
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped == "Args:":
            in_args = True
            continue
        if in_args:
            if stripped == "" or (not stripped.startswith(" ") and ":" in stripped and not stripped[0].islower()):
                in_args = False
                continue
            if ":" in stripped:
                pname, pdesc = stripped.split(":", 1)
                param_docs[pname.strip()] = pdesc.strip()

    properties = {}
    required = []
    for pname, param in sig.parameters.items():
        properties[pname] = {
            **_python_type_to_json_schema(param.annotation),
            "description": param_docs.get(pname, ""),
        }
        if param.default is inspect.Parameter.empty:
            required.append(pname)

    # Use only the first line of the docstring as the function description
    description = doc.splitlines()[0] if doc else fn.__name__

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


class Agent:
    def __init__(self, provider: str = "gemini", model_name: str = None):
        """
        Args:
            provider: "gemini" to use Google's Gemini API, or "ollama" to use a
                      locally running Ollama model via its OpenAI-compatible endpoint.
            model_name: The model to use. Defaults to "gemini-2.5-flash" for
                        Gemini and "llama3" for Ollama.
        """
        self.provider = provider

        if provider == "ollama":
            from openai import OpenAI
            self.model_name = model_name or DEFAULT_OLLAMA_MODEL
            self.client = OpenAI(
                base_url=OLLAMA_BASE_URL,
                api_key="ollama",  # Required by the SDK but unused by Ollama
            )
            all_callables = list(TOOL_MAP.values()) + list(get_skill_registry().values())
            self.openai_tools = [_build_openai_tool_schema(fn) for fn in all_callables]
            self.history = [{"role": "system", "content": SYSTEM_INSTRUCTION}]

        else:  # gemini
            from google import genai
            from google.genai import types
            self._types = types
            self.model_name = model_name or DEFAULT_GEMINI_MODEL
            self.client = genai.Client()
            all_callables = list(TOOL_MAP.values()) + list(get_skill_registry().values())
            self.chat = self.client.chats.create(
                model=self.model_name,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=all_callables,
                ),
            )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process_input(self, user_input: str) -> str:
        """Sends user input to the agent and runs the ReAct loop until a final answer."""
        if self.provider == "ollama":
            return self._process_ollama(user_input)
        return self._process_gemini(user_input)

    # ------------------------------------------------------------------
    # Provider-specific implementations
    # ------------------------------------------------------------------

    def _process_gemini(self, user_input: str) -> str:
        try:
            response = self.chat.send_message(user_input)
            while True:
                if response.function_calls:
                    function_responses = []
                    for call in response.function_calls:
                        result = self._execute_tool(call.name, call.args or {})
                        function_responses.append(
                            self._types.Part.from_function_response(
                                name=call.name,
                                response={"result": str(result)},
                            )
                        )
                    response = self.chat.send_message(function_responses)
                else:
                    return response.text
        except Exception as e:
            return f"An error occurred during generation: {e}"

    def _process_ollama(self, user_input: str) -> str:
        self.history.append({"role": "user", "content": user_input})
        try:
            while True:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=self.history,
                    tools=self.openai_tools,
                )
                message = response.choices[0].message

                # Add the assistant's response turn to history
                self.history.append(message)

                if message.tool_calls:
                    for tool_call in message.tool_calls:
                        name = tool_call.function.name
                        args = json.loads(tool_call.function.arguments)
                        result = self._execute_tool(name, args)

                        # Feed the tool result back as a "tool" role message
                        self.history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": str(result),
                        })
                else:
                    return message.content
        except Exception as e:
            return f"An error occurred during generation: {e}"

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        args_str = ", ".join(f"{k}={v!r}" for k, v in tool_args.items())
        skill_registry = get_skill_registry()

        # Skills take priority when the name matches, shown with a different indicator
        if tool_name in skill_registry:
            console.print(f"[bold magenta]  ⚡ skill: {tool_name}({args_str})[/bold magenta]")
            try:
                return skill_registry[tool_name](**tool_args)
            except Exception as e:
                return f"Error executing skill '{tool_name}': {e}"

        # Fall back to low-level tools
        console.print(f"[dim cyan]  → {tool_name}({args_str})[/dim cyan]")
        if tool_name in TOOL_MAP:
            try:
                return TOOL_MAP[tool_name](**tool_args)
            except Exception as e:
                return f"Error executing {tool_name}: {e}"

        return f"Error: Unknown tool or skill '{tool_name}'"
