import os
from typing import Any


def get_env_var(env_var: str, default: Any = None):
    return os.getenv(env_var, default)


class EnvironmentVariable:
    EVENTBUS_PROTOCOL: str = os.getenv("EVENTBUS_PROTOCOL", "")
    EVENTBUS_USERNAME: str = os.getenv("EVENTBUS_USERNAME", "")
    EVENTBUS_PASSWORD: str = os.getenv("EVENTBUS_PASSWORD", "")
    EVENTBUS_VHOST: str = os.getenv("EVENTBUS_VHOST", "")
    EVENTBUS_HOST: str = os.getenv( "EVENTBUS_HOST", "")
    EVENTBUS_PORT: str = os.getenv("EVENTBUS_PORT", "")
