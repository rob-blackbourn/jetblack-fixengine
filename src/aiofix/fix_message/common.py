from typing import List, Tuple

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
