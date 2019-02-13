from __future__ import annotations
from typing import MutableMapping, Union, List, Optional, Mapping, Any
from collections import OrderedDict
from datetime import datetime
from ..meta_data import (
    ProtocolMetaData,
    MessageMetaData,
    FieldMetaData,
    MessageFieldMetaDataMapping,
    message_member_iter,
    FieldMessageDataMap
)
from .encoder import encode, SOH
from .decoder import decode


def _to_value(protocol: ProtocolMetaData, meta_data: FieldMetaData, value: bytes) -> Any:
    if not value:
        return None
    elif meta_data.values and value in meta_data.values:
        return meta_data.values[value]
    elif meta_data.type in ('INT', 'SEQNUM', 'NUMINGROUP', 'LENGTH'):
        return int(value.lstrip(b'0') or b'0')
    elif meta_data.type in ('FLOAT', 'QTY', 'PRICE', 'PRICEOFFSET'):
        return float(value)
    elif meta_data.type in ('CHAR', 'STRING', 'CURRENCY', 'EXCHANGE'):
        return value.decode('ascii')
    elif meta_data.type == 'BOOLEAN':
        return value == b'Y'
    elif meta_data.type == 'MULTIPLEVALUESTRING':
        return value.decode('ascii').split(' ')
    elif meta_data.type in ('UTCTIMESTAMP', 'UTCTIMEONLY'):
        return datetime.strptime(value.decode('ascii'), protocol.formats[meta_data.type])
    elif meta_data.type in ('LOCALMKTDATE', 'UTCDATE'):
        return datetime.strptime(value.decode('ascii'), '%Y%m%d')
    elif meta_data.type == 'MONTHYEAR':
        return value.decode('ascii')
    else:
        return value.decode('ascii')


def _from_value(protocol: ProtocolMetaData, meta_data: FieldMetaData, value: Any) -> bytes:
    if value is None:
        return b''
    elif meta_data.values_by_name and value in meta_data.values_by_name:
        return meta_data.values_by_name[value]
    elif meta_data.type in ('INT', 'SEQNUM', 'NUMINGROUP', 'LENGTH'):
        return str(value).encode()
    elif meta_data.type in ('FLOAT', 'QTY', 'PRICE', 'PRICEOFFSET', 'AMT'):
        return str(value).encode()
    elif meta_data.type in ('CHAR', 'STRING', 'CURRENCY', 'EXCHANGE'):
        return value.encode()
    elif meta_data.type == 'BOOLEAN':
        return b'Y' if value else b'N'
    elif meta_data.type == 'MULTIPLEVALUESTRING':
        return ' '.join(value).encode()
    elif meta_data.type in ('UTCTIMESTAMP', 'UTCTIMEONLY'):
        return value.strftime(protocol.formats[meta_data.type]).encode()
    elif meta_data.type in ('LOCALMKTDATE', 'UTCDATE'):
        return value.strftime('%Y%m%d').encode()
    elif meta_data.type == 'MONTHYEAR':
        return value.encode()
    else:
        return str(value).encode()


def _to_dict(protocol: ProtocolMetaData, data: FieldMessageDataMap) -> Mapping[str, Any]:
    return {
        meta_data.name: _to_value(protocol, meta_data, value) if isinstance(value, bytes) else [
            _to_dict(protocol, nested_data) for nested_data in value
        ]
        for meta_data, value in data.items()
    }


class FixMessageGroup:

    def __init__(
            self,
            meta_data: MessageFieldMetaDataMapping,
            data: List[FixMessageMap]
    ) -> None:
        self._message_field_meta_data = {
            member.member.name: member
            for member in message_member_iter(meta_data.values())
        }
        self._data = data

    def __getitem__(self, index: int) -> FixMessageMap:
        return self._data[index]

    def __setitem__(self, index: int, value: FixMessageMap) -> None:
        self._data[index] = value

    def __delitem__(self, index: int) -> None:
        del self._data[index]

    def add(self) -> FixMessageMap:
        item = FixMessageMap(self._message_field_meta_data, OrderedDict())
        self._data.append(item)
        return item


