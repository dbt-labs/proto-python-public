import logging
from abc import abstractmethod
import logging
from typing import TypeVar, Generic, Type
from google.protobuf import message

import pika

from dbtlabs.proto.private.v1.messaging_queue.event import (
    RoutingKey,
)


ProtoKlassType = TypeVar("ProtoKlassType", bound=message.Message)

"""
Assumes that any given queue will only send 1 kind of proto to be deserialized to.
Use composition and optional fields to achieve this if you need to send multiple
different kinds of proto over one queue (one parent proto for all messages that
can contain other protos).
"""

logger = logging.getLogger(__name__)


class ProtoConsumerHandler(Generic[ProtoKlassType]):
    def __init__(self, ProtoKlass: Type[ProtoKlassType]):
        self.ProtoKlass = ProtoKlass

    @abstractmethod
    def on_message(self, event: ProtoKlassType, props: pika.spec.BasicProperties):
        """Consumes an incoming proto"""
        pass

    def routing_key(self):
        """Returns the canonical routing key for the consumer"""
        return RoutingKey(self.ProtoKlass())

    def on_error(self, error_type: Exception, error_message: str):
        """Consumes any Exception that occurred in the PikaConsumerClient"""
        pass

    def get_logger(self) -> logging.Logger:
        """Warning: deprecated. Please use standard logging module instead."""
        logger = logging.getLogger("ProtoConsumerHandler")
        logger.setLevel(logging.INFO)
        return logger

    def message_from_string(self, body: bytes) -> ProtoKlassType:
        """Deserialize a protobuf"""
        message: ProtoKlassType = self.ProtoKlass()
        message.ParseFromString(body)
        return message
