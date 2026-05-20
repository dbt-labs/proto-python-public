import base64
import logging
from dbtlabs.proto.private.v1.messaging_queue.event import (
    EXCHANGE_NAME,
    EXCHANGE_TYPE,
    DEADLETTER_EXCHANGE_NAME,
)
from dbtlabs.proto.private.v1.messaging_queue.consumer_handler import (
    ProtoConsumerHandler,
)
from dbtlabs.proto.private.v1.messaging_queue.config import get_default_eventbus_params

import pika.exceptions
from pika.spec import Basic
from pika.spec import BasicProperties
import time
from typing import Optional, Type

logger = logging.getLogger(__name__)


class ConsumerOptions:
    def __init__(
        self,
        enable_requeue_on_error=True,
        delay_msec: int = 60 * 1000,
        ack: bool = True,
        durable_queue: bool = True,
        auto_delete_queue: bool = False,
        exclusive_queue: bool = False,
        consume_inactivity_timeout_secs: int = 5,
        enable_deadletter: bool = False,
        deadletter_routing_key: Optional[str] = None,
        deadletter_timeout_msecs: int = 0,
        exchange_name: str = EXCHANGE_NAME,
        exchange_type: str = EXCHANGE_TYPE,
        exchange_arguments: Optional[dict] = None,
        prefetch_count: int = 1,
        routing_key_for_binding: Optional[str] = None,
        retry_limit: Optional[int] = None,
    ) -> None:
        self.enable_requeue_on_error = enable_requeue_on_error
        self.delay_msec = delay_msec
        self.ack = ack
        self.durable_queue = durable_queue
        self.auto_delete_queue = auto_delete_queue
        self.exclusive_queue = exclusive_queue
        self.consume_inactivity_timeout_secs = consume_inactivity_timeout_secs
        self.enable_deadletter = enable_deadletter
        self.deadletter_routing_key = deadletter_routing_key
        self.deadletter_timeout_msecs = deadletter_timeout_msecs
        self.exchange_name = exchange_name
        self.exchange_type = exchange_type
        if exchange_arguments is None:
            exchange_arguments = {}
        self.exchange_arguments = exchange_arguments
        self.prefetch_count = prefetch_count
        self.routing_key_for_binding = routing_key_for_binding
        self.retry_limit = retry_limit

    @classmethod
    def Default(cls) -> "ConsumerOptions": 
        return ConsumerOptions(
            enable_requeue_on_error=True,
            ack=True,
            durable_queue=True,
            exclusive_queue=False,
            auto_delete_queue=False,
            consume_inactivity_timeout_secs=5,
            exchange_name=EXCHANGE_NAME,
            exchange_type=EXCHANGE_TYPE,
            prefetch_count=1,
            retry_limit=None,
        )


