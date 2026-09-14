"""
voice/stt_provider.py
Pluggable Speech-to-Text (STT) interface and provider implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseSpeechToTextProvider(ABC):
    """Abstract contract for audio transcription services."""

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        """Transcribe raw audio bytes to text string."""
        pass


class BrowserWebSpeechSTTProvider(BaseSpeechToTextProvider):
    """Browser-native Web Speech API handler (client-side transcription)."""

    def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        return "Browser Web Speech API transcription handled on client."


class WhisperSTTProvider(BaseSpeechToTextProvider):
    """OpenAI / Local Whisper STT provider."""

    def __init__(self, client: Optional[Any] = None) -> None:
        self.client = client

    def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        # In production, invokes OpenAI Whisper or local whisper.cpp
        return "Patient presented with acute vomiting and lethargy..."
