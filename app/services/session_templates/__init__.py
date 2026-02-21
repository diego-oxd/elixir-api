"""Registry of session type prompt templates."""

from typing import Callable

from app.models.session_types import SessionType

from .general import general_template
from .new_feature import new_feature_template

registry: dict[SessionType, Callable[[str], str]] = {
    SessionType.GENERAL: general_template,
    SessionType.NEW_FEATURE: new_feature_template,
}


def get_template_for_type(session_type: SessionType) -> Callable[[str], str]:
    """Get the template function for a given session type.

    Raises:
        ValueError: If session type is not registered
    """
    if session_type not in registry:
        raise ValueError(f"No template registered for session type: {session_type}")
    return registry[session_type]
