from quotacompass.adapters.claude_oauth import ClaudeOAuthAdapter
from quotacompass.adapters.cursor import CursorAdapter


def test_fixed_helper_adapter_marks_reauth_automatable() -> None:
    hint = ClaudeOAuthAdapter("claude").error_auth("auth_expired").reauth

    assert hint and hint.automatable


def test_command_only_adapter_does_not_offer_one_click_reauth() -> None:
    hint = CursorAdapter("cursor").error_auth("auth_expired").reauth

    assert hint and not hint.automatable
