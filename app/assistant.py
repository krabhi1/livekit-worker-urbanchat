from livekit.agents import (
    Agent,
    function_tool,
    RunContext,
    get_job_context,
)
import asyncio
from .logger import logger

from livekit.api import LiveKitAPI, DeleteRoomRequest

class Assistant(Agent):
    def __init__(self, lk_api: LiveKitAPI) -> None:
        super().__init__(instructions="You are a helpful voice AI assistant.")
        self.lk_api = lk_api
        self._closing_task: asyncio.Task[None] | None = None

    async def on_enter(self):
        logger.info("Agent on_enter")

    async def on_exit(self):
        logger.info("Agent on_exit")

    # to hang up the call as part of a function call
    @function_tool
    async def end_call(self, ctx: RunContext):
        """Use this tool when the user has signaled they wish to end the current call. The session will end automatically after invoking this tool."""
        # let the agent finish speaking
        logger.info("end_call")
        current_speech = ctx.session.current_speech
        if current_speech:
            await current_speech.wait_for_playout()
        await self.session.say("Thank you for calling. Goodbye!")
        # job_ctx = get_job_context()
        # await self.lk_api.room.delete_room(DeleteRoomRequest(room=job_ctx.room.name))
        # don't await it, the function call will be awaited before closing
        self._closing_task = asyncio.create_task(self.session.aclose())