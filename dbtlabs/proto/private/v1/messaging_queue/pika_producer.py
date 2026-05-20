import logging
from functools import lru_cache
import os
from queue import Empty
from queue import Queue
from threading import Event, Thread, Lock, Condition, get_ident

from time import sleep
from google.protobuf import message
from abc import ABCMeta, abstractmethod
from typing import Callable, Tuple, Type, Dict, Optional, Any, Generic
import uuid

import pika
import pika.exceptions
from dbtlabs.proto.private.v1.messaging_queue.event import EXCHANGE_NAME
from dbtlabs.proto.private.v1.messaging_queue.event import EXCHANGE_TYPE
from dbtlabs.proto.private.v1.messaging_queue.event import RoutingKey
from dbtlabs.proto.private.v1.messaging_queue.event import TimeoutException
from dbtlabs.proto.private.v1.messaging_queue.config import (
    EventbusConfig,
    get_default_eventbus_params,
)
from dbtlabs.proto.private.v1.messaging_queue.consumer_handler import (
    ProtoKlassType,
)


@lru_cache(maxsize=1)
def _get_pod_name():
    return os.environ.get("POD_NAME", "unknown")


class EventPublisher(metaclass=ABCMeta):
    @abstractmethod
    def connect(self):
        """Connect to messaging system"""
        pass

    @abstractmethod
    def publish(self, event):
        """Publish event"""
        pass

    @abstractmethod
    def process(self, timeout=0):
        """Process published events if necessary"""
        pass

    @abstractmethod
    def disconnect(self):
        """Disconnect from messaging system"""
        pass


class PikaPublisher(EventPublisher):
    def __init__(self, params: EventbusConfig, logger: logging.Logger):
        self.params = pika.URLParameters(str(params))
        self.params.client_properties = {"product": _get_pod_name()}
        self.logger = logger

    def connect(self):
        self.connection = pika.BlockingConnection(
            parameters=self.params,
        )
        self.channel = self.connection.channel()
        self.channel.exchange_declare(
            exchange=EXCHANGE_NAME, exchange_type=EXCHANGE_TYPE, durable=True
        )

    def publish(self, event):
        if event is None:
            return
        self._validate_event(event)
        self.channel.basic_publish(
            body=event["body"],
            exchange=event["exchange"],
            routing_key=event["routing_key"],
            properties=pika.BasicProperties(**event["props"]),
        )

    def _validate_event(self, event):
        if event is None:
            return
        if (
            "body" not in event
            or "routing_key" not in event
            or "props" not in event
            or "exchange" not in event
        ):
            raise RuntimeError(f"Malformed event: {event}")

    def process(self, timeout=0):
        self.connection.process_data_events(timeout)

    def disconnect(self):
        try:
            if self.channel.get_waiting_message_count() > 0:
                self.logger.info(
                    "PikaPublisher: processing data events before disconnect"
                )
                self.process()

            self.logger.info("PikaPublisher: closing connection")
            self.connection.close()
        except AttributeError:
            return


_publisher_proc_shutdown_sentinel = object()


