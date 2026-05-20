from google.protobuf import message
from google.protobuf.json_format import MessageToJson

# EXCHANGE_NAME is the name of the default event bus exchange into
# which producers can send events, and from which consumers can bind
# queues.
EXCHANGE_NAME = "topic.event"

# EXCHANGE_TYPE is the type of the default event bus exchange.
EXCHANGE_TYPE = "topic"

# DEADLETTER_EXCHANGE_NAME is the name of the default event bus
# deadletter exchange which queues can utilize, for example, to send
# messages which exceed a TTL.
DEADLETTER_EXCHANGE_NAME = "topic.event.deadletter"


# RoutingKey returns the canonical routing key for the event e, for
# example "isaac.desk.missing" or "metadata.apirequest.received"
# eventProto should be an unserialized proto
def RoutingKey(event_proto: message.Message):
    return event_proto.DESCRIPTOR.full_name.lower()


def ToJson(event_proto: message.Message):
    MessageToJson(event_proto)


class TimeoutException(Exception):
    pass
