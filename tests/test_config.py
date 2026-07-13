from pathlib import Path

import pytest
from pydantic import ValidationError

from quotacompass.core.config import AppConfig, load_config


def test_defaults_are_local_and_polite() -> None:
    config = AppConfig()
    assert config.server.host == "127.0.0.1"
    assert config.poll.default_interval_minutes >= 5
    assert config.security.reauth_trigger == "local"


def test_remote_reauth_requires_distinct_scoped_tokens() -> None:
    with pytest.raises(ValidationError, match="server.auth_token"):
        AppConfig.model_validate({"security": {"reauth_trigger": "remote"}})

    with pytest.raises(ValidationError, match="security.reauth_token"):
        AppConfig.model_validate(
            {
                "server": {"auth_token": "read-secret"},
                "security": {"reauth_trigger": "remote"},
            }
        )

    with pytest.raises(ValidationError, match="must differ"):
        AppConfig.model_validate(
            {
                "server": {"auth_token": "same-secret"},
                "security": {"reauth_trigger": "remote", "reauth_token": "same-secret"},
            }
        )

    config = AppConfig.model_validate(
        {
            "server": {"auth_token": "read-secret"},
            "security": {"reauth_trigger": "remote", "reauth_token": "reauth-secret"},
        }
    )
    assert config.security.reauth_token == "reauth-secret"


def test_non_loopback_requires_token() -> None:
    with pytest.raises(ValidationError, match="non-loopback"):
        AppConfig.model_validate({"server": {"host": "0.0.0.0"}})


def test_load_yaml(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("server:\n  port: 4888\n", encoding="utf-8")
    assert load_config(path).server.port == 4888
