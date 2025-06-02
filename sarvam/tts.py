from __future__ import annotations
from typing import Literal

import asyncio
import base64
import io
import os
import wave
from dataclasses import dataclass

import aiohttp

from livekit import rtc
from livekit.agents import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    tts,
    utils,
    APIConnectOptions,
    DEFAULT_API_CONNECT_OPTIONS,
)

import logging

logger = logging.getLogger("sarvam")

TTSEncoding = Literal["wav",]

TTSModels = Literal["bulbul:v1", "bulbul:v2"]
TTSLanguages = Literal[
    "te-IN", "en-IN", "gu-IN", "kn-IN", "ml-IN", "od-IN", "pa-IN", "ta-IN"
]

TTSVoices = Literal[
    "Diya",
    "Maya",
    "Meera",
    "Pavithra",
    "Maitreyi",
    "Misha",
    "Amol",
    "Arjun",
    "Amartya",
    "Arvind",
    "Neel",
    "Vian",
]


SARVAM_TTS_BASE_URL = "https://api.sarvam.ai/text-to-speech"

# Sarvam TTS specific models and speakers
SarvamTTSModels = Literal["bulbul:v1", "bulbul:v2"]
SarvamTTSSpeakers = Literal[
    # bulbul:v1 Female (lowercase)
    "diya",
    "maya",
    "meera",
    "pavithra",
    "maitreyi",
    "misha",
    # bulbul:v1 Male (lowercase)
    "amol",
    "arjun",
    "amartya",
    "arvind",
    "neel",
    "vian",
    # bulbul:v2 Female (lowercase)
    "anushka",
    "manisha",
    "vidya",
    "arya",
    # bulbul:v2 Male (lowercase)
    "abhilash",
    "karun",
    "hitesh",
]


@dataclass
class _TTSOptions:
    """Options for the Sarvam.ai TTS service.

    Args:
        target_language_code: BCP-47 language code, e.g., "hi-IN"
        text: The text to synthesize (will be provided by stream adapter)
        speaker: Voice to use for synthesis
        pitch: Voice pitch adjustment (-20.0 to 20.0)
        pace: Speech rate multiplier (0.5 to 2.0)
        loudness: Volume multiplier (0.5 to 2.0)
        speech_sample_rate: Audio sample rate (8000, 16000, 22050, or 24000)
        enable_preprocessing: Whether to use text preprocessing
        model: The Sarvam TTS model to use
        api_key: Sarvam.ai API key
        base_url: API endpoint URL
    """

    target_language_code: str  # BCP-47, e.g., "hi-IN"
    text: str | None = None  # Will be provided by the stream adapter
    speaker: SarvamTTSSpeakers | str = "misha"  # Default speaker
    pitch: float = 0.0
    pace: float = 1.0
    loudness: float = 1.0
    speech_sample_rate: int = 22050  # Default 22050 Hz
    enable_preprocessing: bool = False
    model: SarvamTTSModels | str = (
        "bulbul:v2"  # Default to v2 as it has more recent speakers
    )
    api_key: str | None = None
    base_url: str = SARVAM_TTS_BASE_URL


class TTS(tts.TTS):
    """Sarvam.ai Text-to-Speech implementation.

    This class provides text-to-speech functionality using the Sarvam.ai API.
    Sarvam.ai specializes in high-quality TTS for Indian languages.

    Args:
        target_language_code: BCP-47 language code, e.g., "hi-IN"
        model: Sarvam TTS model to use
        speaker: Voice to use for synthesis
        speech_sample_rate: Audio sample rate in Hz
        num_channels: Number of audio channels (Sarvam outputs mono)
        pitch: Voice pitch adjustment (-20.0 to 20.0)
        pace: Speech rate multiplier (0.5 to 2.0)
        loudness: Volume multiplier (0.5 to 2.0)
        enable_preprocessing: Whether to use text preprocessing
        api_key: Sarvam.ai API key (falls back to SARVAM_API_KEY env var)
        base_url: API endpoint URL
        http_session: Optional aiohttp session to use
    """

    def __init__(
        self,
        *,
        target_language_code: str,
        model: SarvamTTSModels | str = "bulbul:v2",
        speaker: SarvamTTSSpeakers | str = "meera",
        speech_sample_rate: int = 22050,
        num_channels: int = 1,  # Sarvam output is mono WAV
        pitch: float = 0.0,
        pace: float = 1.0,
        loudness: float = 1.0,
        enable_preprocessing: bool = False,
        api_key: str | None = None,
        base_url: str = SARVAM_TTS_BASE_URL,
        http_session: aiohttp.ClientSession | None = None,
    ) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=speech_sample_rate,
            num_channels=num_channels,
        )

        self._api_key = api_key or os.environ.get("SARVAM_API_KEY")
        if not self._api_key:
            raise ValueError(
                "Sarvam API key is required. Provide it directly or set SARVAM_API_KEY env var."
            )

        self._opts = _TTSOptions(
            target_language_code=target_language_code,
            model=model,
            speaker=speaker,
            speech_sample_rate=speech_sample_rate,
            pitch=pitch,
            pace=pace,
            loudness=loudness,
            enable_preprocessing=enable_preprocessing,
            api_key=self._api_key,
            base_url=base_url,
        )
        self._session = http_session
        self._logger = logger.getChild(self.__class__.__name__)

    def _ensure_session(self) -> aiohttp.ClientSession:
        if not self._session:
            self._session = utils.http_context.http_session()
        return self._session

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> ChunkedStream:
        return ChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
            session=self._ensure_session(),
            opts=self._opts,
        )


