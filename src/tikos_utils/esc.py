import json
import subprocess

# The block of a shared environment (tikos-tech/services/local) whose `environmentVariables` every
# service in it gets, under the service's own block's.
SHARED_BLOCK = "shared"


class EscOpenError(Exception):
    pass


def split_address(address: str) -> tuple[str, str | None]:
    """An ESC address's environment, and its block (None for the whole environment)."""
    environment, sep, block = address.partition("#")
    if not environment or (sep and not block):
        raise EscOpenError(f"Not an ESC address: '{address}' (expected <environment>[#<block>]).")
    return environment, block or None


def open_environment_variables(esc_environment: str, timeout: int = 30) -> dict[str, str]:
    """Return the resolved environment variables an ESC address gives a service.

    `org/project/env` is the environment's own `environmentVariables`, e.g.
    `tikos-tech/local-dev/tikos-platform-backend`. `org/project/env#<block>` is one service's block
    of a shared environment, e.g. `tikos-tech/services/local#tikos-api-server`: the environment's
    `shared` block's `environmentVariables`, with the service's block's own on top.
    """
    environment, block = split_address(esc_environment)
    if block is None:
        values = _open(environment, ["environmentVariables"], esc_environment, timeout)
    else:
        opened = _open(environment, [], esc_environment, timeout)
        own = opened.get(block)
        if not isinstance(own, dict):
            raise EscOpenError(f"ESC address '{esc_environment}' names no block '{block}'.")
        shared = opened.get(SHARED_BLOCK) or {}
        values = {
            **_variables(shared, esc_environment),
            **_variables(own, esc_environment),
        }
    return {str(k): str(v) for k, v in values.items()}


def _variables(block: object, address: str) -> dict:
    values = block.get("environmentVariables", {}) if isinstance(block, dict) else None
    if not isinstance(values, dict):
        raise EscOpenError(f"Unexpected response shape opening ESC address '{address}'.")
    return values


def _open(environment: str, path: list[str], address: str, timeout: int) -> dict:
    try:
        result = subprocess.run(
            ["pulumi", "env", "open", environment, *path, "--format", "json"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise EscOpenError(
            "Pulumi CLI is required for local ESC configuration. "
            "Install Pulumi and run `pulumi login`."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise EscOpenError(f"Timed out opening ESC environment '{address}'.") from exc

    if result.returncode != 0:
        raise EscOpenError(
            f"Could not open ESC environment '{address}': not logged in "
            f"(`pulumi login`), no access, or the environment doesn't exist."
        )

    try:
        values = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise EscOpenError(f"Malformed response opening ESC environment '{address}'.") from exc

    if not isinstance(values, dict):
        raise EscOpenError(f"Unexpected response shape opening ESC environment '{address}'.")

    return values
