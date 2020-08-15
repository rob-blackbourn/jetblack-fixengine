"""Common Code"""

from aiofix.fix_message.errors import DecodingError, EncodingError
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, List, Tuple, Union

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


def _decode_int(
        _protocol: ProtocolMetaData,
        meta_data: FieldMetaData,
        value: bytes
) -> Union[int, str]:
    if meta_data.values and value in meta_data.values:
        return meta_data.values[value]
    else:
        return int(value.lstrip(b'0') or b'0')


def _decode_seqnum(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: bytes
) -> int:
    return int(value.lstrip(b'0') or b'0')


def _decode_numingroup(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: bytes
) -> int:
    return int(value.lstrip(b'0') or b'0')


def _decode_length(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: bytes
) -> int:
    return int(value.lstrip(b'0') or b'0')


def _decode_float(
        protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: bytes
) -> Union[float, Decimal]:
    return Decimal(value.decode('ascii')) if protocol.is_float_decimal else float(value)


def _decode_qty(
        protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: bytes
) -> Union[float, Decimal]:
    return Decimal(value.decode('ascii')) if protocol.is_float_decimal else float(value)


def _decode_price(
        protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: bytes
) -> Union[float, Decimal]:
    return Decimal(value.decode('ascii')) if protocol.is_float_decimal else float(value)


def _decode_price_offset(
        protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: bytes
) -> Union[float, Decimal]:
    return Decimal(value.decode('ascii')) if protocol.is_float_decimal else float(value)


def _decode_amt(
        protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: bytes
) -> Union[float, Decimal]:
    return Decimal(value.decode('ascii')) if protocol.is_float_decimal else float(value)


def _decode_char(
        _protocol: ProtocolMetaData,
        meta_data: FieldMetaData,
        value: bytes
) -> str:
    if meta_data.values and value in meta_data.values:
        return meta_data.values[value]
    else:
        return value.decode('ascii')


def _decode_string(
        _protocol: ProtocolMetaData,
        meta_data: FieldMetaData,
        value: bytes
) -> str:
    if meta_data.values and value in meta_data.values:
        return meta_data.values[value]
    else:
        return value.decode('ascii')


def _decode_currency(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: bytes
) -> str:
    return value.decode('ascii')


def _decode_exchange(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: bytes
) -> str:
    return value.decode('ascii')


def _decode_multiple_value_str(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: bytes
) -> List[str]:
    return value.decode('ascii').split(' ')


def _decode_bool(
        protocol: ProtocolMetaData,
        meta_data: FieldMetaData,
        value: bytes
) -> Union[bool, str]:
    if protocol.is_bool_enum and meta_data.values and value in meta_data.values:
        return meta_data.values[value]
    else:
        return value == b'Y'


def _decode_utc_timestamp(
        protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: bytes
) -> datetime:
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


def _decode_utc_time_only(
        protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: bytes
) -> datetime:
    if protocol.is_millisecond_time:
        return datetime.strptime(value.decode('ascii'), UTCTIMEONLY_FMT_MILLIS)
    else:
        return datetime.strptime(value.decode('ascii'), UTCTIMEONLY_FMT_NO_MILLIS)


def _decode_localmktdate(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: bytes
) -> datetime:
    return datetime.strptime(value.decode('ascii'), '%Y%m%d')


def _decode_utcdate(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: bytes
) -> datetime:
    return datetime.strptime(value.decode('ascii'), '%Y%m%d')


def _decode_monthyear(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: bytes
) -> str:
    return value.decode('ascii')


_DECODERS = {
    'INT': _decode_int,
    'SEQNUM': _decode_seqnum,
    'NUMINGROUP': _decode_numingroup,
    'LENGTH': _decode_length,
    'FLOAT': _decode_float,
    'QTY': _decode_qty,
    'PRICE': _decode_price,
    'PRICEOFFSET': _decode_price_offset,
    'AMT': _decode_amt,
    'CHAR': _decode_char,
    'STRING': _decode_string,
    'CURRENCY': _decode_currency,
    'EXCHANGE': _decode_exchange,
    'BOOLEAN': _decode_bool,
    'MULTIPLEVALUESTRING': _decode_multiple_value_str,
    'UTCTIMESTAMP': _decode_utc_timestamp,
    'UTCTIMEONLY': _decode_utc_time_only,
    'LOCALMKTDATE': _decode_localmktdate,
    'UTCDATE': _decode_utcdate,
    'MONTHYEAR': _decode_monthyear
}


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

    decoder = _DECODERS.get(meta_data.type)
    if not decoder:
        raise DecodingError(f'Unknown type "{meta_data.type}"')
    return decoder(protocol, meta_data, value)


def _encode_int(
        _protocol: ProtocolMetaData,
        meta_data: FieldMetaData,
        value: Union[int, str]
) -> bytes:
    if isinstance(value, str) and meta_data.values_by_name and value in meta_data.values_by_name:
        return meta_data.values_by_name[value]
    else:
        return str(value).encode()


