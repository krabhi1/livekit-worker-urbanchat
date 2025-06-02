from dataclasses import dataclass
from typing import Optional
from enum import Enum


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


agentInfo = VoiceAgent(
    id="agent_001",
    name="Voice Assistant",
    language="en-US",
    end_call_after_silence_in_sec=5,
    maximum_call_duration_in_sec=3600,
    tts_provider=TTSProvider.openai,
    tts_model="text-davinci-003",
    tts_voice_id="default",
    tts_speed=1.0,
    tts_temperature=0.7,
    tts_volume=1.0,
    stt_provider=STTProvider.openai,
    stt_model="whisper-1",
    llm_provider=LLMProvider.openai,
    llm_model="gpt-3.5-turbo",
    llm_temperature=0.7,
    llm_max_tokens=1500,
    llm_general_prompt="You are a helpful assistant.",
    llm_begin_message=None,
    ambient_sound=None,
    ambient_sound_volume=0.5,
    user_id="user_123",
)

print(agentInfo)
