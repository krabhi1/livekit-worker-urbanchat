import aiohttp
import os

SERVER_URL = os.getenv("SERVER_URL")
SERVER_API_KEY = os.getenv("SERVER_API_KEY")

if not SERVER_URL:
    raise ValueError("SERVER_URL environment variable is not set")
if not SERVER_API_KEY:
    raise ValueError("SERVER_API_KEY environment variable is not set")

HEADERS = {"x-server-api-key": SERVER_API_KEY}


async def get_agent_by_phone(phone: str):
    url = f"{SERVER_URL}/api/agents/by-phone/{phone}"
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(url) as response:
            return await response.json()


async def get_agent_by_id(agent_id: str, user_id: str):
    url = f"{SERVER_URL}/api/agents/{agent_id}?userId={user_id}"
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(url) as response:
            return await response.json()


async def update_call(call_id: str, user_id: str, call_data: dict):
    url = f"{SERVER_URL}/api/calls/{call_id}?userId={user_id}"
    headers = HEADERS | {"Content-Type": "application/json"}  # merge headers
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.patch(url, json=call_data) as response:
            return await response.json()
