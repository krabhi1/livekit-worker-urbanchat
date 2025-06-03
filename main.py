from livekit import agents, rtc
from livekit.agents import (
    AgentSession,
    AutoSubscribe,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    RoomOutputOptions,
    JobContext,
    CloseEvent,
)

from livekit.plugins import (
    deepgram,
    openai,
    silero,
)

import app.env  # noqa: F401

from app.assistant import Assistant
from app.usage_collector import UsageCollector
from sarvam import tts as sarvam
from utils import get_worker_payload
from livekit.api import LiveKitAPI

from app.logger import logger


def prewarm(job: JobProcess):
    job.userdata["vad"] = silero.VAD.load()


# Add any cleanup code here


async def entrypoint(ctx: agents.JobContext):
    lk_api = LiveKitAPI()

    async def participant_entry(ctx: JobContext, p: rtc.RemoteParticipant):
        logger.info(f"Participant entrypoint {p} attributes: {p.attributes}")
        if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD:
            pass
        elif p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            pass

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(p: rtc.RemoteParticipant):
        summary = usage_collector.get_summary()
        if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD:
            pass
        elif p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            pass
        logger.info(f"Participant disconnected: {p} Summary: {summary}")

    async def my_shutdown_hook():
        logger.info("worker is shutting down")

    ctx.add_shutdown_callback(my_shutdown_hook)
    ctx.add_participant_entrypoint(participant_entry)

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    participant = await ctx.wait_for_participant()
    print(f"participant connected: {participant} attributes: {participant.attributes}")

    worker_payload = get_worker_payload(ctx.job.metadata or "{}")
    logger.info(f"worker_payload: {worker_payload}")

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        # stt=openai.STT(
        #     model="gpt-4o-transcribe",
        # ),
        llm=openai.LLM(model="gpt-4o-mini"),
        # Use one of the built-in TTS providers instead of custom SarvamTTS
        # tts=openai.TTS(),
        tts=sarvam.TTS(speaker="meera", target_language_code="en-IN", model="bulbul:v1"),
        # tts=openai.TTS(),
        vad=ctx.proc.userdata["vad"],
    )

    usage_collector = UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        usage_collector.collect(ev.metrics)

    @session.on("close")
    def _on_close(ev:CloseEvent):
        logger.info("Session closed")
        ctx.delete_room()

    await session.start(
        room=ctx.room,
        agent=Assistant(lk_api=lk_api),
        room_input_options=RoomInputOptions(
            text_enabled=True,
            audio_enabled=True,
        ),
        room_output_options=RoomOutputOptions(
            transcription_enabled=True,
            audio_enabled=True,
        ),
    )
    logger.info("Session started")

    # session.generate_reply(instructions="Greet the user and offer your assistance.")
    session.say("Hello! How can I assist you today?")


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            shutdown_process_timeout=20,
        )
    )
