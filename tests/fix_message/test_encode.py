"""Tests for encoding"""

from typing import Any, Mapping

from aiofix.loader import load_protocol
from aiofix.fix_message import FixMessage, find_message_meta_data
from aiofix.meta_data import FieldMessageDataMap

from datetime import datetime, timezone


def _is_match(source: Mapping[str, Any], dest: Mapping[str, Any]) -> bool:
    for name, value in source.items():
        if value != dest[name]:
            return False
    return True


def test_encode_logon():
    msg_seq_num = 42
    send_time_utc = datetime(2020, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
    sender_comp_id = "SENDER"
    target_comp_id = "TARGET"
    encrypt_method = "NONE"
    heartbeat_timeout = 30
    message = {
        'MsgType': 'LOGON',
        'MsgSeqNum': msg_seq_num,
        'SenderCompID': sender_comp_id,
        'TargetCompID': target_comp_id,
        'SendingTime': send_time_utc,
        'EncryptMethod': encrypt_method,
        'HeartBtInt': heartbeat_timeout
    }
    protocol = load_protocol(
        'etc/FIX44.yaml',
        is_millisecond_time=True,
        is_float_decimal=True
    )
    meta_data = find_message_meta_data(protocol, message)
    fix_message = FixMessage(protocol, message, meta_data)
    encoded_message = fix_message.encode(regenerate_integrity=True)
    roundtrip = FixMessage.decode(protocol, encoded_message)
    assert fix_message.data == roundtrip.data
