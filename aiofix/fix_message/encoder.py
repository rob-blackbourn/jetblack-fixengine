"""Encode a FIX message"""

from aiofix.meta_data.message_member import FieldMetaData
from typing import Iterator, List, Tuple, cast

from ..meta_data import (
    message_member_iter,
    MessageMemberMetaData,
    MessageMetaData,
    ProtocolMetaData,
    FieldMessageDataMap
)
from .errors import EncodingError
from .common import SOH, encode_value


def _encode_fields(
        protocol: ProtocolMetaData,
        encoded_message: List[Tuple[bytes, bytes]],
        data: FieldMessageDataMap,
        meta_data: Iterator[MessageMemberMetaData]
) -> None:
    for meta_datum in meta_data:
        # Check for required fields.
        if meta_datum.member.name not in data:
            if meta_datum.is_required:
                raise EncodingError(
                    f'required field "{meta_datum.member.name}" is missing')
            continue

        item_data = data[meta_datum.member.name]
        if meta_datum.type == 'field':
            field_member = cast(FieldMetaData, meta_datum.member)
            value = encode_value(protocol, field_member, item_data)
            encoded_message.append((field_member.number, value))
        elif meta_datum.type == 'group':
            field_member = cast(FieldMetaData, meta_datum.member)
            item_list = cast(List[FieldMessageDataMap], item_data)
            value = encode_value(protocol, field_member, len(item_list))
            encoded_message.append((field_member.number, value))
            assert meta_datum.children is not None
            for group_item in item_list:
                _encode_fields(
                    protocol,
                    encoded_message,
                    group_item,
                    message_member_iter(meta_datum.children.values())
                )
        else:
            raise EncodingError(
                f'unknown type "{meta_datum.type}" for item "{meta_datum.member.name}"')


def _regenerate_integrity(
        protocol: ProtocolMetaData,
        encoded_message: List[Tuple[bytes, bytes]],
        sep: bytes,
        convert_sep_for_checkum: bool
) -> bytes:
    body = sep.join(field + b'=' + value for field,
                    value in encoded_message[2:-1]) + sep
    body_lengh = len(body)

    encoded_header = [
        (protocol.fields_by_name['BeginString'].number, protocol.begin_string),
        (protocol.fields_by_name['BodyLength'].number,
         str(body_lengh).encode('ascii'))
    ]
    header = sep.join(field + b'=' + value for field,
                      value in encoded_header) + sep

    buf = header + body

    # Calculate the checksum
    check_sum = sum(
        buf if sep == SOH or not convert_sep_for_checkum else buf.replace(sep, SOH)) % 256
    buf += protocol.fields_by_name['CheckSum'].number + \
        b'=' + f'{check_sum:#03}'.encode('ascii') + sep

    return buf


def encode(
        protocol: ProtocolMetaData,
        data: FieldMessageDataMap,
        meta_data: MessageMetaData,
        *,
        sep: bytes = SOH,
        regenerate_integrity: bool = True,
        convert_sep_for_checksum: bool = True
) -> bytes:
    encoded_message: List[Tuple[bytes, bytes]] = []

    if regenerate_integrity:
        data['BeginString'] = protocol.begin_string.decode('ascii')
        data['BodyLength'] = 0
        data['CheckSum'] = '000'

    _encode_fields(protocol, encoded_message, data,
                   message_member_iter(protocol.header.values()))
    _encode_fields(protocol, encoded_message, data,
                   message_member_iter(meta_data.fields.values()))
    _encode_fields(protocol, encoded_message, data,
                   message_member_iter(protocol.trailer.values()))

    if regenerate_integrity:
        buf = _regenerate_integrity(
            protocol, encoded_message, sep, convert_sep_for_checksum)
    else:
        buf = sep.join(field + b'=' + value for field,
                       value in encoded_message) + sep

    return buf
