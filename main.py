from dotenv import load_dotenv
from livekit import agents
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    RoomOutputOptions,
    metrics,
)
from livekit.plugins import (
    deepgram,
    openai,
    silero,
)

import sarvam

load_dotenv()


# class Assistant(Agent):
#     def __init__(self) -> None:
#         super().__init__(instructions="You are a helpful voice AI assistant.")


# async def entrypoint(ctx: agents.JobContext):
#     session = AgentSession(
#         stt=deepgram.STT(model="nova-3", language="multi"),
#         llm=openai.LLM(model="gpt-4o-mini"),
#         vad=silero.VAD.load(),
#         # Use one of the built-in TTS providers instead of custom SarvamTTS
#         tts=plugins.SarvamTTS(
#             speaker="meera", target_language_code="en-IN", model="bulbul:v1"
#         ),
#     )

#     await session.start(
#         room=ctx.room,
#         agent=Assistant(),
#         room_input_options=RoomInputOptions(
#             # LiveKit Cloud enhanced noise cancellation
#             # - If self-hosting, omit this parameter
#             # - For telephony applications, use `BVCTelephony` for best results
#         ),
#     )

#     await ctx.connect()

#     await session.generate_reply(
#         instructions="Greet the user and offer your assistance."
#     )


# if __name__ == "__main__":
#     agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))


def prewarm(job: JobProcess):
    job.userdata["vad"] = silero.VAD.load()


# Add any cleanup code here
class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are a helpful voice AI assistant.")

    async def on_enter(self):
        print("--info:agent.on_enter-- ")

    async def on_exit(self):
        print("--info:agent.on_exit-- ")


async def entrypoint(ctx: agents.JobContext):
    def on_connected():
        print("--Connected to the room!")

    def on_disconnected():
        print("--Disconnected from the room!")

    async def my_shutdown_hook():
        summary = usage_collector.get_summary()
        print("--close:summary-- ", summary, usage_collector)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    print("--info:job.metadata-- ", ctx.job.metadata)
    participant = await ctx.wait_for_participant()
    print("--info:participant-- ", participant)

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=openai.LLM(model="gpt-4o-mini"),
        # Use one of the built-in TTS providers instead of custom SarvamTTS
        # tts=openai.TTS(),
        tts=sarvam.TTS(
            speaker="meera", target_language_code="en-IN", model="bulbul:v1"
        ),
        vad=ctx.proc.userdata["vad"],
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        usage_collector.collect(ev.metrics)

    @session.on("close")
    def _on_close():
        print("Session closed")

    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
            text_enabled=True,
            audio_enabled=True,
        ),
        room_output_options=RoomOutputOptions(
            transcription_enabled=True,
            audio_enabled=True,
        ),
    )

    session.generate_reply(instructions="Greet the user and offer your assistance.")

    ctx.add_shutdown_callback(my_shutdown_hook)
    ctx.room.on("connected", on_connected)
    ctx.room.on("disconnected", on_disconnected)
    ctx.room.on("participant_connected", lambda p: print(f"Participant connected: {p}"))
    ctx.room.on(
        "participant_disconnected", lambda p: print(f"Participant disconnected: {p}")
    )


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm)
    )
