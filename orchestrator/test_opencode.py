"""Standalone test for OpenCode client. Run with: uv run python test_opencode.py"""

import asyncio
import json
from opencode_client import OpenCodeClient


async def main():
    client = OpenCodeClient("http://localhost:4096")

    print("==> Checking server health...")
    health = await client.health()
    print(f"   {health}")

    print("\n==> Creating session...")
    session_id = await client.create_session("Test from M2")
    print(f"   Session ID: {session_id}")

    print("\n==> Sending prompt (this may take 30-60s)...")
    result = await client.send_prompt(
        "Replace the contents of src/App.tsx so the page shows a centered "
        "heading that says 'Hello from Lingua!' on a blue background. "
        "Keep it minimal — just one h1 element with inline styles."
    )

    print("\n==> Response received.")
    print(f"   AI text: {client.extract_text_response(result)[:200]}...")

    files = client.extract_file_changes(result)
    print(f"   Files changed: {files}")

    with open("last_response.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\n==> Saved full response to last_response.json")

    print("\n Done. Check http://localhost:3000 to see the change.")


if __name__ == "__main__":
    asyncio.run(main())
