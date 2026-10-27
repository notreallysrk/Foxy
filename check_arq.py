import asyncio
import os
from aiohttp import ClientSession

async def main():
    url = os.environ.get("ARQ_API_URL", "").rstrip("/")
    key = os.environ.get("ARQ_API_KEY", "")

    if not url or not key:
        print("ERROR: ARQ_API_URL or ARQ_API_KEY missing")
        return

    async with ClientSession() as session:
        from Python_ARQ import ARQ

        arq = ARQ(url, key, session)

        try:
            response = await arq.luna(
                "Hello, how are you?",
                123456789,
            )

            print("LUNA RESULT:", repr(response.result))

        except Exception as e:
            print("LUNA ERROR:", type(e).__name__, str(e))

asyncio.run(main())