class PublisherProc:
    HEARTBEAT_SECONDS = 10

    def __init__(
        self,
        publisher: EventPublisher,
        logger: logging.Logger,
        queue: Queue,
        run_async: bool = True,
    ):
        self.eventbus_connected = False
        self.publisher = publisher
        self.logger = logger
        self.queue = queue
        self.run_async = run_async
        self.shutdown_started = False
        self.queue_timeout = None
        self.active = True
        self.shutdown_complete = Event()
        self.shutdown_timed_out = False
        if self.run_async:
            self.queue_timeout = self.HEARTBEAT_SECONDS

    def set_active(self, a: bool):
        self.active = a

    def shutdown(self):
        self.logger.info("PublisherProc: shutting down")
        self.shutdown_started = True
        self.queue.put((_publisher_proc_shutdown_sentinel, None))
        self.set_active(True)

        if not self.eventbus_connected:
            self.logger.info(
                "PublisherProc: eventbus is not connected, shutdown complete"
            )
            return

        if not self.run_async:
            # The underlying connection can be closed in the main thread since
            # there is no background async thread when using the sync producer.
            # The connection will get created by the main thread when using the
            # sync publisher.
            self.logger.info(
                "PublisherProc: not running async, disconnecting from broker"
            )
            self.publisher.disconnect()
            return

        is_complete = self.shutdown_complete.wait(timeout=self.HEARTBEAT_SECONDS * 2)
        if is_complete:
            self.logger.info("PublisherProc: shutdown complete")
        else:
            self.logger.info(
                "PublisherProc: timed out waiting for shutdown to complete"
            )
            self.shutdown_timed_out = True

    def run(self, ready=None):
        connection_ok = True

        # it could be the case that the server is under heavy load,
        # and connecting might fail. Try a few times before giving up.
        connection_attempts = 5
        for connection_attempt in range(connection_attempts):
            try:
                connection_ok = True
                self.connect()
                break
            except Exception as e:
                connection_ok = False
                self.logger.warning(
                    f"PublisherProc: run: unexpected exception attempting to connect: {type(e)}: {e}"
                )
                if connection_attempt < connection_attempts - 1:
                    self.logger.warning("PublisherProc: run: retrying connection")
                    sleep(1)
                else:
                    self.logger.error(
                        "PublisherProc: run: unable to establish connection"
                    )

        if ready:
            with ready:
                ready.notify()
        if not connection_ok:
            return
        if self.run_async:
            self.process_async()
            self.logger.debug("PublisherProc: run: async: done")
            return
        self.process_sync()

    def connect(self):
        if self.run_async:
            self.connect_to_eventbus()
            return
        self.connect_until_successful()

    def connect_to_eventbus(self):
        self.logger.debug("PublisherProc: connect_to_eventbus")
        try:
            self.publisher.connect()
            self.eventbus_connected = True
        except Exception as e:
            self.logger.warning(
                f"PublisherProc: connect_to_eventbus: unexpected exception attempting to connect: {type(e)}: {e}"
            )
            raise
        self.logger.debug("PublisherProc: connect_to_eventbus: success")

    def connect_until_successful(self):
        self.logger.debug("PublisherProc: connect_until_successful")
        while not self.eventbus_connected:
            try:
                self.connect_to_eventbus()
            except Exception:
                self.wait()
        self.logger.debug("PublisherProc: connect_until_successful: success")

    def process_async(self):
        """
        This is a long-running thread responsible for maintaining a
        persistent connection to the event bus.  Connection parameters
        are passed as a parameter from a controlling thread
        (django). In addition, a thread-safe queue (also a parameter)
        is used to communicate with this thread.
        Each message in the queue should be a dictionary containing a
        "body" and "routing_key". These messages will be published to
        the event bus immediately.
        Exceptions are handled, including re-connecting to the event
        bus in the event the connection is lost or dropped.
        Additionally, an error_callback function is optionally passed
        in (by the consumer of the client) and stored in the queue
        along with the event. In the exception case, that error_callback
        will be invoked. Because we use a singleton version of the
        Producer client in some places (dbt-cloud), the hope/intention
        is that this will be a lightweight, non-blocking callback
        function, so that we don't negatively impact event processing
        within the system.
        NOTE: since this long-running thread is expected to be always
        "on", in the extreme case re-connection attempts will be tried
        over and over (with an appropriate delay), until
        successful. Messages may be lost if the thread is abruptly
        stopped. Use process_sync if there is no tolerance for lost
        messages.
        """
        in_shutdown = False
        while True:
            try:
                (event, error_callback) = self.get_event_and_callback(fast=in_shutdown)
                if not event and not in_shutdown:
                    continue

                # The queue has been drained, so it's safe to close the
                # underlying connection.
                if not event and in_shutdown:
                    self.logger.info("process_async: disconnecting from eventbus")

                    # The underlying connection should be closed in the same
                    # thread that opened the connection, which is why disconnect
                    # is called here and not in the `shutdown` method.
                    self.publisher.disconnect()
                    self.logger.info("process_async: disconnected from eventbus")

                    self.logger.info("process_async: all tasks done")
                    self.shutdown_complete.set()
                    return

            except (
                pika.exceptions.StreamLostError,
                pika.exceptions.ConnectionClosedByBroker,
            ) as e:
                # This indicates some sort of connection issue, and
                # there will have been no event received. Reconnect
                # and try again.
                self.logger.info(
                    f"process_async: failed to get event and callback: {e}, attempting re-connect"
                )
                self.requeue_and_reconnect((None, None))
                continue

            except ValueError as e:
                # handle specific connection problem
                if "Timeout closed before call" in str(e):
                    self.logger.warning(
                        f"process_async: failed to get event and callback due to timeout: {e}, attempting re-connect"
                    )
                    self.requeue_and_reconnect((None, None))
                    continue
                else:
                    self.logger.info(
                        f"process_async: failed to get event and callback due to value error: {e}"
                    )
                    self.wait()
                    continue

            except Exception as e:
                # the queue was empty after HEARTBEAT_SECONDS seconds,
                # so let pika breathe now
                self.logger.exception(
                    f"process_async: failed to get event and callback: {e}"
                )
                self.wait()
                continue

            try:
                if event is _publisher_proc_shutdown_sentinel:
                    self.logger.info("process_async: in shutdown")
                    in_shutdown = True
                    self.queue.task_done()

                    # Continue processing events until we have drained the
                    # queue of any stragglers.
                    continue

                self.publish_event(event)
                self.queue.task_done()
            except Exception as e:
                # re-queueing below, so make sure the bookkeeping on
                # the queue is correct
                self.logger.warning(
                    f"unexpected problem encountered; processing will continue {e}"
                )
                self.queue.task_done()
                # if the caller has passed in an error callback
                # let's call that here before we requeue the event
                if error_callback is not None:
                    try:
                        error_callback(event, e)
                    except Exception as callback_exception:
                        self.logger.warning(
                            f"unexpected problem encountered during call to the error_callback: {callback_exception}, processing will continue."
                        )
                # lots of bad things could have happened, including
                # various pika exceptions, so wait and then make a
                # big effort to reconnect and keep going
                self.requeue_and_reconnect((event, error_callback))

    def process_sync(self):
        (event, error_callback) = self.get_event_and_callback()
        if event is None:
            return
        self.publish_event(event)
        self.queue.task_done()

    def requeue_and_reconnect(self, event_and_callback):
        self.logger.debug("PublisherProc: requeue_and_reconnect")
        # make sure the event is not None before putting back into the
        # queue
        if event_and_callback[0] is not None:
            self.logger.debug(f" - restoring event and callback: {event_and_callback}")
            self.queue.put(event_and_callback)
        self.eventbus_connected = False
        self.connect_until_successful()
        self.logger.debug("PublisherProc: requeue_and_reconnect: success")

    def get_event_and_callback(
        self, fast=False
    ) -> Tuple[Optional[Dict], Optional[Callable]]:
        event_and_callback = (None, None)
        if not self.active:
            self.publisher.process()
            return event_and_callback
        try:
            event_and_callback = self.queue.get(
                timeout=self.queue_timeout if not fast else 0
            )
        except Empty:
            self.publisher.process()
        return event_and_callback

    def publish_event(self, event):
        if event is None:
            return
        try:
            self.publisher.publish(event)
        except RuntimeError as e:
            # this should never happen, here for completeness
            self.logger.error(
                f"PublisherProc: Exception: {e} for message: {event}, abandoning"
            )
            raise
        except Exception as e:
            # lots of bad things could have happened, including
            # various pika exceptions, so log and then raise the
            # exception
            # the caller of this method can decide what to do in this
            # exception case
            self.logger.warning(
                f"PublisherProc: Unhandled exception: {e} for message: {event}."
            )
            raise

    def wait(self):
        sleep(self.HEARTBEAT_SECONDS)


