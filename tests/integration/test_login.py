"""
Manual QA test for login().

Runs the automation against the shared browser (CDP). After running,
a human (or Claude via browser-mcp) verifies the result visually.

Usage:
    CDP_PORT=9222 python tests/integration/test_login.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

if not os.getenv("CDP_PORT"):
    print("ERROR: CDP_PORT is not set. Start the shared browser first and set CDP_PORT.")
    sys.exit(1)

import scanner


async def main():
    print("Running login()...")
    page = await scanner._get_page()
    print(f"Done. Current URL: {page.url}")

    print("Running dismiss_modals()...")
    await scanner.dismiss_modals(page)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
