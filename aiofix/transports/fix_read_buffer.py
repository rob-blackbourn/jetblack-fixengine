"""FIX read buffer"""

from collections import deque
from enum import IntEnum
from typing import Callable, Deque, Optional, Tuple

from ..fix_message import SOH, calc_checksum

from .fix_events import (
    FixReadEvent,
    FixReadNeedsMoreData,
    FixReadDataReady,
    FixReadError,
    FixReadEndOfFile
)


class InputState(IntEnum):

    EMPTY = 1
    HAS_DATA = 2
    EOF = 3


class ReadState(IntEnum):

    PROTOCOL_ERROR = 0x01
    STATE_ERROR = 0x02
    CLOSED = 0x03
    DONE = 0x0f

    IDLE = 0x10
    EXPECT_BEGIN_STRING = 0x20
    EXPECT_BODY_LENGTH = 0x30
    EXPECT_BODY = 0x40
    END_OF_FILE = 0x50
    EXPECT = 0xf0


StateResponse = Tuple[Optional[FixReadEvent], bool]


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
        self._queue: Deque[bytes] = deque()
        self._buf: bytes = b''
        self._index = 0
        self._required_length = -1

        self._state = ReadState.IDLE
        self._transitions = {

            (ReadState.IDLE, InputState.EMPTY): (
                self._request_data,
                ReadState.IDLE
            ),
            (ReadState.IDLE, InputState.HAS_DATA): (
                self._proceed_to_next_state,
                ReadState.EXPECT_BEGIN_STRING
            ),
            (ReadState.IDLE, InputState.EOF): (
                self._handle_end_of_file,
                ReadState.END_OF_FILE
            ),

            (ReadState.EXPECT_BEGIN_STRING, InputState.EMPTY): (
                self._request_data,
                ReadState.EXPECT_BEGIN_STRING
            ),
            (ReadState.EXPECT_BEGIN_STRING, InputState.HAS_DATA): (
                self._process_begin_string,
                ReadState.EXPECT_BODY_LENGTH
            ),

            (ReadState.EXPECT_BODY_LENGTH, InputState.EMPTY): (
                self._request_data,
                ReadState.EXPECT_BODY_LENGTH
            ),
            (ReadState.EXPECT_BODY_LENGTH, InputState.HAS_DATA): (
                self._process_body_length,
                ReadState.EXPECT_BODY
            ),

            (ReadState.EXPECT_BODY, InputState.EMPTY): (
                self._request_data,
                ReadState.EXPECT_BODY
            ),

            (ReadState.EXPECT_BODY, InputState.HAS_DATA): (
                self._process_body,
                ReadState.IDLE
            ),

            (ReadState.END_OF_FILE, InputState.EOF): (
                self._handle_end_of_file,
                ReadState.CLOSED
            )
        }

    @property
    def input_state(self) -> InputState:
        if len(self._queue) == 0:
            return InputState.EMPTY
        elif not self._queue[0]:
            return InputState.EOF
        else:
            return InputState.HAS_DATA

    def receive(self, buf: bytes):
        self._queue.append(buf)

    def next_event(self) -> FixReadEvent:

        event: Optional[FixReadEvent] = None

        while self._state & ReadState.EXPECT:
            try:
                transition = (self._state, self.input_state)
                func, next_state = self._transitions[transition]
            except KeyError:
                raise FixReadError('Unknown transition')
            else:
                event, is_complete = func()
                if is_complete:
                    self._state = next_state

            if event is not None:
                return event

        raise FixReadError('Invalid state')

    def _requeue_unprocessed(self) -> None:
        if len(self._buf) > self._index:
            self._queue.appendleft(self._buf[self._index:])
            self._buf = self._buf[:self._index]

    def _proceed_to_next_state(self) -> StateResponse:
        return None, True

    def _request_data(self) -> StateResponse:
        return FixReadNeedsMoreData(), False

    def _process_begin_string(self) -> StateResponse:
        assert self._index == 0

        self._buf += self._queue.popleft()

        # Find the SOH field separator.
        soh_index = self._buf.find(self.sep)
        if soh_index == -1:
            # We need more data
            return FixReadNeedsMoreData(), False

        # Should start with the BeginString tag: e.g. b'8=FIX.4.2\x01'.
        if not self._buf.startswith(b'8='):
            raise FixReadError('Expected BeginString')

        # Advance the index and expect body length.
        self._index = soh_index + 1
        self._requeue_unprocessed()

        return None, True

    def _process_body_length(self) -> StateResponse:
        self._buf += self._queue.popleft()

        # Find the net SOH field separator.
        soh_index = self._buf.find(self.sep, self._index)
        if soh_index == -1:
            # We need more data.
            return FixReadNeedsMoreData(), False

        # We expect the BodyLength tag: e.g. b'9=129\x01'.
        if not self._buf[self._index: soh_index].startswith(b'9='):
            raise FixReadError('Expected BodyLength')

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

        self._requeue_unprocessed()

        return None, True

    def _process_body(self) -> StateResponse:
        self._buf += self._queue.popleft()

        # Have we got enough data?
        if len(self._buf) < self._required_length:
            # We can supply a hint for how much data we need.
            return FixReadNeedsMoreData(self._required_length - len(self._buf)), False

        # We have the full message.
        data = self._buf[:self._required_length]
        if not data .endswith(self.sep):
            raise FixReadError('No terminating separator')

        if self.validate:
            checksum = data[-self._checksum_length:-self._sep_length]
            if not checksum.startswith(b'10='):
                raise FixReadError('No terminating checksum')

            checksum_value = checksum[3:]
            expected = calc_checksum(
                data,
                self.sep,
                self.convert_sep_to_soh_for_checksum
            )
            if checksum_value != expected:
                raise FixReadError("Wrong checksum")

        # Reset state
        self._queue.appendleft(self._buf[self._required_length:])
        self._buf = b''
        self._index = 0
        self._required_length = 0

        return FixReadDataReady(data), True

    def _handle_end_of_file(self) -> StateResponse:
        return FixReadEndOfFile(), True
