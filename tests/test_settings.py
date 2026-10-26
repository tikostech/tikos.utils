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


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    saved = dict(os.environ)
    monkeypatch.delenv("TIKOS_ENV_FILE", raising=False)
    monkeypatch.chdir(tmp_path)
    yield
    os.environ.clear()
    os.environ.update(saved)


def write_env_file(path, **values):
    path.write_text("".join(f"{key}={value}\n" for key, value in values.items()))
    return path


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


def test_env_file_overrides_esc(monkeypatch, settings_cls, tmp_path):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    write_env_file(tmp_path / ".env", PORT="2222")
    with patch(
        "tikos_utils.settings.open_environment_variables",
        return_value={"FOO": "from-esc", "PORT": "9090"},
    ):
        settings = settings_cls.load()
    assert settings.FOO == "from-esc"
    assert settings.PORT == 2222


def test_process_env_overrides_env_file(monkeypatch, settings_cls, tmp_path):
    monkeypatch.setenv("FOO", "from-env")
    monkeypatch.setenv("PORT", "1111")
    write_env_file(tmp_path / ".env", FOO="from-file", PORT="2222")
    with patch("tikos_utils.settings.open_environment_variables") as mock_open:
        settings = settings_cls.load()
    assert settings.FOO == "from-env"
    assert settings.PORT == 1111
    mock_open.assert_not_called()


def test_env_file_alone_never_calls_esc(monkeypatch, settings_cls, tmp_path):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    write_env_file(tmp_path / ".env", FOO="from-file", PORT="2222")
    with patch("tikos_utils.settings.open_environment_variables") as mock_open:
        settings = settings_cls.load()
    assert (settings.FOO, settings.PORT) == ("from-file", 2222)
    mock_open.assert_not_called()


def test_env_file_values_reach_os_environ(monkeypatch, settings_cls, tmp_path):
    # Code that reads os.environ directly (the services' database modules) sees them too, ahead
    # of ESC's.
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("DATABASE_HOST", raising=False)
    write_env_file(tmp_path / ".env", DATABASE_HOST="from-file")
    with patch(
        "tikos_utils.settings.open_environment_variables",
        return_value={"FOO": "from-esc", "PORT": "9090", "DATABASE_HOST": "from-esc"},
    ):
        settings_cls.load()
    assert os.environ["DATABASE_HOST"] == "from-file"


def test_env_file_path_comes_from_tikos_env_file(monkeypatch, settings_cls, tmp_path):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setenv("TIKOS_ENV_FILE", str(write_env_file(tmp_path / "dev.env", FOO="x", PORT="3")))
    with patch("tikos_utils.settings.open_environment_variables") as mock_open:
        settings = settings_cls.load()
    assert (settings.FOO, settings.PORT) == ("x", 3)
    mock_open.assert_not_called()


def test_empty_tikos_env_file_turns_the_file_off(monkeypatch, settings_cls, tmp_path):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.setenv("TIKOS_ENV_FILE", "")
    write_env_file(tmp_path / ".env", FOO="from-file", PORT="2222")
    with patch(
        "tikos_utils.settings.open_environment_variables",
        return_value={"FOO": "from-esc", "PORT": "9090"},
    ):
        settings = settings_cls.load()
    assert (settings.FOO, settings.PORT) == ("from-esc", 9090)


def test_missing_env_file_is_ignored(monkeypatch, settings_cls):
    monkeypatch.setenv("FOO", "bar")
    monkeypatch.setenv("PORT", "8080")
    monkeypatch.setenv("TIKOS_ENV_FILE", "does-not-exist.env")
    assert settings_cls.load().PORT == 8080


def test_env_file_logs_names_not_values(monkeypatch, settings_cls, tmp_path, caplog):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("PORT", raising=False)
    write_env_file(tmp_path / ".env", FOO="sk_test_secret", PORT="2222")
    with caplog.at_level("INFO", logger="tikos_utils"):
        settings_cls.load()
    assert "FOO" in caplog.text
    assert "sk_test_secret" not in caplog.text
