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
    voice,
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
from app.call_info import CallInfo, CallStatus

from app.assistant import Assistant
from app.usage_collector import AverageUsageCollector
from app.voice_info import TTSProvider, VoiceInfo
from sarvam import tts as sarvam
from livekit.api import LiveKitAPI

from app.logger import logger

import utils


BASE_PROMPT = """
You are a real-time voice assistant speaking to users over a phone or voice call.

Behavior:
- Speak naturally and conversationally, like a human agent.
- Keep responses short and to the point, ideally 1–2 sentences at a time.
- Be polite, professional, and patient at all times.
- Respond based on what the user just said — avoid giving long monologues.
- Listen carefully, even if the user is confused, emotional, or frustrated.

Voice Tone:
- Friendly and calm
- Clear and confident
- Not overly formal or robotic

Instructions:
- Greet the user at the beginning of the call.
- Ask clarifying questions if you're unsure what the user meant.
- Offer help, information, or next steps as appropriate.
- End the call politely once the conversation is finished or the user hangs up.

Rules:
- Never interrupt the user while they are speaking.
- Don’t make up answers. Say “I’m not sure about that” if needed.
- Avoid repeating the same phrases frequently.
- Do not mention that you are an AI or voice assistant unless asked directly.
- Always respond in {language_name}

Language: {language_name}
"""


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
    call = None
    session = None

    def on_call_end(reason: str):
        nonlocal is_call_ended
        if is_call_ended:
            return
        is_call_ended = True

        if call:
            try:
                transcript = None
                if session:
                    try:
                        history = session.history.to_dict()
                        transcript = json.dumps(history)
                    except Exception as e:
                        logger.warning(f"Could not get transcript: {e}")

                call.call_status = CallStatus.ENDED
                call.call_end_time = utils.timestamp()
                call.call_disconnect_reason = reason
                call.transcript = transcript
                call.latency = usage_collector.get_latency()

                logger.info(f"Call ended: {reason}")
                asyncio.create_task(call.update())

            except Exception:
                logger.exception("Failed during call end cleanup")
        else:
            logger.warning(f"Call not initialized, but on_call_end triggered. Reason: {reason}")

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(p: rtc.RemoteParticipant):
        logger.info(f"Participant disconnected: {p} {p.attributes}")
        on_call_end("user_hangup")

    async def on_shutdown(reason: str):
        logger.info(f"Shutdown hook called: {reason}")
        if not is_call_ended:
            on_call_end("unknown")

    ctx.add_shutdown_callback(on_shutdown)

    try:
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

        participant = await ctx.wait_for_participant()
        logger.info(f"attributes: {participant.attributes} metadata: {ctx.job.metadata}")

        call, agent, is_web_call = await load(ctx, participant)
        logger.info(f"call: {call}, agent: {agent}, is_web_call: {is_web_call}")

        if agent.tts_provider == TTSProvider.sarvam:
            language = {
                "hi": "hi-IN",
                "en": "en-IN",
            }[agent.language]
            tts = sarvam.TTS(
                speaker=agent.tts_voice_id,
                target_language_code=language,
                model=agent.tts_model,
                pace=agent.tts_speed,
                loudness=agent.tts_volume,
            )
        else:
            raise ValueError(f"Unsupported TTS provider: {agent.tts_provider}")

        session = AgentSession(
            stt=deepgram.STT(model="nova-3", language="multi"),
            llm=openai.LLM(model=agent.llm_model, temperature=agent.llm_temperature),
            tts=tts,
            vad=ctx.proc.userdata["vad"],
        )

        @session.on("metrics_collected")
        def _on_metrics_collected(ev: MetricsCollectedEvent):
            usage_collector.collect(ev.metrics)

        @session.on("close")
        def _on_close(ev: CloseEvent):
            logger.info(f"Session closed: {ev}")
            if ev.error:
                on_call_end(ev.error.type)
            else:
                on_call_end("unknown")
            ctx.delete_room()

        @session.on("error")
        def _on_error(ev: ErrorEvent):
            logger.error(f"Session error: {ev.error.type}")

        def on_call_ongoing():
            call.call_status = CallStatus.ONGOING
            call.call_start_time = utils.timestamp()
            logger.info("Call is active")
            asyncio.create_task(call.update())

        prompt = BASE_PROMPT.format(
            language_name=(
                "Hindi (hi-IN)"
                if agent.language == "hi"
                else "English (en-IN)"
                if agent.language == "en"
                else agent.language.capitalize()
            )
        )

        await session.start(
            room=ctx.room,
            agent=Assistant(
                voice_info=agent, instructions=f"{prompt}.\n{agent.llm_general_prompt}"
            ),
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
        # Register the call as ongoing
        on_call_ongoing()
        # beign message
        if agent.llm_begin_message is None:
            session.generate_reply(user_input="Welcome user with a greeting message.")
        elif agent.llm_begin_message != "":
            session.say(agent.llm_begin_message)

    except Exception:
        logger.exception("Unhandled exception in entrypoint")
        on_call_end("error")


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            shutdown_process_timeout=20,
        )
    )
