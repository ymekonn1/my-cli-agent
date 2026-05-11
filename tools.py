import os
import subprocess

def read_file(path: str) -> str:
    """Reads the contents of a file.
    
    Args:
        path: The absolute or relative path to the file to read.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(path: str, content: str) -> str:
    """Writes content to a file, overwriting it if it exists.
    
    Args:
        path: The path to the file to write.
        content: The content to write into the file.
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {e}"

def run_shell_command(command: str) -> str:
    """Runs a shell command and returns the output.
    
    Args:
        command: The shell command to execute.
    """
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = result.stdout
        if result.stderr:
            if output:
                output += "\n"
            output += f"STDERR:\n{result.stderr}"
        return output if output else "Command executed successfully with no output."
    except Exception as e:
        return f"Error executing command: {e}"
