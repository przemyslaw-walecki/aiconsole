import asyncio
import json
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any, Dict, List, Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test_client")

load_dotenv()  # load environment variables from .env

# Constants
EXECUTION_TIMEOUT = 5  # seconds
DEFAULT_RESPONSE = {"stdout": "", "stderr": "", "returncode": -1, "result": None}


class MCPClient:
    def __init__(self, pool_size: int = 4):
        # Pool of MCP sessions and their locks
        self.pool_size = pool_size
        self.sessions: List[ClientSession] = []
        self.locks: List[asyncio.Lock] = []
        self.exit_stack = AsyncExitStack()
        self._rr_counter = 0

    async def connect_to_server(self, server_script_path: str):
        """Connect to multiple MCP worker subprocesses"""
        logger.info("Initializing MCP pool of %d workers from: %s", self.pool_size, server_script_path)
        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        params = StdioServerParameters(command=command, args=[server_script_path], env=None)

        # Launch each worker
        for i in range(self.pool_size):
            try:
                logger.debug("Starting MCP worker %d/%d", i + 1, self.pool_size)
                stdio_transport = await self.exit_stack.enter_async_context(stdio_client(params))
                stdio, write = stdio_transport

                session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
                await session.initialize()

                # Confirm tool available once
                if i == 0:
                    tools = (await session.list_tools()).tools
                    if "python_executor" not in [t.name for t in tools]:
                        raise RuntimeError("python_executor tool not found in MCP server tools")

                self.sessions.append(session)
                self.locks.append(asyncio.Lock())
                logger.info("MCP worker %d connected", i + 1)

            except Exception as e:
                logger.error("Failed to start MCP worker %d: %s", i + 1, str(e), exc_info=True)
                await self.cleanup()
                raise RuntimeError(f"Failed to initialize MCP worker {i + 1}: {e}")

        logger.info("Successfully initialized MCP pool with %d workers", len(self.sessions))

    async def execute_code(self, code: str) -> Dict[str, Any]:
        """Execute code on a round-robin MCP worker with timeout"""
        if not self.sessions:
            raise RuntimeError("MCP client not initialized")

        # Round-robin selection
        idx = self._rr_counter % len(self.sessions)
        self._rr_counter += 1
        session = self.sessions[idx]
        lock = self.locks[idx]

        async with lock:
            try:
                logger.debug("Worker %d executing code", idx + 1)
                task = asyncio.create_task(session.call_tool("python_executor", {"code": code}))
                resp = await asyncio.wait_for(task, timeout=EXECUTION_TIMEOUT)

                logger.debug("Raw response from worker %d: %s", idx + 1, resp)
                if not resp or not getattr(resp, "content", None):
                    logger.warning("Empty response from worker %d", idx + 1)
                    return DEFAULT_RESPONSE

                content = resp.content
                # Handle TextContent list
                if isinstance(content, list) and len(content) > 0 and hasattr(content[0], "text"):
                    try:
                        content = json.loads(content[0].text)
                    except json.JSONDecodeError:
                        return {"stdout": content[0].text, "stderr": "", "returncode": 0, "result": None}

                if isinstance(content, dict):
                    return {
                        "stdout": content.get("stdout", ""),
                        "stderr": content.get("stderr", ""),
                        "returncode": content.get("returncode", -1),
                        "result": content.get("result", None),
                    }

                logger.warning("Unexpected content format from worker %d: %s", idx + 1, type(content))
                return DEFAULT_RESPONSE

            except asyncio.TimeoutError:
                logger.error("Execution timed out on worker %d after %d seconds", idx + 1, EXECUTION_TIMEOUT)
                return {
                    "stdout": "",
                    "stderr": f"Execution timed out after {EXECUTION_TIMEOUT}s",
                    "returncode": -1,
                    "result": None,
                }
            except Exception as e:
                logger.error("Execution error on worker %d: %s", idx + 1, str(e), exc_info=True)
                return {"stdout": "", "stderr": f"Execution error: {str(e)}", "returncode": -1, "result": None}

    async def cleanup(self):
        """Terminate all MCP worker subprocesses"""
        logger.debug("Cleaning up all MCP workers")
        await self.exit_stack.aclose()


# Instantiate global client with pool size 4 (adjust as needed)
mcp_client = MCPClient(pool_size=4)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import os

    server_path = os.path.join(os.path.dirname(__file__), "mcp_server.py")
    await mcp_client.connect_to_server(server_path)
    yield
    await mcp_client.cleanup()


app = FastAPI(lifespan=lifespan)


class CodeRequest(BaseModel):
    code: str


@app.get("/health")
async def health_check():
    if not mcp_client.sessions:
        raise HTTPException(status_code=503, detail="MCP client not initialized")
    return {"status": "ok", "message": f"Server running with {len(mcp_client.sessions)} workers"}


@app.post("/execute")
async def execute_code(request: CodeRequest):
    if not mcp_client.sessions:
        raise HTTPException(status_code=503, detail="MCP client not initialized")

    result = await mcp_client.execute_code(request.code)
    return result


def main():
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="debug")


if __name__ == "__main__":
    main()