class PikaConsumerClient:
    def __init__(
        self,
        queue: str,
        client_handler: ProtoConsumerHandler,
        opts: ConsumerOptions = ConsumerOptions.Default(),
    ):
        self.queue = queue
        self.params = pika.URLParameters(str(get_default_eventbus_params()))
        self.logger = logger
        self.client_handler = client_handler
        self.opts = opts
        self.interrupt = False

    def _add_requeue_support(self):
        delayed_exchange = f"{self.queue}.delayed"
        requeue_exchange = f"{delayed_exchange}.requeue"
        delayed_queue = f"{self.queue}.delayed"

        self.channel.exchange_declare(
            exchange=delayed_exchange, exchange_type="topic", durable=True
        )

        logger.debug(f"Declared delayed exchange: {delayed_exchange}")

        self.channel.exchange_declare(
            exchange=requeue_exchange,
            exchange_type="topic",
            durable=True,
        )

        logger.debug(f"Declared requeue exchange: {requeue_exchange}")

        self.channel.queue_declare(
            queue=delayed_queue,
            durable=True,
            exclusive=False,
            auto_delete=False,
            arguments={
                "x-dead-letter-exchange": requeue_exchange,
                "x-message-ttl": self.opts.delay_msec,
            },
        )

        logger.debug(f"Declared delayed queue: {delayed_queue}")

        self.channel.queue_bind(
            exchange=delayed_exchange,
            queue=delayed_queue,
            routing_key="#",
        )

        self.channel.queue_bind(
            exchange=requeue_exchange,
            queue=self.queue,
            routing_key="#",
        )

    def _add_deadletter_support(self):
        self.channel.exchange_declare(
            exchange=DEADLETTER_EXCHANGE_NAME, exchange_type=EXCHANGE_TYPE, durable=True
        )

    def setup_connection(self):
        try:
            self.connection = pika.BlockingConnection(parameters=self.params)
            # Open the channel
            self.channel = self.connection.channel()

            # Prefetch messages before processing is complete
            self.channel.basic_qos(prefetch_count=self.opts.prefetch_count)

            args = {}

            self.channel.exchange_declare(
                exchange=self.opts.exchange_name,
                exchange_type=self.opts.exchange_type,
                arguments=self.opts.exchange_arguments,
                durable=True,
            )

            if self.opts.enable_deadletter:
                self._add_deadletter_support()
                args["x-dead-letter-exchange"] = DEADLETTER_EXCHANGE_NAME
                args["x-dead-letter-routing-key"] = (
                    self.opts.deadletter_routing_key or self.queue
                )
                args["x-message-ttl"] = self.opts.deadletter_timeout_msecs

            # Initialize the queue, creates if it doesn't exist
            self.channel.queue_declare(
                queue=self.queue,
                durable=self.opts.durable_queue,
                exclusive=self.opts.exclusive_queue,
                auto_delete=self.opts.auto_delete_queue,
                arguments=args,
            )

            # Bind to the messages we are interested in
            self.channel.queue_bind(
                exchange=self.opts.exchange_name,
                queue=self.queue,
                routing_key=self.opts.routing_key_for_binding
                or self.client_handler.routing_key(),
            )

            if self.opts.enable_requeue_on_error:
                self._add_requeue_support()

        except Exception as err:
            message = f"Pika: Error initializing connection. Error: {err}"
            logger.warning(f"Pika: Error initializing connection. Error: {err}")
            self.client_handler.on_error(err, message)
            raise err

    def on_message(
        self,
        channel,
        method_frame: Basic.Deliver,
        header_frame: BasicProperties,
        body: bytes,
    ) -> None:
        logger.debug(f"Pika: Received a message from queue: {self.queue}")
        success = False

        header_frame.headers = header_frame.headers or {}
        retry_count = header_frame.headers.get("retry_count", 0)
        logger.debug(f"Pika: on_message retry count: {retry_count}")
        try:
            message = self.client_handler.message_from_string(body)
            logger.debug(f"Pika: message_from_string: {message}")
            self.client_handler.on_message(event=message, props=header_frame)
            success = True
        except Exception as err:
            message = f"Unable to consume event {str(body)} (base64: {base64.b64encode(body).decode('utf-8')}) because of {type(err)}: {err}"
            logger.warning(message)
            if self.opts.retry_limit is None:
                self.client_handler.on_error(err, message)
            else:
                if retry_count > self.opts.retry_limit and self.opts.ack:
                    logger.warning(
                        "Pika: retry limit reached, acking message to not requeue"
                    )
                    if method_frame.delivery_tag is not None:
                        self.basic_ack(method_frame.delivery_tag)
                    return
                retry_count += 1
                self.client_handler.on_error(err, message)

        if not success and self.opts.enable_requeue_on_error:
            self.delayed_requeue(body, headers={"retry_count": retry_count})

        if self.opts.ack and method_frame.delivery_tag is not None:
            self.basic_ack(method_frame.delivery_tag)

    def delayed_requeue(self, body: bytes, headers: Optional[dict] = None):
        try:
            props = BasicProperties(
                delivery_mode=2,
                timestamp=int(time.time()),
                headers=headers,
            )
            self.channel.basic_publish(
                body=body,
                exchange=f"{self.queue}.delayed",
                routing_key=self.client_handler.routing_key(),
                properties=props,
            )
        except Exception as error:
            logger.warning(f"Failed to publish to delayed exchange: {error}")

    def basic_ack(self, delivery_tag: int):
        self.channel.basic_ack(delivery_tag=delivery_tag)

    def basic_nack(self, delivery_tag: int):
        self.channel.basic_nack(delivery_tag=delivery_tag)

    def close(self):
        logger.debug(f"Pika: close(): {self.queue}.")
        self.interrupt = True
        self.channel.stop_consuming()
        self.connection.close()

    def async_close(self):
        """Stops consuming once there is no more activity. This is
        useful to invoke from a separate thread."""
        logger.debug(f"Pika: async_close(): {self.queue}.")
        self.interrupt = True

    def start_consumer(self):
        connect_and_consume = True
        while connect_and_consume and not self.interrupt:
            try:
                logger.debug(f"Pika: Connecting to queue: {self.queue}.")
                self.setup_connection()
                logger.debug(f"Pika: Connected to queue: {self.queue}.")
                try:
                    logger.debug(f"Pika: consuming queue: {self.queue}.")
                    while not self.interrupt:
                        for method, properties, body in self.channel.consume(
                            self.queue,
                            auto_ack=False,  #  we are specifically handling this in the consumer
                            exclusive=self.opts.exclusive_queue,
                            inactivity_timeout=self.opts.consume_inactivity_timeout_secs,
                        ):
                            if self.interrupt:
                                logger.debug(f"Pika {self.queue}: interrupted, closing")
                                # this is how async_close() actually
                                # closes the connection within the thread
                                # actually reading from the queue
                                self.close()
                                connect_and_consume = False
                                break
                            if not body:
                                continue
                            self.on_message(self.channel, method, properties, body)
                    logger.debug(
                        f"Pika: done consuming queue: {self.queue} interrupted: {self.interrupt}."
                    )
                except KeyboardInterrupt as err:
                    logger.debug(f"Pika {self.queue}: KeyboardInterrupt.")
                    self.close()
                    message = "Pika: Keyboard Interrupt"
                    self.client_handler.on_error(err, message)
                    connect_and_consume = False
                    break
            except pika.exceptions.ConnectionClosedByBroker as err:
                message = (
                    "Pika {self.queue}: Connection closed by broker, reconnecting..."
                )
                logger.warning(message)
                self.client_handler.on_error(err, message)
                continue
            # There are some channel errors that can be solved by reconnecting
            except (
                pika.exceptions.ChannelClosed,
                pika.exceptions.ConsumerCancelled,
                pika.exceptions.ChannelWrongStateError,
            ) as err:
                message = f"Pika {self.queue}: Caught a channel error: {repr(err)}, reconnecting..."
                logger.warning(message)
                self.client_handler.on_error(err, message)
                continue
            # Do not recover on other channel errors
            except pika.exceptions.AMQPChannelError as err:
                message = (
                    f"Pika {self.queue}: Caught a channel error: {repr(err)}, giving up"
                )
                logger.error(message)
                self.client_handler.on_error(err, message)
                break
            # Do not recover on authentication / credential errors
            except pika.exceptions.ProbableAuthenticationError as err:
                message = (
                    f"Pika {self.queue}: Authentication with broker failed, giving up"
                )
                logger.error(message)
                self.client_handler.on_error(err, message)
                break
            # Recover on all other connection errors
            except pika.exceptions.AMQPConnectionError as err:
                message = f"Pika {self.queue}: Connection was closed. Retrying... Error {err}."
                logger.warning(message)
                self.client_handler.on_error(err, message)
                continue
