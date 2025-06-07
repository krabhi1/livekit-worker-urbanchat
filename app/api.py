import aiohttp


from app import env
from utils import is_ok


HEADERS = {"x-server-api-key": env.SERVER_API_KEY}


async def get_agent_by_phone(phone: str, direction: str):
    url = f"{env.SERVER_URL}/api/agents/by-phone/{phone}"
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(url) as response:
            result = await response.json()
            if not is_ok(response.status):
                raise ValueError(f"Failed to fetch agent: {result}")
            return result["data"][direction]


async def get_agent_by_id(agent_id: str, user_id: str):
    url = f"{env.SERVER_URL}/api/agents/{agent_id}?userId={user_id}"
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(url) as response:
            result = await response.json()
            if not is_ok(response.status):
                raise ValueError(f"Failed to fetch agent: {result}")
            return result["data"]


async def update_call(call_id: str, user_id: str, call_data: dict):
    url = f"{env.SERVER_URL}/api/calls/{call_id}?userId={user_id}"
    headers = HEADERS | {"Content-Type": "application/json"}  # merge headers
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.patch(url, json=call_data) as response:
            result = await response.json()
            if not is_ok(response.status):
                raise ValueError(f"Failed to update call: {result}")
            return result["data"]


async def register_inbound_call(fromNumber: str, toNumber: str):
    url = f"{env.SERVER_URL}/api/calls/register-inbound-call"
    headers = HEADERS | {"Content-Type": "application/json"}  # merge headers
    payload = {
        "fromNumber": fromNumber,
        "toNumber": toNumber,
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(url, json=payload) as response:
            result = await response.json()
            if not is_ok(response.status):
                raise ValueError(f"Failed to register inbound call: {result}")
            return result["data"]


async def get_call_by_id(call_id: str):
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        url = f"{env.SERVER_URL}/api/calls/{call_id}"
        async with session.get(url) as response:
            result = await response.json()
            if not is_ok(response.status):
                raise ValueError(f"Failed to fetch call: {result}")
            return result["data"]
