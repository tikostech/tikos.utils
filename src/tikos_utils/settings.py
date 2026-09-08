"""Pydantic settings base that auto-fetches from Pulumi ESC when required fields are missing."""

import os
from typing import ClassVar

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from .esc import EscOpenError, open_environment_variables


class TikosBaseSettings(BaseSettings):
    """Subclass this, declare `esc_environment` and required fields, then call `.load()`.

    Precedence: explicit constructor/test override > real process env > Pulumi ESC > field
    default. `.load()` tries process env + field defaults first (no Pulumi call at all if that
    already satisfies every required field - the common case once docker-compose or a cloud
    deployment has already injected everything); only on a missing field does it open ESC once,
    merge it in under real process env, and retry. The resolved instance is cached per class so
    repeated `.load()` calls never re-invoke Pulumi.
    """

    model_config = SettingsConfigDict(extra="ignore")

    esc_environment: ClassVar[str]

    _cache: ClassVar[BaseSettings | None] = None

    @classmethod
    def load(cls) -> "TikosBaseSettings":
        if cls._cache is not None:
            return cls._cache

        try:
            instance = cls()
        except ValidationError as exc:
            missing = _missing_fields(exc)
            if not missing:
                raise
            try:
                esc_values = open_environment_variables(cls.esc_environment)
            except EscOpenError as esc_exc:
                raise RuntimeError(str(esc_exc)) from esc_exc

            merged = {**esc_values, **os.environ}  # real process env still wins over ESC
            try:
                instance = cls(**merged)
            except ValidationError as exc2:
                still_missing = sorted(_missing_fields(exc2))
                raise RuntimeError(
                    f"Missing required settings for ESC environment "
                    f"'{cls.esc_environment}': {', '.join(still_missing)}."
                ) from exc2

        cls._cache = instance
        return instance

    @classmethod
    def _clear_cache(cls) -> None:
        """Test-only: force the next `.load()` to re-resolve instead of returning the cache."""
        cls._cache = None


def _missing_fields(exc: ValidationError) -> set[str]:
    return {str(err["loc"][0]) for err in exc.errors() if err["type"] == "missing"}
