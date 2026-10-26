import logging
import os
from pathlib import Path
from typing import ClassVar

from dotenv import dotenv_values
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from .esc import EscOpenError, open_environment_variables

ENV_FILE_VARIABLE = "TIKOS_ENV_FILE"

logger = logging.getLogger(__name__)


class TikosBaseSettings(BaseSettings):
    """Subclass this, declare `esc_environment` and required fields, then call `.load()`.

    Precedence: explicit constructor/test override > real process env > `.env` > Pulumi ESC >
    field default. The `.env` is the working directory's, or the file `TIKOS_ENV_FILE` names; an
    empty `TIKOS_ENV_FILE` turns it off.
    """

    model_config = SettingsConfigDict(extra="ignore")

    esc_environment: ClassVar[str]

    _cache: ClassVar[BaseSettings | None] = None

    @classmethod
    def load(cls) -> "TikosBaseSettings":
        if cls._cache is not None:
            return cls._cache

        _apply_env_file()
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


def _apply_env_file() -> None:
    path = os.environ.get(ENV_FILE_VARIABLE, ".env")
    if not path or not Path(path).is_file():
        return
    values = {key: value for key, value in dotenv_values(path).items() if value is not None}
    for key, value in values.items():
        os.environ.setdefault(key, value)
    if values:
        logger.info("Settings from %s: %s", path, ", ".join(sorted(values)))
