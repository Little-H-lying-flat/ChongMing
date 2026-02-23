import asyncio
import httpx

async def test():
    try:
        async with httpx.AsyncClient(timeout=1.0, trust_env=False) as client:
            resp = await client.get('http://127.0.0.1:7861/health')
            print("Status:", resp.status_code)
            print("Text:", resp.text)
    except Exception as e:
        print("EXCEPTION:", type(e).__name__, str(e))

asyncio.run(test())
