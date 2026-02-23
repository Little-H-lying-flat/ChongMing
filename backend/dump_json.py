import httpx, json, asyncio
async def main():
    async with httpx.AsyncClient() as client:
        r = await client.get('http://127.0.0.1:8000/api/v1/test-cases?mode=API')
        with open('cases_out.json', 'w', encoding='utf-8') as f:
            json.dump(r.json(), f, indent=2, ensure_ascii=False)
asyncio.run(main())
