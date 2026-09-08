import subprocess
from unittest.mock import patch

import pytest

from tikos_utils.esc import EscOpenError, open_environment_variables


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_open_environment_variables_success():
    with patch("subprocess.run", return_value=_completed(stdout='{"FOO": "bar", "BAZ": "1"}')) as mock_run:
        values = open_environment_variables("org/proj/env")
    assert values == {"FOO": "bar", "BAZ": "1"}
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[:3] == ["pulumi", "env", "open"]
    assert "org/proj/env" in args


def test_open_environment_variables_cli_not_installed():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(EscOpenError, match="Pulumi CLI is required"):
            open_environment_variables("org/proj/env")


def test_open_environment_variables_not_logged_in_or_no_access():
    with patch("subprocess.run", return_value=_completed(returncode=255, stderr="secret leaking text")):
        with pytest.raises(EscOpenError) as exc_info:
            open_environment_variables("org/proj/env")
    message = str(exc_info.value)
    assert "org/proj/env" in message
    assert "secret leaking text" not in message  # never surface raw stdout/stderr


def test_open_environment_variables_bad_json():
    with patch("subprocess.run", return_value=_completed(stdout="not json")):
        with pytest.raises(EscOpenError, match="Malformed response"):
            open_environment_variables("org/proj/env")


def test_open_environment_variables_timeout():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pulumi", timeout=30)):
        with pytest.raises(EscOpenError, match="Timed out"):
            open_environment_variables("org/proj/env")
