import asyncio
import aiohttp
import re
import base64

BASE = "http://15.206.47.5:9090"

async def solve():
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Fetch task
                async with session.get(f"{BASE}/task") as r:
                    html = await r.text()

                # Extract string from HTML
                match = re.search(r'>([^<]+)<', html)
                if not match:
                    print("Could not extract string!")
                    continue

                s = match.group(1).strip()

                # Transform
                rev = s[::-1]
                b64 = base64.b64encode(rev.encode()).decode()
                answer = f"CSK__{b64}__2025"

                # Submit
                async with session.post(f"{BASE}/submit",
                                        data={"answer": answer}) as r:
                    response = await r.text()

                print("Server:", response)

                if "flag" in response.lower():
                    print("\n🎉 FLAG FOUND")
                    break

            except Exception as e:
                print("ERR:", e)

asyncio.run(solve())
