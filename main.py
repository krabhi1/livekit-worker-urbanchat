import json
from typing import Optional
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
import app.env  # noqa: F401

from livekit.plugins import (
    deepgram,
    openai,
    silero,
)
import asyncio

from app.api import (
    get_agent_by_id,
    get_agent_by_phone,
    get_call_by_id,
    register_inbound_call,
    update_call,
)
from app.call import Call

from app.assistant import Assistant
from app.usage_collector import UsageCollector
from app.voice_agent import VoiceAgent
from sarvam import tts as sarvam
from utils import get_worker_payload
from livekit.api import LiveKitAPI

from app.logger import logger


def prewarm(job: JobProcess):
    job.userdata["vad"] = silero.VAD.load()


async def load(ctx: JobContext, p: rtc.RemoteParticipant):
    agent: Optional[VoiceAgent] = None
    call: Optional[Call] = None
    is_web_call = p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD
    if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
        trunk_phone = p.attributes["sip.trunkPhoneNumber"].lstrip("+")
        phone = p.attributes["sip.phoneNumber"].lstrip("+")
        direction = p.attributes["direction"]
        agent = VoiceAgent.from_json(await get_agent_by_phone(trunk_phone, direction))
        if direction == "inbound":
            # Register the SIP call
            call = Call.from_json(await register_inbound_call(phone, trunk_phone))
        elif direction == "outbound":
            call = Call.from_json(await get_call_by_id(p.attributes["callId"]))

    if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD:
        meta = json.loads(ctx.job.metadata or "{}")
        agent_id = meta["agentId"]
        user_id = meta["userId"]
        call_id = meta["callId"]
        agent = VoiceAgent.from_json(await get_agent_by_id(agent_id, user_id))
        call = Call.from_json(await get_call_by_id(call_id))
    pass

    if not agent:
        raise ValueError("No agent found for the participant.")
    if not call:
        raise ValueError("No call found for the participant.")
    return call, agent, is_web_call


async def entrypoint(ctx: agents.JobContext):
    lk_api = LiveKitAPI()

    async def participant_entry(ctx: JobContext, p: rtc.RemoteParticipant):
        if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            direction = p.attributes["direction"]
            fromNumber = p.attributes["sip.phoneNumber"].lstrip("+")
            toNumber = p.attributes["sip.trunkPhoneNumber"].lstrip("+")
            if direction == "inbound":
                # Register the SIP call
                await register_inbound_call(fromNumber, toNumber)
                logger.info(f"Registered inbound call from {fromNumber} to {toNumber}")
                pass

    ctx.add_participant_entrypoint(participant_entry)
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    participant = await ctx.wait_for_participant()
    logger.info(f"attributes: {participant.attributes} metadata: {ctx.job.metadata}")
    payload = get_worker_payload(ctx, participant)

    call, agent, is_web_call = await load(ctx, participant)
    logger.info(f"call: {call}, agent: {agent}, is_web_call: {is_web_call}")

    logger.info(f"worker_payload: {payload}")

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
    def _on_close(ev: CloseEvent):
        # asyncio.create_task(application.on_close())
        # update call status to successful
        # await update_call()
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
