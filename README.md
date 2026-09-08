# tikos.utils

Shared Pulumi ESC config resolver and pydantic settings base for internal Tikos Python services.

Install:

```
tikos-utils @ git+https://github.com/tikostech/tikos.utils.git@v0.1.0
```

Usage:

```python
from typing import ClassVar
from tikos_utils import TikosBaseSettings

class Settings(TikosBaseSettings):
    esc_environment: ClassVar[str] = "tikos-tech/local-dev/<your-service>"

    DATABASE_URL: str
    LOG_LEVEL: str = "INFO"  # a genuine code constant is fine to keep as a default

settings = Settings.load()
```

`Settings.load()` tries real process env + field defaults first — no Pulumi call at all if that
already satisfies every required field (the common case once `docker compose` or a cloud
deployment has already injected everything). Only if a required field is missing does it run
`pulumi env open <esc_environment> environmentVariables --format json` once, merge the result in
under real process env (env still wins over ESC), and retry. Requires the `pulumi` CLI installed
and an active `pulumi login` session — it deliberately does not use `pulumi-esc-sdk`/
`PULUMI_ACCESS_TOKEN`, since the SDK does not reuse an existing CLI login session (see
`src/tikos_utils/esc.py` for why).

`tikos_utils.esc` has no dependencies beyond the Python standard library, so it can be imported
on its own (e.g. by a Docker Compose provider script) without needing this package's own venv.
