import json
import subprocess


class EscOpenError(Exception):
    pass


def open_environment_variables(esc_environment: str, timeout: int = 30) -> dict[str, str]:
    """Return the resolved `environmentVariables` value of a Pulumi ESC environment.

    `esc_environment` is the full `org/project/env` triple, e.g.
    `tikos-tech/local-dev/tikos-platform-backend`.
    """
    try:
        result = subprocess.run(
            ["pulumi", "env", "open", esc_environment, "environmentVariables", "--format", "json"],
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
        raise EscOpenError(f"Timed out opening ESC environment '{esc_environment}'.") from exc

    if result.returncode != 0:
        raise EscOpenError(
            f"Could not open ESC environment '{esc_environment}': not logged in "
            f"(`pulumi login`), no access, or the environment doesn't exist."
        )

    try:
        values = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise EscOpenError(f"Malformed response opening ESC environment '{esc_environment}'.") from exc

    if not isinstance(values, dict):
        raise EscOpenError(f"Unexpected response shape opening ESC environment '{esc_environment}'.")

    return {str(k): str(v) for k, v in values.items()}
