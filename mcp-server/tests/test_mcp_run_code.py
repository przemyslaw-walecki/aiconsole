import asyncio
import json

import aiohttp
from aiohttp import ClientTimeout


# Mock classes to simulate the chat_mutator environment
class MockToolCall:
    def __init__(self, code, language="python"):
        self.code = code
        self.language = language


class MockToolCallLocation:
    def __init__(self, tool_call):
        self.tool_call = tool_call


class MockChat:
    def get_tool_call_location(self, tool_call_id):
        return self.tool_call_location


class MockChatMutator:
    def __init__(self, chat):
        self.chat = chat
        self.outputs = []

    async def mutate(self, mutation):
        if hasattr(mutation, "output_delta"):
            print(f"Output received: {repr(mutation.output_delta)}")
            self.outputs.append(mutation.output_delta)


# The fibonacci code we're testing
FIBONACCI_CODE = """
import time
def fibonacci(n):
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b

fib10 = fibonacci(10)
fib10  # This should return the value without printing"""


async def run_code_test():
    # Set up the mock environment
    tool_call = MockToolCall(FIBONACCI_CODE)
    tool_call_location = MockToolCallLocation(tool_call)
    chat = MockChat()
    chat.tool_call_location = tool_call_location
    chat_mutator = MockChatMutator(chat)

    # Actual code from run_code.py
    try:
        print("\nSending request to MCP server...")
        timeout = ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post("http://127.0.0.1:8001/execute", json={"code": tool_call.code}) as response:
                print(f"\nResponse status: {response.status}")
                raw_response = await response.text()
                print(f"Raw response text: {repr(raw_response)}")

                try:
                    # First try to parse as direct JSON
                    result = json.loads(raw_response)
                    print(f"Parsed JSON result: {json.dumps(result, indent=2)}")
                except json.JSONDecodeError:
                    print("Failed to parse response as JSON")
                    return

                # Output stdout if present
                if result.get("stdout"):
                    print(f"\nFound stdout: {repr(result['stdout'])}")

                # Output stderr if present
                if result.get("stderr"):
                    print(f"\nFound stderr: {repr(result['stderr'])}")

                # Output result value if present and not None
                if result.get("result") is not None:
                    print(f"\nFound result: {repr(result['result'])}")

                # Show the final output that would be sent to the user
                output_parts = []
                if result.get("stdout"):
                    output_parts.append(result["stdout"])
                if result.get("stderr"):
                    output_parts.append(result["stderr"])
                if result.get("result") is not None:
                    output_parts.append(str(result["result"]))

                if output_parts:
                    output = "\n".join(output_parts) + "\n"
                    print(f"\nFinal output that would be shown to user: {repr(output)}")
                    await chat_mutator.mutate(type("Mutation", (), {"output_delta": output})())
                else:
                    print("\nNo output parts found!")

    except Exception as e:
        print(f"Error: {type(e).__name__}: {str(e)}")


def main():
    asyncio.run(run_code_test())


if __name__ == "__main__":
    main()
