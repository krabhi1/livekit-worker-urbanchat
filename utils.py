import json
from dataclasses import dataclass
from typing import Optional
from livekit.agents import (
    JobContext,
)

from itertools import chain

from app.logger import logger


@dataclass
class WorkerPayload:
    agentId: Optional[str] = None
    phoneNumber: Optional[str] = None


def get_worker_payload(data: str):
    json_data = json.loads(data)
    agentId = json_data.get("agentId")
    phoneNumber = json_data.get("phoneNumber")
    if not agentId and not phoneNumber:
        # raise ValueError(
        #     "One of 'agentId' or 'phoneNumber' must be provided in the payload."
        # )
        return None
    return WorkerPayload(agentId=agentId, phoneNumber=phoneNumber)


async def room_stats(ctx: JobContext):
    rtc_stats = await ctx.room.get_rtc_stats()
    all_stats = chain(
        (("PUBLISHER", stats) for stats in rtc_stats.publisher_stats),
        (("SUBSCRIBER", stats) for stats in rtc_stats.subscriber_stats),
    )
    list = []
    for kind, stats in all_stats:
        # stats_kind = stats.WhichOneof("stats")
        list.append(stats)

    logger.info(f"room stat {list}")
