import asyncio
from app.api import get_agent_by_id, get_agent_by_phone, register_inbound_call
import app.env  # noqa: F401


async def main():
    agent = await get_agent_by_id(
        "3d11ac3d-ef6a-4a0d-9703-8f1906509db8", "2822a8f4-d9b5-49dd-a08a-fd39cb63b576"
    )
    print(f"agent by id {agent} \n")

    agent = await get_agent_by_phone("918035738849", "inbound")
    print(f"agent by phone {agent}")

    result = await register_inbound_call("919525140960", "918035738849")
    print(f"register inbound call result: {result}")


asyncio.run(main())
