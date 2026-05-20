import time
from typing import Any, Optional
import uuid

import dbtlabs.proto.private.v1.events.audit_pb2 as proto_events_audit
import dbtlabs.proto.private.v1.fields.account_pb2 as proto_fields_account
import dbtlabs.proto.private.v1.records.account_pb2 as proto_records_account
import dbtlabs.proto.private.v1.messaging_queue.event as proto_event


class UnknownAuditType(Exception):
    """Exception raised for unknown audit log events.
    """
    pass


def create_audit_event(account_id: str,
                       source: proto_events_audit.Record.Source,
                       service: proto_events_audit.Record.Service,
                       actor_type: proto_events_audit.Record.ActorType,
                       actor_id: str,
                       actor_name: str,
                       actor_ip: str,
                       event: Any,
                       actor_license_type: str = ""):
    """Wraps the specified 'event' with the appropriate auditing
metadata. The event can be any proto object. The audit event which is
returned is suitable for sending through the event bus, where it will
be routed to the appropriate backend services for long term
storage."""

    a = proto_records_account.Account(fields=proto_fields_account.Account(id=account_id))
    e = proto_events_audit.Record()
    e.id = str(uuid.uuid4())
    e.created_at_utc = int(time.time())
    e.account.CopyFrom(a)
    e.source = source # type: ignore
    e.service = service # type: ignore
    e.actor.type = actor_type # type: ignore
    e.actor.id = actor_id
    e.actor.name = actor_name
    e.actor.ip = actor_ip
    e.actor.license_type = actor_license_type

    event_found = False
    # find the corresponding event by its type
    for descriptor in e.DESCRIPTOR.fields:
        if descriptor.type == descriptor.TYPE_MESSAGE:
            if type(getattr(e, descriptor.name)) == type(event):
                getattr(e, descriptor.name).CopyFrom(event)
                e.routing_key = proto_event.RoutingKey(event)
                event_found = True
    if not event_found:
        raise UnknownAuditType(f"unknown event type: {type(event)}")
    e.internal = False
    return e


def create_internal_audit_event(account_id: str,
                                source: proto_events_audit.Record.Source,
                                service: proto_events_audit.Record.Service,
                                actor_type: proto_events_audit.Record.ActorType,
                                actor_id: str,
                                actor_name: str,
                                actor_ip: str,
                                event: Any):
    """Same as `create_audit_event`, but additionally marks the returned
event as "internal". Internal audit events will not be visible to end
users.
    """
    e = create_audit_event(account_id=account_id,
                           source=source,
                           service=service,
                           actor_type=actor_type,
                           actor_id=actor_id,
                           actor_name=actor_name,
                           actor_ip=actor_ip,
                           event=event)
    e.internal = True
    return e
