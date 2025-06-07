from dataclasses import dataclass
from typing import Optional
from enum import Enum

from livekit import rtc
from livekit.agents import JobContext

from utils import WorkerPayload
from app.api import get_agent_by_phone, get_agent_by_id


# Enums for providers and other attributes
class TTSProvider(str, Enum):
    openai = "openai"
    elevenlabs = "elevenlabs"
    sarvam = "sarvam"
    smallest = "smallest"
    deepgram = "deepgram"


class STTProvider(str, Enum):
    openai = "openai"
    deepgram = "deepgram"


class LLMProvider(str, Enum):
    openai = "openai"
    google = "google"
    deepseek = "deepseek"


@dataclass
class VoiceAgent:
    id: str
    name: str
    language: str
    end_call_after_silence_in_sec: int
    maximum_call_duration_in_sec: int

    # TTS attributes
    tts_provider: TTSProvider
    tts_model: str
    tts_voice_id: str
    tts_speed: float
    tts_temperature: float
    tts_volume: float

    # STT attributes
    stt_provider: STTProvider
    stt_model: str

    # LLM attributes
    llm_provider: LLMProvider
    llm_model: str
    llm_temperature: float
    llm_max_tokens: int
    llm_general_prompt: str
    llm_begin_message: Optional[str]

    # Ambient sound attributes
    ambient_sound: Optional[str]
    ambient_sound_volume: float

    # Relations
    user_id: str

    @staticmethod
    def from_json(data: dict):
        return VoiceAgent(
            id=data["id"],
            user_id=data["userId"],
            name=data["name"],
            language=data["language"],
            end_call_after_silence_in_sec=data["endCallAfterSilenceInSec"],
            maximum_call_duration_in_sec=data["maximumCallDurationInSec"],
            tts_provider=TTSProvider(data["ttsProvider"]),
            tts_model=data["ttsModel"],
            tts_voice_id=data["ttsVoiceId"],
            tts_speed=data["ttsSpeed"],
            tts_temperature=data["ttsTemperature"],
            tts_volume=data["ttsVolume"],
            stt_provider=STTProvider(data["sttProvider"]),
            stt_model=data["sttModel"],
            llm_provider=LLMProvider(data["llmProvider"]),
            llm_model=data["llmModel"],
            llm_temperature=data["llmTemperature"],
            llm_max_tokens=data["llmMaxTokens"],
            llm_general_prompt=data["llmGeneralPrompt"],
            llm_begin_message=data["llmBeginMessage"],
            ambient_sound=data["ambientSound"],
            ambient_sound_volume=data["ambientSoundVolume"],
        )
