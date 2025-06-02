from attr import dataclass
from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    RoomOutputOptions,
    metrics,
    JobContext,
    function_tool,
    RunContext,
)
from livekit.agents.metrics import (
    AgentMetrics,
    LLMMetrics,
    STTMetrics,
    TTSMetrics,
)
from livekit.plugins import (
    deepgram,
    openai,
    silero,
)
import logging
from sarvam import tts as sarvam
from itertools import chain
from copy import deepcopy
from utils import get_worker_payload

load_dotenv()
logger = logging.getLogger("@@@my-worker")
logger.setLevel(logging.INFO)


@dataclass
class UsageSummary:
    llm_prompt_tokens: int
    llm_prompt_cached_tokens: int
    llm_completion_tokens: int
    tts_characters_count: int
    stt_audio_duration: float
    tts_audio_duration: float = 0.0
    llm_audio_duration: float = 0.0


class UsageCollector:
    def __init__(self) -> None:
        self._summary = UsageSummary(0, 0, 0, 0, 0.0)

    def __call__(self, metrics: AgentMetrics) -> None:
        self.collect(metrics)

    def collect(self, metrics: AgentMetrics) -> None:
        if isinstance(metrics, LLMMetrics):
            self._summary.llm_prompt_tokens += metrics.prompt_tokens
            self._summary.llm_prompt_cached_tokens += metrics.prompt_cached_tokens
            self._summary.llm_completion_tokens += metrics.completion_tokens
            self._summary.llm_audio_duration += metrics.duration
            logger.info(f"llm time {metrics.duration}")

        # elif isinstance(metrics, RealtimeModelMetrics):
        #     self._summary.llm_prompt_tokens += metrics.input_tokens
        #     self._summary.llm_prompt_cached_tokens += (
        #         metrics.input_token_details.cached_tokens
        #     )
        #     self._summary.llm_completion_tokens += metrics.output_tokens
        #     # self._summary.llm_audio_duration += metrics.duration

        elif isinstance(metrics, TTSMetrics):
            self._summary.tts_characters_count += metrics.characters_count
            self._summary.tts_audio_duration += metrics.audio_duration
            logger.info(f"tts time {metrics.audio_duration}")

        elif isinstance(metrics, STTMetrics):
            self._summary.stt_audio_duration += metrics.audio_duration
            logger.info(f"stt time {metrics.audio_duration}")

    def get_summary(self) -> UsageSummary:
        return deepcopy(self._summary)


@dataclass
class AgentInfo:
    id: str
    name: str
    language: str
    endCallAfterSilenceInSec: int
    maximumCallDurationInSec: int
    ttsProvider: str
    ttsModel: str


def prewarm(job: JobProcess):
    job.userdata["vad"] = silero.VAD.load()


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

    logger.info("--info:room_stats-- %s", list)


# Add any cleanup code here
class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(instructions="You are a helpful voice AI assistant.")

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


async def entrypoint(ctx: agents.JobContext):
    print("-----------init-------")

    @ctx.room.on("connected")
    def on_connected():
        logger.info("--Connected to the room!")

    @ctx.room.on("disconnected")
    def on_disconnected():
        logger.info("--Disconnected from the room!")

    # @ctx.room.on("participant_connected")
    # def on_participant_connected(participant):
    #     logger.info(f"--Participant connected: {participant}")
    #

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
        tts=sarvam.TTS(
            speaker="meera", target_language_code="en-IN", model="bulbul:v1"
        ),
        # tts=openai.TTS(),
        vad=ctx.proc.userdata["vad"],
    )

    usage_collector = UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        usage_collector.collect(ev.metrics)

    @session.on("close")
    def _on_close():
        logger.info("Session closed")

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
    logger.info("Session started")

    # session.generate_reply(instructions="Greet the user and offer your assistance.")
    session.say("Hello! How can I assist you today?")

    # while True:
    #     await room_stats(ctx)
    #     await asyncio.sleep(3)


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name="urbanchat-agent",
            shutdown_process_timeout=20,
        )
    )
