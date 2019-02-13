from typing import Mapping, Union
from .message_member import MessageMemberMetaData

MessageFieldMetaDataMapping = Mapping[str, Union[MessageMemberMetaData, 'MessageFieldMetaDataMapping']]


class MessageMetaData:

    def __init__(self, name: str, msgtype: bytes, msgcat: str, fields: MessageFieldMetaDataMapping) -> None:
        self._name = name
        self._msgtype = msgtype
        self._msgcat = msgcat
        self._fields = fields

    @property
    def name(self) -> str:
        return self._name

    @property
    def msgtype(self) -> bytes:
        return self._msgtype

    @property
    def msgcat(self) -> str:
        return self._msgcat

    @property
    def fields(self) -> MessageFieldMetaDataMapping:
        return self._fields

    def __str__(self) -> str:
        return f'<MessageMetaData: name="{self.name}", msgtype="{self.msgtype}", msgcat="{self.msgcat}">'

    __repr__ = __str__
