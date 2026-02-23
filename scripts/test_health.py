import asyncio
import time
from httpx import AsyncClient

async def check():
    async with AsyncClient(base_url='http://localhost:8000', timeout=60.0) as client:
        # Check overall health endpoint
        t0 = time.time()
        try:
            r1 = await client.get('/api/v1/health')
            print(f'GET /api/v1/health: {r1.status_code}, time: {time.time()-t0:.3f}s')
        except Exception as e:
            print(f'GET /api/v1/health FAILED: {e}, time: {time.time()-t0:.3f}s')

        # Check environments
        t0 = time.time()
        r2 = await client.get('/api/v1/environments')
        print(f'GET /api/v1/environments: {r2.status_code}, time: {time.time()-t0:.3f}s')
        if r2.status_code == 200:
            envs = r2.json()
            for env in envs:
                t0 = time.time()
                try:
                    r3 = await client.get(f'/api/v1/environments/{env["id"]}/health')
                    print(f'GET env {env["name"]} health: {r3.status_code}, time: {time.time()-t0:.3f}s')
                except Exception as e:
                    print(f'GET env {env["name"]} FAILED: {e}, time: {time.time()-t0:.3f}s')

if __name__ == '__main__':
    asyncio.run(check())
