from datetime import datetime
from typing import List, Tuple, Any
from ..meta_data import ProtocolMetaData, FieldMetaData

SOH = b'\x01'


def calc_checksum(buf: bytes, sep: bytes, convert_sep_to_soh_for_checksum: bool) -> bytes:
    if sep != SOH and convert_sep_to_soh_for_checksum:
        buf = buf.replace(sep, SOH)

    check_sum = sum(buf[:-len(b'10=000\x01')]) % 256
    return f'{check_sum:#03}'.encode('ascii')


def calc_body_length(buf: bytes, encoded_message: List[Tuple[bytes, bytes]], sep: bytes = SOH) -> int:
    header = sep.join([b'='.join(field_value) for field_value in encoded_message[:2]]) + sep
    trailer = b'='.join(encoded_message[-1]) + sep
    body_length = len(buf) - len(header) - len(trailer)
    return body_length


def decode_value(protocol: ProtocolMetaData, meta_data: FieldMetaData, value: bytes) -> Any:
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


def encode_value(protocol: ProtocolMetaData, meta_data: FieldMetaData, value: Any) -> bytes:
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
