from copy import deepcopy
from attr import dataclass
from .logger import logger
from livekit.agents.metrics import (
    AgentMetrics,
    EOUMetrics,
    LLMMetrics,
    TTSMetrics,
)


@dataclass
class UsageSummary:
    llm_prompt_tokens: int
    llm_prompt_cached_tokens: int
    llm_completion_tokens: int
    tts_characters_count: int
    # time
    # stt_audio_duration: float
    tts_ttfb: float = 0.0
    llm_ttft: float = 0.0
    eou_end_of_utterance_delay: float = 0.0


class UsageCollector:
    def __init__(self) -> None:
        self._summary = UsageSummary(0, 0, 0, 0, 0.0)

    def __call__(self, metrics: AgentMetrics) -> None:
        self.collect(metrics)

    def collect(self, metrics: AgentMetrics) -> None:
        if isinstance(metrics, EOUMetrics):
            if self._summary.eou_end_of_utterance_delay < metrics.end_of_utterance_delay:
                self._summary.eou_end_of_utterance_delay = metrics.end_of_utterance_delay
            logger.info(f"eou time {metrics.end_of_utterance_delay}")

        elif isinstance(metrics, LLMMetrics):
            self._summary.llm_prompt_tokens += metrics.prompt_tokens
            self._summary.llm_prompt_cached_tokens += metrics.prompt_cached_tokens
            self._summary.llm_completion_tokens += metrics.completion_tokens
            if self._summary.llm_ttft < metrics.ttft:
                self._summary.llm_ttft = metrics.ttft
            logger.info(f"llm time {metrics.ttft}")

        elif isinstance(metrics, TTSMetrics):
            self._summary.tts_characters_count += metrics.characters_count
            if self._summary.tts_ttfb < metrics.ttfb:
                self._summary.tts_ttfb = metrics.ttfb
            logger.info(f"tts time {metrics.ttfb}")

        # elif isinstance(metrics, RealtimeModelMetrics):
        #     self._summary.llm_prompt_tokens += metrics.input_tokens
        #     self._summary.llm_prompt_cached_tokens += (
        #         metrics.input_token_details.cached_tokens
        #     )
        #     self._summary.llm_completion_tokens += metrics.output_tokens
        #     # self._summary.llm_audio_duration += metrics.duration

        # elif isinstance(metrics, STTMetrics):
        #     self._summary.stt_audio_duration += metrics.audio_duration
        #     logger.info(f"stt time {metrics.audio_duration}")

    def get_summary(self) -> UsageSummary:
        return deepcopy(self._summary)

    def get_latency(self) -> str:
        return f"{self._summary.eou_end_of_utterance_delay:.2f} {self._summary.llm_ttft:.2f} {self._summary.tts_ttfb:.2f}"


class AverageUsageCollector:
    def __init__(self) -> None:
        self._summary = UsageSummary(0, 0, 0, 0, 0.0)

        # New internal counters
        self._eou_delays = []
        self._llm_ttfts = []
        self._tts_ttfbs = []

    def __call__(self, metrics: AgentMetrics) -> None:
        self.collect(metrics)

    def collect(self, metrics: AgentMetrics) -> None:
        if isinstance(metrics, EOUMetrics):
            self._eou_delays.append(metrics.end_of_utterance_delay)
            logger.info(f"eou time {metrics.end_of_utterance_delay}")

        elif isinstance(metrics, LLMMetrics):
            self._summary.llm_prompt_tokens += metrics.prompt_tokens
            self._summary.llm_prompt_cached_tokens += metrics.prompt_cached_tokens
            self._summary.llm_completion_tokens += metrics.completion_tokens
            self._llm_ttfts.append(metrics.ttft)
            logger.info(f"llm time {metrics.ttft}")

        elif isinstance(metrics, TTSMetrics):
            self._summary.tts_characters_count += metrics.characters_count
            self._tts_ttfbs.append(metrics.ttfb)
            logger.info(f"tts time {metrics.ttfb}")

    def get_summary(self) -> UsageSummary:
        # Compute averages
        self._summary.eou_end_of_utterance_delay = (
            sum(self._eou_delays) / len(self._eou_delays) if self._eou_delays else 0.0
        )
        self._summary.llm_ttft = (
            sum(self._llm_ttfts) / len(self._llm_ttfts) if self._llm_ttfts else 0.0
        )
        self._summary.tts_ttfb = (
            sum(self._tts_ttfbs) / len(self._tts_ttfbs) if self._tts_ttfbs else 0.0
        )
        return deepcopy(self._summary)

    def get_latency(self) -> str:
        return f"{self._summary.eou_end_of_utterance_delay:.2f} {self._summary.llm_ttft:.2f} {self._summary.tts_ttfb:.2f}"