class ChunkedStream(tts.ChunkedStream):
    """Synthesize using the Sarvam.ai API in chunks (LiveKit compatible)."""

    def __init__(
        self,
        *,
        tts: TTS,
        input_text: str,
        opts: _TTSOptions,
        conn_options: APIConnectOptions,
        session: aiohttp.ClientSession,
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._tts = tts
        self._session = session
        self._opts = opts

    async def _run(self) -> None:
        # Prepare payload and headers as in _synthesize_impl
        opts = self._tts._opts
        payload = {
            "target_language_code": opts.target_language_code,
            "text": self._input_text,
            "speaker": opts.speaker,
            "pitch": opts.pitch,
            "pace": opts.pace,
            "loudness": opts.loudness,
            "speech_sample_rate": opts.speech_sample_rate,
            "enable_preprocessing": opts.enable_preprocessing,
            "model": opts.model,
        }
        headers = {
            "api-subscription-key": opts.api_key,
            "Content-Type": "application/json",
        }
        _request_id = ""
        try:
            async with self._session.post(
                url=self._opts.base_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20.0),  # Adjust timeout as needed
            ) as res:
                if res.status != 200:
                    error_text = await res.text()
                    raise APIStatusError(
                        message=f"Sarvam TTS API Error: {error_text}",
                        status_code=res.status,
                    )

                response_json = await res.json()
                _request_id = response_json.get("request_id", "")  # Store request_id

                # Sarvam returns a list of base64 audios, we'll take the first one.
                if (
                    not response_json.get("audios")
                    or not isinstance(response_json["audios"], list)
                    or len(response_json["audios"]) == 0
                ):
                    raise APIConnectionError(
                        "Sarvam TTS API response invalid: no audio data"
                    )

                base64_wav = response_json["audios"][0]
                wav_bytes = base64.b64decode(base64_wav)
                logger.debug("------- %s %d", self._input_text, len(base64_wav))

                # Parse WAV and generate AudioFrames
                # Standard frame duration for WebRTC is 20ms, but can be 10ms. Let's use 20ms.
                frame_duration_ms = 20

                with io.BytesIO(wav_bytes) as wav_io:
                    with wave.open(wav_io, "rb") as wf:
                        sample_rate = wf.getframerate()
                        num_channels = wf.getnchannels()
                        sample_width = wf.getsampwidth()  # Bytes per sample

                        if sample_rate != self._opts.speech_sample_rate:
                            # self._logger.warning(
                            #     f"Sarvam TTS output sample rate {sample_rate} differs "
                            #     f"from requested {self._opts.speech_sample_rate}"
                            # )

                            # Use actual sample rate from WAV for frame calculation
                            pass
                        samples_per_channel_val = (
                            sample_rate * frame_duration_ms
                        ) // 1000  # Renamed for clarity
                        # For mono, samples_per_channel_val is samples_per_frame.
                        # If stereo, it would be samples_per_frame / num_channels.
                        # Since num_channels is 1, samples_per_channel_val is correct here.

                        bytes_per_frame = (
                            samples_per_channel_val * num_channels * sample_width
                        )

                        emitter = tts.SynthesizedAudioEmitter(
                            event_ch=self._event_ch,
                            request_id=_request_id,
                        )

                        while True:
                            frame_data = wf.readframes(
                                samples_per_channel_val
                            )  # Read based on samples per channel
                            if not frame_data:
                                break

                            current_length = len(frame_data)
                            if current_length < bytes_per_frame:
                                # Pad with silence (zeros)
                                padding_needed = bytes_per_frame - current_length
                                frame_data += b"\x00" * padding_needed

                            audio_frame = rtc.AudioFrame(
                                data=frame_data,
                                sample_rate=sample_rate,  # Use actual sample rate from WAV
                                num_channels=num_channels,
                                samples_per_channel=samples_per_channel_val,
                            )
                            # yield tts.SynthesizedAudio(
                            #     request_id=_request_id, frame=audio_frame
                            # )
                            # self._event_ch.send_nowait(
                            #     tts.SynthesizedAudio(
                            #         request_id=_request_id, frame=audio_frame
                            #     )
                            # )
                            emitter.push(audio_frame)
                        emitter.flush()

        except asyncio.TimeoutError as e:
            raise APITimeoutError("Sarvam TTS API request timed out") from e
        except aiohttp.ClientError as e:
            raise APIConnectionError(f"Sarvam TTS API connection error: {e}") from e
        except Exception as e:
            raise APIConnectionError(f"Unexpected error in Sarvam TTS: {e}") from e
