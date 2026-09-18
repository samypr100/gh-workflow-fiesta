"""Backend configuration, loaded from the environment."""

import functools

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_TIMEOUT_SECONDS = 10
MAX_TIMEOUT_SECONDS = 300


class Settings(BaseSettings):
    """Runtime configuration.

    Attributes:
        github_token: Fine-grained token scoped to the benchmark repository.
        github_owner: Owner of the repository benchmark runs execute in.
        github_repo: Name of that repository.
        github_ref: Git ref the dispatched workflow checks out and runs.
        token_secret: Key used to sign run tokens handed to the frontend.
        user_key_secret: Key used to derive a user key from a client address.
        leg_timeout_seconds: Per-leg time budget passed to the workflow.
        rate_limit_window_seconds: Window used when counting a user's recent runs.
        rate_limit_max_runs: Runs permitted per user within that window.
        run_token_ttl_seconds: Lifetime of a run token.
        interpreter_cache_ttl_seconds: Lifetime of the cached interpreter list.
        uv_executable: Path to the uv binary used to probe interpreters.
        cors_origins: Origins permitted to call the API from a browser.
        repo_is_public: Whether the benchmark repository is public. Public
            repositories get larger Linux and Windows runners, which changes
            the core count every leg is normalised to.
        debug: Whether to emit human-readable logs instead of JSON.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    github_token: SecretStr
    github_owner: str = "samypr100"
    github_repo: str = "gh-workflow-fiesta"
    github_ref: str = "dev"

    token_secret: SecretStr
    user_key_secret: SecretStr

    leg_timeout_seconds: int = Field(default=300, ge=MIN_TIMEOUT_SECONDS, le=MAX_TIMEOUT_SECONDS)
    rate_limit_window_seconds: int = Field(default=3600, ge=60)
    rate_limit_max_runs: int = Field(default=5, ge=1)
    run_token_ttl_seconds: int = Field(default=86_400, ge=300)
    interpreter_cache_ttl_seconds: int = Field(default=3600, ge=60)

    uv_executable: str = "uv"
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    repo_is_public: bool = False
    debug: bool = False


@functools.cache
def get_settings() -> Settings:
    """Return the process-wide settings.

    Returns:
        The settings, constructed once and reused.
    """
    return Settings()
