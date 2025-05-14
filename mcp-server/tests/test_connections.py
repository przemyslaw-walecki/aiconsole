import asyncio
import json
from typing import Any, Dict

import aiohttp
from aiohttp import ClientTimeout

# Constants
HEALTH_CHECK_TIMEOUT = 5  # seconds
EXECUTION_TIMEOUT = 5  # seconds to match test_client.py


async def execute_test_case(session: aiohttp.ClientSession, code: str, description: str) -> None:
    """Execute a single test case and handle its response"""
    print(f"\nTest: {description}")
    print(f"Code: {code}")

    try:
        async with session.post("http://127.0.0.1:8001/execute", json={"code": code}) as response:
            if response.status != 200:
                print(f"Error: HTTP {response.status}")
                try:
                    error_details = await response.json()
                    print(f"Server response: {json.dumps(error_details, indent=2)}")
                except:
                    print(f"Raw response: {await response.text()}")
                return

            result = await response.json()
            print("Response:", json.dumps(result, indent=2))

            # Validate response format
            if not isinstance(result, dict):
                print("Error: Invalid response format - expected dictionary")
                return

            if "returncode" not in result:
                print("Error: Invalid response format - missing returncode")
                return

            if result["returncode"] != 0:
                print(f"Warning: Non-zero return code: {result['returncode']}")
                if "stderr" in result and result["stderr"]:
                    print(f"stderr: {result['stderr']}")

    except aiohttp.ClientError as e:
        print(f"Connection error: {e}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")


async def test_code_execution():
    """Run a series of test cases against the MCP server"""
    timeout = ClientTimeout(total=EXECUTION_TIMEOUT + 2)  # Add 2 seconds buffer for network

    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Test cases
        test_cases = [
            ("print('Hello from MCP!')", "Simple print statement"),
            ("print(10 * 5)", "Math operation"),
            ("1/0", "Error handling"),
            ("import time\ntime.sleep(6)\nprint('Done')", "Timeout test"),
            ("x = {'a': 1, 'b': 2}\nprint(x)", "Dictionary output"),
        ]

        for code, description in test_cases:
            await execute_test_case(session, code, description)


async def main():
    print("Starting MCP client connection test...")
    print("Checking if server is running...")

    # Health check with shorter timeout
    try:
        timeout = ClientTimeout(total=HEALTH_CHECK_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get("http://127.0.0.1:8001/health") as response:
                if response.status != 200:
                    print(f"Error: Server health check failed with status {response.status}")
                    try:
                        error_details = await response.json()
                        print(f"Server response: {json.dumps(error_details, indent=2)}")
                    except:
                        print(f"Raw response: {await response.text()}")
                    return

                health = await response.json()
                if health.get("status") != "ok":
                    print(f"Error: Server not ready: {health.get('message')}")
                    return

                print("Server is healthy and ready for tests")

    except aiohttp.ClientError as e:
        print(f"Error: Could not connect to server. Is it running on port 8001? Error: {e}")
        return
    except Exception as e:
        print(f"Unexpected error during health check: {str(e)}")
        return

    try:
        await test_code_execution()
        print("\nAll tests completed!")
    except Exception as e:
        print(f"\nError during testing: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
