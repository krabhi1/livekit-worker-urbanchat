import json
from typing import Optional
from livekit import agents, rtc
from livekit.agents import (
    AgentSession,
    AutoSubscribe,
    ErrorEvent,
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
)
from app.call_info import CallDisconnectReason, CallInfo, CallStatus

from app.assistant import Assistant
from app.usage_collector import AverageUsageCollector, UsageCollector
from app.voice_info import VoiceInfo
from sarvam import tts as sarvam
from livekit.api import LiveKitAPI

from app.logger import logger

import utils


def prewarm(job: JobProcess):
    job.userdata["vad"] = silero.VAD.load(
        min_speech_duration=0.03,
        min_silence_duration=0.3,
        prefix_padding_duration=0.3,
        activation_threshold=0.3,
    )


async def load(ctx: JobContext, p: rtc.RemoteParticipant):
    agent: Optional[VoiceInfo] = None
    call: Optional[CallInfo] = None
    is_web_call = p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD
    if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
        trunk_phone = p.attributes["sip.trunkPhoneNumber"].lstrip("+")
        phone = p.attributes["sip.phoneNumber"].lstrip("+")
        direction = p.attributes["direction"]
        agent = VoiceInfo.from_json(await get_agent_by_phone(trunk_phone, direction))
        if direction == "inbound":
            # Register the SIP call
            call = CallInfo.from_json(await register_inbound_call(phone, trunk_phone))
        elif direction == "outbound":
            call = CallInfo.from_json(await get_call_by_id(p.attributes["callId"]))

    if p.kind == rtc.ParticipantKind.PARTICIPANT_KIND_STANDARD:
        meta = json.loads(ctx.job.metadata or "{}")
        agent_id = meta["agentId"]
        user_id = meta["userId"]
        call_id = meta["callId"]
        agent = VoiceInfo.from_json(await get_agent_by_id(agent_id, user_id))
        call = CallInfo.from_json(await get_call_by_id(call_id))
    pass

    if not agent:
        raise ValueError("No agent found for the participant.")
    if not call:
        raise ValueError("No call found for the participant.")
    return call, agent, is_web_call


async def entrypoint(ctx: agents.JobContext):
    lk_api = LiveKitAPI()
    is_call_ended = False
    usage_collector = AverageUsageCollector()

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(p: rtc.RemoteParticipant):
        nonlocal is_call_ended
        logger.info(f"Participant disconnected: {p} {p.attributes}")
        is_call_ended = True
        on_call_end("user_hangup")

    async def on_shutdown(reason: str):
        logger.info(f"shutdown hook called {reason}")
        if is_call_ended:
            return
        on_call_end("unknown")

    ctx.add_shutdown_callback(on_shutdown)
    # ctx.add_participant_entrypoint(participant_entry)
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    participant = await ctx.wait_for_participant()
    logger.info(f"attributes: {participant.attributes} metadata: {ctx.job.metadata}")

    call, agent, is_web_call = await load(ctx, participant)
    logger.info(f"call: {call}, agent: {agent}, is_web_call: {is_web_call}")

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

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        usage_collector.collect(ev.metrics)

    @session.on("close")
    def _on_close(ev: CloseEvent):
        nonlocal is_call_ended
        if is_call_ended:
            return
        is_call_ended = True
        on_call_end("agent_hangup")
        logger.info(f"Session closed {ev}")
        ctx.delete_room()

    @session.on("error")
    def _on_error(ev: ErrorEvent):
        logger.error(f"Session error: {ev.error}")

    def on_call_ongoing():
        # update status to ongoing
        call.call_status = CallStatus.ONGOING
        call.call_start_time = utils.timestamp()
        # start time
        logger.info("Call is active")
        asyncio.create_task(call.update())

    def on_call_end(reason: str):
        # get transcript
        history = session.history.to_dict()
        transcript = json.dumps(history)

        # TODO calcuate cost
        # TODO recording url
        call.call_status = CallStatus.ENDED
        call.call_end_time = utils.timestamp()
        call.call_disconnect_reason = CallDisconnectReason(reason)
        call.transcript = transcript
        # total_latency = eou.end_of_utterance_delay + llm.ttft + tts.ttfb
        # update lantency info "eou.eud llm.ttft tts.ttfb"
        call.latency = usage_collector.get_latency()

        logger.info(f"Call ended: {reason}")
        asyncio.create_task(call.update())

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
    on_call_ongoing()
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
