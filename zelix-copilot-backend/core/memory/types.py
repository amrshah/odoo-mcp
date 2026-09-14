"""Memory Types.

Defines supported structured memory classifications.
"""

from enum import Enum


class MemoryType(str, Enum):
    """Classifications for persistent knowledge."""

    FACT = "FACT"
    PREFERENCE = "PREFERENCE"
    DECISION = "DECISION"
    COMMITMENT = "COMMITMENT"
    OBSERVATION = "OBSERVATION"
