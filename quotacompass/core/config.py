from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from platformdirs import user_config_path, user_state_path
from pydantic import BaseModel, Field, model_validator


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=4747, ge=1, le=65535)
    auth_token: str | None = None


class SecurityConfig(BaseModel):
    reauth_trigger: Literal["local", "remote", "off"] = "local"
    reauth_token: str | None = None


class PollConfig(BaseModel):
    default_interval_minutes: int = Field(default=15, ge=5)
    concurrency: int = Field(default=4, ge=1, le=32)


class StateConfig(BaseModel):
    dir: Path | None = None
    history_retention_days: int = Field(default=90, ge=1)


class NudgeThreshold(BaseModel):
    unused_pct: float = Field(default=25, ge=0, le=100)
    within_hours: float = Field(default=24, gt=0)


class AdvisorConfig(BaseModel):
    nudge_threshold: NudgeThreshold = Field(default_factory=NudgeThreshold)
    task_weights: dict[str, dict[str, float]] = Field(default_factory=dict)


class ProviderConfig(BaseModel):
    adapter: str
    label: str | None = None
    enabled: bool = True
    priority: float = Field(default=1.0, ge=0)
    linked_account: str | None = None
    support_tier: Literal["stable", "beta", "experimental"] | None = None
    options: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class AppConfig(BaseModel):
    timezone: str = "UTC"
    server: ServerConfig = Field(default_factory=ServerConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    poll: PollConfig = Field(default_factory=PollConfig)
    state: StateConfig = Field(default_factory=StateConfig)
    reserved_ports: list[int] = Field(default_factory=list)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    advisor: AdvisorConfig = Field(default_factory=AdvisorConfig)

    @model_validator(mode="after")
    def remote_reauth_requires_token(self) -> AppConfig:
        if self.security.reauth_trigger == "remote":
            if not self.server.auth_token:
                raise ValueError("remote reauth requires server.auth_token")
            if not self.security.reauth_token:
                raise ValueError("remote reauth requires security.reauth_token")
            if self.security.reauth_token == self.server.auth_token:
                raise ValueError("security.reauth_token must differ from server.auth_token")
        if self.server.host not in {"127.0.0.1", "localhost", "::1"} and not self.server.auth_token:
            raise ValueError("non-loopback server binding requires server.auth_token")
        return self


def default_config_path() -> Path:
    override = os.getenv("QUOTACOMPASS_CONFIG")
    return (
        Path(override).expanduser()
        if override
        else user_config_path("quotacompass") / "config.yaml"
    )


def default_state_dir() -> Path:
    override = os.getenv("QUOTACOMPASS_STATE_DIR")
    return Path(override).expanduser() if override else user_state_path("quotacompass")


def load_config(path: Path | None = None, *, allow_missing: bool = True) -> AppConfig:
    config_path = path or default_config_path()
    if not config_path.exists():
        if allow_missing:
            return AppConfig()
        raise FileNotFoundError(config_path)
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config = AppConfig.model_validate(data)
    if config.state.dir is not None:
        config.state.dir = config.state.dir.expanduser()
    return config


def resolved_state_dir(config: AppConfig) -> Path:
    return config.state.dir or default_state_dir()
