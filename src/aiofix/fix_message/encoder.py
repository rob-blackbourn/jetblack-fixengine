from typing import Iterator, List, Tuple, MutableMapping
from ..meta_data import (
    message_member_iter,
    MessageMemberMetaData,
    MessageFieldMetaDataMapping,
    ProtocolMetaData,
    FieldMessageDataMap,
    FieldMetaData
)
from .errors import EncodingError
from .common import SOH


def _encode(
        encoded_message: List[Tuple[bytes, bytes]],
        data: FieldMessageDataMap,
        meta_data: Iterator[MessageMemberMetaData]
) -> None:
    for meta_data_item in meta_data:
        # Check for required fields.
        if meta_data_item.member not in data:
            if meta_data_item.is_required:
                raise EncodingError(f'required field "{meta_data_item.member.name}" is missing')
            continue

        item_data = data[meta_data_item.member]
        if meta_data_item.type == 'field':
            encoded_message.append((meta_data_item.member.number, item_data))
        elif meta_data_item.type == 'group':
            encoded_message.append((meta_data_item.member.number, str(len(item_data)).encode('ascii')))
            for group_item in item_data:
                _encode(
                    encoded_message,
                    group_item,
                    message_member_iter(meta_data_item.children.values())
                )
        else:
            raise EncodingError(f'unknown type "{meta_data_item.type}" for item "{meta_data_item.member.name}"')


def _regenerate_integrity(
        protocol: ProtocolMetaData,
        encoded_message: List[Tuple[bytes, bytes]],
        sep: bytes
) -> bytes:
    body = sep.join(field + b'=' + value for field, value in encoded_message[2:-1]) + sep
    body_lengh = len(body)

    encoded_header = [
        (protocol.fields_by_name['BeginString'].number, protocol.begin_string),
        (protocol.fields_by_name['BodyLength'].number, str(body_lengh).encode('ascii'))
    ]
    header = sep.join(field + b'=' + value for field, value in encoded_header) + sep

    buf = header + body

    # Calculate the checksum
    check_sum = sum(buf if sep == SOH else buf.replace(sep, SOH)) % 256
    buf += protocol.fields_by_name['CheckSum'].number + b'=' + f'{check_sum:#03}'.encode('ascii') + sep

    return buf


def encode(
        protocol: ProtocolMetaData,
        data: MutableMapping[FieldMetaData, bytes],
        message_field_meta_data: MessageFieldMetaDataMapping,
        sep: bytes = SOH,
        regenerate_integrity: bool = True
) -> bytes:
    encoded_message: List[Tuple[bytes, bytes]] = []

    _encode(encoded_message, data, message_member_iter(protocol.header.values()))
    _encode(encoded_message, data, message_member_iter(message_field_meta_data.values()))
    _encode(encoded_message, data, message_member_iter(protocol.trailer.values()))

    if regenerate_integrity:
        buf = _regenerate_integrity(protocol, encoded_message, sep)
    else:
        buf = sep.join(field + b'=' + value for field, value in encoded_message) + sep

    return buf
