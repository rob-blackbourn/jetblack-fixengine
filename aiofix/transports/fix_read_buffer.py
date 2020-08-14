"""FIX read buffer"""

from enum import IntEnum
from typing import Callable, Mapping, Optional, Tuple

from ..fix_message import SOH, calc_checksum

from .fix_events import (
    FixReadEvent,
    FixReadNeedsMoreData,
    FixReadDataReady,
    FixReadError,
    FixReadEndOfFile
)


class ReadState(IntEnum):

    PROTOCOL_ERROR = 0x01
    STATE_ERROR = 0x02
    CLOSED = 0x04
    DONE = 0x0f

    END_OF_FILE = 0x10
    EXPECT_BEGIN_STRING = 0x20
    EXPECT_BODY_LENGTH = 0x40
    EXPECT_BODY = 0x80
    EXPECT = 0xf0


StateResponse = Tuple[Optional[FixReadEvent], bool]
StateHandler = Callable[[], StateResponse]
Transition = Tuple[StateHandler, ReadState]


class FixReadBuffer:

    def __init__(
            self,
            sep: bytes = SOH,
            convert_sep_to_soh_for_checksum: bool = False,
            validate: bool = True
    ) -> None:
        self.sep = sep
        self.convert_sep_to_soh_for_checksum = convert_sep_to_soh_for_checksum
        self.validate = validate

        self._sep_length = len(sep)
        self._checksum_length = len(b'10=000') + self._sep_length
        self._buf = b''
        self._index = 0
        self._required_length = -1

        self._state = ReadState.EXPECT_BEGIN_STRING
        self._transitions: Mapping[ReadState, Transition] = {
            ReadState.EXPECT_BEGIN_STRING: (
                self._handle_expect_begin_string,
                ReadState.EXPECT_BODY_LENGTH
            ),
            ReadState.EXPECT_BODY_LENGTH: (
                self._handle_expect_body_length,
                ReadState.EXPECT_BODY
            ),
            ReadState.EXPECT_BODY: (
                self._handle_expect_body,
                ReadState.EXPECT_BEGIN_STRING
            ),
            ReadState.END_OF_FILE: (
                self._handle_end_of_file,
                ReadState.CLOSED
            )
        }

    def receive(self, buf: Optional[bytes]) -> bool:
        if not buf:
            # An empty read indicates the connection has closed.
            self._state = ReadState.END_OF_FILE
            return False

        # Accumulate the result.
        self._buf += buf
        return True

    def next_event(self) -> FixReadEvent:

        event: Optional[FixReadEvent] = None

        while self._state & ReadState.EXPECT:
            try:
                func, next_state = self._transitions[self._state]
            except KeyError:
                self._state = ReadState.STATE_ERROR
                event = FixReadError('Unknown state')
            else:
                event, is_complete = func()
                if is_complete:
                    self._state = next_state

            if event is not None:
                return event

        return FixReadError('Invalid state')

    def _handle_expect_begin_string(self) -> StateResponse:
        assert self._index == 0

        # Find the SOH field separator.
        soh_index = self._buf.find(self.sep)
        if soh_index == -1:
            # We need more data
            return FixReadNeedsMoreData(), False

        # Should start with the BeginString tag: e.g. b'8=FIX.4.2\x01'.
        if not self._buf.startswith(b'8='):
            self._state = ReadState.PROTOCOL_ERROR
            return FixReadError('Expected BeginString'), False

        # Advance the index and expect body length.
        self._index = soh_index + 1
        self._state = ReadState.EXPECT_BODY_LENGTH

        return None, True

    def _handle_expect_body_length(self) -> StateResponse:
        # Find the net SOH field separator.
        soh_index = self._buf.find(self.sep, self._index)
        if soh_index == -1:
            # We need more data.
            return FixReadNeedsMoreData(), False

        # We expect the BodyLength tag: e.g. b'9=129\x01'.
        if not self._buf[self._index: soh_index].startswith(b'9='):
            self._state = ReadState.PROTOCOL_ERROR
            return FixReadError('Expected BodyLength'), False

        value = self._buf[self._index+2:soh_index]
        # It is within the specification for the length to be zero padded.
        if len(value) > 1 and value.startswith(b'0'):
            value = value.lstrip(b'0')
        body_length = int(value)
        # The total length includes the checksum.
        self._required_length = soh_index + self._sep_length + \
            body_length + self._checksum_length

        # Advance the index and expect the body.
        self._index = soh_index + 1
        self._state = ReadState.EXPECT_BODY

        return None, True

    def _handle_expect_body(self) -> StateResponse:
        # Have we got enough data?
        if len(self._buf) < self._required_length:
            # We can supply a hint for how much data we need.
            return FixReadNeedsMoreData(self._required_length - len(self._buf)), False

        # We have the full message.
        data = self._buf[:self._required_length]
        if not data .endswith(self.sep):
            return FixReadError('No terminating separator'), False

        if self.validate:
            checksum = data[-self._checksum_length:-self._sep_length]
            if not checksum.startswith(b'10='):
                self._state = ReadState.PROTOCOL_ERROR
                return FixReadError('No terminating checksum'), False

            checksum_value = checksum[3:]
            expected = calc_checksum(
                data,
                self.sep,
                self.convert_sep_to_soh_for_checksum
            )
            if checksum_value != expected:
                return FixReadError("Wrong checksum"), False

        # Reset state
        self._buf = self._buf[self._required_length:]
        self._index = 0
        self._required_length = 0
        self._state = ReadState.EXPECT_BEGIN_STRING

        return FixReadDataReady(data), True

    def _handle_end_of_file(self) -> StateResponse:
        return FixReadEndOfFile(), True
