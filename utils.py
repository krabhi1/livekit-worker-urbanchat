from livekit.agents import JobContext
from itertools import chain
import re
from app.logger import logger


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


def is_ok(code: int) -> bool:
    return 200 <= code < 300
