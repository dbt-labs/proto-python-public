from dbtlabs.proto.private.v1.messaging_queue.pika_producer import (
    EventbusProducerClient,
    PikaProducerClient,
    EventbusRpcClient,
)
from dbtlabs.proto.private.v1.messaging_queue.pika_consumer import (
    ProtoConsumerHandler as _ProtoConsumerHandler,
)
from dbtlabs.proto.private.v1.messaging_queue.pika_consumer import PikaConsumerClient
from dbtlabs.proto.private.v1.messaging_queue.pika_consumer import ConsumerOptions as _ConsumerOptions

"""
Used to publish protos to the messaging queue for consumption elsewhere.
"""
ProtoPublishClient = PikaProducerClient
ProtoRpcClient = EventbusRpcClient

"""
Used to consume incoming serialized protos.
"""
ProtoConsumerClient = PikaConsumerClient
ProtoConsumerHandler = _ProtoConsumerHandler
ProtoConsumerOptions = _ConsumerOptions
