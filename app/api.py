import aiohttp
import os

from app import env


HEADERS = {"x-server-api-key": env.SERVER_API_KEY}


async def get_agent_by_phone(phone: str):
    url = f"{env.SERVER_URL}/api/agents/by-phone/{phone}"
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(url) as response:
            return await response.json()


async def get_agent_by_id(agent_id: str, user_id: str):
    url = f"{env.SERVER_URL}/api/agents/{agent_id}?userId={user_id}"
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(url) as response:
            return await response.json()


async def update_call(call_id: str, user_id: str, call_data: dict):
    url = f"{env.SERVER_URL}/api/calls/{call_id}?userId={user_id}"
    headers = HEADERS | {"Content-Type": "application/json"}  # merge headers
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.patch(url, json=call_data) as response:
            return await response.json()


async def make_inbound_call(fromNumber: str, toNumber: str):
    url = f"{env.SERVER_URL}/api/calls/make-phone-call"
    headers = HEADERS | {"Content-Type": "application/json"}  # merge headers
    payload = {
        "fromNumber": fromNumber,
        "toNumber": toNumber,
        "direction": "inbound",
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(url, json=payload) as response:
            return await response.json()
