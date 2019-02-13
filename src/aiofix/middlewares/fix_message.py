import logging
from ..meta_data import ProtocolMetaData
from ..fix_message import FixMessage
from ..types import Send, Receive, Handler, Event

logger = logging.getLogger(__name__)


class FixMessageMiddleware:

    def __init__(self, protocol: ProtocolMetaData) -> None:
        self.protocol = protocol

    async def __call__(self, send: Send, receive: Receive, handler: Handler) -> None:
        async def wrapped_send(event: Event) -> None:
            if event['type'] == 'fix':
                decoded_message = FixMessage.from_dict(self.protocol, event['message_contents'])
                encoded_message = decoded_message.encode(regenerate_integrity=True)
                event['message'] = encoded_message
            await send(event)

        async def wrapped_receive() -> Event:
            event = await receive()
            if event['type'] == 'fix':
                decoded_message = FixMessage.decode(self.protocol, event['message'])
                event['message_contents'] = decoded_message.to_dict()
                event['message_category'] = decoded_message.message_meta_data.msgcat
            return event

        await handler(wrapped_send, wrapped_receive)