class FixMessageMap:

    def __init__(
            self,
            meta_data: MessageFieldMetaDataMapping,
            data: Optional[FieldMessageDataMap]
    ) -> None:
        self._message_field_meta_data = {
            member.member.name: member
            for member in message_member_iter(meta_data.values())
        }
        self._data = data or OrderedDict()

    @property
    def message_field_meta_data(self) -> MessageFieldMetaDataMapping:
        return self._message_field_meta_data

    @property
    def data(self) -> MutableMapping[FieldMetaData, bytes]:
        return self._data

    def __getitem__(self, key: str) -> Union[bytes, FixMessageGroup]:
        member = self._message_field_meta_data[key]
        if member.type == 'field':
            field: FieldMetaData = member.member
            return self._data.get(field)
        elif member.type == 'group':
            group: FieldMetaData = member.member
            if group not in self._data:
                self._data[group] = []
            return FixMessageGroup(member.children, self._data[group])
        else:
            raise ValueError(f'unknown type "{member.type}"')

    def __setitem__(self, key: str, value: bytes) -> None:
        member = self._message_field_meta_data[key]
        self._data[member.member] = value


def _populate_message_from_dict(
        protocol: ProtocolMetaData,
        message: FixMessageMap,
        dct: Mapping[str, Any]
) -> FixMessageMap:
    for name, value in dct.items():
        if isinstance(value, list):
            for item in value:
                group = message[name].add()
                _populate_message_from_dict(protocol, group, item)
        else:
            field_meta_data = message.message_field_meta_data[name]
            message[name] = _from_value(protocol, field_meta_data.member, value)

    return message


class FixMessage(FixMessageMap):

    def __init__(
            self,
            protocol: ProtocolMetaData,
            message_name: str,
            data: Optional[FieldMessageDataMap] = None
    ) -> None:
        self._protocol = protocol
        self._message_meta_data = protocol.messages_by_name[message_name]

        meta_data = OrderedDict()
        meta_data.update({
            member.member.name: member
            for member in message_member_iter(protocol.header.values())
        })
        meta_data.update({
            member.member.name: member
            for member in message_member_iter(self._message_meta_data.fields.values())
        })
        meta_data.update({
            member.member.name: member
            for member in message_member_iter(protocol.trailer.values())
        })

        super().__init__(meta_data, data)

        if not data:
            self['BeginString'] = protocol.begin_string
            self['BodyLength'] = b''
            self['MsgType'] = self._message_meta_data.msgtype
            self['CheckSum'] = b'000'

    @property
    def protocol(self) -> ProtocolMetaData:
        return self._protocol

    @property
    def message_meta_data(self) -> MessageMetaData:
        return self._message_meta_data

    @classmethod
    def decode(
            cls,
            protocol: ProtocolMetaData,
            buf: bytes,
            *,
            strict: bool = True,
            validate: bool = True,
            sep: bytes = SOH,
            convert_sep_to_soh_for_checksum: bool = True
    ) -> FixMessage:
        message_name, decoded_message = decode(
            protocol,
            buf,
            strict=strict,
            validate=validate,
            sep=sep,
            convert_sep_to_soh_for_checksum=convert_sep_to_soh_for_checksum
        )
        return FixMessage(protocol, message_name, decoded_message)

    def encode(
            self,
            sep: bytes = SOH,
            regenerate_integrity: bool = True
    ) -> bytes:
        meta_data = {
            member.member.name: member
            for member in message_member_iter(self._message_meta_data.fields.values())
        }
        return encode(
            self.protocol,
            self.data,
            meta_data,
            sep,
            regenerate_integrity=regenerate_integrity
        )

    def to_dict(self) -> Mapping[str, Any]:
        return _to_dict(self.protocol, self.data)

    @classmethod
    def from_dict(cls, protocol: ProtocolMetaData, dct: Mapping[str, Any]) -> FixMessage:
        msgtype = _from_value(protocol, protocol.fields_by_name['MsgType'], dct['MsgType'])
        message_name = protocol.messages_by_type[msgtype].name
        message = FixMessage(protocol, message_name)
        _populate_message_from_dict(protocol, message, dct)
        return message
