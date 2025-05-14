import asyncio
import json
import logging
import traceback

import aiohttp
from aiohttp import ClientError, ClientTimeout

from aiconsole.api.websockets.connection_manager import connection_manager
from aiconsole.api.websockets.server_messages import ErrorServerMessage
from aiconsole.core.assets.materials.material import Material
from aiconsole.core.chat.chat_mutations import (
    AppendToOutputToolCallMutation,
    SetIsExecutingToolCallMutation,
    SetOutputToolCallMutation,
)
from aiconsole.core.chat.chat_mutator import ChatMutator
from aiconsole.core.code_running.run_code import run_in_code_interpreter

_log = logging.getLogger(__name__)


async def run_code(
    chat_mutator: ChatMutator,
    materials: list[Material],
    tool_call_id,
):
    """
    Execute code via MCP server; if language unsupported or MCP is unreachable,
    fallback to notebook-based execution.
    """
    tool_call_location = chat_mutator.chat.get_tool_call_location(tool_call_id)
    if not tool_call_location:
        raise Exception(f"Tool call {tool_call_id} should have been created")

    tool_call = tool_call_location.tool_call

    try:
        # Mark executing and clear previous output
        await chat_mutator.mutate(SetIsExecutingToolCallMutation(tool_call_id=tool_call_id, is_executing=True))
        await chat_mutator.mutate(SetOutputToolCallMutation(tool_call_id=tool_call_id, output=""))

        # Determine execution path
        lang = tool_call.language.lower() if tool_call.language else None

        # Only Python supported by MCP
        use_notebook = False
        if lang != "python":
            _log.info("Language '%s' not supported by MCP, using notebook fallback", lang)
            use_notebook = True

        if not use_notebook:
            try:
                # Attempt MCP execution
                timeout = ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        "http://127.0.0.1:8001/execute", json={"code": tool_call.code}
                    ) as response:
                        if response.status != 200:
                            text = await response.text()
                            raise Exception(f"MCP error: {response.status} {text}")

                        raw = await response.text()
                        result = json.loads(raw)

                        # Build combined output
                        parts = []
                        if result.get("stderr"):
                            parts.append(result["stderr"].rstrip())
                        if result.get("stdout"):
                            out = result["stdout"].rstrip()
                            if out:
                                parts.append(out)
                        if result.get("result") is not None:
                            res = str(result["result"]).rstrip()
                            if not result.get("stdout") or res not in result.get("stdout", ""):
                                parts.append(res)

                        if parts:
                            final = "\n".join(parts) + "\n"
                            await chat_mutator.mutate(
                                AppendToOutputToolCallMutation(tool_call_id=tool_call_id, output_delta=final)
                            )
                        return
            except (ClientError, asyncio.TimeoutError, Exception) as mcp_err:
                _log.warning(
                    "MCP execution failed (%s); falling back to notebook:\n%s",
                    type(mcp_err).__name__,
                    traceback.format_exc(),
                )

        # Notebook fallback
        try:
            async for token in await run_in_code_interpreter(
                tool_call.language, chat_mutator.chat.id, tool_call.code, materials
            ):
                await chat_mutator.mutate(
                    AppendToOutputToolCallMutation(
                        tool_call_id=tool_call_id,
                        output_delta=token,
                    )
                )
        except Exception:
            err = traceback.format_exc().strip()
            await connection_manager().send_to_chat(ErrorServerMessage(error=err), chat_mutator.chat.id)
            await chat_mutator.mutate(AppendToOutputToolCallMutation(tool_call_id=tool_call_id, output_delta=err))

    finally:
        # Always unset executing flag
        await chat_mutator.mutate(SetIsExecutingToolCallMutation(tool_call_id=tool_call_id, is_executing=False))
