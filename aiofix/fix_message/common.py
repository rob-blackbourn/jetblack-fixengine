"""Common Code"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Tuple, Any
from ..meta_data import ProtocolMetaData, FieldMetaData

SOH = b'\x01'

UTCTIMESTAMP_FMT_MILLIS = '%Y%m%d-%H:%M:%S.%f'
UTCTIMESTAMP_FMT_NO_MILLIS = '%Y%m%d-%H:%M:%S'
UTCTIMEONLY_FMT_MILLIS = '%H:%M:%S.%f'
UTCTIMEONLY_FMT_NO_MILLIS = '%H:%M:%S'


def calc_checksum(
        buf: bytes,
        sep: bytes = SOH,
        convert_sep_to_soh_for_checksum: bool = False
) -> bytes:
    """Calculate the FIX message checksum.

    In production the separator is always SOH (ascii 0x01). For diagnostics the
    '|' charactor is often used to allow the message to be printed. As this will
    give a different checksum a flag is provided to convert the separator to SOH
    if required.

    Args:
        buf (bytes): The FIX message buffer.
        sep (bytes, optional): The separator. Defaults to SOH.
        convert_sep_to_soh_for_checksum (bool, optional): If true convert the
            separator to SOH before calculating the checksum. Defaults to False.

    Returns:
        bytes: The checksum.
    """
    if sep != SOH and convert_sep_to_soh_for_checksum:
        buf = buf.replace(sep, SOH)

    check_sum = sum(buf[:-len(b'10=000\x01')]) % 256
    return f'{check_sum:#03}'.encode('ascii')


def calc_body_length(
        buf: bytes,
        encoded_message: List[Tuple[bytes, bytes]],
        sep: bytes = SOH
) -> int:
    """Calculate the body length

    Args:
        buf (bytes): The FIX message buffer
        encoded_message (List[Tuple[bytes, bytes]]): The encoded FIX message
        sep (bytes, optional): The message separator. Defaults to SOH.

    Returns:
        int: The length of the body.
    """
    header = sep.join([
        b'='.join(field_value)
        for field_value in encoded_message[:2]
    ]) + sep
    trailer = b'='.join(encoded_message[-1]) + sep
    body_length = len(buf) - len(header) - len(trailer)
    return body_length


def decode_value(
        protocol: ProtocolMetaData,
        meta_data: FieldMetaData,
        value: bytes
) -> Any:
    """Decoide the value of a field

    Args:
        protocol (ProtocolMetaData): The FIX protocol
        meta_data (FieldMetaData): The field meta data
        value (bytes): The value of the field

    Returns:
        Any: [description]
    """
    if not value:
        return None
    elif meta_data.values and value in meta_data.values:
        return meta_data.values[value]
    elif meta_data.type in ('INT', 'SEQNUM', 'NUMINGROUP', 'LENGTH'):
        return int(value.lstrip(b'0') or b'0')
    elif meta_data.type in ('FLOAT', 'QTY', 'PRICE', 'PRICEOFFSET'):
        return Decimal(value.decode('ascii')) if protocol.is_float_decimal else float(value)
    elif meta_data.type in ('CHAR', 'STRING', 'CURRENCY', 'EXCHANGE'):
        return value.decode('ascii')
    elif meta_data.type == 'BOOLEAN':
        return value == b'Y'
    elif meta_data.type == 'MULTIPLEVALUESTRING':
        return value.decode('ascii').split(' ')
    elif meta_data.type == 'UTCTIMESTAMP':
        if protocol.is_millisecond_time:
            return datetime.strptime(
                value.decode('ascii'),
                UTCTIMESTAMP_FMT_MILLIS
            ).replace(tzinfo=timezone.utc)
        else:
            return datetime.strptime(
                value.decode('ascii'),
                UTCTIMESTAMP_FMT_NO_MILLIS
            ).replace(tzinfo=timezone.utc)
    elif meta_data.type == 'UTCTIMEONLY':
        if protocol.is_millisecond_time:
            return datetime.strptime(value.decode('ascii'), UTCTIMEONLY_FMT_MILLIS)
        else:
            return datetime.strptime(value.decode('ascii'), UTCTIMEONLY_FMT_NO_MILLIS)
    elif meta_data.type in ('LOCALMKTDATE', 'UTCDATE'):
        return datetime.strptime(value.decode('ascii'), '%Y%m%d')
    elif meta_data.type == 'MONTHYEAR':
        return value.decode('ascii')
    else:
        return value.decode('ascii')


def encode_value(
        protocol: ProtocolMetaData,
        meta_data: FieldMetaData,
        value: Any
) -> bytes:
    """Encode a field value

    Args:
        protocol (ProtocolMetaData): The FIX protocol meta data
        meta_data (FieldMetaData): The field meta data
        value (Any): The value to encode

    Returns:
        bytes: The encoded field value
    """
    if value is None:
        return b''
    elif meta_data.values_by_name and value in meta_data.values_by_name:
        return meta_data.values_by_name[value]
    elif meta_data.type in ('INT', 'SEQNUM', 'NUMINGROUP', 'LENGTH'):
        return str(value).encode()
    elif meta_data.type in ('FLOAT', 'QTY', 'PRICE', 'PRICEOFFSET', 'AMT'):
        if isinstance(value, Decimal):
            return str(value).encode()
        elif value != int(value):
            return str(int(value)).encode()
        else:
            return str(value).encode()
    elif meta_data.type in ('CHAR', 'STRING', 'CURRENCY', 'EXCHANGE'):
        return value.encode()
    elif meta_data.type == 'BOOLEAN':
        return b'Y' if value else b'N'
    elif meta_data.type == 'MULTIPLEVALUESTRING':
        return ' '.join(value).encode()
    elif meta_data.type == 'UTCTIMESTAMP':
        if protocol.is_millisecond_time:
            return value.strftime(UTCTIMESTAMP_FMT_MILLIS)[:-3].encode()
        else:
            return value.strftime(UTCTIMESTAMP_FMT_NO_MILLIS).encode()
    elif meta_data.type == 'UTCTIMEONLY':
        if protocol.is_millisecond_time:
            return value.strftime(UTCTIMEONLY_FMT_MILLIS).encode()
        else:
            return value.strftime(UTCTIMEONLY_FMT_NO_MILLIS).encode()
    elif meta_data.type in ('LOCALMKTDATE', 'UTCDATE'):
        return value.strftime('%Y%m%d').encode()
    elif meta_data.type == 'MONTHYEAR':
        return value.encode()
    else:
        return str(value).encode()
