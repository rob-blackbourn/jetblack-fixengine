from typing import MutableMapping, Tuple, Optional, List, Iterator
from collections import OrderedDict
from ..meta_data import (
    ProtocolMetaData,
    FieldMetaData,
    MessageMemberMetaData,
    message_member_iter,
    FieldMessageDataMap,
    MessageMetaData
)
from .errors import FieldValueError, DecodingError
from .common import SOH, calc_checksum, calc_body_length


def _assert_field_value_matches(field: FieldMetaData, expected: bytes, received: bytes) -> None:
    if expected != received:
        raise FieldValueError(field, received, expected)


def _to_encoded_message(buf: bytes, sep: bytes) -> List[Tuple[bytes, bytes]]:
    encoded_message: List[Tuple[bytes, bytes]] = [
        field_value.split(b'=', maxsplit=1)
        for field_value in buf.split(sep)
    ]
    return encoded_message[:-1]


def _find_next_member(
        received_field: FieldMetaData,
        expected_fields: Iterator[MessageMemberMetaData],
        strict: bool
) -> Optional[MessageMemberMetaData]:
    # Find the next matching field.
    while True:
        try:
            expected_field = next(expected_fields)
            if expected_field.member.number == received_field.number:
                return expected_field

            if expected_field.is_required and strict:
                raise DecodingError(f'required field missing {expected_field}')

        except StopIteration:
            return None


def _decode_fields_in_order(
        protocol: ProtocolMetaData,
        encoded_message: List[Tuple[bytes, bytes]],
        index: int,
        message_members: Iterator[MessageMemberMetaData],
        strict: bool
) -> Tuple[FieldMessageDataMap, int]:
    decoded_message: FieldMessageDataMap = OrderedDict()

    while index < len(encoded_message):

        field_number, value = encoded_message[index]
        received_field = protocol.fields_by_number.get(field_number)
        if not received_field:
            raise DecodingError(f'received unknown field "{field_number}" of value "{value}"')
        member = _find_next_member(received_field, message_members, strict)
        if not member:
            break
        index += 1

        if member.type == 'group':
            decoded_groups, index = _decode_group(protocol, encoded_message, index, member, int(value), strict)
            decoded_message[received_field] = value
        else:
            decoded_message[received_field] = value

    # Check if any members are required.
    required_fields = list(filter(lambda x: x.is_required, message_members))
    if len(required_fields) > 0:
        raise DecodingError(f'required fields missing: {required_fields}')

    return decoded_message, index


def _decode_fields_any_order(
        protocol: ProtocolMetaData,
        encoded_message: List[Tuple[bytes, bytes]],
        index: int,
        message_members: MutableMapping[str, MessageMemberMetaData],
        strict: bool = True
) -> Tuple[FieldMessageDataMap, int]:
    decoded_message: FieldMessageDataMap = OrderedDict()

    while index < len(encoded_message):

        field_number, value = encoded_message[index]
        received_field = protocol.fields_by_number[field_number]
        member = message_members.get(field_number)
        if not member:
            break

        del message_members[field_number]
        index += 1

        if member.type == 'group':
            decoded_groups, index = _decode_group(protocol, encoded_message, index, member, int(value), strict)
            decoded_message[received_field] = decoded_groups
        else:
            decoded_message[received_field] = value

    required_members = list(filter(lambda x: x.is_required, message_members.values()))
    if len(required_members) > 0:
        raise DecodingError(f'required fields missing: {[member.member.name for member in required_members]}')

    return decoded_message, index


def _decode_group(
        protocol: ProtocolMetaData,
        encoded_message: List[Tuple[bytes, bytes]],
        index: int,
        member: MessageMemberMetaData,
        count: int,
        strict: bool
) -> Tuple[List[FieldMessageDataMap], int]:
    decoded_groups: List[FieldMessageDataMap] = []
    for i in range(int(count)):
        decoded_group, index = _decode_fields_in_order(
            protocol,
            encoded_message,
            index,
            message_member_iter(member.children.values()),
            strict
        )
        decoded_groups.append(decoded_group)
    return decoded_groups, index


