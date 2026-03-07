"""
Dev-mode browser launcher.

Starts a visible Chromium instance with CDP exposed on CDP_PORT (default 9222),
then blocks so browser-mcp (configured with --cdp-endpoint http://localhost:PORT)
and the MCP server (CDP_PORT env var) can both attach to the same browser.

Usage:
    CDP_PORT=9222 python launch_browser.py
"""

import asyncio
import os
import signal
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

PORT = int(os.getenv("CDP_PORT", "9222"))


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[f"--remote-debugging-port={PORT}"],
        )
        print(f"Browser running. CDP endpoint: http://localhost:{PORT}")
        print("Start the MCP server (CDP_PORT={PORT} python server.py) and reload Claude Code.")
        print("Press Ctrl+C to stop.")

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, stop.set)
        loop.add_signal_handler(signal.SIGTERM, stop.set)

        await stop.wait()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
