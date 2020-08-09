"""FIX read buffer"""

from enum import IntEnum
from typing import Optional

from ..fix_message import SOH, calc_checksum

from .fix_events import (
    FixReadEvent,
    FixReadNeedsMoreData,
    FixReadDataReady,
    FixReadError,
    FixReadEndOfFile
)


class ReadState(IntEnum):

    END_OF_FILE = 0x01
    BAD_BEGIN_STRING = 0x02
    BAD_BODY_LENGTH = 0x04
    BAD_BODY = 0x08
    ERROR = 0x0f

    EXPECT_BEGIN_STRING = 0x10
    EXPECT_BODY_LENGTH = 0x20
    EXPECT_BODY = 0x30


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

        self.sep_length = len(sep)
        self.checksum_length = len(b'10=000') + self.sep_length
        self.state = ReadState.EXPECT_BEGIN_STRING
        self.buf = b''
        self.index = 0
        self.required_length = -1

    def receive(self, buf: Optional[bytes]) -> bool:
        if not buf:
            # An empty read indicates the connection has closed.
            self.state = ReadState.END_OF_FILE
            return False

        # Accumulate the result.
        self.buf += buf
        return True

    def next_event(self) -> FixReadEvent:

        while not self.state & ReadState.ERROR:
            if self.state == ReadState.EXPECT_BEGIN_STRING:
                assert self.index == 0

                # Find the SOH field separator.
                soh_index = self.buf.find(self.sep)
                if soh_index == -1:
                    # We need more data
                    return FixReadNeedsMoreData()

                # Should start with the BeginString tag: e.g. b'8=FIX.4.2\x01'.
                if not self.buf.startswith(b'8='):
                    self.state = ReadState.BAD_BEGIN_STRING
                    return FixReadError('Expected BeginString')

                # Advance the index and expect body length.
                self.index = soh_index + 1
                self.state = ReadState.EXPECT_BODY_LENGTH

            elif self.state == ReadState.EXPECT_BODY_LENGTH:

                # Find the net SOH field separator.
                soh_index = self.buf.find(self.sep, self.index)
                if soh_index == -1:
                    # We need more data.
                    return FixReadNeedsMoreData()

                # We expect the BodyLength tag: e.g. b'9=129\x01'.
                if not self.buf[self.index: soh_index].startswith(b'9='):
                    self.state = ReadState.BAD_BODY_LENGTH
                    return FixReadError('Expected BodyLength')

                value = self.buf[self.index+2:soh_index]
                # It is within the specification for the length to be zero padded.
                if len(value) > 1 and value.startswith(b'0'):
                    value = value.lstrip(b'0')
                body_length = int(value)
                # The total length includes the checksum.
                self.required_length = soh_index + self.sep_length + \
                    body_length + self.checksum_length

                # Advance the index and expect the body.
                self.index = soh_index + 1
                self.state = ReadState.EXPECT_BODY

            elif self.state == ReadState.EXPECT_BODY:

                # Have we got enough data?
                if len(self.buf) < self.required_length:
                    # We can supply a hint for how much data we need.
                    return FixReadNeedsMoreData(self.required_length - len(self.buf))

                # We have the full message.
                data = self.buf[:self.required_length]
                if not data .endswith(self.sep):
                    return FixReadError('No terminating separator')

                if self.validate:
                    checksum = data[-self.checksum_length:-self.sep_length]
                    if not checksum.startswith(b'10='):
                        self.state = ReadState.BAD_BODY
                        return FixReadError('No terminating checksum')

                    checksum_value = checksum[3:]
                    expected = calc_checksum(
                        data,
                        self.sep,
                        self.convert_sep_to_soh_for_checksum
                    )
                    if checksum_value != expected:
                        return FixReadError("Wrong checksum")

                # Reset state
                self.buf = self.buf[self.required_length:]
                self.index = 0
                self.required_length = 0
                self.state = ReadState.EXPECT_BEGIN_STRING

                return FixReadDataReady(data)
            else:
                return FixReadError('Unknown state')

        if self.state == ReadState.END_OF_FILE:
            return FixReadEndOfFile()
        else:
            # If we got here there was an error.
            return FixReadError('Invalid state')