def _encode_seqnum(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: int
) -> bytes:
    return str(value).encode()


def _encode_numingroup(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: int
) -> bytes:
    return str(value).encode()


def _encode_length(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: int
) -> bytes:
    return str(value).encode()


def _encode_float(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: Union[Decimal, float, int]
) -> bytes:
    if isinstance(value, Decimal):
        return str(value).encode()
    elif value != int(value):
        return str(int(value)).encode()
    else:
        return str(value).encode()


def _encode_qty(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: Union[Decimal, float, int]
) -> bytes:
    if isinstance(value, Decimal):
        return str(value).encode()
    elif value != int(value):
        return str(int(value)).encode()
    else:
        return str(value).encode()


def _encode_price(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: Union[Decimal, float, int]
) -> bytes:
    if isinstance(value, Decimal):
        return str(value).encode()
    elif value != int(value):
        return str(int(value)).encode()
    else:
        return str(value).encode()


def _encode_price_offset(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: Union[Decimal, float, int]
) -> bytes:
    if isinstance(value, Decimal):
        return str(value).encode()
    elif value != int(value):
        return str(int(value)).encode()
    else:
        return str(value).encode()


def _encode_amt(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: Union[Decimal, float, int]
) -> bytes:
    if isinstance(value, Decimal):
        return str(value).encode()
    elif value != int(value):
        return str(int(value)).encode()
    else:
        return str(value).encode()


def _encode_char(
        _protocol: ProtocolMetaData,
        meta_data: FieldMetaData,
        value: str
) -> bytes:
    if meta_data.values_by_name and value in meta_data.values_by_name:
        return meta_data.values_by_name[value]
    else:
        return value.encode()


def _encode_string(
        _protocol: ProtocolMetaData,
        meta_data: FieldMetaData,
        value: str
) -> bytes:
    if meta_data.values_by_name and value in meta_data.values_by_name:
        return meta_data.values_by_name[value]
    else:
        return value.encode()


def _encode_currency(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: str
) -> bytes:
    return value.encode()


def _encode_exchange(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: str
) -> bytes:
    return value.encode()


def _encode_monthyear(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: str
) -> bytes:
    return value.encode()


def _encode_bool(
        _protocol: ProtocolMetaData,
        meta_data: FieldMetaData,
        value: Union[bool, str]
) -> bytes:
    if isinstance(value, str) and meta_data.values_by_name and value in meta_data.values_by_name:
        return meta_data.values_by_name[value]
    else:
        return b'Y' if value else b'N'


def _encode_multi_value_str(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: List[str]
) -> bytes:
    return ' '.join(value).encode()


def _encode_utc_timestamp(
        protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: datetime
) -> bytes:
    if protocol.is_millisecond_time:
        return value.strftime(UTCTIMESTAMP_FMT_MILLIS)[:-3].encode()
    else:
        return value.strftime(UTCTIMESTAMP_FMT_NO_MILLIS).encode()


def _encode_utc_time_only(
        protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: datetime
) -> bytes:
    if protocol.is_millisecond_time:
        return value.strftime(UTCTIMEONLY_FMT_MILLIS).encode()
    else:
        return value.strftime(UTCTIMEONLY_FMT_NO_MILLIS).encode()


def _encode_localmktdate(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: datetime
) -> bytes:
    return value.strftime('%Y%m%d').encode()


def _encode_utcdate(
        _protocol: ProtocolMetaData,
        _meta_data: FieldMetaData,
        value: datetime
) -> bytes:
    return value.strftime('%Y%m%d').encode()


_ENCODERS = {
    'INT': _encode_int,
    'SEQNUM': _encode_seqnum,
    'NUMINGROUP': _encode_numingroup,
    'LENGTH': _encode_length,
    'FLOAT': _encode_float,
    'QTY': _encode_qty,
    'PRICE': _encode_price,
    'PRICEOFFSET': _encode_price_offset,
    'AMT': _encode_amt,
    'CHAR': _encode_char,
    'STRING': _encode_string,
    'CURRENCY': _encode_currency,
    'EXCHANGE': _encode_exchange,
    'BOOLEAN': _encode_bool,
    'MULTIPLEVALUESTRING': _encode_multi_value_str,
    'UTCTIMESTAMP': _encode_utc_timestamp,
    'UTCTIMEONLY': _encode_utc_time_only,
    'LOCALMKTDATE': _encode_localmktdate,
    'UTCDATE': _encode_utcdate,
    'MONTHYEAR': _encode_monthyear
}


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

    encoder = _ENCODERS.get(meta_data.type)
    if not encoder:
        raise EncodingError(f'Unknown type "{meta_data.type}"')

    return encoder(protocol, meta_data, value)