def get_default_logger(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("EventbusProvider")
    logger.setLevel(level)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        logger.addHandler(handler)
    return logger


class EventbusProducerClient:
    def __init__(
        self,
        publisher: Type[PikaPublisher] = PikaPublisher,
        logger: logging.Logger = get_default_logger(),
        params: EventbusConfig = get_default_eventbus_params(),
        queue: Queue = Queue(),
        run_async: bool = True,
    ):
        self.params = params
        self.publisher = publisher(params=params, logger=logger)
        self.logger = logger
        self.queue = queue
        self.async_connection_ready = False
        self.run_async = run_async
        self.async_connection_lock = Lock()
        self.publisher_proc = PublisherProc(
            self.publisher,
            self.logger,
            self.queue,
            run_async=run_async,
        )
        self.enabled_warning = True

    def publish_to_eventbus(
        self,
        event_proto: message.Message,
        error_callback=None,
        routing_key: Optional[str] = None,
        props: Optional[dict] = None,
        exchange: Optional[str] = None,
    ):
        """
        The error_callback parameter is an optional callback function
        that a consumer of this client can utilize to invoke some
        custom logic if any exceptions are encountered during the
        async processing. It will receive the event and the error as
        parameters.
        """
        if not self.params.enabled:
            if self.enabled_warning:
                self.logger.debug("EventbusProducerClient: Eventbus not enabled")
            self.enabled_warning = False
            return
        if self.run_async and not self.async_connection_ready:
            self._prepare_async_connection()
        self._publish(event_proto, error_callback, routing_key, props, exchange)

    def shutdown(self):
        self.publisher_proc.shutdown()

    def _publish(
        self,
        event_proto: message.Message,
        error_callback=None,
        routing_key: Optional[str] = None,
        props: Optional[dict] = None,
        exchange: Optional[str] = None,
    ):
        event = get_event_from_proto(
            event_proto, routing_key=routing_key, props=props, exchange=exchange
        )
        try:
            if self.queue is not None:
                if self.run_async and self.publisher_proc.shutdown_started:
                    raise Exception(
                        "EventbusProducerClient: Unable to publish due to shutting down"
                    )
                # this will get pickled before put into queue
                self.queue.put((event, error_callback))
            if not self.run_async:
                self.publisher_proc.run()
        except Exception as e:
            self.logger.error(
                f"EventbusProducerClient: Error connecting to or publishing to eventbus: {event} [err: {e}]"
            )
            raise

    def _prepare_async_connection(self):
        """
        Pika is not thread safe. Since pika could be the client,
        block (via lock) creation of the connection thread.
        If pika becomes thread safe or if we primarily rely on another
        client, consider removing the threading lock.
        In async mode, messages are put into an in-memory Python queue.
        If the thread lock times out and the connection is not established,
        messages will still be in this queue. The next time a message is
        published, this code will run again.
        """
        is_acquired = False
        while not is_acquired:
            self.logger.debug(
                f"EventbusProducerClient (thread id {get_ident()}): trying to acquire async connection lock"
            )
            is_acquired = self.async_connection_lock.acquire(blocking=True, timeout=1)

        try:
            if not self.async_connection_ready:
                self.logger.debug(
                    f"EventbusProducerClient (thread id {get_ident()}): Preparing the connection thread under a threading lock"
                )
                condition = Condition()
                with condition:
                    self.worker = Thread(
                        target=self.publisher_proc.run,
                        args=[condition],
                        daemon=True,
                    )
                    self.worker.start()
                    condition.wait()
                    if not self.publisher_proc.eventbus_connected:
                        raise Exception("unable to connect")

                self.async_connection_ready = True

                self.logger.debug(
                    f"EventbusProducerClient (thread id {get_ident()}): releasing async connection lock"
                )
        finally:
            self.async_connection_lock.release()


def get_event_from_proto(
    event_proto: message.Message,
    routing_key: Optional[str] = None,
    props: Optional[dict] = None,
    exchange: Optional[str] = None,
) -> dict:
    return {
        "body": event_proto.SerializeToString(),
        "exchange": exchange if exchange is not None else EXCHANGE_NAME,
        "routing_key": routing_key if routing_key else RoutingKey(event_proto),
        "props": props if props else {"delivery_mode": 2},
    }


class EventbusRpcClient(Generic[ProtoKlassType]):
    def __init__(
        self,
        proto_class: Type[ProtoKlassType],
        publisher: Type[PikaPublisher] = PikaPublisher,
        logger: logging.Logger = get_default_logger(),
        params: EventbusConfig = get_default_eventbus_params(),
    ):
        self.proto_class = proto_class
        self.params = params
        self.publisher = publisher(params=params, logger=logger)
        self.logger = logger

        if not self.params.enabled:
            self.logger.debug("EventbusRpcClient: Eventbus not enabled")
            return
        self.publisher.connect()
        result = self.publisher.channel.queue_declare(queue="", exclusive=True)
        self.callback_queue = result.method.queue
        self.publisher.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True,
        )
        self.response: Optional[ProtoKlassType] = None

    def on_response(self, ch: Any, method: Any, props: Any, body: bytes) -> None:
        if self.corr_id == props.correlation_id:
            message: ProtoKlassType = self.proto_class()
            message.ParseFromString(body)
            self.response = message

    def call(self, event_proto: message.Message, timeout_secs: float = 5.0, expiration_secs:  Optional[float] = None):
        """This blocks until a response is received from the event
        bus, or a timeout occurs (whereupon a TimeoutException will be
        raised)

        """
        if not self.params.enabled:
            raise RuntimeError("EventbusRpcClient: Eventbus not enabled")
        self.corr_id = str(uuid.uuid4())
        props = {
            "reply_to": self.callback_queue,
            "correlation_id": self.corr_id,
        }
        if expiration_secs:
            props["expiration"] = str(int(expiration_secs * 1000))
        self.publisher.publish(
            get_event_from_proto(
                event_proto,
                props=props,
            )
        )
        self.publisher.process(timeout_secs)
        if not self.response:
            raise TimeoutException(
                f"timeout waiting for response after {timeout_secs}s"
            )
        return self.response


PikaProducerClient = EventbusProducerClient()
PikaSyncProducerClient = EventbusProducerClient(run_async=False)
