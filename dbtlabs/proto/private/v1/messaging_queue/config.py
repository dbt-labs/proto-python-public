import urllib
from typing import Type

from dbtlabs.proto.private.v1.common.environment_variables import EnvironmentVariable


class EventbusConfig:

    def __init__(
        self,
        protocol: str,
        vhost: str,
        username: str,
        password: str,
        host: str,
        port: str,
    ):
        self.protocol = protocol
        self.vhost = vhost
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        # vhost is allowed to be an empty string, so we do not check it here
        self.enabled = all([protocol, host, username, password, port])

    def __str__(self):
        """
        If none of the above variables are set, EventbusConifg
        will not produce a valid connection string
        """
        if not self.enabled:
            return "amqp://eventbus.not/enabled"
        username = urllib.parse.quote_plus(self.username)
        password = urllib.parse.quote_plus(self.password)
        return f"{self.protocol}://{username}:{password}@{self.host}:{self.port}/{self.vhost}"


def get_default_eventbus_params() -> EventbusConfig:
    return EventbusConfig(
        protocol=EnvironmentVariable.EVENTBUS_PROTOCOL,
        vhost=EnvironmentVariable.EVENTBUS_VHOST,
        username=EnvironmentVariable.EVENTBUS_USERNAME,
        password=EnvironmentVariable.EVENTBUS_PASSWORD,
        host=EnvironmentVariable.EVENTBUS_HOST,
        port=EnvironmentVariable.EVENTBUS_PORT,
    )
