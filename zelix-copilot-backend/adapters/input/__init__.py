"""Input adapters module."""

from adapters.input.api import APIInput
from adapters.input.text import TextInput
from adapters.input.voice import VoiceInput
from adapters.input.web import WebInput
from adapters.input.whatsapp import WhatsAppInput

__all__ = ["APIInput", "TextInput", "VoiceInput", "WebInput", "WhatsAppInput"]
