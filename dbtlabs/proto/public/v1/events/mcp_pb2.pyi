"""
@generated by mypy-protobuf.  Do not edit manually!
isort:skip_file
"""

import builtins
import collections.abc
import dbtlabs.proto.public.v1.events.vortex_pb2
import google.protobuf.descriptor
import google.protobuf.internal.containers
import google.protobuf.message
import typing

DESCRIPTOR: google.protobuf.descriptor.FileDescriptor

@typing.final
class ToolCalled(google.protobuf.message.Message):
    DESCRIPTOR: google.protobuf.descriptor.Descriptor

    @typing.final
    class ArgumentsEntry(google.protobuf.message.Message):
        DESCRIPTOR: google.protobuf.descriptor.Descriptor

        KEY_FIELD_NUMBER: builtins.int
        VALUE_FIELD_NUMBER: builtins.int
        key: builtins.str
        value: builtins.str
        def __init__(
            self,
            *,
            key: builtins.str = ...,
            value: builtins.str = ...,
        ) -> None: ...
        def ClearField(self, field_name: typing.Literal["key", b"key", "value", b"value"]) -> None: ...

    ENRICHMENT_FIELD_NUMBER: builtins.int
    EVENT_ID_FIELD_NUMBER: builtins.int
    START_TIME_MS_FIELD_NUMBER: builtins.int
    END_TIME_MS_FIELD_NUMBER: builtins.int
    TOOL_NAME_FIELD_NUMBER: builtins.int
    ARGUMENTS_FIELD_NUMBER: builtins.int
    ERROR_MESSAGE_FIELD_NUMBER: builtins.int
    DBT_CLOUD_ENVIRONMENT_ID_DEV_FIELD_NUMBER: builtins.int
    DBT_CLOUD_ENVIRONMENT_ID_PROD_FIELD_NUMBER: builtins.int
    DBT_CLOUD_USER_ID_FIELD_NUMBER: builtins.int
    LOCAL_USER_ID_FIELD_NUMBER: builtins.int
    HOST_FIELD_NUMBER: builtins.int
    MULTICELL_ACCOUNT_PREFIX_FIELD_NUMBER: builtins.int
    event_id: builtins.str
    """event_id is the unique identifier for this event. It is a generated UUID."""
    start_time_ms: builtins.int
    """The start of the tool call in milliseconds since the Unix epoch"""
    end_time_ms: builtins.int
    """The end of the tool call in milliseconds since the Unix epoch"""
    tool_name: builtins.str
    """The name of the tool, e.g. get_dimentions, dbt build, get_mart_models"""
    error_message: builtins.str
    """An error message if the call fails"""
    dbt_cloud_environment_id_dev: builtins.str
    """The user can optionally set their dev environment id to use tools like the execute_sql"""
    dbt_cloud_environment_id_prod: builtins.str
    """The user can optionally set their prod environment id to use tools like list_metrics"""
    dbt_cloud_user_id: builtins.str
    """The user can optionally set their user id to use tools like execute_sql"""
    local_user_id: builtins.str
    """The user id found at ~/.dbt/.user.yml if present"""
    host: builtins.str
    """The dbt Cloud host that the user configured"""
    multicell_account_prefix: builtins.str
    """The multicell account prefix that the user configured: https://docs.getdbt.com/docs/cloud/about-cloud/access-regions-ip-addresses"""
    @property
    def enrichment(self) -> dbtlabs.proto.public.v1.events.vortex_pb2.VortexMessageEnrichment: ...
    @property
    def arguments(self) -> google.protobuf.internal.containers.ScalarMap[builtins.str, builtins.str]:
        """The arguments supplied to the tool, e.g. a list of metrics or a dbt CLI selector"""

    def __init__(
        self,
        *,
        enrichment: dbtlabs.proto.public.v1.events.vortex_pb2.VortexMessageEnrichment | None = ...,
        event_id: builtins.str = ...,
        start_time_ms: builtins.int = ...,
        end_time_ms: builtins.int = ...,
        tool_name: builtins.str = ...,
        arguments: collections.abc.Mapping[builtins.str, builtins.str] | None = ...,
        error_message: builtins.str = ...,
        dbt_cloud_environment_id_dev: builtins.str = ...,
        dbt_cloud_environment_id_prod: builtins.str = ...,
        dbt_cloud_user_id: builtins.str = ...,
        local_user_id: builtins.str = ...,
        host: builtins.str = ...,
        multicell_account_prefix: builtins.str = ...,
    ) -> None: ...
    def HasField(self, field_name: typing.Literal["enrichment", b"enrichment"]) -> builtins.bool: ...
    def ClearField(self, field_name: typing.Literal["arguments", b"arguments", "dbt_cloud_environment_id_dev", b"dbt_cloud_environment_id_dev", "dbt_cloud_environment_id_prod", b"dbt_cloud_environment_id_prod", "dbt_cloud_user_id", b"dbt_cloud_user_id", "end_time_ms", b"end_time_ms", "enrichment", b"enrichment", "error_message", b"error_message", "event_id", b"event_id", "host", b"host", "local_user_id", b"local_user_id", "multicell_account_prefix", b"multicell_account_prefix", "start_time_ms", b"start_time_ms", "tool_name", b"tool_name"]) -> None: ...

global___ToolCalled = ToolCalled
