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
    protocol = load_protocol(
        'etc/FIX44.yaml',
        is_millisecond_time=True,
        is_float_decimal=True,
        is_bool_enum=False
    )
    messages = [
        {
            'MsgType': 'LOGON',
            'MsgSeqNum': 42,
            'SenderCompID': "SENDER",
            'TargetCompID': "TARGET",
            'SendingTime': datetime(2020, 1, 1, 12, 30, 0, tzinfo=timezone.utc),
            'EncryptMethod': "NONE",
            'HeartBtInt': 30
        },
        {
            'MsgType': 'LOGOUT',
            'MsgSeqNum': 43,
            'SenderCompID': "SENDER",
            'TargetCompID': "TARGET",
            'SendingTime': datetime(2020, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
        },
        {
            'MsgType': 'HEARTBEAT',
            'MsgSeqNum': 43,
            'SenderCompID': "SENDER",
            'TargetCompID': "TARGET",
            'SendingTime': datetime(2020, 1, 1, 12, 30, 0, tzinfo=timezone.utc)
        },
        {
            'MsgType': 'RESEND_REQUEST',
            'MsgSeqNum': 42,
            'SenderCompID': "SENDER",
            'TargetCompID': "TARGET",
            'SendingTime': datetime(2020, 1, 1, 12, 30, 0, tzinfo=timezone.utc),
            'BeginSeqNo': 10,
            'EndSeqNo': 12
        },
        {
            'MsgType': 'TEST_REQUEST',
            'MsgSeqNum': 42,
            'SenderCompID': "SENDER",
            'TargetCompID': "TARGET",
            'SendingTime': datetime(2020, 1, 1, 12, 30, 0, tzinfo=timezone.utc),
            'TestReqID': "This is not a test"
        },
        {
            'MsgType': 'SEQUENCE_RESET',
            'MsgSeqNum': 42,
            'SenderCompID': "SENDER",
            'TargetCompID': "TARGET",
            'SendingTime': datetime(2020, 1, 1, 12, 30, 0, tzinfo=timezone.utc),
            'GapFillFlag': False,
            'NewSeqNo': 12
        }
    ]
    for message in messages:
        fix_message = FixMessage(protocol, message)
        encoded_message = fix_message.encode(regenerate_integrity=True)
        roundtrip = FixMessage.decode(protocol, encoded_message)
        assert fix_message.data == roundtrip.data
