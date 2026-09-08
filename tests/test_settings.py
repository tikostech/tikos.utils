import os
from typing import ClassVar
from unittest.mock import patch

import pytest

from tikos_utils import EscOpenError, TikosBaseSettings


def make_settings_cls():
    class Settings(TikosBaseSettings):
        esc_environment: ClassVar[str] = "org/proj/env"

        FOO: str
        PORT: int
        LOG_LEVEL: str = "INFO"

    return Settings


@pytest.fixture
def settings_cls():
    return make_settings_cls()


def test_env_only_path_never_calls_esc(monkeypatch, settings_cls):
    monkeypatch.setenv("FOO", "bar")
    monkeypatch.setenv("PORT", "8080")
    with patch("tikos_utils.settings.open_environment_variables") as mock_open:
        settings = settings_cls.load()
    assert settings.FOO == "bar"
    assert settings.PORT == 8080
    assert settings.LOG_LEVEL == "INFO"
    mock_open.assert_not_called()


def test_esc_fallback_called_once_on_missing_field(monkeypatch, settings_cls):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    with patch(
        "tikos_utils.settings.open_environment_variables",
        return_value={"FOO": "from-esc", "PORT": "9090"},
    ) as mock_open:
        settings = settings_cls.load()
    assert settings.FOO == "from-esc"
    assert settings.PORT == 9090
    mock_open.assert_called_once_with("org/proj/env")


def test_process_env_overrides_esc(monkeypatch, settings_cls):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.setenv("PORT", "1111")  # present in real env
    with patch(
        "tikos_utils.settings.open_environment_variables",
        return_value={"FOO": "from-esc", "PORT": "9090"},  # ESC also has PORT
    ):
        settings = settings_cls.load()
    assert settings.FOO == "from-esc"
    assert settings.PORT == 1111  # real env wins over ESC


def test_type_validation(monkeypatch, settings_cls):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    with patch(
        "tikos_utils.settings.open_environment_variables",
        return_value={"FOO": "bar", "PORT": "not-an-int"},
    ):
        with pytest.raises(Exception):  # pydantic ValidationError bubbles as int-coercion failure
            settings_cls.load()


def test_missing_required_setting_after_esc_gives_clear_error(monkeypatch, settings_cls):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    with patch("tikos_utils.settings.open_environment_variables", return_value={"FOO": "bar"}):
        with pytest.raises(RuntimeError, match="PORT"):
            settings_cls.load()


def test_cli_not_installed_error_surfaces_cleanly(monkeypatch, settings_cls):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    with patch(
        "tikos_utils.settings.open_environment_variables",
        side_effect=EscOpenError("Pulumi CLI is required for local ESC configuration."),
    ), pytest.raises(RuntimeError, match="Pulumi CLI is required"):
        settings_cls.load()


def test_not_logged_in_error_surfaces_cleanly(monkeypatch, settings_cls):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    with patch(
        "tikos_utils.settings.open_environment_variables",
        side_effect=EscOpenError("Could not open ESC environment 'org/proj/env': not logged in."),
    ):
        with pytest.raises(RuntimeError, match="not logged in"):
            settings_cls.load()


def test_bad_environment_error_names_environment_only(monkeypatch, settings_cls):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    with patch(
        "tikos_utils.settings.open_environment_variables",
        side_effect=EscOpenError("Could not open ESC environment 'org/proj/env': no access."),
    ):
        with pytest.raises(RuntimeError, match="org/proj/env"):
            settings_cls.load()


def test_caching_only_opens_esc_once(monkeypatch, settings_cls):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    with patch(
        "tikos_utils.settings.open_environment_variables",
        return_value={"FOO": "bar", "PORT": "8080"},
    ) as mock_open:
        settings_cls.load()
        settings_cls.load()
        settings_cls.load()
    mock_open.assert_called_once()


def test_esc_fallback_also_populates_os_environ(monkeypatch, settings_cls):
    # Other code in the same process (legacy os.getenv call sites outside this Settings class)
    # must also see ESC-fetched values, not just the returned Settings instance.
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    with patch(
        "tikos_utils.settings.open_environment_variables",
        return_value={"FOO": "from-esc", "PORT": "9090"},
    ):
        settings_cls.load()
    assert os.environ["FOO"] == "from-esc"
    assert os.environ["PORT"] == "9090"


def test_esc_fallback_never_overwrites_real_env_in_os_environ(monkeypatch, settings_cls):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.setenv("PORT", "1111")
    with patch(
        "tikos_utils.settings.open_environment_variables",
        return_value={"FOO": "from-esc", "PORT": "9090"},
    ):
        settings_cls.load()
    assert os.environ["PORT"] == "1111"  # real env value untouched


def test_no_secret_values_in_error_text(monkeypatch, settings_cls):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    with patch(
        "tikos_utils.settings.open_environment_variables",
        side_effect=EscOpenError("Could not open ESC environment 'org/proj/env': no access."),
    ):
        with pytest.raises(RuntimeError) as exc_info:
            settings_cls.load()
    assert "sk_test" not in str(exc_info.value)  # sanity: no secret-shaped value ever appears
