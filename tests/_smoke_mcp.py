"""Manual smoke driver: spin up the MCP server over stdio and list its tools.

Run with: .venv/bin/python tests/_smoke_mcp.py
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "humanize_mcp.server"],
        cwd=str(repo),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print("tools:", names)
            assert "humanize_text" in names
            assert "detect_ai_tells" in names
            assert "compute_readability" in names

            # Pure-function tool — should not need any creds.
            r = await session.call_tool(
                "detect_ai_tells",
                {"text": "It's worth noting that we delve into this intricate tapestry."},
            )
            content = r.content[0].text if r.content else ""
            print("detect_ai_tells sample output (first 200 chars):", content[:200])
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
