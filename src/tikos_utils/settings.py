import os
from typing import ClassVar

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from .esc import EscOpenError, open_environment_variables


class TikosBaseSettings(BaseSettings):
    """Subclass this, declare `esc_environment` and required fields, then call `.load()`.

    Precedence: explicit constructor/test override > real process env > Pulumi ESC > field
    default.
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

            merged = {**esc_values, **os.environ}
            try:
                instance = cls(**merged)
            except ValidationError as exc2:
                still_missing = sorted(_missing_fields(exc2))
                raise RuntimeError(
                    f"Missing required settings for ESC environment "
                    f"'{cls.esc_environment}': {', '.join(still_missing)}."
                ) from exc2

            for key, value in esc_values.items():
                os.environ.setdefault(key, value)

        cls._cache = instance
        return instance

    @classmethod
    def _clear_cache(cls) -> None:
        cls._cache = None


def _missing_fields(exc: ValidationError) -> set[str]:
    return {str(err["loc"][0]) for err in exc.errors() if err["type"] == "missing"}
