from typing import Mapping
from .message_member import FieldMetaData, ComponentMetaData, MessageMemberMetaData
from .message import MessageMetaData


class ProtocolMetaData:

    def __init__(
            self,
            version: str,
            begin_string: bytes,
            fields: Mapping[str, FieldMetaData],
            components: Mapping[str, ComponentMetaData],
            messages: Mapping[str, MessageMetaData],
            header: Mapping[str, MessageMemberMetaData],
            trailer: Mapping[str, MessageMemberMetaData],
            *,
            is_millisecond_time: bool = True,
            is_float_decimal=False
    ) -> None:
        self._version = version
        self._begin_string = begin_string
        self._fields_by_name = fields
        self._fields_by_number = {field.number: field for field in fields.values()}
        self._components = components
        self._messages_by_name = messages
        self._messages_by_type = {message.msgtype: message for message in messages.values()}
        self._header = header
        self._trailer = trailer
        self._is_millisecond_time = is_millisecond_time
        self._is_float_decimal = is_float_decimal

    @property
    def version(self) -> str:
        return self._version

    @property
    def begin_string(self) -> bytes:
        return self._begin_string

    @property
    def fields_by_name(self) -> Mapping[str, FieldMetaData]:
        return self._fields_by_name

    @property
    def fields_by_number(self) -> Mapping[bytes, FieldMetaData]:
        return self._fields_by_number

    @property
    def components(self) -> Mapping[str, ComponentMetaData]:
        return self._components

    @property
    def messages_by_name(self) -> Mapping[str, MessageMetaData]:
        return self._messages_by_name

    @property
    def messages_by_type(self) -> Mapping[bytes, MessageMetaData]:
        return self._messages_by_type

    @property
    def header(self) -> Mapping[str, MessageMemberMetaData]:
        return self._header

    @property
    def trailer(self) -> Mapping[str, MessageMemberMetaData]:
        return self._trailer

    @property
    def is_millisecond_time(self) -> bool:
        return self._is_millisecond_time

    @property
    def is_float_decimal(self) -> bool:
        return self._is_float_decimal

    def __str__(self) -> str:
        return f'<ProtocolMetaData: version="{self.version}", begin_string={self.begin_string}'

    __repr__ = __str__
