"""Pulumi ESC resolver.

Stdlib-only (json, subprocess) so the Compose provider in tikos.infrastructure can use this
module directly without an activated venv - only this file matters there, not the rest of the
package.

Shells out to the `pulumi` CLI rather than using `pulumi-esc-sdk`: the SDK only authenticates via
a `PULUMI_ACCESS_TOKEN` env var and does not reuse an existing `pulumi login` session (confirmed
against the SDK's own source, and live against the actual API - a valid CLI login session got a
401 from the SDK with no token set). The CLI is the only thing that reuses a login a developer
already has and keeps valid for other infra work, with no new credential to create or rotate.
"""

import json
import subprocess


class EscOpenError(Exception):
    """Raised when `pulumi env open` fails - missing CLI, no login, no access, or bad environment."""


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
        # Never include result.stdout/stderr here - they may contain partially-resolved secrets.
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
