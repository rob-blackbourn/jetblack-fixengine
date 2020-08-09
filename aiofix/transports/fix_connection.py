"""FIX Transport"""

import logging

from ..meta_data import ProtocolMetaData
from ..fix_message import SOH

from .fix_read_buffer import FixReadBuffer

logger = logging.getLogger(__name__)


class FixConnection:

    def __init__(
            self,
            protocol: ProtocolMetaData,
            *,
            sep: bytes = SOH,
            strict: bool = True,
            validate: bool = True,
            convert_sep_for_checksum: bool = False
    ) -> None:
        self.protocol = protocol
        self.strict = strict
        self.validate = validate
        self.convert_sep_for_checksum = convert_sep_for_checksum

        self.read_buffer = FixReadBuffer(
            sep,
            convert_sep_for_checksum,
            validate
        )

        # self.event_queue: Deque[FixEvent] = deque()

    # def read(self, buf: Optional[bytes]) -> None:
    #     fix_event = self.read_buffer.receive(buf)
    #     if fix_event.event_type == FixEventType.DATA:
    #         decoded_message = FixMessage.decode(
    #             self.protocol, cast(Data, fix_event).data)
    #         self.event_queue.append(MessageRead(decoded_message))
    #     else:
    #         self.event_queue.append(self.read_buffer.receive(buf))

    # def write(self, data: FieldMessageDataMap) -> None:
    #     meta_data = find_message_meta_data(self.protocol, data)
    #     fix_message = FixMessage(self.protocol, data, meta_data)
    #     encoded_message = fix_message.encode(regenerate_integrity=True)
    #     self.event_queue.append(MessageWrite(encoded_message))

    # def next_event(self) -> FixEvent:
    #     return self.event_queue.popleft()
