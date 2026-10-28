# tikos.utils

Shared Pulumi ESC config resolver and pydantic settings base for internal Tikos Python services.

Install:

```
tikos-utils @ git+https://github.com/tikostech/tikos.utils.git@v0.3.0
```

Usage:

```python
from typing import ClassVar
from tikos_utils import TikosBaseSettings

class Settings(TikosBaseSettings):
    esc_environment: ClassVar[str] = "tikos-tech/services/local#<your-service>"

    DATABASE_URL: str
    LOG_LEVEL: str = "INFO"  # a genuine code constant is fine to keep as a default

settings = Settings.load()
```

`Settings.load()` first reads the working directory's `.env` (or the file `TIKOS_ENV_FILE` names;
set it empty to turn this off) into the process environment, without overriding anything already
set there, and logs the names it read, never the values. A value in `.env` therefore overrides
ESC's, and a real environment variable overrides both, so you can point one service at another
database, say, by putting its settings in that repo's gitignored `.env`.

It then tries process env + field defaults — no Pulumi call at all if that
already satisfies every required field (the common case once `docker compose` or a cloud
deployment has already injected everything). Only if a required field is missing does it open the
ESC address once with `pulumi env open`, merge the result in under real process env (env still
wins over ESC), and retry.

`esc_environment` is an ESC address:
- `org/project/env`: that environment's `environmentVariables`;
- `org/project/env#<block>`: one service's block of a shared environment, such as
  `tikos-tech/services/local#tikos-api-server`. The service gets the environment's `shared` block's
  `environmentVariables`, with its own block's `environmentVariables` on top. The compose stack's
  ESC provider (tikos.infrastructure) applies the same rule. Requires the `pulumi` CLI installed
and an active `pulumi login` session — it deliberately does not use `pulumi-esc-sdk`/
`PULUMI_ACCESS_TOKEN`, since the SDK does not reuse an existing CLI login session (see
`src/tikos_utils/esc.py` for why).

`tikos_utils.esc` has no dependencies beyond the Python standard library, so it can be imported
on its own (e.g. by a Docker Compose provider script) without needing this package's own venv.
