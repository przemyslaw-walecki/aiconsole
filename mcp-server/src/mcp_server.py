import io
import logging
import sys
from contextlib import asynccontextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict

from mcp.server.fastmcp.server import Context, FastMCP

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mcp_server")

# Enable debug logging for MCP
logging.getLogger("mcp").setLevel(logging.DEBUG)


# List of dangerous builtins that should be excluded
UNSAFE_BUILTINS = {
    "eval",
    "exec",
    "compile",  # Code execution
    "open",
    "file",  # File operations
    "globals",
    "locals",
    "vars",  # Access to scopes
    "getattr",
    "setattr",
    "delattr",  # Attribute manipulation
    "__import__",
}


def create_safe_builtins():
    """Create a safe subset of builtins."""
    safe_builtins = {}
    for name, value in __builtins__.items() if isinstance(__builtins__, dict) else vars(__builtins__).items():
        if name not in UNSAFE_BUILTINS and not name.startswith("_"):
            safe_builtins[name] = value

    # Add back specific dunders we want to allow
    safe_builtins["__import__"] = __import__  # Allow imports
    return safe_builtins


@dataclass
class AppContext:
    # placeholder for shared resources
    db: Any = None


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    logger.info("Starting MCP server lifespan")
    yield AppContext()
    logger.info("Ending MCP server lifespan")


# instantiate server (uses stdio JSON-RPC transport by default)
mcp = FastMCP(name="python_runner", lifespan=app_lifespan)


def create_print_wrapper(stdout_buffer: io.StringIO):
    """Create a print function that writes to our buffer."""

    def custom_print(*args, **kwargs):
        # Get the original 'sep' and 'end' or use defaults
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")

        # Convert all arguments to strings and join them
        print_output = sep.join(str(arg) for arg in args)
        logger.debug("Print wrapper called with args: %r, creating output: %r", args, print_output)

        # Clear the buffer first to avoid accumulation
        stdout_buffer.seek(0)
        stdout_buffer.truncate()

        # Write to our buffer, adding end only once
        stdout_buffer.write(print_output)
        if end:  # Only add end if it's not empty
            stdout_buffer.write(end)
        logger.debug("Buffer content after print: %r", stdout_buffer.getvalue())

    return custom_print


@mcp.tool(name="python_executor", description="Execute Python code and return stdout/stderr")
def python_executor_tool(ctx: Context, code: str) -> Dict[str, Any]:
    """Runs Python code and captures its output."""
    logger.info("Received code execution request")
    logger.debug("Code to execute: %s", code)

    stdout = io.StringIO()
    stderr = io.StringIO()
    result_value = None

    try:
        # Compile the code first to catch syntax errors
        logger.debug("Compiling code")
        compiled_code = compile(code, "<string>", "exec")

        # Create globals with safe builtins
        safe_builtins = create_safe_builtins()
        safe_builtins["print"] = create_print_wrapper(stdout)
        logger.debug("Created print wrapper")

        globals_dict = {
            "__builtins__": safe_builtins,
        }
        locals_dict = {}  # Separate locals dict to capture the result

        # Execute the code with captured output
        logger.debug("Executing code")
        with redirect_stderr(stderr):  # Only redirect stderr
            exec(compiled_code, globals_dict, locals_dict)
            logger.debug("Code executed, stdout buffer content: %r", stdout.getvalue())

            # Try to get the last expression's value
            try:
                last_line = code.strip().split("\n")[-1]
                if not (last_line.startswith("def ") or last_line.startswith("class ") or "=" in last_line):
                    result_value = eval(last_line, globals_dict, locals_dict)
                    logger.debug("Last expression value: %r", result_value)
            except Exception as e:
                logger.debug("Failed to get last expression value: %s", str(e))
                pass

        stdout_content = stdout.getvalue()
        stderr_content = stderr.getvalue()

        logger.info("Code execution completed successfully")
        logger.debug("Final stdout content: %r", stdout_content)
        logger.debug("Final stderr content: %r", stderr_content)
        logger.debug("Final result value: %r", result_value)

        result = {"stdout": stdout_content, "stderr": stderr_content, "returncode": 0, "result": result_value}
        logger.debug("Returning result: %r", result)
        return result

    except Exception as e:
        logger.error("Code execution failed", exc_info=True)
        error_msg = f"{type(e).__name__}: {str(e)}"
        result = {"stdout": stdout.getvalue(), "stderr": error_msg, "returncode": 1}
        logger.debug("Returning error result: %r", result)
        return result
    finally:
        stdout.close()
        stderr.close()


def main():
    logger.info("Starting MCP server (stdio JSON-RPC)")
    try:
        mcp.run()  # reads JSON-RPC from stdin, writes JSON-RPC to stdout
    except Exception as e:
        logger.error("MCP server failed", exc_info=True)
        raise


if __name__ == "__main__":
    main()
