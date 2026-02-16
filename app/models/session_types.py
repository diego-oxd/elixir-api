"""Session type definitions."""

from enum import Enum


class SessionType(str, Enum):
    """Types of sessions with different behaviors."""

    GENERAL = "general"
    NEW_FEATURE = "new_feature"
