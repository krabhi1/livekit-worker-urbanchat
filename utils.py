import json
from dataclasses import dataclass
from typing import Optional
from livekit import rtc
from livekit.agents import JobContext
from itertools import chain
import re
from app.logger import logger


@dataclass
class WorkerPayload:
    user_id: str
    agent_id: str
    call_id: str


@dataclass
class WorkerPhonePayload(WorkerPayload):
    number: str
    trunk_number: str
    direction: str


def get_worker_payload(ctx: JobContext, p: rtc.RemoteParticipant):
    if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
        phone_number = p.attributes.get("sip.phoneNumber", "").lstrip("+")
        trunk_number = p.attributes.get("sip.trunkPhoneNumber", "").lstrip("+")
        direction = p.attributes.get("direction", "")
        call_id = p.attributes.get("callId", "")
        user_id = p.attributes.get("userId", "")
        agent_id = p.attributes.get("agentId", "")
        return WorkerPhonePayload(
            user_id=user_id,
            agent_id=agent_id,
            call_id=call_id,
            number=phone_number,
            trunk_number=trunk_number,
            direction=direction,
        )

    if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD:
        meta = json.loads(ctx.job.metadata or "{}")
        user_id = meta["userId"]
        agent_id = meta["agentId"]
        call_id = meta["callId"]
        return WorkerPayload(user_id=user_id, agent_id=agent_id, call_id=call_id)
    raise ValueError("Unsupported participant kind or missing attributes.")


async def room_stats(ctx: JobContext):
    rtc_stats = await ctx.room.get_rtc_stats()
    all_stats = chain(
        (("PUBLISHER", stats) for stats in rtc_stats.publisher_stats),
        (("SUBSCRIBER", stats) for stats in rtc_stats.subscriber_stats),
    )
    list = []
    for kind, stats in all_stats:
        list.append(stats)

    logger.info(f"room stat {list}")


def camel_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


# async def load_agent(p: rtc.RemoteParticipant, payload: WorkerPayload | None):
#     from app.api import get_agent_by_phone, get_agent_by_id  # Moved imports here

#     if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
#         phone = p.attributes.get("sip.trunkPhoneNumber", "").lstrip("+")
#         return await get_agent_by_phone(phone, p.attributes["direction"])

#     if not payload:
#         raise ValueError("Worker payload must contain either 'agentId' or 'phoneNumber'.")
#     if payload.agent_id:
#         return await get_agent_by_id(payload.agent_id, payload.user_id)


def is_ok(code: int) -> bool:
    return 200 <= code < 300
