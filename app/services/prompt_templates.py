"""Prompt template registry for different session types."""

from typing import Callable

from app.models.session_types import SessionType
from app.services.new_feature_prompt import new_feature_prompt_template


def general_template(user_message: str) -> str:
    """General session template - returns message as-is.

    Args:
        user_message: The user's message

    Returns:
        The unmodified user message
    """
    return user_message


def new_feature_template(user_message: str) -> str:
    """New feature session template - injects requirements into template.

    Args:
        user_message: The user's feature requirements

    Returns:
        Formatted prompt with requirements injected
    """
    return new_feature_prompt_template.format(requirements=user_message)


# Template registry mapping session types to their template functions
TEMPLATE_REGISTRY: dict[SessionType, Callable[[str], str]] = {
    SessionType.GENERAL: general_template,
    SessionType.NEW_FEATURE: new_feature_template,
}


def get_template_for_type(session_type: SessionType) -> Callable[[str], str]:
    """Get the template function for a given session type.

    Args:
        session_type: The type of session

    Returns:
        Template function that takes user message and returns formatted prompt

    Raises:
        ValueError: If session type is not registered
    """
    if session_type not in TEMPLATE_REGISTRY:
        raise ValueError(f"No template registered for session type: {session_type}")
    return TEMPLATE_REGISTRY[session_type]
