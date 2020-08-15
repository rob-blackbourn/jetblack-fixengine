import logging
from typing import Optional
from ..meta_data import ProtocolMetaData
from ..fix_message import FixMessage
from ..types import Send, Receive, Handler, Event

logger = logging.getLogger(__name__)


class FixMessageMiddleware:

    def __init__(
            self,
            protocol: ProtocolMetaData,
            *,
            strict: Optional[bool] = True,
            validate: Optional[bool] = True,
            convert_sep_for_checksum: Optional[bool] = False
    ) -> None:
        self.protocol = protocol
        self.strict = strict if strict is not None else True
        self.validate = validate if validate is not None else True
        self.convert_sep_for_checksum = convert_sep_for_checksum if convert_sep_for_checksum is not None else False

    async def __call__(self, send: Send, receive: Receive, handler: Handler) -> None:
        async def wrapped_receive() -> Event:
            event = await receive()
            if event['type'] == 'fix':
                decoded_message = FixMessage.decode(
                    self.protocol, event['message'])
                event['message_contents'] = decoded_message.data
                event['message_category'] = decoded_message.meta_data.msgcat
            return event

        await handler(send, wrapped_receive)
