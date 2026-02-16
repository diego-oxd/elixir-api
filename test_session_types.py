"""Quick test to verify session types implementation."""

from app.models.session_types import SessionType
from app.services.prompt_templates import get_template_for_type


def test_general_template():
    """Test general session template."""
    template_func = get_template_for_type(SessionType.GENERAL)
    message = "What is this codebase about?"
    result = template_func(message)
    assert result == message, "General template should return message as-is"
    print("✓ General template test passed")


def test_new_feature_template():
    """Test new feature session template."""
    template_func = get_template_for_type(SessionType.NEW_FEATURE)
    requirements = "Add JWT authentication with refresh tokens"
    result = template_func(requirements)

    # Verify requirements are injected
    assert requirements in result, "Requirements should be in template"
    assert "Feature Implementation Guide" in result, "Should contain template header"
    assert "Affected Components" in result, "Should contain template sections"
    print("✓ New feature template test passed")
    print(f"  Template length: {len(result)} characters")


def test_session_types():
    """Test session type enum."""
    assert SessionType.GENERAL.value == "general"
    assert SessionType.NEW_FEATURE.value == "new_feature"

    # Test string conversion
    assert SessionType("general") == SessionType.GENERAL
    assert SessionType("new_feature") == SessionType.NEW_FEATURE
    print("✓ SessionType enum test passed")


if __name__ == "__main__":
    test_session_types()
    test_general_template()
    test_new_feature_template()
    print("\n✅ All tests passed!")