def _decode_header(
        protocol: ProtocolMetaData,
        encoded_message: List[Tuple[bytes, bytes]],
        strict: bool
) -> Tuple[FieldMessageDataMap, int]:
    decoded_message: FieldMessageDataMap = OrderedDict()

    # The first three header fields must be in order.
    header_fields = list(message_member_iter(protocol.header.values()))
    decoded_header_head, index = _decode_fields_in_order(
        protocol,
        encoded_message,
        0,
        iter(header_fields[:3]),
        strict
    )
    decoded_message.update(decoded_header_head)
    # The remaining header fields can be in any order.
    decoded_header_tail, index = _decode_fields_any_order(
        protocol,
        encoded_message,
        index,
        {member.member.number: member for member in header_fields[3:]},
        strict
    )
    decoded_message.update(decoded_header_tail)

    return decoded_message, index


def _decode_body(
        protocol: ProtocolMetaData,
        encoded_message: List[Tuple[bytes, bytes]],
        index: int,
        decoded_message: FieldMessageDataMap,
        strict: bool
) -> Tuple[FieldMessageDataMap, int, MessageMetaData]:
    # Find the message type meta data.
    msg_type_field = protocol.fields_by_name['MsgType']
    msg_type = decoded_message[msg_type_field]
    meta_data = protocol.messages_by_type[msg_type]

    # Body fields can be in any order
    decoded_body, index = _decode_fields_any_order(
        protocol,
        encoded_message,
        index,
        {member.member.number: member for member in message_member_iter(meta_data.fields.values())},
        strict
    )
    decoded_message.update(decoded_body)

    return decoded_message, index, meta_data


def _decode_trailer(
        protocol: ProtocolMetaData,
        encoded_message: List[Tuple[bytes, bytes]],
        index: int,
        decoded_message: FieldMessageDataMap,
        strict: bool
) -> FieldMessageDataMap:
    # All but the last field can be in any order.
    trailer_fields = list(message_member_iter(protocol.trailer.values()))
    decoded_trailer_head, index = _decode_fields_any_order(
        protocol,
        encoded_message,
        index,
        {member.member.number: member for member in trailer_fields[:-1]},
        strict
    )
    decoded_message.update(decoded_trailer_head)

    # The last field should be the checksum.
    decoded_trailer_tail, index = _decode_fields_in_order(
        protocol,
        encoded_message,
        index,
        iter(trailer_fields[-1:]),
        strict
    )
    decoded_message.update(decoded_trailer_tail)

    return decoded_message


def assert_message_valid(
        protocol: ProtocolMetaData,
        buf: bytes,
        encoded_message: List[Tuple[bytes, bytes]],
        decoded_message: FieldMessageDataMap,
        sep: bytes,
        convert_sep_to_soh_for_checksum: bool
) -> None:
    begin_string_field = protocol.fields_by_name['BeginString']
    begin_string_value = decoded_message[begin_string_field]
    _assert_field_value_matches(begin_string_field, protocol.begin_string, begin_string_value)

    # Calculate the body length.
    body_length_field = protocol.fields_by_name['BodyLength']
    body_length_value = decoded_message[body_length_field]
    body_length = calc_body_length(buf, encoded_message, sep)
    _assert_field_value_matches(body_length_field, body_length_value, str(body_length).encode('ascii'))

    # Calculate the checkum.
    check_sum_field = protocol.fields_by_name['CheckSum']
    check_sum_value = decoded_message[check_sum_field]
    check_sum = calc_checksum(buf, sep, convert_sep_to_soh_for_checksum)
    _assert_field_value_matches(protocol.fields_by_name['CheckSum'], check_sum, check_sum_value)


def decode(
        protocol: ProtocolMetaData,
        buf: bytes,
        *,
        strict: bool = True,
        validate: bool = True,
        sep: bytes = SOH,
        convert_sep_to_soh_for_checksum: bool = True
) -> Tuple[str, FieldMessageDataMap]:
    encoded_message = _to_encoded_message(buf, sep)

    decoded_message, index = _decode_header(protocol, encoded_message, strict)
    decoded_message, index, meta_data = _decode_body(protocol, encoded_message, index, decoded_message, strict)
    decoded_message = _decode_trailer(protocol, encoded_message, index, decoded_message, strict)

    if validate:
        assert_message_valid(protocol, buf, encoded_message, decoded_message, sep, convert_sep_to_soh_for_checksum)

    return meta_data.name, decoded_message
